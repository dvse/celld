// Copyright 2026 Deno Land Inc. Apache-2.0 license.
use super::*;

pub(super) fn export(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let Some(slot) = crate::pool::current_slot() else {
        // Direct engine embeddings/tests have no routable Slot. Their local
        // markers remain usable, but no fake cross-isolate route is minted.
        // A configured node must always have a live dispatch slot.
        if !crate::capability::configured() {
            rv.set(v8::null(scope).into());
            return;
        }
        return loader_throw(scope, "capability export requires a live isolate turn");
    };
    let token = args.get(0).to_rust_string_lossy(scope);
    let context = event_context(scope);
    // A target can be serialized from a different event in this same heap.
    // The harness records its originating actor; validate that storage here
    // rather than lending it the serializing caller's identity.
    let storage_scope = if args.length() > 1 {
        args.get(1)
            .is_string()
            .then(|| args.get(1).to_rust_string_lossy(scope))
    } else {
        context
            .egress
            .lock()
            .unwrap()
            .last()
            .map(|frame| frame.storage.clone())
    };
    if storage_scope
        .as_deref()
        .is_some_and(|cell| storage::activation_epoch(cell).is_none())
    {
        return loader_throw(
            scope,
            "capability actor activation is not live in this isolate",
        );
    }
    let identity = match storage_scope
        .as_deref()
        .map(storage::storage_identity)
        .transpose()
    {
        Ok(identity) => identity.flatten(),
        Err(error) => return loader_throw(scope, &format!("capability storage identity: {error}")),
    };
    let owner_scope = identity.as_ref().map(|id| id.root_scope.clone());
    let epoch = storage_scope.as_deref().and_then(storage::activation_epoch);
    match crate::capability::export(slot, token, storage_scope, owner_scope, epoch) {
        Ok(route) => rv.set(v8::String::new(scope, &route).unwrap().into()),
        Err(error) => loader_throw(scope, &error.to_string()),
    }
}
pub(super) fn call(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    request(scope, args, &mut rv, false);
}
pub(super) fn release(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    request(scope, args, &mut rv, true);
}
fn request(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    rv: &mut v8::ReturnValue<v8::Value>,
    release: bool,
) {
    let context = event_context(scope);
    if !release {
        if let Err(error) = context.charge_subrequest() {
            return loader_throw(scope, &error);
        }
    }
    let route = match serde_json::from_str(&args.get(0).to_rust_string_lossy(scope)) {
        Ok(route) => route,
        Err(error) => return loader_throw(scope, &format!("invalid capability route: {error}")),
    };
    let path = if release {
        vec![]
    } else {
        match serde_json::from_str::<Vec<String>>(&args.get(1).to_rust_string_lossy(scope)) {
            Ok(path) if path.len() <= 128 => path,
            _ => return loader_throw(scope, "invalid capability path"),
        }
    };
    let value = args.get(2);
    let bytes = if release || value.is_null() {
        None
    } else {
        match view_bytes(value) {
            Some(bytes) if bytes.len() <= 8 * 1024 * 1024 => Some(bytes),
            _ => return loader_throw(scope, "invalid or oversized capability arguments"),
        }
    };
    let order_value = args.get(if release { 1 } else { 3 });
    let order = if order_value.is_undefined() || order_value.is_null() {
        None
    } else {
        match serde_json::from_str::<crate::capability::CallOrder>(
            &order_value.to_rust_string_lossy(scope),
        ) {
            Ok(order) => Some(order),
            Err(error) => {
                return loader_throw(scope, &format!("invalid capability ordering: {error}"))
            }
        }
    };
    let mut request = crate::capability::Request {
        route,
        order,
        path,
        args: bytes,
        release,
        prepared_wire: None,
    };
    if let Err(error) = crate::capability::prepare_request(&mut request) {
        return loader_throw(scope, &error.to_string());
    }
    let gate = egress_gate_request(&context, celld_logic::Channel::Service);
    let pending = async move {
        await_egress_gate(gate)
            .await
            .map_err(|e| format!("capability output gate failed: {e}"))?;
        crate::capability::call(request)
            .await
            .map_err(crate::capability::op_failure)
    };
    // Release is teardown, and must outlive an unawaited handler result.
    let id = if release {
        asyncrt::enqueue_io_context(pending)
    } else {
        asyncrt::enqueue(pending)
    };
    rv.set(promise_for(scope, id));
}

fn invoke<'s>(
    tc: &mut v8::PinScope<'s, '_>,
    route: &crate::capability::Route,
    operation: crate::WorkerRpcOperation,
    release: bool,
    started: &str,
) -> Result<v8::Local<'s, v8::Value>> {
    let token = crate::capability::validate(route)?;
    let f = internal_function(
        tc,
        if release {
            "__releaseCapability"
        } else {
            "__dispatchCapability"
        },
    )?;
    let token = v8::String::new(tc, &token).unwrap();
    let (path, args) = match operation {
        crate::WorkerRpcOperation::Get { path } => (path, v8::null(tc).into()),
        crate::WorkerRpcOperation::Call { path, args } => (path, bytes_value(tc, args)),
    };
    let path: Vec<v8::Local<v8::Value>> = path
        .iter()
        .map(|p| v8::String::new(tc, p).unwrap().into())
        .collect();
    let path = v8::Array::new_with_elements(tc, &path);
    let recv = v8::undefined(tc).into();
    let started = v8::String::new(tc, started).unwrap();
    let result = f
        .call(tc, recv, &[token.into(), path.into(), args, started.into()])
        .ok_or_else(|| anyhow!("capability dispatch threw"));
    result
}

pub(super) fn begin(
    tc: &mut v8::PinScope,
    props: Vec<u8>,
    operation: crate::WorkerRpcOperation,
    release: bool,
    reply: tokio::sync::oneshot::Sender<Result<Vec<u8>>>,
) -> Begun {
    let invocation = match serde_json::from_slice::<crate::capability::Invocation>(&props) {
        Ok(invocation) => invocation,
        Err(error) => {
            let _ = reply.send(Err(error.into()));
            return Begun::Nothing;
        }
    };
    let route = invocation.route;
    let started_ticket = invocation.started;
    if let Err(error) = crate::capability::validate(&route) {
        let _ = reply.send(Err(error));
        return Begun::Nothing;
    }
    if let Some(scope) = route.storage_scope.clone() {
        return start_cell_event(tc, &scope, Answer::Rpc(reply), None, None, false, |tc| {
            invoke(tc, &route, operation, release, &started_ticket)
        });
    }
    let runtime_state = actor_runtime_state(tc);
    let context = IoContext::tracked(&runtime_state);
    let guard = CurrentGuard::enter(context.clone());
    let previous = install_io_context(tc, &context);
    context.begin_cpu_turn();
    let started = (|| {
        begin_event_context(tc)?;
        let ret = invoke(tc, &route, operation, release, &started_ticket)?;
        match ret.try_cast::<v8::Promise>() {
            Ok(promise) => Ok(promise),
            Err(_) => resolved_promise(tc, ret),
        }
    })();
    let result = match started {
        Ok(promise) => {
            tc.perform_microtask_checkpoint();
            Begun::Running(Box::new(InFlight {
                runtime_state,
                promise: v8::Global::new(tc, promise),
                context: context.clone(),
                scope: None,
                writes_before: None,
                request_id: None,
                active_request_id: None,
                reply: Some(Answer::Rpc(reply)),
                gated_reply: None,
                background: None,
                completed_cell_event: false,
                ops: HashSet::new(),
                io_context_ops: HashSet::new(),
                unrefed_ops: HashSet::new(),
                alarm: None,
                started: Instant::now(),
                trace: None,
                failure: None,
                tail_report: None,
            }))
        }
        Err(error) => {
            let _ = end_event_context(tc);
            let _ = context.finish_cpu_turn();
            let _ = reply.send(Err(error));
            Begun::Nothing
        }
    };
    restore_io_context(tc, previous);
    drop(guard);
    result
}

/// Transfer a sampled actor/facet output proof into the ordinary reply gate.
pub(super) fn gate_reply(context: &Arc<IoContext>) {
    let gate = egress_gate_request(context, celld_logic::Channel::Service);
    let (send, receive) = tokio::sync::oneshot::channel();
    register_arm_gate_with_current_event(receive, Some(context.clone()));
    asyncrt::spawn(async move {
        let _ = send.send(await_egress_gate(gate).await);
    })
    .detach();
}

pub(super) fn revoke(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    let route = match serde_json::from_str::<crate::capability::Route>(
        &args.get(0).to_rust_string_lossy(scope),
    ) {
        Ok(route) => route,
        Err(_) => return loader_throw(scope, "invalid capability revoke route"),
    };
    // Revocation is allowed after cell storage closes, but never from a
    // different heap. The opaque bearer remains necessary as well.
    if let Err(error) = crate::capability::revoke(&route) {
        loader_throw(scope, &error.to_string());
    }
}

// One-shot acknowledgement issued after the target method's synchronous entry.
pub(super) fn started(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    crate::capability::acknowledge_start(&args.get(0).to_rust_string_lossy(scope));
}
