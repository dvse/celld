// OR2-01 (review 2, N-1): the per-session lane index must forget an
// export's lanes when the export is revoked or pruned. Repeated export/call/
// revoke over one long-lived peer session keeps the index bounded.
// Included from crates/celld/capability.rs.
use super::*;

fn bind_one(session: &str) -> String {
    let route = Route {
        node: "n".into(),
        addr: "127.0.0.1:1".into(),
        process: process().into(),
        heap: "1".into(),
        token: random_id(),
        seal: String::new(),
        owner_scope: None,
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
    // One ordered call over the peer session binds the export's lane.
    let order = CallOrder {
        lane: "peer-lane".into(),
        sequence: 0,
    };
    let lane = order_lane(&route, &order, Some(session)).unwrap();
    assert_eq!(lane.state.lock().unwrap().session.as_deref(), Some(session));
    route.token
}

fn indexed(session: &str) -> usize {
    session_lanes()
        .lock()
        .unwrap()
        .get(session)
        .map_or(0, Vec::len)
}

/// Exports whose heap is gone are pruned by `retain_live_exports`.
#[test]
fn pruned_exports_leave_the_session_index() {
    let session =
        crate::capability_session::Session::register(random_id(), "peer".into(), "p".repeat(64))
            .unwrap();
    for _ in 0..1000 {
        let token = bind_one(&session.id);
        // Prune only this export (the global table is shared by other tests).
        let mut local = HashMap::new();
        let export = exports().lock().unwrap().remove(&token).unwrap();
        local.insert(token, export);
        let _guard = exports().lock().unwrap();
        retain_live_exports(&mut local);
        assert!(local.is_empty());
    }
    assert_eq!(indexed(&session.id), 0, "index grew with pruned exports");
    session.close();
}

/// Revocation removes the export's lanes from the index.
#[test]
fn revoked_exports_leave_the_session_index() {
    let session =
        crate::capability_session::Session::register(random_id(), "peer".into(), "q".repeat(64))
            .unwrap();
    for _ in 0..1000 {
        let token = bind_one(&session.id);
        let mut entries = exports().lock().unwrap();
        let export = entries.remove(&token).unwrap();
        forget_session_lanes(&export);
    }
    assert_eq!(indexed(&session.id), 0, "index grew with revoked exports");
    session.close();
}
