// OR2-02 (review 2, N-3/N-4): closing capabilities is final. An export
// taken by a request still draining a generation-retired (or condemned) heap
// neither pins it nor returns it to service, so the old generation frees.
// Included from crates/celld/pool.rs.
use super::capability_drain_tests::pool;

#[test]
fn export_after_close_neither_pins_nor_unretires() {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap()
        .block_on(async {
            let pool = pool();
            let slot = pool.grow(None).unwrap();
            let request = slot.affiliate();
            pool.retire_all();
            assert!(slot.is_retiring());
            assert!(slot.pin_export().is_none(), "a closed heap takes no pin");
            // The export itself is still minted (its calls are refused).
            let _route =
                crate::capability::export(slot.clone(), "late".into(), None, None, None).unwrap();
            assert!(slot.is_retiring(), "closing is never reversed");
            drop(request);
            pool.free_drained();
            assert!(slot.worker.lock().await.is_none(), "the retired heap frees");
            assert!(pool.is_drained());

            let condemned = pool.grow(None).unwrap();
            assert!(condemned.condemn("test"));
            assert!(condemned.pin_export().is_none());
            assert!(condemned.is_retiring());
        });
}
