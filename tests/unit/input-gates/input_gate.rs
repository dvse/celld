use celld_logic::gate::InputGate;
#[test] fn independent_event_waits_for_outermost_hold(){let mut g=InputGate::new();assert!(g.acquire(1));assert!(g.acquire(1));assert!(!g.acquire(2));assert!(!g.release(1));assert!(!g.is_open());assert!(g.release(1));assert!(g.acquire(2));}
#[test] fn foreign_release_cannot_open_gate(){let mut g=InputGate::new();assert!(g.acquire(1));assert!(!g.release(2));assert!(!g.is_open());}
#[test] fn stale_release_cannot_release_new_holder(){let mut g=InputGate::new();assert!(g.acquire(1));g.abandon(1);assert!(g.acquire(2));assert!(!g.release(1));assert!(!g.is_open());assert!(g.release(2));}
#[test] fn empty_gate_is_open(){let g=InputGate::new();assert!(g.is_open());}
