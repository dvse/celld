#[test]
fn r5_03_snapshot_excludes_a_descendant_native_writer() {
    let runtime = tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_all().build().unwrap();
    runtime.block_on(async {
        let state = root("r5-03-native", 1);
        let cut = state.freeze();
        let writer = state.clone();
        let (attempted, attempt) = std::sync::mpsc::channel();
        let (entered, entry) = std::sync::mpsc::channel();
        let handle = tokio::runtime::Handle::current();
        let thread = std::thread::spawn(move || {
            let _runtime = handle.enter();
            attempted.send(()).unwrap();
            let _write = writer.enter("r5-03-native", 1);
            entered.send(()).unwrap();
        });
        attempt.recv().unwrap();
        assert!(entry.recv_timeout(std::time::Duration::from_millis(30)).is_err(), "descendant wrote across the snapshot cut");
        drop(cut);
        entry.recv_timeout(std::time::Duration::from_secs(2)).unwrap();
        thread.join().unwrap();
    });
}
#[test]
fn r5_03_failed_mutation_stays_on_root_outputs() {
    let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
    runtime.block_on(async {
        let state = root("r5-03-failed", 1);
        let mutation = state.add("r5-03-failed".into(), 1, "r5-03-failed/facets/b".into(), vec!["b".into()], Image::new());
        let waiting = state.proofs();
        assert!(tokio::time::timeout(std::time::Duration::from_millis(1), prove(waiting.clone())).await.is_err());
        state.finish(&mutation, Err("injected copy failure".into()));
        assert_eq!(prove(waiting).await.unwrap_err(), "injected copy failure");
        assert_eq!(prove(state.proofs()).await.unwrap_err(), "injected copy failure");
        let next = state.add("r5-03-failed".into(), 1, "r5-03-failed/facets/c".into(), vec!["c".into()], Image::new());
        assert_eq!(prove(next.previous.clone()).await.unwrap_err(), "injected copy failure");
    });
}

#[test]
fn r5_03_abandoned_copy_cannot_leave_a_pending_root_proof() {
    let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
    runtime.block_on(async {
        let state = root("r5-03-abandoned", 1);
        let mutation = state.add("r5-03-abandoned".into(), 1, "destination".into(), vec!["b".into()], Image::new());
        *mutation.origin.lock().unwrap() = Some("origin-facet".into());
        state.abandon(Some("other-facet"));
        assert!(tokio::time::timeout(std::time::Duration::from_millis(1), prove(state.proofs())).await.is_err());
        state.abandon(Some("origin-facet"));
        assert!(prove(state.proofs()).await.unwrap_err().contains("originating actor stopped"));
        assert!(!mutation.claim());
    });
}
