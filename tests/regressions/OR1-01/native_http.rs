// OR1-01, HTTP half (Opus review 1 P1-1; moved by review 2 N-5 into the
// Fetcher HTTP feature that defines Fetch/fetch_ordered). Included from
// crates/celld/capability.rs next to fetch_ordered.
use super::*;

fn local_export() -> Route {
    let route = Route {
        node: "n".into(),
        addr: "127.0.0.1:1".into(),
        process: process().into(),
        heap: "1".into(),
        token: random_id(),
        seal: String::new(),
        owner_scope: Some("Actor:1".into()),
        storage_scope: None,
        epoch: None,
    };
    exports().lock().unwrap().insert(
        route.token.clone(),
        Export {
            route: route.clone(),
            lanes: HashMap::new(),
            slot: Weak::new(),
            token: "1".into(),
            pin: None,
        },
    );
    route
}
fn order(sequence: u64) -> CallOrder {
    CallOrder {
        lane: "same-process-http".into(),
        sequence,
    }
}

/// The Fetcher HTTP half: a same-process fetch whose dispatch fails before
/// invoke_local_fetch (here: no HTTP transport) resolves its slot.
#[tokio::test]
async fn fetch_refused_before_the_callee_guard_resolves_its_slot() {
    let route = local_export();
    let control = FetchControl {
        session: None,
        route: route.clone(),
        order: Some(order(0)),
        restore: vec![],
    };
    let slot = CallerOrderSlot::new(&route, control.order.as_ref(), None);
    let fetch = Fetch {
        control,
        url: "http://x/".into(),
        method: "GET".into(),
        body: crate::js::RequestBody::Bytes(Default::default()),
        headers: vec![],
    };
    // Library tests never configure the HTTP transport, so dispatch fails
    // before invoke_local_fetch could build its guard.
    assert!(FETCH_DISPATCH.get().is_none());
    assert!(fetch_ordered(fetch, slot).await.is_err());
    drop(
        tokio::time::timeout(
            std::time::Duration::from_secs(2),
            ordered_admission(&route, Some(&order(1)), None),
        )
        .await
        .expect("the next call must not wait for the gap timeout")
        .unwrap(),
    );
}
