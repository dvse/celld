use super::*;

fn with_entry(test: impl FnOnce(&mut v8::PinScope, &mut InFlight)) {
    Engine::init();
    let mut isolate = v8::Isolate::new(v8::CreateParams::default());
    v8::scope!(let hs, &mut isolate);
    let realm = v8::Context::new(hs, v8::ContextOptions::default());
    let scope = &mut v8::ContextScope::new(hs, realm);
    let state = Arc::new(ActorRuntimeState::default());
    scope.set_slot(state.clone());
    let source = v8::String::new(scope, "(() => null)").unwrap();
    let script = v8::Script::compile(scope, source, None).unwrap();
    let hook = v8::Local::<v8::Function>::try_from(script.run(scope).unwrap()).unwrap();
    state
        .event_hooks
        .set(EventHooks {
            begin_event: v8::Global::new(scope, hook),
            end_event: v8::Global::new(scope, hook),
            advance_io_time: v8::Global::new(scope, hook),
            abort_incoming_request: v8::Global::new(scope, hook),
        })
        .ok()
        .unwrap();
    let internals = v8::Object::new(scope);
    let key = v8::String::new(scope, "__retireInputGateContext").unwrap();
    internals.set(scope, key.into(), hook.into());
    state
        .internals
        .set(v8::Global::new(scope, internals))
        .ok()
        .unwrap();
    let resolver = v8::PromiseResolver::new(scope).unwrap();
    let promise = resolver.get_promise(scope);
    let mut entry = InFlight {
        runtime_state: state.clone(),
        promise: v8::Global::new(scope, promise),
        context: IoContext::tracked(&state),
        scope: None,
        writes_before: None,
        request_id: None,
        active_request_id: None,
        reply: None,
        gated_reply: None,
        background: None,
        completed_cell_event: false,
        ops: HashSet::new(),
        io_context_ops: HashSet::new(),
        adopted_ops: HashMap::new(),
        cancel_own_ops: false,
        unrefed_ops: HashSet::new(),
        alarm: None,
        started: Instant::now(),
        trace: None,
        failure: None,
        tail_report: None,
    };
    test(scope, &mut entry);
    entry.abandon();
}

fn store_resolver(scope: &mut v8::PinScope, entry: &InFlight, id: u64) -> v8::Global<v8::Promise> {
    let resolver = v8::PromiseResolver::new(scope).unwrap();
    let promise = resolver.get_promise(scope);
    entry
        .runtime_state
        .promises
        .lock()
        .unwrap()
        .insert(id, v8::Global::new(scope, resolver));
    v8::Global::new(scope, promise)
}

struct DropProbe(Arc<AtomicBool>);

impl Drop for DropProbe {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
    }
}

fn hand(
    entry: &InFlight,
    id: u64,
    lifetime: asyncrt::OpLifetime,
    ownership: Ownership,
) -> Arc<AtomicBool> {
    let dropped = Arc::new(AtomicBool::new(false));
    let probe = DropProbe(dropped.clone());
    assert!(entry
        .context
        .try_hand_op(
            id,
            Box::pin(async move {
                let _probe = probe;
                std::future::pending().await
            }),
            lifetime,
            ownership,
        )
        .is_ok());
    dropped
}

#[test]
fn cancellation_drains_accepted_ownership_before_filtering() {
    with_entry(|scope, entry| {
        let resource = IoContext::tracked(&entry.runtime_state);
        let owner = resource.continuation_id().unwrap();
        for id in [1, 2, 3] {
            store_resolver(scope, entry, id);
        }
        entry.record_handed_op(1, asyncrt::OpLifetime::Handler, Ownership::Own);
        // Cancellation is queued before this foreign handoff is drained.
        let adopted_dropped = hand(
            entry,
            2,
            asyncrt::OpLifetime::Handler,
            Ownership::Adopted(owner),
        );
        let own_dropped = hand(entry, 3, asyncrt::OpLifetime::Handler, Ownership::Own);
        assert!(entry.adopted_ops.is_empty());
        cancel(scope, entry, false);
        let handed = entry.retain_native_ops(Vec::new());
        assert_eq!(entry.ops, HashSet::from([2]));
        assert_eq!(
            handed.iter().map(|(id, _)| *id).collect::<Vec<_>>(),
            vec![2]
        );
        let promises = entry.runtime_state.promises.lock().unwrap();
        assert!(
            promises.contains_key(&2),
            "adopted promise must remain resolvable"
        );
        assert!(!promises.contains_key(&1));
        assert!(!promises.contains_key(&3));
        assert!(own_dropped.load(Ordering::Acquire));
        assert!(!adopted_dropped.load(Ordering::Acquire));
        drop(handed);
        assert!(adopted_dropped.load(Ordering::Acquire));
    });
}

#[test]
fn adopted_resource_does_not_retain_unrelated_native_ops() {
    with_entry(|scope, entry| {
        let resource = IoContext::tracked(&entry.runtime_state);
        let owner = resource.continuation_id().unwrap();
        for id in [1, 2] {
            store_resolver(scope, entry, id);
        }
        entry.record_handed_op(1, asyncrt::OpLifetime::Handler, Ownership::Own);
        entry.record_handed_op(2, asyncrt::OpLifetime::IoContext, Ownership::Adopted(owner));
        // Resource-lifetime adopted work is not a reason to keep own work.
        let _ = entry.retain_native_ops(Vec::new());
        assert_eq!(entry.ops, HashSet::from([2]));
        cancel(scope, entry, false);
        let _ = entry.retain_native_ops(Vec::new());
        assert_eq!(entry.ops, HashSet::from([2]));
        drop(resource);
        let _ = entry.retain_native_ops(Vec::new());
        assert!(entry.ops.is_empty());
        assert!(entry.runtime_state.promises.lock().unwrap().is_empty());
    });
}

#[test]
fn stateless_retirement_drains_before_abandoning() {
    with_entry(|scope, entry| {
        let resource = IoContext::tracked(&entry.runtime_state);
        let owner = resource.continuation_id().unwrap();
        assert!(!entry.keeps_native_ops());
        let promise = store_resolver(scope, entry, 4);
        // The handler has answered; only then is the handoff accepted.
        hand(
            entry,
            4,
            asyncrt::OpLifetime::Handler,
            Ownership::Adopted(owner),
        );
        let late = entry.retain_native_ops(Vec::new());
        assert_eq!(late.len(), 1);
        assert!(entry.keeps_native_ops());
        assert!(!entry.finished());
        deliver(scope, entry, 4, Ok(asyncrt::OpOut::Str("complete".into())));
        assert_eq!(
            v8::Local::new(scope, &promise).state(),
            v8::PromiseState::Fulfilled
        );
        assert!(entry.runtime_state.promises.lock().unwrap().is_empty());
        assert!(entry.finished());
        assert!(entry.close_mailbox().is_empty());
        assert!(!entry.context.accepts_handed_ops());
    });
}

#[test]
fn shutdown_abandons_even_accepted_adopted_work() {
    with_entry(|scope, entry| {
        let resource = IoContext::tracked(&entry.runtime_state);
        store_resolver(scope, entry, 1);
        hand(
            entry,
            1,
            asyncrt::OpLifetime::Handler,
            Ownership::Adopted(resource.continuation_id().unwrap()),
        );
        cancel(scope, entry, true);
        assert!(entry.retain_native_ops(Vec::new()).is_empty());
        assert!(entry.runtime_state.promises.lock().unwrap().is_empty());
        assert!(entry.finished());
    });
}

#[test]
fn actor_context_is_shared_until_incarnation_release() {
    let state = Arc::new(ActorRuntimeState::default());
    let frame = EgressFrame {
        storage: "Actor:a".into(),
        before: 0,
        root: None,
    };
    let first = state.actor_context("Actor:a", frame.clone());
    let first_id = first.continuation_id().unwrap();
    assert!(Arc::ptr_eq(
        &first,
        &state.actor_context("Actor:a", frame.clone())
    ));
    state.release_actor_context("Actor:a");
    // A surviving resource cannot lend a new incarnation its old token.
    assert!(state.io_context(first_id).is_none());
    let next = state.actor_context("Actor:a", frame);
    assert_ne!(first_id, next.continuation_id().unwrap());
    state.release_actor_context("Actor:a");
}

#[test]
fn dead_reaction_cannot_borrow_running_context() {
    with_entry(|scope, entry| {
        let stale = IoContext::tracked(&entry.runtime_state);
        let previous = install_io_context(scope, &stale);
        drop(stale);
        let _running = CurrentGuard::enter(entry.context.clone());
        assert!(event_context(scope).is_none());
        restore_io_context(scope, previous);
    });
}

#[test]
fn actor_resource_preserves_event_driver_during_foreign_turn() {
    with_entry(|scope, entry| {
        let frame = EgressFrame {
            storage: "Actor:a".into(),
            before: 0,
            root: None,
        };
        entry.context.egress.lock().unwrap().push(frame.clone());
        let resource = entry.runtime_state.actor_context("Actor:a", frame);
        let previous = install_resource_context(scope, &resource, &entry.context, false);
        let foreign = IoContext::tracked(&entry.runtime_state);
        let _running = CurrentGuard::enter(foreign.clone());
        assert!(Arc::ptr_eq(&event_context(scope).unwrap(), &resource));
        assert!(Arc::ptr_eq(
            &operation_driver_context(scope).unwrap(),
            &entry.context
        ));
        // Reply proofs must attach to the event, not its long-lived actor.
        let (_send, receive) = tokio::sync::oneshot::channel();
        register_arm_gate_with_current_event(receive, operation_driver_context(scope));
        assert_eq!(entry.context.take_arm_gates().len(), 1);
        assert!(resource.take_arm_gates().is_empty());
        let _ = entry.context.close_handed_ops();
        // Ordinary actor work can move after its original driver retires.
        assert!(Arc::ptr_eq(
            &operation_driver_context(scope).unwrap(),
            &foreign
        ));
        restore_io_context(scope, previous);
        entry.runtime_state.release_actor_context("Actor:a");
    });
}

#[test]
fn critical_section_cannot_borrow_driver_after_retirement() {
    with_entry(|scope, entry| {
        let resource = IoContext::tracked(&entry.runtime_state);
        let previous = install_resource_context(scope, &resource, &entry.context, true);
        let foreign = IoContext::tracked(&entry.runtime_state);
        let _running = CurrentGuard::enter(foreign);
        assert!(Arc::ptr_eq(
            &operation_driver_context(scope).unwrap(),
            &entry.context
        ));
        let _ = entry.context.close_handed_ops();
        assert!(event_context(scope).is_some());
        assert!(operation_driver_context(scope).is_none());
        restore_io_context(scope, previous);
    });
}
