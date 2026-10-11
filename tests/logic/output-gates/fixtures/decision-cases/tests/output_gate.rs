//! Hand-authored finite schedules against the actual celld-logic decision core.
//! No mock State, network, runtime, clock, random seed, or generated test matrix.
//! Each test begins with a new State and advances it ONLY through on_event.
use celld_logic::wake::{AlarmSnapshot, AlarmSource, PublicationId};
use celld_logic::*;

fn config(leases: bool) -> Config {
    Config {
        max_resident: 4,
        max_activations: 2,
        max_evictions: 2,
        max_releases: 2,
        max_outbound_websockets: 2,
        ownership_on_evict: OwnershipOnEvict::Sticky,
        require_node_lease: leases,
        peer_protocol: 1,
        operation_deadline_ms: Some(50),
        owner_log_recovery_backoff_ms: 10,
        owner_log_recovery_attempts: 2,
        alarm_resident_ms: 0,
        idle_evict_ms: None,
        pressure: pressure::PressureConfig::default(),
    }
}
struct H {
    s: State,
    clock: u64,
    count: usize,
}
impl H {
    fn new() -> Self {
        Self {
            s: State::new("fixture", config(false)),
            clock: 0,
            count: 0,
        }
    }
    fn leased() -> (Self, Timer, Timer) {
        let mut h = Self {
            s: State::new("fixture", config(true)),
            clock: 100,
            count: 0,
        };
        let e = h.step(Event::StartNodeLease {
            now_ms: 100,
            now_mono_ms: 100,
            spec: NodeLeaseSpec {
                addr: "fixture.invalid:0".into(),
                peer_protocol: 1,
                generation: "generation-a".into(),
                resume_generation: None,
                ttl_ms: 100,
            },
        });
        let op = one_op(&e, "lease-read");
        let e = h.step(Event::SelfNodeLeaseRead {
            op,
            now_ms: 100,
            now_mono_ms: 100,
            result: Ok(None),
        });
        let op = one_op(&e, "lease-cas");
        let e = h.step(Event::NodeLeaseCasCompleted {
            op,
            now_mono_ms: 100,
            result: Ok(LeaseCasOutcome::Applied {
                etag: "lease-1".into(),
            }),
            stamped_log_state: None,
        });
        let renew = timer(&e, "renew");
        let fence = timer(&e, "fence");
        assert!(h.s.node_authoritative());
        h.step(Event::LocalCellsRead { result: Ok(vec![]) });
        (h, renew, fence)
    }
    fn step(&mut self, event: Event) -> Vec<Effect> {
        self.count += 1;
        assert!(
            self.count <= 100,
            "finite trace exceeded its 100-event guard"
        );
        println!("event {:02}: {:?}", self.count, event);
        let effects = on_event(&mut self.s, event);
        println!("effects {:02}: {:?}", self.count, effects);
        self.s
            .validate()
            .expect("core structural invariant at every event boundary");
        effects
    }
    fn activate(&mut self, cell: &str, request: u64, previous: Option<u64>) -> u64 {
        let e = self.step(Event::RequestAt {
            request,
            cell: cell.into(),
            now_mono_ms: self.clock,
        });
        let op = one_op(&e, "owner-read");
        let owner = previous.map(|epoch| OwnerRecord {
            node: Some("fixture".into()),
            epoch,
            etag: format!("owner-{epoch}"),
        });
        let e = self.step(Event::OwnerRead {
            op,
            now_ms: self.clock,
            result: Ok(owner),
        });
        let op = one_op(&e, "owner-cas");
        let epoch = e
            .iter()
            .find_map(|e| {
                if let Effect::CasOwner { epoch, .. } = e {
                    Some(*epoch)
                } else {
                    None
                }
            })
            .unwrap();
        assert_eq!(epoch, previous.unwrap_or(0) + 1, "new writer lineage");
        let e = self.step(Event::OwnerCasCompleted {
            op,
            result: Ok(CasOutcome::Applied),
        });
        let op = one_op(&e, "restore");
        let e = self.step(Event::RestoreCompleted {
            op,
            result: Ok(RestoreOutcome {
                restored: previous.is_some(),
                alarm: None,
            }),
        });
        let op = one_op(&e, "start");
        let e = self.step(Event::RuntimeStarted {
            op,
            isolate: None,
            generation: 1,
            result: Ok(()),
        });
        let op = one_op(&e, "publish");
        let e = self.step(Event::Published { op, result: Ok(()) });
        assert!(
            e.contains(&Effect::Complete {
                request,
                result: Ok(Route::Local)
            }),
            "activation did not route: {e:?}"
        );
        assert_eq!(self.s.phase(cell), Some(&Phase::Resident { epoch }));
        epoch
    }
    fn join(&mut self, cell: &str, request: u64) {
        let e = self.step(Event::RequestAt {
            request,
            cell: cell.into(),
            now_mono_ms: self.clock,
        });
        assert!(
            e.contains(&Effect::Complete {
                request,
                result: Ok(Route::Local)
            }),
            "missing local admission: {e:?}"
        );
    }
    fn out(
        &mut self,
        request: u64,
        channel: Channel,
        position: Option<u64>,
        observed: Option<u64>,
        epoch: Option<u64>,
    ) -> Vec<Effect> {
        self.step(Event::OutputAt {
            request,
            channel,
            position,
            observed,
            epoch,
            now_mono_ms: self.clock,
        })
    }
    fn write(&mut self, request: u64, channel: Channel, position: u64) -> u64 {
        let e = self.out(request, channel, Some(position), None, Some(1));
        no_release(&e);
        one_op(&e, "await")
    }
    fn proof(&mut self, op: u64, position: u64) -> Vec<Effect> {
        self.step(Event::DurableReached {
            op,
            result: Ok(position),
            source: ProofSource::Fleet,
        })
    }
    fn bucket(&mut self, op: u64, position: u64) -> Vec<Effect> {
        self.step(Event::DurableReached {
            op,
            result: Ok(position),
            source: ProofSource::Bucket,
        })
    }
    fn fail(&mut self, op: u64) -> Vec<Effect> {
        self.step(Event::DurableReached {
            op,
            result: Err(Failure::Ambiguous),
            source: ProofSource::Fleet,
        })
    }
    fn expire(&mut self, op: u64) -> Vec<Effect> {
        self.clock += 50;
        self.step(Event::TimerFired {
            timer: Timer::OperationDeadline { op },
            now_ms: self.clock,
            now_mono_ms: self.clock,
        })
    }
    fn finish(&mut self, request: u64) {
        self.step(Event::ActivityFinished { request });
    }
    fn reset_done(&mut self, e: &[Effect], cell: &str) {
        let op = one_op(e, "reset");
        self.step(Event::RuntimeStopped { op });
        assert_eq!(self.s.phase(cell), Some(&Phase::Inactive));
    }
    fn alarm(&mut self, cell: &str) -> u64 {
        let at = self.clock + 10;
        let e = self.step(Event::AlarmObserved {
            cell: cell.into(),
            alarm: snapshot(Some(at as i64), 1, 1, 1),
            covered: true,
            now_ms: self.clock,
            now_mono_ms: self.clock,
        });
        let t = timer(&e, "alarm");
        self.clock = at;
        let e = self.step(Event::TimerFired {
            timer: t,
            now_ms: at,
            now_mono_ms: at,
        });
        one_op(&e, "alarm")
    }
    fn consumed(&mut self, alarm: u64, cell: &str, pos: u64) -> (u64, AlarmSnapshot) {
        let snap = snapshot(None, 1, 2, pos);
        let e = self.step(Event::AlarmFinished {
            op: alarm,
            cell: cell.into(),
            epoch: 1,
            now_ms: self.clock,
            now_mono_ms: self.clock,
            result: Ok((snap, true, Some(pos))),
        });
        no_release(&e);
        no_wake(&e);
        (one_op(&e, "await"), snap)
    }
    fn independent_witness(&mut self) {
        self.activate("witness", 900, None);
        let e = self.out(900, Channel::Response, None, None, Some(1));
        releases(&e, &[(900, Channel::Response, Ok(()))]);
        self.finish(900);
    }
}
fn one_op(e: &[Effect], kind: &str) -> u64 {
    let ops: Vec<u64> = e
        .iter()
        .filter_map(|e| match (kind, e) {
            ("lease-read", Effect::ReadSelfNodeLease { op })
            | ("lease-cas", Effect::CasNodeLease { op, .. })
            | ("owner-read", Effect::ReadOwner { op, .. })
            | ("owner-cas", Effect::CasOwner { op, .. })
            | ("restore", Effect::Restore { op, .. })
            | ("start", Effect::StartRuntime { op, .. })
            | ("publish", Effect::Publish { op, .. })
            | ("await", Effect::AwaitDurable { op, .. })
            | ("verify", Effect::VerifyOwnership { op, .. })
            | ("ensure", Effect::EnsureDurable { op, .. })
            | ("alarm", Effect::FireAlarm { op, .. }) => Some(*op),
            (
                "reset",
                Effect::StopRuntime {
                    op,
                    cause: StopCause::Reset,
                    ..
                },
            )
            | (
                "swap",
                Effect::StopRuntime {
                    op,
                    cause: StopCause::Swap,
                    ..
                },
            ) => Some(*op),
            _ => None,
        })
        .collect();
    assert_eq!(ops.len(), 1, "expected one {kind} effect: {e:?}");
    ops[0]
}
fn timer(e: &[Effect], kind: &str) -> Timer {
    e.iter()
        .find_map(|e| {
            if let Effect::ScheduleTimer { timer, .. } = e {
                match (kind, timer) {
                    ("renew", Timer::NodeLeaseRenew { .. })
                    | ("fence", Timer::NodeLeaseFence { .. })
                    | ("alarm", Timer::CellAlarm { .. }) => Some(timer.clone()),
                    _ => None,
                }
            } else {
                None
            }
        })
        .unwrap_or_else(|| panic!("missing {kind} timer: {e:?}"))
}
fn releases(e: &[Effect], expected: &[(u64, Channel, Result<(), RequestError>)]) {
    let actual: Vec<_> = e
        .iter()
        .filter_map(|e| {
            if let Effect::Release {
                request,
                channel,
                result,
            } = e
            {
                Some((*request, *channel, *result))
            } else {
                None
            }
        })
        .collect();
    assert_eq!(
        actual, expected,
        "wrong externally observable release set/order: {e:?}"
    );
}
fn no_release(e: &[Effect]) {
    releases(e, &[]);
}
fn no_wake(e: &[Effect]) {
    assert!(
        !e.iter()
            .any(|e| matches!(e, Effect::ReconcileWakeEntry { .. })),
        "premature alarm publication: {e:?}"
    );
}
fn verified(e: &[Effect], op: u64, cell: &str, epoch: u64) {
    no_release(e);
    assert!(
        e.contains(&Effect::VerifyOwnership {
            op,
            cell: cell.into(),
            epoch
        }),
        "missing exact ownership verification: {e:?}"
    );
}
fn snapshot(at: Option<i64>, epoch: u64, sequence: u64, position: u64) -> AlarmSnapshot {
    AlarmSnapshot::committed(
        at,
        AlarmSource {
            id: PublicationId { epoch, sequence },
            position,
        },
    )
}
const DU: Result<(), RequestError> = Err(RequestError::DurabilityUnproven);
const NF: Result<(), RequestError> = Err(RequestError::NodeFenced);

#[test]
fn g001_older_success_does_not_release_newest_reader() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let first = h.write(1, Channel::Response, 10);
    let last = h.write(2, Channel::Fetch, 20);
    no_release(&h.out(3, Channel::Service, None, None, Some(1)));
    releases(&h.proof(first, 10), &[(1, Channel::Response, Ok(()))]);
    let e = h.fail(last);
    releases(&e, &[(2, Channel::Fetch, DU), (3, Channel::Service, DU)]);
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g002_newest_release_does_not_make_old_failed_ticket_successful() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let first = h.write(1, Channel::Response, 10);
    let last = h.write(2, Channel::Fetch, 20);
    no_release(&h.out(3, Channel::Service, None, None, Some(1)));
    releases(
        &h.proof(last, 20),
        &[(2, Channel::Fetch, Ok(())), (3, Channel::Service, Ok(()))],
    );
    let e = h.fail(first);
    releases(&e, &[(1, Channel::Response, DU)]);
    no_release(&h.proof(last, 20));
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g003_reader_before_writer_survives_only_its_covering_proof() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let e = h.out(2, Channel::Response, None, Some(20), Some(1));
    no_release(&e);
    let read = one_op(&e, "await");
    let write = h.write(1, Channel::Fetch, 10);
    releases(&h.proof(write, 10), &[(1, Channel::Fetch, Ok(()))]);
    releases(&h.proof(read, 20), &[(2, Channel::Response, Ok(()))]);
    h.finish(1);
    h.finish(2);
}
#[test]
fn g004_higher_observation_cannot_join_lower_pending_write() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let low = h.write(1, Channel::Response, 10);
    let e = h.out(2, Channel::Fetch, None, Some(20), Some(1));
    no_release(&e);
    let high = one_op(&e, "await");
    no_release(&h.out(3, Channel::Service, None, Some(15), Some(1)));
    releases(&h.proof(low, 10), &[(1, Channel::Response, Ok(()))]);
    releases(
        &h.proof(high, 20),
        &[(2, Channel::Fetch, Ok(())), (3, Channel::Service, Ok(()))],
    );
    h.finish(1);
    h.finish(2);
    h.finish(3);
}
#[test]
fn g005_late_lower_ticket_does_not_hide_older_covering_gate() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let high = h.write(1, Channel::Response, 30);
    let low = h.write(2, Channel::Fetch, 10);
    let e = h.out(3, Channel::Service, None, Some(25), Some(1));
    no_release(&e);
    assert!(
        !e.iter().any(|e| matches!(e, Effect::AwaitDurable { .. })),
        "reader should share existing covering proof"
    );
    releases(&h.proof(low, 10), &[(2, Channel::Fetch, Ok(()))]);
    releases(
        &h.proof(high, 30),
        &[
            (1, Channel::Response, Ok(())),
            (3, Channel::Service, Ok(())),
        ],
    );
    h.finish(1);
    h.finish(2);
    h.finish(3);
}
#[test]
fn g006_cached_observation_still_trails_later_unproven_state() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let first = h.write(1, Channel::Response, 10);
    releases(&h.proof(first, 10), &[(1, Channel::Response, Ok(()))]);
    let second = h.write(2, Channel::Fetch, 20);
    no_release(&h.out(3, Channel::Service, None, Some(5), Some(1)));
    let e = h.fail(second);
    releases(&e, &[(2, Channel::Fetch, DU), (3, Channel::Service, DU)]);
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g007_cell_scoped_cache_cannot_cover_another_cells_observation() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.activate("b", 2, None);
    let a = h.write(1, Channel::Response, 100);
    releases(&h.proof(a, 100), &[(1, Channel::Response, Ok(()))]);
    let e = h.out(2, Channel::Response, None, Some(5), Some(1));
    no_release(&e);
    let b = one_op(&e, "await");
    assert!(e.contains(&Effect::AwaitDurable {
        op: b,
        cell: "b".into(),
        epoch: 1,
        position: 5
    }));
    releases(&h.proof(b, 5), &[(2, Channel::Response, Ok(()))]);
    h.finish(1);
    h.finish(2);
}
#[test]
fn g008_reset_discards_cached_proof_before_new_epoch_observation() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let old = h.write(1, Channel::Response, 100);
    releases(&h.proof(old, 100), &[(1, Channel::Response, Ok(()))]);
    let bad = h.write(1, Channel::Fetch, 101);
    let e = h.fail(bad);
    releases(&e, &[(1, Channel::Fetch, DU)]);
    h.reset_done(&e, "a");
    h.activate("a", 2, Some(1));
    let e = h.out(2, Channel::Response, None, Some(1), Some(2));
    no_release(&e);
    let new = one_op(&e, "await");
    no_release(&h.proof(old, 100));
    releases(&h.proof(new, 1), &[(2, Channel::Response, Ok(()))]);
    h.finish(2);
}
#[test]
fn g009_finished_activity_with_two_channels_keeps_last_gate_pin() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let a = h.write(1, Channel::Fetch, 10);
    let b = h.write(1, Channel::Response, 20);
    h.finish(1);
    releases(&h.proof(a, 10), &[(1, Channel::Fetch, Ok(()))]);
    let e = h.step(Event::EvictRequested {
        request: 90,
        cell: "a".into(),
        now_mono_ms: 0,
    });
    assert!(
        !e.iter().any(|e| matches!(e, Effect::EnsureDurable { .. })),
        "remaining gate must pin residency"
    );
    releases(&h.proof(b, 20), &[(1, Channel::Response, Ok(()))]);
    releases(
        &h.out(1, Channel::Service, None, None, Some(1)),
        &[(1, Channel::Service, DU)],
    );
    let e = h.step(Event::Evict { cell: "a".into() });
    one_op(&e, "ensure");
}
#[test]
fn g010_finished_follower_remains_held_then_loses_activity() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let gate = h.write(1, Channel::Response, 20);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    h.finish(2);
    releases(
        &h.proof(gate, 20),
        &[(1, Channel::Response, Ok(())), (2, Channel::Fetch, Ok(()))],
    );
    releases(
        &h.out(2, Channel::Service, None, None, Some(1)),
        &[(2, Channel::Service, DU)],
    );
    h.finish(1);
    h.join("a", 3);
    releases(
        &h.out(3, Channel::Response, None, Some(20), Some(1)),
        &[(3, Channel::Response, Ok(()))],
    );
    h.finish(3);
}
#[test]
fn g011_cancelled_writer_still_holds_readers_until_proof() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let gate = h.write(1, Channel::Response, 20);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    no_release(&h.step(Event::Cancel { request: 1 }));
    releases(
        &h.proof(gate, 20),
        &[(1, Channel::Response, Ok(())), (2, Channel::Fetch, Ok(()))],
    );
    releases(
        &h.out(1, Channel::Service, None, None, Some(1)),
        &[(1, Channel::Service, DU)],
    );
    h.finish(2);
}
#[test]
fn g012_cancelled_follower_does_not_cancel_live_writer_proof() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let gate = h.write(1, Channel::Response, 20);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    no_release(&h.step(Event::Cancel { request: 2 }));
    let e = h.bucket(gate, 20);
    verified(&e, gate, "a", 1);
    releases(
        &h.step(Event::OwnershipVerified {
            op: gate,
            result: Ok(()),
        }),
        &[(1, Channel::Response, Ok(())), (2, Channel::Fetch, Ok(()))],
    );
    releases(
        &h.out(2, Channel::Service, None, None, Some(1)),
        &[(2, Channel::Service, DU)],
    );
    h.finish(1);
}
#[test]
fn g013_short_proof_resets_sibling_gates_but_not_other_cell() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.activate("b", 3, None);
    let a = h.write(1, Channel::Response, 10);
    let sibling = h.write(2, Channel::Fetch, 20);
    let b = h.write(3, Channel::Response, 7);
    let e = h.proof(a, 9);
    releases(&e, &[(1, Channel::Response, DU), (2, Channel::Fetch, DU)]);
    no_release(&h.proof(sibling, 20));
    h.reset_done(&e, "a");
    releases(&h.proof(b, 7), &[(3, Channel::Response, Ok(()))]);
    h.finish(3);
}
#[test]
fn g014_bucket_verification_deadline_refuses_owner_and_late_read() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let gate = h.write(1, Channel::Response, 10);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    verified(&h.bucket(gate, 10), gate, "a", 1);
    let e = h.expire(gate);
    releases(&e, &[(1, Channel::Response, DU), (2, Channel::Fetch, DU)]);
    no_release(&h.step(Event::OwnershipVerified {
        op: gate,
        result: Ok(()),
    }));
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g015_one_bucket_ownership_read_cannot_unlock_sibling_barrier() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let a = h.write(1, Channel::Response, 10);
    let b = h.write(2, Channel::Fetch, 20);
    verified(&h.bucket(a, 10), a, "a", 1);
    verified(&h.bucket(b, 20), b, "a", 1);
    releases(
        &h.step(Event::OwnershipVerified {
            op: b,
            result: Ok(()),
        }),
        &[(2, Channel::Fetch, Ok(()))],
    );
    no_release(&h.step(Event::OwnershipVerified {
        op: b,
        result: Ok(()),
    }));
    releases(
        &h.step(Event::OwnershipVerified {
            op: a,
            result: Ok(()),
        }),
        &[(1, Channel::Response, Ok(()))],
    );
    h.finish(1);
    h.finish(2);
}
#[test]
fn g016_bucket_ownership_loss_invalidates_pending_fleet_sibling() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    h.join("a", 3);
    let a = h.write(1, Channel::Response, 10);
    let b = h.write(2, Channel::Fetch, 20);
    no_release(&h.out(3, Channel::Service, None, None, Some(1)));
    verified(&h.bucket(a, 10), a, "a", 1);
    let e = h.step(Event::OwnershipVerified {
        op: a,
        result: Err(Failure::Definite),
    });
    releases(
        &e,
        &[
            (1, Channel::Response, DU),
            (2, Channel::Fetch, DU),
            (3, Channel::Service, DU),
        ],
    );
    no_release(&h.proof(b, 20));
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g017_unknown_verification_op_cannot_release_real_pending_gate() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let gate = h.write(1, Channel::Response, 10);
    verified(&h.bucket(gate, 10), gate, "a", 1);
    no_release(&h.step(Event::OwnershipVerified {
        op: gate + 1000,
        result: Ok(()),
    }));
    releases(
        &h.step(Event::OwnershipVerified {
            op: gate,
            result: Ok(()),
        }),
        &[(1, Channel::Response, Ok(()))],
    );
    h.finish(1);
}
#[test]
fn g018_old_epoch_sample_refused_without_poisoning_new_epoch_gate() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let old = h.write(1, Channel::Response, 10);
    let e = h.fail(old);
    h.reset_done(&e, "a");
    h.activate("a", 2, Some(1));
    releases(
        &h.out(2, Channel::Fetch, Some(10), None, Some(1)),
        &[(2, Channel::Fetch, DU)],
    );
    let e = h.out(2, Channel::Response, Some(1), None, Some(2));
    no_release(&e);
    let gate = one_op(&e, "await");
    no_release(&h.bucket(old, 10));
    releases(&h.proof(gate, 1), &[(2, Channel::Response, Ok(()))]);
    h.finish(2);
}
#[test]
fn g019_fence_between_bucket_proof_and_ownership_refuses_every_cell() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.activate("b", 2, None);
    let a = h.write(1, Channel::Response, 10);
    let b = h.write(2, Channel::Fetch, 20);
    verified(&h.bucket(a, 10), a, "a", 1);
    releases(
        &h.step(Event::NodeFenced),
        &[(1, Channel::Response, NF), (2, Channel::Fetch, NF)],
    );
    no_release(&h.step(Event::OwnershipVerified {
        op: a,
        result: Ok(()),
    }));
    no_release(&h.proof(b, 20));
    assert!(h.s.is_fenced());
    assert!(!h.s.ready_to_serve());
    let e = h.step(Event::Request {
        request: 3,
        cell: "a".into(),
    });
    assert!(e.contains(&Effect::Complete {
        request: 3,
        result: Err(RequestError::NodeFenced)
    }));
}
#[test]
fn g020_expired_ticket_cannot_rewind_clock_to_regain_authority() {
    let (mut h, _, fence) = H::leased();
    h.activate("a", 1, None);
    h.clock = 200;
    releases(
        &h.out(1, Channel::Response, None, None, Some(1)),
        &[(1, Channel::Response, NF)],
    );
    h.clock = 199;
    releases(
        &h.out(1, Channel::Fetch, None, None, Some(1)),
        &[(1, Channel::Fetch, NF)],
    );
    assert!(!h.s.node_authoritative());
    h.step(Event::TimerFired {
        timer: fence,
        now_ms: 200,
        now_mono_ms: 200,
    });
    assert!(h.s.is_fenced());
}

// These two nonpromoting characterization cases record late settlement.
// A prior write may legitimately be acknowledged after authority expires if
// its proof establishes a successor-recoverable linearization point. These
// cases do not equate a late Release Ok with a durability/linearizability bug.
// Their verdict checks setup, positive controls, exactly-once settlement and
// terminal fencing, not a yet-unestablished no-late-ack policy.
#[test]
fn g021_fleet_proof_after_authority_expiry_records_settlement() {
    let (mut h, _, fence) = H::leased();
    h.activate("a", 1, None);
    let control = h.write(1, Channel::Sync, 5);
    releases(&h.proof(control, 5), &[(1, Channel::Sync, Ok(()))]);
    h.clock = 199;
    let delayed = h.write(1, Channel::Response, 10);
    let e = h.step(Event::RequestAt {
        request: 2,
        cell: "a".into(),
        now_mono_ms: 200,
    });
    assert!(e.contains(&Effect::Complete {
        request: 2,
        result: Err(RequestError::NodeUnavailable)
    }));
    assert!(!h.s.node_authoritative());
    assert!(
        !h.s.is_fenced(),
        "expiration must precede the delayed fence timer"
    );
    let e = h.proof(delayed, 10);
    println!(
        "CHARACTERIZATION late_effects={e:?} authoritative={} fenced={}",
        h.s.node_authoritative(),
        h.s.is_fenced()
    );
    assert!(!h.s.node_authoritative());
    let terminal = h.step(Event::TimerFired {
        timer: fence,
        now_ms: 200,
        now_mono_ms: 200,
    });
    println!(
        "CHARACTERIZATION fence_effects={terminal:?} authoritative={} fenced={}",
        h.s.node_authoritative(),
        h.s.is_fenced()
    );
    assert!(h.s.is_fenced());
    assert!(!h.s.node_authoritative());
    let settlements: Vec<_> = e
        .iter()
        .chain(terminal.iter())
        .filter_map(|effect| {
            if let Effect::Release {
                request,
                channel,
                result,
            } = effect
            {
                Some((*request, *channel, *result))
            } else {
                None
            }
        })
        .collect();
    assert_eq!(
        settlements.len(),
        1,
        "held ticket must settle exactly once by the actual fence: {settlements:?}"
    );
    assert_eq!((settlements[0].0, settlements[0].1), (1, Channel::Response));
    println!(
        "CHARACTERIZATION observed_settlement={:?}; policy_verdict=UNRESOLVED; promotion=false",
        settlements[0].2
    );
}
#[test]
fn g022_bucket_verification_after_authority_expiry_records_settlement() {
    let (mut h, _, fence) = H::leased();
    h.activate("a", 1, None);
    let control = h.write(1, Channel::Sync, 5);
    verified(&h.bucket(control, 5), control, "a", 1);
    releases(
        &h.step(Event::OwnershipVerified {
            op: control,
            result: Ok(()),
        }),
        &[(1, Channel::Sync, Ok(()))],
    );
    h.clock = 199;
    let delayed = h.write(1, Channel::Response, 10);
    verified(&h.bucket(delayed, 10), delayed, "a", 1);
    let e = h.step(Event::RequestAt {
        request: 2,
        cell: "a".into(),
        now_mono_ms: 200,
    });
    assert!(e.contains(&Effect::Complete {
        request: 2,
        result: Err(RequestError::NodeUnavailable)
    }));
    assert!(!h.s.node_authoritative());
    assert!(!h.s.is_fenced());
    let e = h.step(Event::OwnershipVerified {
        op: delayed,
        result: Ok(()),
    });
    println!(
        "CHARACTERIZATION late_effects={e:?} authoritative={} fenced={}",
        h.s.node_authoritative(),
        h.s.is_fenced()
    );
    assert!(!h.s.node_authoritative());
    let terminal = h.step(Event::TimerFired {
        timer: fence,
        now_ms: 200,
        now_mono_ms: 200,
    });
    println!(
        "CHARACTERIZATION fence_effects={terminal:?} authoritative={} fenced={}",
        h.s.node_authoritative(),
        h.s.is_fenced()
    );
    assert!(h.s.is_fenced());
    assert!(!h.s.node_authoritative());
    let settlements: Vec<_> = e
        .iter()
        .chain(terminal.iter())
        .filter_map(|effect| {
            if let Effect::Release {
                request,
                channel,
                result,
            } = effect
            {
                Some((*request, *channel, *result))
            } else {
                None
            }
        })
        .collect();
    assert_eq!(
        settlements.len(),
        1,
        "held ticket must settle exactly once by the actual fence: {settlements:?}"
    );
    assert_eq!((settlements[0].0, settlements[0].1), (1, Channel::Response));
    println!(
        "CHARACTERIZATION observed_settlement={:?}; policy_verdict=UNRESOLVED; promotion=false",
        settlements[0].2
    );
}
#[test]
fn g023_unanswered_renewal_cannot_extend_output_authority() {
    let (mut h, renew, fence) = H::leased();
    h.activate("a", 1, None);
    let e = h.step(Event::TimerFired {
        timer: renew,
        now_ms: 133,
        now_mono_ms: 133,
    });
    let renewal = one_op(&e, "lease-cas");
    h.clock = 199;
    let gate = h.write(1, Channel::Response, 10);
    releases(&h.proof(gate, 10), &[(1, Channel::Response, Ok(()))]);
    h.clock = 200;
    releases(
        &h.out(1, Channel::Fetch, Some(11), None, Some(1)),
        &[(1, Channel::Fetch, NF)],
    );
    let e = h.step(Event::NodeLeaseCasCompleted {
        op: renewal,
        now_mono_ms: 200,
        result: Ok(LeaseCasOutcome::Applied {
            etag: "too-late".into(),
        }),
        stamped_log_state: None,
    });
    assert!(h.s.is_fenced());
    assert!(e.iter().any(|e| matches!(
        e,
        Effect::Halt {
            reason: HaltReason::NodeLeaseExpired,
            ..
        }
    )));
    no_release(&h.step(Event::TimerFired {
        timer: fence,
        now_ms: 200,
        now_mono_ms: 200,
    }));
}
#[test]
fn g024_stale_fence_after_timely_renewal_does_not_kill_pending_gate() {
    let (mut h, renew, old_fence) = H::leased();
    h.activate("a", 1, None);
    let e = h.step(Event::TimerFired {
        timer: renew,
        now_ms: 133,
        now_mono_ms: 133,
    });
    let renewal = one_op(&e, "lease-cas");
    h.step(Event::NodeLeaseCasCompleted {
        op: renewal,
        now_mono_ms: 140,
        result: Ok(LeaseCasOutcome::Applied {
            etag: "lease-2".into(),
        }),
        stamped_log_state: None,
    });
    h.clock = 199;
    let gate = h.write(1, Channel::Response, 10);
    no_release(&h.step(Event::TimerFired {
        timer: old_fence,
        now_ms: 200,
        now_mono_ms: 200,
    }));
    assert!(h.s.node_authoritative());
    releases(&h.proof(gate, 10), &[(1, Channel::Response, Ok(()))]);
    h.finish(1);
}

#[test]
fn g025_alarm_proof_does_not_unlock_reader_behind_later_output() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let alarm = h.alarm("a");
    let (consume, snap) = h.consumed(alarm, "a", 20);
    let write = h.write(1, Channel::Response, 30);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    let e = h.proof(consume, 20);
    no_release(&e);
    assert!(e.contains(&Effect::ReconcileWakeEntry {
        cell: "a".into(),
        alarm: snap
    }));
    let e = h.fail(write);
    releases(&e, &[(1, Channel::Response, DU), (2, Channel::Fetch, DU)]);
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g026_reader_trails_new_alarm_instead_of_earlier_output() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let write = h.write(1, Channel::Response, 10);
    let alarm = h.alarm("a");
    let (consume, snap) = h.consumed(alarm, "a", 20);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    releases(&h.proof(write, 10), &[(1, Channel::Response, Ok(()))]);
    let e = h.proof(consume, 20);
    releases(&e, &[(2, Channel::Fetch, Ok(()))]);
    assert!(e.contains(&Effect::ReconcileWakeEntry {
        cell: "a".into(),
        alarm: snap
    }));
    h.finish(1);
    h.finish(2);
}
#[test]
fn g027_alarm_bucket_proof_keeps_wake_and_reader_until_ownership() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let alarm = h.alarm("a");
    let (consume, snap) = h.consumed(alarm, "a", 20);
    no_release(&h.out(1, Channel::Response, None, Some(20), Some(1)));
    let e = h.bucket(consume, 20);
    verified(&e, consume, "a", 1);
    no_wake(&e);
    let e = h.step(Event::OwnershipVerified {
        op: consume,
        result: Ok(()),
    });
    releases(&e, &[(1, Channel::Response, Ok(()))]);
    assert!(e.contains(&Effect::ReconcileWakeEntry {
        cell: "a".into(),
        alarm: snap
    }));
    no_wake(&h.step(Event::OwnershipVerified {
        op: consume,
        result: Ok(()),
    }));
    h.finish(1);
}
#[test]
fn g028_failed_alarm_ownership_rearms_without_deleting_wake() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let alarm = h.alarm("a");
    let (consume, _) = h.consumed(alarm, "a", 20);
    no_release(&h.out(1, Channel::Response, None, None, Some(1)));
    verified(&h.bucket(consume, 20), consume, "a", 1);
    let e = h.step(Event::OwnershipVerified {
        op: consume,
        result: Err(Failure::Ambiguous),
    });
    releases(&e, &[(1, Channel::Response, DU)]);
    no_wake(&e);
    timer(&e, "alarm");
    h.reset_done(&e, "a");
    no_release(&h.proof(consume, 20));
    h.independent_witness();
}
#[test]
fn g029_post_reset_consumed_observation_cannot_retire_alarm_wake() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let alarm = h.alarm("a");
    let (consume, snap) = h.consumed(alarm, "a", 20);
    let e = h.fail(consume);
    no_wake(&e);
    timer(&e, "alarm");
    no_wake(&h.step(Event::AlarmObserved {
        cell: "a".into(),
        alarm: snap,
        covered: true,
        now_ms: 11,
        now_mono_ms: 11,
    }));
    no_wake(&h.proof(consume, 20));
    h.reset_done(&e, "a");
    h.activate("a", 2, Some(1));
    releases(
        &h.out(2, Channel::Response, None, None, Some(2)),
        &[(2, Channel::Response, Ok(()))],
    );
    h.finish(2);
}
#[test]
fn g030_stale_alarm_completion_cannot_gate_reactivated_epoch() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let alarm = h.alarm("a");
    let (_consuming_gate, _) = h.consumed(alarm, "a", 9);
    let write = h.write(1, Channel::Response, 10);
    let e = h.fail(write);
    h.reset_done(&e, "a");
    h.activate("a", 2, Some(1));
    let e = h.step(Event::AlarmFinished {
        op: alarm,
        cell: "a".into(),
        epoch: 1,
        now_ms: h.clock,
        now_mono_ms: h.clock,
        result: Ok((snapshot(None, 1, 2, 20), true, Some(20))),
    });
    no_wake(&e);
    no_release(&e);
    assert!(
        !e.iter().any(|e| matches!(e, Effect::AwaitDurable { .. })),
        "old alarm opened a gate in a replacement epoch"
    );
    let e = h.out(2, Channel::Response, Some(1), None, Some(2));
    let gate = one_op(&e, "await");
    no_release(&e);
    releases(&h.proof(gate, 1), &[(2, Channel::Response, Ok(()))]);
    h.finish(2);
}
#[test]
fn g031_late_alarm_write_after_handler_timeout_still_holds_reader() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let alarm = h.alarm("a");
    let e = h.expire(alarm);
    no_wake(&e);
    timer(&e, "alarm");
    let (consume, _) = h.consumed(alarm, "a", 20);
    no_release(&h.out(1, Channel::Response, None, Some(20), Some(1)));
    let e = h.proof(consume, 20);
    releases(&e, &[(1, Channel::Response, Ok(()))]);
    no_wake(&e); // Timed-out firing is no longer entitled to delete its wake.
    h.finish(1);
}
#[test]
fn g032_output_failure_drains_alarm_barrier_and_its_reader() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    let write = h.write(1, Channel::Response, 10);
    let alarm = h.alarm("a");
    let (consume, _) = h.consumed(alarm, "a", 20);
    no_release(&h.out(2, Channel::Fetch, None, None, Some(1)));
    let e = h.fail(write);
    releases(&e, &[(1, Channel::Response, DU), (2, Channel::Fetch, DU)]);
    no_wake(&e);
    timer(&e, "alarm");
    let late = h.bucket(consume, 20);
    no_release(&late);
    no_wake(&late);
    assert!(!late
        .iter()
        .any(|e| matches!(e, Effect::VerifyOwnership { .. })));
    h.reset_done(&e, "a");
    h.independent_witness();
}
#[test]
fn g033_same_epoch_generation_swap_forgets_previous_runtime_proof() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let old = h.write(1, Channel::Response, 100);
    releases(&h.proof(old, 100), &[(1, Channel::Response, Ok(()))]);
    h.finish(1);
    let e = h.step(Event::GenerationChanged {
        generation: 2,
        now_mono_ms: 0,
        max_age_ms: 100,
        eager_classes: vec![],
    });
    let stop = one_op(&e, "swap");
    let e = h.step(Event::RuntimeStopped { op: stop });
    let start = one_op(&e, "start");
    let e = h.step(Event::RuntimeStarted {
        op: start,
        isolate: None,
        generation: 2,
        result: Ok(()),
    });
    let publish = one_op(&e, "publish");
    h.step(Event::Published {
        op: publish,
        result: Ok(()),
    });
    assert_eq!(h.s.phase("a"), Some(&Phase::Resident { epoch: 1 }));
    h.join("a", 2);
    let e = h.out(2, Channel::Response, None, Some(1), Some(1));
    no_release(&e);
    let new = one_op(&e, "await");
    no_release(&h.proof(old, 100));
    releases(&h.proof(new, 1), &[(2, Channel::Response, Ok(()))]);
    h.finish(2);
}
#[test]
fn g034_quiescing_swap_admits_handler_gate_without_early_stop() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let e = h.step(Event::GenerationChanged {
        generation: 2,
        now_mono_ms: 0,
        max_age_ms: 100,
        eager_classes: vec![],
    });
    assert!(!e.iter().any(|e| matches!(e, Effect::StopRuntime { .. })));
    let e = h.step(Event::GateRequestAt {
        request: 2,
        cell: "a".into(),
        now_mono_ms: 1,
    });
    assert!(e.contains(&Effect::Complete {
        request: 2,
        result: Ok(Route::Local)
    }));
    let gate = h.write(2, Channel::Fetch, 10);
    h.finish(1);
    h.finish(2);
    assert_eq!(h.s.phase("a"), Some(&Phase::Resident { epoch: 1 }));
    let e = h.proof(gate, 10);
    releases(&e, &[(2, Channel::Fetch, Ok(()))]);
    let stop = one_op(&e, "swap");
    let e = h.step(Event::RuntimeStopped { op: stop });
    let start = one_op(&e, "start");
    let e = h.step(Event::RuntimeStarted {
        op: start,
        isolate: None,
        generation: 2,
        result: Ok(()),
    });
    let publish = one_op(&e, "publish");
    h.step(Event::Published {
        op: publish,
        result: Ok(()),
    });
    h.join("a", 3);
    releases(
        &h.out(3, Channel::Response, None, None, Some(1)),
        &[(3, Channel::Response, Ok(()))],
    );
    h.finish(3);
}
#[test]
fn g035_released_response_head_does_not_cover_later_chunk() {
    let mut h = H::new();
    h.activate("a", 1, None);
    h.join("a", 2);
    releases(
        &h.out(1, Channel::Response, None, None, Some(1)),
        &[(1, Channel::Response, Ok(()))],
    );
    let write = h.write(2, Channel::Fetch, 10);
    no_release(&h.out(1, Channel::Response, None, Some(10), Some(1)));
    verified(&h.bucket(write, 10), write, "a", 1);
    releases(
        &h.step(Event::OwnershipVerified {
            op: write,
            result: Ok(()),
        }),
        &[(2, Channel::Fetch, Ok(())), (1, Channel::Response, Ok(()))],
    );
    releases(
        &h.out(1, Channel::Response, None, Some(10), Some(1)),
        &[(1, Channel::Response, Ok(()))],
    );
    h.finish(1);
    h.finish(2);
}
#[test]
fn g036_eviction_rescue_cannot_reuse_cache_as_new_proof() {
    let mut h = H::new();
    h.activate("a", 1, None);
    let first = h.write(1, Channel::Response, 10);
    releases(&h.proof(first, 10), &[(1, Channel::Response, Ok(()))]);
    h.finish(1);
    let e = h.step(Event::Evict { cell: "a".into() });
    let eviction = one_op(&e, "ensure");
    h.join("a", 2);
    assert_eq!(h.s.phase("a"), Some(&Phase::Resident { epoch: 1 }));
    let e = h.out(2, Channel::Response, None, Some(10), Some(1));
    no_release(&e);
    let gate = one_op(&e, "await");
    let e = h.step(Event::DurabilityChecked {
        op: eviction,
        result: Ok(()),
    });
    no_release(&e);
    assert!(
        !e.iter().any(|e| matches!(e, Effect::StopRuntime { .. })),
        "cancelled eviction stopped the rescued runtime"
    );
    releases(&h.proof(gate, 10), &[(2, Channel::Response, Ok(()))]);
    h.finish(2);
}
