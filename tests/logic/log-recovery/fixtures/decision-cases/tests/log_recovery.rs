//! Finite, handwritten component schedules. Every decision below calls the
//! delivered celld-logic crate. Storage acknowledgements, ownership readbacks,
//! restore chains and CAS outcomes are explicitly synthetic premises, not I/O.
use celld_logic::durability::{proof_deadline, ProofProgress, ProofWait};
use celld_logic::epoch_gc::{self, ListedEpoch};
use celld_logic::log_evict::{EvictionPolicy, FollowerHealth, Verdict};
use celld_logic::log_tier::*;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Debug;

struct Receipt {
    id: &'static str,
    events: usize,
}
impl Receipt {
    fn new(id: &'static str) -> Self {
        println!("BEGIN {id}: native-component; synthetic storage facts; no I/O");
        Self { id, events: 0 }
    }
    fn observe<T: Debug>(&mut self, label: &str, result: T) -> T {
        self.events += 1;
        assert!(self.events <= 100, "finite observation ceiling");
        println!("{} {:03} {} => {:?}", self.id, self.events, label, result);
        result
    }
    fn done(self) {
        assert!(self.events >= 4, "incomplete trace receipt");
        println!(
            "END {} observations={}; cleanup=drop owned values; external resources=0",
            self.id, self.events
        );
    }
}
macro_rules! obs {
    ($r:ident, $label:literal, $value:expr) => {{
        let result = $value;
        $r.observe($label, result)
    }};
}
fn members(names: &[&str]) -> BTreeSet<String> {
    names.iter().map(|s| (*s).to_string()).collect()
}
fn record(names: &[&str], base: u64) -> LogRecord {
    create_record(members(names), base).expect("nonempty synthetic ensemble")
}
fn view(record: &LogRecord) -> LeaderView {
    LeaderView {
        epoch: record.epoch,
        ensemble: record.ensemble.clone(),
    }
}
fn listed(values: &[(u64, u64)]) -> Vec<ListedEpoch> {
    values
        .iter()
        .map(|&(epoch, newest_ms)| ListedEpoch { epoch, newest_ms })
        .collect()
}
fn policy() -> EvictionPolicy {
    EvictionPolicy {
        budget_ms: 25,
        sibling_factor: 4,
        sustain_ms: 20,
        backstop_ms: 100,
        quarantine_ms: 200,
        min_swap_interval_ms: 50,
        window_ms: 100,
        min_samples: 3,
        hedge_floor_ms: 10,
        hedge_factor: 2,
    }
}

#[test]
fn j001_later_cell_flush_cannot_skip_uncovered_head_batch() {
    let mut r = Receipt::new("J001");
    let mut ledger = ShipLedger::default();
    obs!(r, "observe epoch 1", ledger.observe_epoch(1));
    obs!(
        r,
        "ship alpha batch through seq 2",
        ledger.shipped(2, "alpha")
    );
    obs!(
        r,
        "ship beta batch through seq 4",
        ledger.shipped(4, "beta")
    );
    obs!(
        r,
        "beta per-cell upload succeeds; alpha fails",
        ledger.advance(|cell| *cell == "beta")
    );
    assert_eq!(
        obs!(r, "truncation remains before hole", ledger.covered_seq()),
        0
    );
    assert!(!obs!(
        r,
        "mixed bundle retained",
        bundle_deletable([(2, 0), (4, 4)])
    ));
    obs!(
        r,
        "alpha retry durable; both batches covered",
        ledger.advance(|_| true)
    );
    assert_eq!(
        obs!(r, "contiguous covered watermark", ledger.covered_seq()),
        4
    );
    assert!(obs!(
        r,
        "mixed bundle may now delete",
        bundle_deletable([(2, 2), (4, 4)])
    ));
    r.done();
}

#[test]
fn j002_capture_credit_gap_blocks_swap_then_new_epoch_resets_truncation() {
    let mut r = Receipt::new("J002");
    let old = record(&["a", "b"], 10);
    let mut ledger = ShipLedger::default();
    obs!(r, "old epoch", ledger.observe_epoch(old.epoch));
    obs!(r, "old batch acked through 12", ledger.shipped(12, ()));
    obs!(r, "old per-cell coverage landed", ledger.advance(|_| true));
    assert_eq!(ledger.covered_seq(), 12);
    assert!(!obs!(
        r,
        "new captured batch not yet credited",
        may_reconfigure(true, true)
    ));
    assert!(obs!(
        r,
        "capture credited and all covered",
        may_reconfigure(false, true)
    ));
    let next = obs!(
        r,
        "plan empty-join replacement",
        plan_reconfigure(&old, 13, members(&["a", "c"]))
    )
    .unwrap();
    assert_eq!(next.tier_through, 13);
    assert_eq!(next.record.tiered, 13);
    assert!(obs!(
        r,
        "old fragment now closed",
        fragment_closed(&next.record, old.epoch)
    ));
    obs!(
        r,
        "successful synthetic CAS changes sequence space",
        ledger.observe_epoch(next.record.epoch)
    );
    assert_eq!(ledger.covered_seq(), 0);
    let mut fresh = FollowerLog::join(next.record.epoch, next.tier_through);
    assert!(obs!(
        r,
        "empty joiner starts above proven bucket base",
        fresh.accept_append(next.record.epoch, 14)
    ));
    assert_eq!((fresh.base, fresh.end), (13, 14));
    r.done();
}

#[test]
fn j003_gray_eviction_cannot_abandon_last_uncovered_fleet_proof() {
    let mut r = Receipt::new("J003");
    let p = policy();
    let old = record(&["a", "b"], 6);
    let mut follower = FollowerLog::join(1, 6);
    assert!(obs!(
        r,
        "a held acknowledged row 7",
        follower.accept_append(1, 7)
    ));
    let ends = BTreeMap::from([("a".into(), 7), ("b".into(), 7)]);
    assert!(obs!(
        r,
        "known fleet proof 7",
        ack_fleet_allowed(&view(&old), &ends, 7)
    ));
    let mut h = FollowerHealth::default();
    obs!(r, "next append to b stalls", h.append_started("b", 10));
    assert_eq!(
        obs!(
            r,
            "backstop nominates b",
            h.verdict(&p, "b", &["a".into(), "b".into()], 110)
        ),
        Verdict::Evict
    );
    assert!(!obs!(
        r,
        "failed bucket upload forbids replacement",
        may_reconfigure(false, false)
    ));
    assert!(!obs!(
        r,
        "old witness remains live",
        fragment_closed(&old, 1)
    ));
    assert_eq!((follower.base, follower.end), (6, 7));
    assert!(obs!(
        r,
        "bucket retry covers 7",
        may_reconfigure(false, true)
    ));
    let next = obs!(
        r,
        "prepare covered replacement",
        plan_reconfigure(&old, 7, members(&["a", "c"]))
    )
    .unwrap();
    assert_eq!(next.tier_through, 7);
    assert!(fragment_closed(&next.record, 1));
    let mut joiner = FollowerLog::join(next.record.epoch, 7);
    assert!(obs!(
        r,
        "fresh joiner accepts next row",
        joiner.accept_append(2, 8)
    ));
    r.done();
}

#[test]
fn j004_recovery_wins_prepared_reconfiguration_before_old_credit() {
    let mut r = Receipt::new("J004");
    let old = record(&["a", "b"], 4);
    let prepared = obs!(
        r,
        "prepare replacement before competing CAS",
        plan_reconfigure(&old, 6, members(&["b", "c"]))
    )
    .unwrap();
    assert_eq!(prepared.record.epoch, 2);
    let recovering = obs!(
        r,
        "synthetic recovery CAS wins old etag",
        start_recovery(&old, "recoverer", 100)
    )
    .unwrap();
    // The CAS loss is a premise. We do not implement or test a bucket CAS.
    assert!(obs!(
        r,
        "reread forbids retrying replacement",
        plan_reconfigure(&recovering, 6, members(&["b", "c"]))
    )
    .is_none());
    assert!(!obs!(
        r,
        "delayed old epoch PUT cannot credit",
        bundle_credit_allowed(Some(&recovering), old.epoch)
    ));
    assert_eq!(
        obs!(
            r,
            "maintenance waits for rival",
            maintain_step(Some(&recovering))
        ),
        MaintainStep::Wait
    );
    let done = obs!(
        r,
        "certified 6 has synthetic durable bucket receipt",
        finish_recovery(&recovering, certify(4, 6))
    )
    .unwrap();
    assert_eq!((done.epoch, done.tiered), (1, 6));
    assert_eq!(takeover_gate(Some(&done)), TakeoverGate::BucketComplete);
    r.done();
}

#[test]
fn j005_partial_append_recovery_preserves_confirmed_prefix_and_optional_tail() {
    let mut r = Receipt::new("J005");
    let rec = record(&["a", "b"], 4);
    let mut a = FollowerLog::join(1, 4);
    let mut b = FollowerLog::join(1, 4);
    assert!(obs!(r, "a receives row 5", a.accept_append(1, 5)));
    assert!(obs!(r, "b receives row 5", b.accept_append(1, 5)));
    let mut ends = BTreeMap::from([("a".into(), 5), ("b".into(), 5)]);
    assert!(obs!(
        r,
        "row 5 is acknowledged",
        ack_fleet_allowed(&view(&rec), &ends, 5)
    ));
    assert!(obs!(r, "only a receives row 6", a.accept_append(1, 6)));
    ends.insert("a".into(), 6);
    assert!(!obs!(
        r,
        "row 6 lacks write-all proof",
        ack_fleet_allowed(&view(&rec), &ends, 6)
    ));
    let recovering = start_recovery(&rec, "r", 100).unwrap();
    let cut_a = obs!(r, "seal longer member", a.seal(recovering.epoch));
    let cut_b = obs!(r, "seal shorter member", b.seal(recovering.epoch));
    assert_eq!(
        (certify(rec.tiered, cut_a), certify(rec.tiered, cut_b)),
        (6, 5)
    );
    assert!(!obs!(
        r,
        "delayed row 6 cannot append to sealed b",
        b.accept_append(1, 6)
    ));
    let done = finish_recovery(&recovering, certify(rec.tiered, cut_a)).unwrap();
    assert!(done.tiered >= 5); // An unacknowledged row's survival is allowed.
    assert_eq!(done.tiered, 6);
    r.done();
}

#[test]
fn j006_recovery_heartbeat_survives_partial_upload_then_stale_claim_changes() {
    let mut r = Receipt::new("J006");
    let old = record(&["a"], 4);
    let claim = obs!(r, "first claimant", start_recovery(&old, "first", 100)).unwrap();
    let refreshed = obs!(
        r,
        "partial upload still working heartbeat",
        refresh_recovery(&claim, "first", 140)
    )
    .unwrap();
    assert!(obs!(
        r,
        "contender blocked while heartbeat fresh",
        take_over_recovery(&refreshed, "second", 180, 50)
    )
    .is_none());
    assert_eq!(takeover_gate(Some(&refreshed)), TakeoverGate::RecoverFirst);
    let successor = obs!(
        r,
        "stale claim taken at boundary",
        take_over_recovery(&refreshed, "second", 190, 50)
    )
    .unwrap();
    assert!(obs!(
        r,
        "old claimant cannot refresh successor record",
        refresh_recovery(&successor, "first", 191)
    )
    .is_none());
    assert_eq!(successor.tiered, 4);
    assert_eq!(takeover_gate(Some(&successor)), TakeoverGate::RecoverFirst);
    let done = obs!(
        r,
        "remaining tail through 8 durable then seal",
        finish_recovery(&successor, certify(4, 8))
    )
    .unwrap();
    assert_eq!(done.tiered, 8);
    assert_eq!(done.claimant, None);
    assert_eq!(takeover_gate(Some(&done)), TakeoverGate::BucketComplete);
    r.done();
}

#[test]
fn j007_zombie_bundle_put_after_seal_is_uncredited_and_retained_until_covered() {
    let mut r = Receipt::new("J007");
    let old = record(&["a"], 2);
    assert!(obs!(
        r,
        "PUT starts under open epoch",
        bundle_credit_allowed(Some(&old), 1)
    ));
    let recovering = obs!(r, "rival recovers epoch", start_recovery(&old, "r", 100)).unwrap();
    let done = obs!(
        r,
        "recovered rows through 4 persisted per-cell",
        finish_recovery(&recovering, 4)
    )
    .unwrap();
    assert!(!obs!(
        r,
        "late unconditional PUT containing row 5 cannot credit",
        bundle_credit_allowed(Some(&done), 1)
    ));
    assert!(!obs!(
        r,
        "bundle still has uncovered row 5",
        bundle_deletable([(4, 4), (5, 4)])
    ));
    assert_eq!(takeover_gate(Some(&done)), TakeoverGate::BucketComplete);
    assert!(obs!(
        r,
        "explicit later per-cell coverage makes object garbage",
        bundle_deletable([(4, 5), (5, 5)])
    ));
    assert_eq!(done.tiered, 4); // Late object does not mutate the sealed cut.
    r.done();
}

#[test]
fn j008_bundle_coverage_cannot_stand_in_for_per_cell_graceful_close() {
    let mut r = Receipt::new("J008");
    let rec = record(&["a", "b"], 3);
    assert!(obs!(
        r,
        "bundle PUT may credit current open epoch",
        bundle_credit_allowed(Some(&rec), 1)
    ));
    assert!(!obs!(
        r,
        "credited bundle still has no per-cell cover",
        bundle_deletable([(4, 3), (5, 3)])
    ));
    assert!(!obs!(
        r,
        "no captured batch but bundle-only tail",
        graceful_seal_allowed(&rec, 1, false, false)
    ));
    assert_eq!(takeover_gate(Some(&rec)), TakeoverGate::RecoverFirst);
    assert!(!obs!(
        r,
        "per-cell coverage lands while another batch captured",
        graceful_seal_allowed(&rec, 1, true, true)
    ));
    assert!(obs!(
        r,
        "capture completes and per-cell tail is whole",
        graceful_seal_allowed(&rec, 1, false, true)
    ));
    assert!(obs!(
        r,
        "old bundle all covered",
        bundle_deletable([(4, 5), (5, 5)])
    ));
    r.done();
}

#[test]
fn j009_reopened_log_needs_fresh_write_all_proof_and_clears_old_ledger() {
    let mut r = Receipt::new("J009");
    let old = record(&["a", "b"], 9);
    let recovering = start_recovery(&old, "r", 10).unwrap();
    let sealed = obs!(
        r,
        "old session recovered through 12",
        finish_recovery(&recovering, 12)
    )
    .unwrap();
    assert_eq!(
        obs!(
            r,
            "own record may reopen next epoch",
            maintain_step(Some(&sealed))
        ),
        MaintainStep::Reopen(2)
    );
    let mut ledger = ShipLedger::default();
    ledger.observe_epoch(1);
    ledger.shipped(12, ());
    ledger.advance(|_| true);
    obs!(
        r,
        "synthetic epoch-2 reopen resets stream",
        ledger.observe_epoch(2)
    );
    assert_eq!(ledger.covered_seq(), 0);
    let new_view = LeaderView {
        epoch: 2,
        ensemble: members(&["a", "c"]),
    };
    let mut confirmations = BTreeMap::from([("a".into(), 1)]);
    assert!(!obs!(
        r,
        "missing c confirmation is no proof",
        ack_fleet_allowed(&new_view, &confirmations, 1)
    ));
    confirmations.insert("c".into(), 1);
    assert!(obs!(
        r,
        "fresh member confirms",
        ack_fleet_allowed(&new_view, &confirmations, 1)
    ));
    assert!(!obs!(
        r,
        "old shipper still cannot credit sealed epoch",
        bundle_credit_allowed(Some(&sealed), 1)
    ));
    assert!(fragment_closed(&sealed, 1));
    r.done();
}

#[test]
fn j010_bucket_floor_survives_short_follower_and_delayed_old_append() {
    let mut r = Receipt::new("J010");
    let rec = record(&["a", "b"], 10);
    // Follower's retained fragment predates bucket progress; it is not a new join.
    let mut lag = FollowerLog::join(1, 6);
    assert!(obs!(r, "older retained row 7", lag.accept_append(1, 7)));
    let claim = obs!(
        r,
        "recovery takes current record",
        start_recovery(&rec, "r", 100)
    )
    .unwrap();
    let end = obs!(r, "seal short retained member", lag.seal(1));
    assert_eq!(end, 7);
    assert_eq!(
        obs!(
            r,
            "bucket cut floors shorter seal",
            certify(rec.tiered, end)
        ),
        10
    );
    assert!(!obs!(
        r,
        "late frame refused after seal",
        lag.accept_append(1, 8)
    ));
    let done = finish_recovery(&claim, certify(rec.tiered, end)).unwrap();
    assert_eq!(done.tiered, 10);
    assert_eq!(takeover_gate(Some(&done)), TakeoverGate::BucketComplete);
    r.done();
}

#[test]
fn j011_checkpoint_promotion_cannot_collect_objects_still_pinned_by_fill() {
    let mut r = Receipt::new("J011");
    let objects = listed(&[(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
    assert!(obs!(
        r,
        "new checkpoint base 4 while old fill reads base 1",
        epoch_gc::plan(6, &[4, 6], &objects, None, true, 100, 10)
    )
    .is_none());
    assert!(!obs!(
        r,
        "no retirement proof for old log row",
        epoch_gc::retired(2, None)
    ));
    assert!(!obs!(
        r,
        "uncovered old bundle kept during fill",
        bundle_deletable([(9, 0)])
    ));
    let ready = obs!(
        r,
        "positive fill completion unpins",
        epoch_gc::plan(6, &[4, 6], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert_eq!((ready.retired_below, ready.record), (4, true));
    assert_eq!(ready.delete, vec![1, 2, 3]);
    assert!(obs!(
        r,
        "persisted retired mark covers old row",
        epoch_gc::retired(2, Some(4))
    ));
    assert!(!epoch_gc::retired(4, Some(4)));
    r.done();
}

#[test]
fn j012_missing_own_checkpoint_opener_blocks_gc_until_listing_catches_up() {
    let mut r = Receipt::new("J012");
    let objects = listed(&[(1, 1), (2, 1), (3, 1)]);
    assert!(obs!(
        r,
        "own epoch 5 not in restore chain yet",
        epoch_gc::plan(5, &[1, 3], &objects, None, false, 100, 10)
    )
    .is_none());
    assert!(!obs!(
        r,
        "unrecorded epoch cannot cover bundle",
        epoch_gc::retired(1, None)
    ));
    let repaired = obs!(
        r,
        "durable own opener now listed",
        epoch_gc::plan(5, &[3, 5], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert_eq!(repaired.delete, vec![1, 2]);
    assert_eq!(repaired.retired_below, 3);
    let repeated = obs!(
        r,
        "mark persisted; repeat does not rewrite it",
        epoch_gc::plan(5, &[3, 5], &objects, Some(3), false, 101, 10)
    )
    .unwrap();
    assert!(!repeated.record);
    assert_eq!(repeated.delete, vec![1, 2]);
    assert!(!epoch_gc::retired(3, Some(3)));
    r.done();
}

#[test]
fn j013_stale_lower_restore_chain_cannot_regress_retirement_proof() {
    let mut r = Receipt::new("J013");
    let objects = listed(&[(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
    assert!(obs!(
        r,
        "stored mark 5 disagrees with stale base 3",
        epoch_gc::plan(7, &[3, 7], &objects, Some(5), false, 100, 10)
    )
    .is_none());
    assert!(obs!(
        r,
        "existing proof still retires epoch 4",
        epoch_gc::retired(4, Some(5))
    ));
    let fresh = obs!(
        r,
        "consistent relisting restores base 5",
        epoch_gc::plan(7, &[5, 7], &objects, Some(5), false, 101, 10)
    )
    .unwrap();
    assert!(!fresh.record);
    assert_eq!(fresh.delete, vec![1, 2, 3, 4]);
    assert!(!obs!(
        r,
        "base epoch stays live",
        epoch_gc::retired(5, Some(5))
    ));
    r.done();
}

#[test]
fn j014_late_old_epoch_upload_restarts_grace_without_deleting_current_base() {
    let mut r = Receipt::new("J014");
    let objects = listed(&[(1, 1), (2, 95), (3, 1), (4, 1), (5, 1), (6, 1)]);
    let first = obs!(
        r,
        "late fenced upload refreshed epoch 2 time",
        epoch_gc::plan(6, &[4, 6], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert_eq!(first.delete, vec![1, 3]);
    assert_eq!(first.retired_below, 4);
    assert!(obs!(
        r,
        "retirement already covers recent old epoch",
        epoch_gc::retired(2, Some(4))
    ));
    let survivors = listed(&[(2, 95), (4, 1), (5, 1), (6, 1)]);
    let second = obs!(
        r,
        "retry after late object grace",
        epoch_gc::plan(6, &[4, 6], &survivors, Some(4), false, 105, 10)
    )
    .unwrap();
    assert_eq!(second.delete, vec![2]);
    assert!(!second.record);
    assert!(!obs!(
        r,
        "checkpoint base not retired",
        epoch_gc::retired(4, Some(4))
    ));
    r.done();
}

#[test]
fn j015_partial_prefix_delete_retries_remaining_victims_under_same_mark() {
    let mut r = Receipt::new("J015");
    let initial = listed(&[(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
    let first = obs!(
        r,
        "plan before any delete",
        epoch_gc::plan(6, &[4, 6], &initial, None, false, 100, 10)
    )
    .unwrap();
    assert!(first.record);
    assert_eq!(first.delete, vec![1, 2, 3]);
    obs!(
        r,
        "synthetic receipts: mark 4 persisted; delete 1 succeeds; delete 2 fails",
        (Some(4_u64), vec![2_u64, 3, 4, 5, 6])
    );
    let remaining = listed(&[(2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
    let retry = obs!(
        r,
        "retry uses surviving listing and durable mark",
        epoch_gc::plan(6, &[4, 6], &remaining, Some(4), false, 101, 10)
    )
    .unwrap();
    assert!(!retry.record);
    assert_eq!(retry.delete, vec![2, 3]);
    let final_listing = listed(&[(4, 1), (5, 1), (6, 1)]);
    let settled = obs!(
        r,
        "both remaining deletes succeeded",
        epoch_gc::plan(6, &[4, 6], &final_listing, Some(4), false, 102, 10)
    )
    .unwrap();
    assert!(settled.delete.is_empty());
    assert_eq!(
        final_listing.iter().map(|e| e.epoch).collect::<Vec<_>>(),
        vec![4, 5, 6]
    );
    r.done();
}

#[test]
fn j016_failed_retirement_write_requires_same_proof_before_delete_retry() {
    let mut r = Receipt::new("J016");
    let objects = listed(&[(1, 1), (2, 1), (3, 1), (4, 1)]);
    let first = obs!(
        r,
        "new base 3 needs recorded mark",
        epoch_gc::plan(5, &[3, 5], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert!(first.record);
    assert_eq!(first.delete, vec![1, 2]);
    obs!(
        r,
        "synthetic retirement PUT failure keeps all objects",
        objects.clone()
    );
    let retry = obs!(
        r,
        "retry without durable mark repeats prerequisite",
        epoch_gc::plan(5, &[3, 5], &objects, None, false, 101, 10)
    )
    .unwrap();
    assert_eq!(retry, first);
    assert!(!obs!(
        r,
        "failed mark is not coverage",
        epoch_gc::retired(2, None)
    ));
    let committed = obs!(
        r,
        "successful mark readback changes plan",
        epoch_gc::plan(5, &[3, 5], &objects, Some(3), false, 102, 10)
    )
    .unwrap();
    assert!(!committed.record);
    assert_eq!(committed.delete, vec![1, 2]);
    assert!(epoch_gc::retired(2, Some(3)));
    assert!(!epoch_gc::retired(3, Some(3)));
    r.done();
}

#[test]
fn j017_off_chain_late_snapshot_does_not_replace_restore_selected_base() {
    let mut r = Receipt::new("J017");
    // Epoch 5 has a late TXID-1 snapshot which the real restore walk excluded.
    // Its TXID interval is an explicit supplied-chain premise, not reimplemented here.
    let objects = listed(&[(1, 1), (2, 1), (3, 1), (4, 1), (5, 90), (6, 1)]);
    let plan = obs!(
        r,
        "restore-selected chain remains 3 to 7",
        epoch_gc::plan(7, &[3, 7], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert_eq!(plan.retired_below, 3);
    assert_eq!(plan.delete, vec![1, 2]);
    assert!(!obs!(
        r,
        "listed late epoch 5 is not retired by base 3",
        epoch_gc::retired(5, Some(3))
    ));
    assert!(!obs!(
        r,
        "chain base 3 remains needed",
        epoch_gc::retired(3, Some(3))
    ));
    let again = obs!(
        r,
        "aging excluded snapshot does not promote it",
        epoch_gc::plan(7, &[3, 7], &objects, Some(3), false, 200, 10)
    )
    .unwrap();
    assert_eq!(again.delete, vec![1, 2]);
    assert_eq!(again.retired_below, 3);
    r.done();
}

#[test]
fn j018_successor_checkpoint_releases_predecessor_margin_from_prior_pass() {
    let mut r = Receipt::new("J018");
    let objects = listed(&[(3, 1), (4, 1), (5, 1), (6, 1)]);
    let first = obs!(
        r,
        "own full checkpoint epoch 6",
        epoch_gc::plan(6, &[6], &objects, None, false, 100, 10)
    )
    .unwrap();
    assert_eq!(first.delete, vec![3, 4]);
    assert_eq!(first.retired_below, 6);
    assert!(obs!(
        r,
        "epoch 5 retired but predecessor retained by margin",
        epoch_gc::retired(5, Some(6))
    ));
    let survivors = listed(&[(5, 1), (6, 1), (7, 105)]);
    let before_opener = obs!(
        r,
        "new owner not listed in chain cannot collect",
        epoch_gc::plan(7, &[6], &survivors, Some(6), false, 110, 10)
    );
    assert!(before_opener.is_none());
    let successor = obs!(
        r,
        "new own checkpoint durable and in chain",
        epoch_gc::plan(7, &[7], &survivors, Some(6), false, 120, 10)
    )
    .unwrap();
    assert_eq!(successor.delete, vec![5]);
    assert_eq!(successor.retired_below, 7);
    assert!(successor.record);
    r.done();
}

#[test]
fn j019_retired_epoch_rows_do_not_cover_current_epoch_tail_in_same_bundle() {
    let mut r = Receipt::new("J019");
    let old_retired = obs!(
        r,
        "stream checkpoint mark 4 retires epoch 2",
        epoch_gc::retired(2, Some(4))
    );
    assert!(old_retired);
    assert!(!obs!(
        r,
        "same mark does not retire current epoch 4",
        epoch_gc::retired(4, Some(4))
    ));
    // u64::MAX models the executor's coverage credit for an actually retired epoch.
    assert!(!obs!(
        r,
        "bundle mixes old epoch row 90 and live row 3",
        bundle_deletable([(90, u64::MAX), (3, 2)])
    ));
    let mut ledger = ShipLedger::default();
    ledger.observe_epoch(8);
    obs!(
        r,
        "mixed bundle ships through sequence 20",
        ledger.shipped(20, [(90, u64::MAX), (3, 2)])
    );
    ledger.advance(|rows| bundle_deletable(*rows));
    assert_eq!(ledger.covered_seq(), 0);
    // The immutable batch identifies row TXIDs; mutable facts arrive separately.
    obs!(
        r,
        "current-epoch row 3 per-cell upload now proven",
        ledger.advance(|_| bundle_deletable([(90, u64::MAX), (3, 3)]))
    );
    assert_eq!(ledger.covered_seq(), 20);
    assert!(bundle_deletable([(90, u64::MAX), (3, 3)]));
    r.done();
}

#[test]
fn j020_gray_follower_heals_and_rejoins_while_swap_rate_cap_persists() {
    let mut r = Receipt::new("J020");
    let p = policy();
    let mut h = FollowerHealth::default();
    let siblings = vec!["a".into(), "b".into()];
    obs!(
        r,
        "a first slow completion",
        h.append_completed("a", 110, 80)
    );
    obs!(
        r,
        "a second slow completion",
        h.append_completed("a", 111, 80)
    );
    obs!(
        r,
        "a third slow completion",
        h.append_completed("a", 112, 80)
    );
    obs!(
        r,
        "b healthy sibling sample",
        h.append_completed("b", 112, 5)
    );
    assert_eq!(
        obs!(r, "a becomes suspect", h.verdict(&p, "a", &siblings, 112)),
        Verdict::Suspect
    );
    assert_eq!(
        obs!(
            r,
            "sustained tail evicts",
            h.verdict(&p, "a", &siblings, 132)
        ),
        Verdict::Evict
    );
    obs!(
        r,
        "executor confirms covered swap occurred",
        h.evicted(&p, "a", 132)
    );
    assert!(!h.quarantined("a", 133));
    assert!(!h.swap_allowed(&p, 133));
    obs!(r, "fresh ensemble reset preserves rate cap", h.reset());
    assert!(!h.swap_allowed(&p, 181));
    assert!(h.swap_allowed(&p, 182));
    obs!(
        r,
        "healed re-recruited a completes quickly",
        h.append_completed("a", 187, 4)
    );
    assert_eq!(h.verdict(&p, "a", &siblings, 187), Verdict::Healthy);
    let rec = record(&["a", "b"], 0);
    assert!(obs!(
        r,
        "both fresh followers prove row 1",
        ack_fleet_allowed(
            &view(&rec),
            &BTreeMap::from([("a".into(), 1), ("b".into(), 1)]),
            1
        )
    ));
    r.done();
}

#[test]
fn j021_correlated_partition_recovers_without_excluding_all_peers() {
    let mut r = Receipt::new("J021");
    let p = policy();
    let mut h = FollowerHealth::default();
    let peers = vec!["a".into(), "b".into()];
    obs!(r, "a append outstanding", h.append_started("a", 10));
    obs!(r, "b append outstanding", h.append_started("b", 15));
    assert!(!obs!(
        r,
        "only a has hit backstop",
        h.correlated_stall(&p, &peers, 110)
    ));
    assert!(obs!(
        r,
        "both hit backstop",
        h.correlated_stall(&p, &peers, 115)
    ));
    assert!(!may_reconfigure(false, false));
    assert!(obs!(
        r,
        "bucket recovery now covers old tail",
        may_reconfigure(false, true)
    ));
    obs!(
        r,
        "executor parks ensemble without incapability verdict",
        h.reset()
    );
    assert!(!h.quarantined("a", 116) && !h.quarantined("b", 116));
    assert!(!h.correlated_stall(&p, &peers, 116));
    obs!(
        r,
        "connectivity healed: fresh a append",
        h.append_started("a", 117)
    );
    obs!(
        r,
        "connectivity healed: fresh a completion",
        h.append_completed("a", 118, 1)
    );
    obs!(
        r,
        "connectivity healed: fresh b completion",
        h.append_completed("b", 119, 2)
    );
    assert_eq!(h.verdict(&p, "a", &peers, 119), Verdict::Healthy);
    assert_eq!(h.verdict(&p, "b", &peers, 119), Verdict::Healthy);
    r.done();
}

#[test]
fn j022_characterize_delayed_health_completion_after_ensemble_reset() {
    let mut r = Receipt::new("J022");
    let p = policy();
    let mut h = FollowerHealth::default();
    obs!(r, "old ensemble append starts", h.append_started("a", 0));
    obs!(r, "new ensemble resets tracker", h.reset());
    assert_eq!(
        obs!(r, "empty window hedge floor", h.hedge_deadline_ms(&p, 20)),
        10
    );
    obs!(
        r,
        "uncorrelated old completion arrives at name-only API",
        h.append_completed("a", 30, 30)
    );
    assert_eq!(
        obs!(
            r,
            "current API incorporates delayed sample",
            h.hedge_deadline_ms(&p, 30)
        ),
        60
    );
    assert!(!h.probe_due("a", 31, 10));
    assert_eq!(
        h.verdict(&p, "a", &["a".into(), "b".into()], 31),
        Verdict::Healthy
    );
    assert_eq!(
        obs!(
            r,
            "aged sample leaves bounded window",
            h.hedge_deadline_ms(&p, 131)
        ),
        10
    );
    assert!(h.probe_due("a", 131, 10));
    // Characterization only: executor cancellation/generation filtering is untested.
    r.done();
}

#[test]
fn j023_same_cell_tickets_split_inflight_stall_from_queued_node_progress() {
    let mut r = Receipt::new("J023");
    let older = ProofWait {
        started_ms: 100,
        ticket: 10,
        budget_ms: 20,
    };
    let newer = ProofWait {
        started_ms: 105,
        ticket: 11,
        budget_ms: 20,
    };
    let queued = ProofProgress {
        node_proof_ms: 110,
        capture_seq: 9,
        capture_started_ms: 90,
    };
    assert_eq!(
        obs!(
            r,
            "older still behind lower capture",
            proof_deadline(&older, &queued)
        ),
        130
    );
    assert_eq!(
        obs!(
            r,
            "newer same queued progress",
            proof_deadline(&newer, &queued)
        ),
        130
    );
    let partial = ProofProgress {
        node_proof_ms: 140,
        capture_seq: 10,
        capture_started_ms: 115,
    };
    assert_eq!(
        obs!(
            r,
            "older capture fixes own deadline despite other proofs",
            proof_deadline(&older, &partial)
        ),
        135
    );
    assert_eq!(
        obs!(
            r,
            "newer uncaptured ticket extends on other proofs",
            proof_deadline(&newer, &partial)
        ),
        160
    );
    let more_elsewhere = ProofProgress {
        node_proof_ms: 155,
        ..partial
    };
    assert_eq!(proof_deadline(&older, &more_elsewhere), 135);
    assert_eq!(proof_deadline(&newer, &more_elsewhere), 175);
    let next_capture = ProofProgress {
        node_proof_ms: 155,
        capture_seq: 11,
        capture_started_ms: 160,
    };
    assert_eq!(
        obs!(
            r,
            "newer begins own fixed upload budget",
            proof_deadline(&newer, &next_capture)
        ),
        180
    );
    r.done();
}

#[test]
fn j024_sustained_progress_caps_queued_wait_then_fresh_retry_gets_own_budget() {
    let mut r = Receipt::new("J024");
    let wait = ProofWait {
        started_ms: 100,
        ticket: 12,
        budget_ms: 20,
    };
    let early = ProofProgress {
        node_proof_ms: 150,
        capture_seq: 11,
        capture_started_ms: 130,
    };
    assert_eq!(
        obs!(r, "other cells land proofs", proof_deadline(&wait, &early)),
        170
    );
    let loaded = ProofProgress {
        node_proof_ms: 210,
        ..early
    };
    assert_eq!(
        obs!(
            r,
            "queued total limit wins over recent progress",
            proof_deadline(&wait, &loaded)
        ),
        220
    );
    let later = ProofProgress {
        node_proof_ms: 500,
        ..early
    };
    assert_eq!(
        obs!(
            r,
            "continued proofs do not extend abandoned queued wait",
            proof_deadline(&wait, &later)
        ),
        220
    );
    assert!(!obs!(
        r,
        "timeout itself grants no bundle coverage",
        bundle_deletable([(12, 11)])
    ));
    let retry = ProofWait {
        started_ms: 501,
        ticket: 12,
        budget_ms: 20,
    };
    let captured = ProofProgress {
        node_proof_ms: 500,
        capture_seq: 12,
        capture_started_ms: 505,
    };
    assert_eq!(
        obs!(
            r,
            "new client attempt waits on covering capture",
            proof_deadline(&retry, &captured)
        ),
        525
    );
    assert!(obs!(
        r,
        "explicit persisted row receipt permits collection",
        bundle_deletable([(12, 12)])
    ));
    // No assertion that a timeout cancels a write, forbids late success, or undoes it.
    r.done();
}
