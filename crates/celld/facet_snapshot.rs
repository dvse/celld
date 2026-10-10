// Copyright 2026 Deno Land Inc. Apache-2.0 license.
//! A root's facet mutations, including images captured before clone() returns.
//!
//! Native SQLite operations share the root's read lock. Snapshot capture takes
//! the write lock, so already-running descendant continuations cannot change
//! any stream during the cut. Pending mutations form a logical tree overlay:
//! clone(a,b); clone(b,c) observes the first snapshot even before its async
//! close/persist work has run. The same mutation owns a root output proof.
#![allow(clippy::disallowed_methods, clippy::disallowed_types)]
use std::collections::{BTreeMap, HashMap};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicU8, Ordering};
use std::sync::{Arc, Mutex, OnceLock, Weak};
use tokio::sync::{watch, OwnedRwLockReadGuard, OwnedRwLockWriteGuard, RwLock};

type Key = (String, u64);
static ROOTS: OnceLock<Mutex<HashMap<Key, Weak<Root>>>> = OnceLock::new();
static NEXT: AtomicU64 = AtomicU64::new(1);
thread_local! {
    // SQLite helpers can nest. Reuse this thread's read owner even when a
    // snapshot writer has queued, avoiding recursive-read writer starvation.
    static READERS: std::cell::RefCell<HashMap<usize, Weak<OwnedRwLockReadGuard<()>>>> = Default::default();
}
#[derive(Default)]
pub(crate) struct Root {
    lock: Arc<RwLock<()>>,
    mutations: Mutex<Vec<Arc<Mutation>>>,
    closing: AtomicBool,
}
pub(crate) fn root(name: &str, epoch: u64) -> Arc<Root> {
    let mut roots = ROOTS.get_or_init(Default::default).lock().unwrap();
    roots.retain(|_, root| root.strong_count() > 0);
    roots
        .entry((name.to_string(), epoch))
        .or_default()
        .upgrade()
        .unwrap_or_else(|| {
            let root = Arc::new(Root::default());
            roots.insert((name.to_string(), epoch), Arc::downgrade(&root));
            root
        })
}
fn wait<T>(f: impl std::future::Future<Output = T>) -> T {
    // Snapshot work uses the host runtime, never the V8 lock. Yield the Tokio
    // worker while synchronous JS waits, so even a one-worker node progresses.
    tokio::task::block_in_place(|| tokio::runtime::Handle::current().block_on(f))
}
impl Root {
    pub(crate) fn enter(
        self: &Arc<Self>,
        _name: &str,
        _epoch: u64,
    ) -> Arc<OwnedRwLockReadGuard<()>> {
        let key = Arc::as_ptr(self) as usize;
        READERS.with(|readers| {
            let mut readers = readers.borrow_mut();
            if let Some(reader) = readers.get(&key).and_then(Weak::upgrade) {
                return reader;
            }
            let reader = Arc::new(
                self.lock
                    .clone()
                    .try_read_owned()
                    .unwrap_or_else(|_| wait(self.lock.clone().read_owned())),
            );
            readers.retain(|_, reader| reader.strong_count() > 0);
            readers.insert(key, Arc::downgrade(&reader));
            reader
        })
    }
    pub(crate) fn freeze(self: &Arc<Self>) -> OwnedRwLockWriteGuard<()> {
        self.lock
            .clone()
            .try_write_owned()
            .unwrap_or_else(|_| wait(self.lock.clone().write_owned()))
    }
    pub(crate) fn is_closing(&self) -> bool {
        self.closing.load(Ordering::Acquire)
    }
    pub(crate) fn abandon(&self, origin: Option<&str>) {
        let pending = self.mutations.lock().unwrap().clone();
        for mutation in pending {
            if origin.is_none() || mutation.origin.lock().unwrap().as_deref() == origin {
                if mutation
                    .status
                    .compare_exchange(0, 2, Ordering::AcqRel, Ordering::Acquire)
                    .is_ok()
                {
                    self.finish(
                        &mutation,
                        Err("facet mutation's originating actor stopped before persistence".into()),
                    );
                }
            }
        }
    }
    pub(crate) fn stopping(&self) {
        self.closing.store(true, Ordering::Release);
        self.abandon(None);
    }
    pub(crate) async fn stopped(self: &Arc<Self>) -> OwnedRwLockWriteGuard<()> {
        self.lock.clone().write_owned().await
    }
    pub(crate) async fn changing(self: &Arc<Self>) -> OwnedRwLockReadGuard<()> {
        self.lock.clone().read_owned().await
    }
    pub(crate) fn overlay(&self, source: &str, mut image: Image) -> Image {
        for mutation in self.mutations.lock().unwrap().iter() {
            let destination = &mutation.destination;
            if destination == source || destination.starts_with(&format!("{source}/")) {
                let at = &destination[source.len()..];
                image.retain(|suffix, _| suffix != at && !suffix.starts_with(&format!("{at}/")));
                for (suffix, db) in &mutation.image {
                    image.insert(format!("{at}{suffix}"), db.clone());
                }
            } else if source.starts_with(&format!("{destination}/")) {
                image.clear();
                let at = &source[destination.len()..];
                for (suffix, db) in &mutation.image {
                    if suffix == at || suffix.starts_with(&format!("{at}/")) {
                        image.insert(suffix[at.len()..].to_string(), db.clone());
                    }
                }
            }
        }
        image
    }
    pub(crate) fn covered(&self, source: &str) -> bool {
        self.mutations
            .lock()
            .unwrap()
            .iter()
            .any(|m| source == m.destination || source.starts_with(&format!("{}/", m.destination)))
    }
    pub(crate) fn add(
        &self,
        root: String,
        epoch: u64,
        destination: String,
        names: Vec<String>,
        image: Image,
    ) -> Arc<Mutation> {
        let previous = self.proofs();
        let (settle, done) = watch::channel(None);
        let mutation = Arc::new(Mutation {
            id: NEXT.fetch_add(1, Ordering::Relaxed),
            root,
            epoch,
            destination,
            names,
            image,
            previous,
            settle,
            done,
            origin: Mutex::new(None),
            status: AtomicU8::new(0),
        });
        self.mutations.lock().unwrap().push(mutation.clone());
        mutation
    }
    pub(crate) fn get(&self, id: u64) -> Option<Arc<Mutation>> {
        self.mutations
            .lock()
            .unwrap()
            .iter()
            .find(|m| m.id == id)
            .cloned()
    }
    pub(crate) fn finish(&self, mutation: &Mutation, result: Result<(), String>) {
        mutation.status.store(2, Ordering::Release);
        let succeeded = result.is_ok();
        mutation.settle.send_replace(Some(result));
        // A failed mutation poisons subsequent root outputs until incarnation
        // teardown. Successful copies now have their physical representation.
        if succeeded {
            self.mutations
                .lock()
                .unwrap()
                .retain(|m| m.id != mutation.id);
        }
    }
    pub(crate) fn proofs(&self) -> Proofs {
        self.mutations
            .lock()
            .unwrap()
            .iter()
            .map(|m| m.done.clone())
            .collect()
    }
}
#[derive(Clone)]
pub(crate) struct Database {
    pub path: PathBuf,
    pub directory: Arc<tempfile::TempDir>,
}
pub(crate) type Image = BTreeMap<String, Database>;
pub struct Mutation {
    pub(crate) id: u64,
    pub(crate) root: String,
    pub(crate) epoch: u64,
    pub(crate) destination: String,
    pub(crate) names: Vec<String>,
    pub(crate) image: Image,
    pub(crate) previous: Proofs,
    pub(crate) origin: Mutex<Option<String>>,
    status: AtomicU8,
    settle: watch::Sender<Option<Result<(), String>>>,
    done: watch::Receiver<Option<Result<(), String>>>,
}
impl Mutation {
    pub(crate) fn claim(&self) -> bool {
        self.status
            .compare_exchange(0, 1, Ordering::AcqRel, Ordering::Acquire)
            .is_ok()
    }
}
pub(crate) type Proofs = Vec<watch::Receiver<Option<Result<(), String>>>>;
pub(crate) async fn prove(proofs: Proofs) -> Result<(), String> {
    for mut proof in proofs {
        loop {
            if let Some(result) = proof.borrow().clone() {
                result?;
                break;
            }
            proof
                .changed()
                .await
                .map_err(|_| "facet mutation was abandoned".to_string())?;
        }
    }
    Ok(())
}
pub(crate) fn proof_gate(proofs: Proofs) -> Option<crate::wake_entry::ArmGateRx> {
    if proofs.is_empty() {
        return None;
    }
    let (send, receive) = tokio::sync::oneshot::channel();
    crate::asyncrt::op_handle().spawn(async move {
        let _ = send.send(prove(proofs).await);
    });
    Some(receive)
}

#[cfg(test)]
mod regression_tests {
    use super::*;
    include!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tests/regressions/R5-03/native.rs"
    ));
}
