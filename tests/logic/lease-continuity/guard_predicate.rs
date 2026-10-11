// Preserve and reuse the exact unchanged-red test source and all 15 oracles.

#[test]
fn intermediate_wall_expiry_alone_fences() {
    let mut s = intermediate_reading();
    let effects = read(&mut s.first.held.state, s.read_op, 30_000, 29_999,
        Ok(Some(s.first.desired)));
    assert_expired_halt(&effects);
    assert!(s.first.held.state.is_fenced());
    assert!(!s.first.held.state.node_authoritative());
    assert_no_cas(&effects);
}
#[test]
fn intermediate_monotonic_expiry_alone_fences() {
    let mut s = intermediate_reading();
    let effects = read(&mut s.first.held.state, s.read_op, 29_999, 30_000,
        Ok(Some(s.first.desired)));
    assert_expired_halt(&effects);
    assert!(s.first.held.state.is_fenced());
    assert!(!s.first.held.state.node_authoritative());
    assert_no_cas(&effects);
}
#[test]
fn every_current_read_branch_at_either_prior_expiry_is_expired() {
    for (wall, mono) in [(30_000, 29_999), (29_999, 30_000)] {
        for branch in 0..5 {
            let (mut s, op) = first_reading();
            let result = match branch {
                0 => Ok(Some(s.desired)),
                1 => Ok(Some(s.held.prior.clone())),
                2 => Err(Failure::Definite),
                3 => Ok(None),
                4 => {
                    let mut successor = s.desired;
                    successor.generation = "ordinary-successor-process".into();
                    successor.etag = "successor-E".into();
                    Ok(Some(successor))
                }
                _ => unreachable!(),
            };
            let effects = read(&mut s.held.state, op, wall, mono, result);
            assert_expired_halt(&effects);
            assert!(s.held.state.is_fenced(), "branch={branch} wall={wall} mono={mono}");
            assert!(!s.held.state.node_authoritative());
            assert_no_cas(&effects);
        }
    }
}
#[test]
fn pre_expiry_missing_and_mismatch_keep_specific_halt_reasons() {
    for missing in [true, false] {
        let (mut s, op) = first_reading();
        let mut successor = s.desired;
        successor.generation = "ordinary-successor-process".into();
        successor.etag = "successor-E".into();
        let effects = read(&mut s.held.state, op, 29_999, 29_999,
            Ok(if missing { None } else { Some(successor) }));
        let expected = if missing { HaltReason::NodeLeaseMissing }
            else { HaltReason::NodeLeaseMismatch };
        assert!(effects.iter().any(|effect| matches!(effect,
            Effect::Halt { code: 3, reason } if *reason == expected)), "{effects:?}");
        assert!(s.held.state.is_fenced());
        assert!(!s.held.state.node_authoritative());
        assert_no_cas(&effects);
    }
}
