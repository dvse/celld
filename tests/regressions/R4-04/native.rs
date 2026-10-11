#[test]
fn r4_04_alarm_wall_time_revokes_incarnation_and_drops_ready_io() {
    with_entry(|scope, entry| {
        let frame = EgressFrame { storage: "Actor:alarm".into(), before: 0, root: None };
        entry.scope = Some("Actor:alarm".into());
        entry.context.egress.lock().unwrap().push(frame.clone());
        let old = entry.runtime_state.actor_context("Actor:alarm", frame.clone());
        let old_id = old.continuation_id().unwrap();
        // A second active request to this incarnation must be invalidated too.
        let other = IoContext::tracked(&entry.runtime_state);
        other.egress.lock().unwrap().push(frame.clone());
        let pending = store_resolver(scope, entry, 4004);
        entry.ops.insert(4004);
        entry.adopted_ops.insert(4004, old_id);
        entry.alarm = Some(AlarmClaim { now_ms: 0 });
        entry.started = Instant::now() - ALARM_WALL_LIMIT - Duration::from_secs(1);
        entry.time_out(Duration::from_secs(30));
        assert!(entry.wall_limit_left().is_none(), "exhausted alarm must not busy-loop");
        assert!(entry.runtime_state.io_context(old_id).is_none(), "old resource remains live");
        assert!(entry.runtime_state.io_context(other.continuation_id().unwrap()).is_none(),
            "another request of the timed-out incarnation remains live");
        // Deliver a completion that was ready at the timeout edge. The JS
        // resolver must stay pending; resuming it would enter the dead actor.
        deliver(scope, entry, 4004, Ok(asyncrt::OpOut::Str("late".into())));
        assert_eq!(v8::Local::new(scope, &pending).state(), v8::PromiseState::Pending);
        assert!(entry.retain_native_ops(Vec::new()).is_empty());
        assert!(entry.ops.is_empty());
        let next = entry.runtime_state.actor_context("Actor:alarm", frame);
        assert_ne!(old_id, next.continuation_id().unwrap());
        entry.runtime_state.release_actor_context("Actor:alarm");
    });
}
