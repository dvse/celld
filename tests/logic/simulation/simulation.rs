// Appended to the preserved lease-continuity fixture at build time.
// Every event advances real State. No wall-clock sleeps or runtime mocking.
fn next(seed:&mut u64)->u64 { *seed^=*seed<<13;*seed^=*seed>>7;*seed^=*seed<<17;*seed }
fn seeded_lease()->Option<(u64,String)> {
 let n=std::env::var("CELLD_SIM_SEEDS").ok().and_then(|s|s.parse().ok()).unwrap_or(64);
 for seed in 1..=n {
  let mut rng=seed;let mut s=intermediate_reading();
  // CAS applied but its reply was lost, a subsequent CAS raced it, and the
  // store read arrives either side of the old wall/monotonic lease boundary.
  let wall=if next(&mut rng)%3==0 {30_000+next(&mut rng)%2000}else{28_000+next(&mut rng)%2000};
  let mono=if next(&mut rng)%3==0 {30_000+next(&mut rng)%2000}else{28_000+next(&mut rng)%2000};
  let expired=wall>=30_000||mono>=30_000;
  let timer_first=expired && next(&mut rng)%2==0;
  if timer_first {fire(&mut s.first.held.state,s.first.held.fence.clone(),wall,mono);}
  let choose=next(&mut rng)%5;
  let reply=match choose {0=>Err(Failure::Definite),1=>Ok(None),2=>Ok(Some(s.first.held.prior.clone())),3=>{let mut other=s.first.desired.clone();other.generation="racing-owner".into();Ok(Some(other))},_=>Ok(Some(s.first.desired.clone()))};
  read(&mut s.first.held.state,s.read_op,wall,mono,reply);
  s.first.held.state.validate().unwrap();
  let observed=s.first.held.state.node_authoritative();
  if expired&&observed{return Some((seed,format!("expired lease returned: wall={wall} mono={mono} timer_first={timer_first} reply={choose}")));}
  // Crash destroys process memory. Late completions for the old process
  // cannot give a fresh State authority without its own lease acquisition.
  let mut restarted=State::new("crashed-node-new-session",config());
  complete(&mut restarted,s.first.cas_op,mono,Ok(LeaseCasOutcome::Applied{etag:"late-old-process".into()}));
  assert!(!restarted.node_authoritative(),"seed {seed}: crash resurrected authority");
  restarted.validate().unwrap();
  // Quiescence must settle a surviving, non-fenced node into a terminal fence.
  fire(&mut s.first.held.state,s.first.held.fence.clone(),60_000,60_000);
  assert!(!s.first.held.state.node_authoritative(),"seed {seed}: quiescent expired node remains a writer");
 }
 println!("seeds={n} store=CAS-race,lost-reply,stale-read clocks=independent-wall-monotonic crash=late-completion");None
}
#[test] fn sim_seeded_lease_store_clock_crash(){if let Some((seed,why))=seeded_lease(){panic!("seed={seed} {why}")}}
