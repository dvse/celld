// OR1-01 (review 1, P1-1): a same-process ordered call that ends before
// its callee builds an OrderSlot must still resolve its sequence slot.
// Included from crates/celld/capability.rs.
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
        lane: "same-process".into(),
        sequence,
    }
}
fn request(route: &Route, sequence: u64) -> Request {
    Request {
        route: route.clone(),
        order: Some(order(sequence)),
        path: vec!["m".into()],
        args: None,
        release: false,
        session: None,
        transfer: None,
        prepared_wire: None,
    }
}

/// The node's dispatch waits in actor routing/admission (app.request,
/// local_request().run()) and the caller's op is dropped there.
#[tokio::test]
async fn rpc_call_dropped_before_the_callee_guard_resolves_its_slot() {
    let route = local_export();
    set_test_local_dispatch(Some(Arc::new(|_| Box::pin(std::future::pending()))));
    let call = {
        let request = request(&route, 0);
        let slot = CallerOrderSlot::new(&request.route, request.order.as_ref(), None);
        call_ordered(request, slot)
    };
    // Poll it into dispatch, then cancel it there.
    assert!(tokio::time::timeout(std::time::Duration::from_millis(20), call)
        .await
        .is_err());
    set_test_local_dispatch(None);
    let next = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        ordered_admission(&route, Some(&order(1)), None),
    )
    .await
    .expect("the next call must not wait for the gap timeout");
    drop(next.unwrap());
}

/// The node's dispatch refuses before invoke_local (preflight, owner moved).
#[tokio::test]
async fn rpc_call_refused_before_the_callee_guard_resolves_its_slot() {
    let route = local_export();
    set_test_local_dispatch(Some(Arc::new(|_| {
        Box::pin(async { Err(not_executed("capability actor moved")) })
    })));
    let request = request(&route, 0);
    let slot = CallerOrderSlot::new(&request.route, request.order.as_ref(), None);
    assert!(call_ordered(request, slot).await.is_err());
    set_test_local_dispatch(None);
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
