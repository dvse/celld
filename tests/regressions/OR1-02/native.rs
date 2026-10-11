// OR1-02 (review 1, P1-2): an export created by a request that is still
// draining a retired stateless heap, held by a long-lived holder, must not
// strand the heap in `retiring`. Included from crates/celld/pool.rs
// (capability_drain_tests).
use super::capability_drain_tests::pool;

#[test]
fn export_created_during_drain_returns_the_heap_to_service() {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap()
        .block_on(async {
            let pool = pool();
            let slot = pool.grow(None).unwrap();
            // A suspended request keeps the heap busy while it is retired.
            let request = slot.affiliate();
            pool.reap();
            assert!(
                slot.is_retiring(),
                "the reaper retires the heap with a draining request"
            );
            // The draining request exports a capability that a long-lived
            // holder (an actor whose context never ends) keeps forever.
            let held: crate::capability::Route = serde_json::from_str(
                &crate::capability::export(slot.clone(), "held".into(), None, None, None).unwrap(),
            )
            .unwrap();
            drop(request);
            for _ in 0..3 {
                pool.reap();
                pool.free_drained();
            }
            assert!(
                !slot.is_retiring(),
                "a heap pinned by a held export must serve, not sit retiring"
            );
            assert_eq!(pool.live(), 1, "it counts as live capacity");
            assert!(slot.worker.lock().await.is_some());
            // It still takes new work: placement admits on it.
            let next = slot.try_affiliate_capability().await;
            assert!(next.is_some());
            drop(next);
            // Holder releases: the heap is an ordinary candidate again.
            slot.turn(|_| crate::capability::revoke(&held))
                .await
                .unwrap();
            pool.reap();
            assert!(slot.is_retiring());
            pool.free_drained();
            assert!(slot.worker.lock().await.is_none());
        });
}
