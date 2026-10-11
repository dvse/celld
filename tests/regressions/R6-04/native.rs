use super::*;
fn route(token: &str) -> Route {
    Route {
        node: "source".into(),
        addr: "127.0.0.1:9700".into(),
        process: "p".repeat(64),
        heap: "h".into(),
        token: token.into(),
        seal: "s".into(),
        owner_scope: None,
        storage_scope: None,
        epoch: None,
    }
}
fn add(session: &Session, id: &str, route: Route) {
    let mut state = session.state.lock().unwrap();
    state
        .exports
        .insert(route.token.clone(), (route.clone(), 1));
    let call = state.calls.get_mut(id).unwrap();
    call.pending.push(route);
    call.bound = true;
}
fn count(session: &Session) -> usize {
    session
        .state
        .lock()
        .unwrap()
        .exports
        .values()
        .map(|(_, n)| n)
        .sum()
}
async fn settled(a: &Session, b: &Session) {
    tokio::time::timeout(std::time::Duration::from_secs(2), async {
        loop {
            if a.state.lock().unwrap().calls.is_empty() && b.state.lock().unwrap().calls.is_empty()
            {
                break;
            }
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
}
async fn pair() -> (Arc<Session>, Arc<Session>) {
    let a = Session::register(crate::capability::random_id(), "b".into(), "b".repeat(64)).unwrap();
    let b = Session::register(crate::capability::random_id(), "a".into(), "a".repeat(64)).unwrap();
    let (left, right) = tokio::io::duplex(1024);
    let x = a.clone();
    let y = b.clone();
    tokio::spawn(async move {
        x.watch(left).await;
    });
    tokio::spawn(async move {
        y.watch(right).await;
    });
    (a, b)
}
#[tokio::test]
async fn r6_04_failed_request_and_unread_reply_settle_without_session_loss() {
    let (a, b) = pair().await;
    let anchor = route("anchor");
    a.state
        .lock()
        .unwrap()
        .exports
        .insert(anchor.token.clone(), (anchor.clone(), 1));
    for n in 0..1000 {
        let call = a.open().await.unwrap();
        let id = call.id().to_string();
        add(&a, &id, route(&format!("request-{n}")));
        add(&b, &id, route(&format!("reply-{n}")));
        // No payload is delivered in either direction. The liveness transport stays up.
        drop(call);
        settled(&a, &b).await;
        assert_eq!(count(&a), 1);
        assert_eq!(count(&b), 0);
        assert!(a.contains(&anchor));
        assert!(b.accept_call(&id).is_err());
        assert!(b.received(&id).is_err());
    }
    a.close();
    b.close();
}
#[tokio::test]
async fn r6_04_ambiguous_delivery_preserves_received_reference_and_ordered_release() {
    let (a, b) = pair().await;
    for n in 0..1000 {
        let call = a.open().await.unwrap();
        let id = call.id().to_string();
        let r = route(&format!("received-{n}"));
        add(&a, &id, r.clone());
        b.received(&id).unwrap();
        // Cancel before the receipt necessarily reaches A. Settlement must use B's
        // authoritative receipt state, not the cancellation time on A's clock.
        drop(call);
        settled(&a, &b).await;
        assert!(a.contains(&r));
        assert_eq!(count(&a), 1);
        b.release_peer(r.clone()).unwrap();
        tokio::time::timeout(std::time::Duration::from_secs(2), async {
            while a.contains(&r) {
                tokio::task::yield_now().await;
            }
        })
        .await
        .unwrap();
        assert_eq!(count(&a), 0);
    }
    a.close();
    b.close();
}
#[tokio::test]
async fn r6_04_release_before_finish_and_reverse_reply_delivery_are_exactly_once() {
    let (a, b) = pair().await;
    for n in 0..1000 {
        let call = a.open().await.unwrap();
        let id = call.id().to_string();
        let r = route(&format!("reply-{n}"));
        add(&b, &id, r.clone());
        a.received(&id).unwrap();
        a.release_peer(r.clone()).unwrap();
        drop(call);
        settled(&a, &b).await;
        assert_eq!(count(&b), 0);
        assert!(!b.release(&r));
    }
    a.close();
    b.close();
}
#[tokio::test]
async fn r6_04_cancellation_during_setup_and_disconnect_drain_all_state() {
    let (a, b) = pair().await;
    let mut open = Box::pin(a.open());
    // Polling once sends Open; dropping the setup future must send Finish too.
    assert!(futures_util::poll!(open.as_mut()).is_pending());
    drop(open);
    settled(&a, &b).await;
    assert!(Session::get(&a.id).is_ok());
    let pending = tokio::spawn({
        let a = a.clone();
        async move {
            let call = a.open().await.unwrap();
            std::future::pending::<()>().await;
            drop(call);
        }
    });
    tokio::task::yield_now().await;
    pending.abort();
    let _ = pending.await;
    a.close();
    tokio::time::timeout(std::time::Duration::from_secs(2), b.disconnected())
        .await
        .unwrap();
    assert_eq!(count(&a), 0);
    assert_eq!(count(&b), 0);
    assert!(b.state.lock().unwrap().calls.is_empty());
}
