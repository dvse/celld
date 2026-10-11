// Copyright 2026 Deno Land Inc. Apache-2.0 license.

//! What a node's cell runtime holds whichever engine runs the cells: the
//! generations it resolves calls against, the data directory, replication,
//! wake discovery and facet streams. Each engine's `RuntimeManager` wraps one
//! and adds what only its engine knows: cells, isolates, requests.

use std::path::Path;
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::anyhow;
use anyhow::Context;

use crate::asyncrt;
use crate::engine_api::AlarmObserver;
use crate::generation::Generation;
use crate::generation::GenerationId;
use crate::ltx_replication::Replication;
use crate::wake::WakeFlusher;

/// The generations a node can resolve a call against: the one it serves and
/// the superseded ones whose isolates are still draining.
///
/// One value under one lock, because installing the new generation and
/// keeping the previous one resolvable are the same instant. Held apart,
/// the window between them resolved an in-flight call from the previous
/// generation against the new deployment graph.
pub(crate) struct Generations {
    pub(crate) current: Arc<Generation>,
    pub(crate) draining: Vec<Arc<Generation>>,
}

/// Select under the caller's one generation lock. `None` is current; a
/// draining index is exact. Zero is the sole current-generation wildcard.
fn dispatch_generation_position(
    requested: GenerationId,
    current: GenerationId,
    draining: impl Iterator<Item = GenerationId>,
) -> anyhow::Result<Option<usize>> {
    if requested == 0 || requested == current {
        return Ok(None);
    }
    draining.enumerate().find_map(|(index, id)| (id == requested).then_some(Some(index)))
        .ok_or_else(|| anyhow!("application generation {requested} has retired; refusing dispatch through a different deployment graph"))
}

#[derive(Clone)]
pub struct CellRuntime {
    /// The generations a call can resolve against. A reader takes one
    /// snapshot and never holds the lock across an await.
    pub(crate) generations: Arc<std::sync::RwLock<Generations>>,
    pub(crate) data_dir: Arc<PathBuf>,
    pub(crate) replication: Option<Replication>,
    pub(crate) wake: Option<Arc<WakeFlusher>>,
    pub(crate) alarm_observer: AlarmObserver,
    /// The facet streams of each resident root object.
    pub(crate) facets: crate::facet_streams::FacetStreams,
    pub(crate) node: Arc<str>,
    pub(crate) region: Arc<str>,
}

impl CellRuntime {
    pub(crate) fn new(
        generation: Arc<Generation>,
        data_dir: PathBuf,
        replication: Option<Replication>,
        wake: Option<Arc<WakeFlusher>>,
        alarm_observer: AlarmObserver,
        node: String,
        region: String,
    ) -> anyhow::Result<Self> {
        require_cell_scope_capacity(&data_dir)?;
        Ok(Self {
            generations: Arc::new(std::sync::RwLock::new(Generations {
                current: generation,
                draining: Vec::new(),
            })),
            data_dir: Arc::new(data_dir),
            replication,
            wake,
            alarm_observer,
            facets: Default::default(),
            node: Arc::from(node),
            region: Arc::from(region),
        })
    }

    /// The generation this node serves now.
    ///
    /// A caller that makes more than one decision from it takes the snapshot
    /// once and uses it throughout: the current generation can change between
    /// two reads, and a request must see one deployment graph, not two.
    pub fn generation(&self) -> Arc<Generation> {
        self.generations
            .read()
            .expect("generation lock poisoned")
            .current
            .clone()
    }

    /// The generation an isolate was built for: the current one when the id
    /// matches, otherwise a superseded generation still draining. Zero — the
    /// tag of an isolate built outside any generation — resolves to current.
    /// An expired nonzero generation must fail instead of silently lending
    /// a retained capability the new deployment's service graph.
    pub fn generation_by_id(&self, id: GenerationId) -> anyhow::Result<Arc<Generation>> {
        // One lock over both halves: read separately, a caller from the
        // previous generation could observe the new one as current before
        // the previous one was resolvable, find neither, and fall through to
        // the new graph -- the cross-generation call this exists to prevent.
        let generations = self.generations.read().expect("generation lock poisoned");
        match dispatch_generation_position(
            id,
            generations.current.id,
            generations.draining.iter().map(|generation| generation.id),
        )? {
            None => Ok(generations.current.clone()),
            Some(index) => Ok(generations.draining[index].clone()),
        }
    }

    /// The id the next generation takes: one past the newest this node has
    /// built, draining generations included, so an id is never reused while
    /// an isolate still carries it.
    pub fn next_generation_id(&self) -> GenerationId {
        let generations = self.generations.read().expect("generation lock poisoned");
        let draining = generations
            .draining
            .iter()
            .map(|generation| generation.id)
            .max()
            .unwrap_or(0);
        generations.current.id.max(draining) + 1
    }

    /// The generations still draining, for `/state`. Each one holds its
    /// isolates until the last cell in them moves, so the caller reads the
    /// census from the generation and not only its version.
    pub fn draining_generations(&self) -> Vec<Arc<Generation>> {
        self.generations
            .read()
            .expect("generation lock poisoned")
            .draining
            .clone()
    }

    /// Resolve a client-supplied cell id to a scope.
    ///
    /// The id arrives from the network, and the scope it becomes is used as a
    /// path component and as an object-store key, so the charset gate runs
    /// first. Without it a scope carries its own path segments and `db_path`
    /// walks out of the data directory through them.
    ///
    /// The fleet-wide storage gate runs a second time on the composed scope. A
    /// bare id takes a class prefix, so the scope that reaches storage is the
    /// value that must fit.
    pub fn cell_scope(&self, id: &str) -> anyhow::Result<String> {
        if !celld_logic::cell::valid_cell_scope(id) {
            return Err(anyhow!("cell id is not a well-formed scope"));
        }
        if id.contains(':') {
            return Ok(id.to_string());
        }
        let generation = self.generation();
        let class = generation.default_do_class().ok_or_else(|| {
            anyhow!("a bare cell id requires exactly one configured Durable Object class")
        })?;
        let scope = format!("{class}:{id}");
        if !celld_logic::cell::valid_cell_scope(&scope) {
            return Err(anyhow!("cell id is not a well-formed scope"));
        }
        Ok(scope)
    }

    pub fn replication(&self) -> Option<Replication> {
        self.replication.clone()
    }

    /// Read the filesystem inventory after the core has replaced the exact
    /// clean predecessor lease generation.
    pub fn local_reload_cells(&self) -> anyhow::Result<Vec<celld_logic::LocalCell>> {
        let replication = self
            .replication
            .as_ref()
            .context("local reload requires replication")?;
        Ok(replication.local_cells())
    }

    pub fn replication_status(&self) -> std::io::Result<Option<std::process::ExitStatus>> {
        match &self.replication {
            Some(replication) => replication.process_status(),
            None => Ok(None),
        }
    }

    pub async fn ensure_durable(
        &self,
        cell: &str,
        epoch: u64,
        revocable: bool,
    ) -> anyhow::Result<()> {
        let Some(replication) = &self.replication else {
            return Ok(());
        };
        for facet in self.facets.resident(cell, epoch) {
            replication.ensure_durable(&facet, epoch, revocable).await?;
        }
        replication.ensure_durable(cell, epoch, revocable).await
    }

    /// The output-gate durability wait (see `Replication::await_durable`).
    /// Returns the proved durable position and its proof source; with no
    /// replicator every position is trivially durable, and the fleet source
    /// keeps the gate read-free exactly like the old immediate release.
    pub async fn await_durable(
        &self,
        cell: &str,
        epoch: u64,
        position: u64,
    ) -> anyhow::Result<(u64, celld_logic::ProofSource)> {
        match &self.replication {
            Some(replication) => replication.await_durable(cell, epoch, position).await,
            None => Ok((position, celld_logic::ProofSource::Fleet)),
        }
    }

    /// Activate a facet's stream and answer its database file.
    pub async fn open_facet(
        &self,
        root: &str,
        epoch: u64,
        names: &[String],
    ) -> anyhow::Result<(PathBuf, bool)> {
        let state = crate::facet_snapshot::root(root, epoch);
        let _access = state.changing().await;
        self.facets
            .open(
                self.replication.as_ref(),
                |cell, epoch| self.db_path(cell, epoch),
                root,
                epoch,
                names,
            )
            .await
    }

    /// Delete a facet's stream and every stream below it.
    pub async fn delete_facet(
        &self,
        root: &str,
        epoch: u64,
        names: &[String],
    ) -> anyhow::Result<()> {
        let state = crate::facet_snapshot::root(root, epoch);
        let _access = state.changing().await;
        self.facets
            .delete(
                self.replication.as_ref(),
                |cell| self.data_dir.join(cell),
                root,
                epoch,
                names,
            )
            .await
    }

    /// Snapshot committed pages for the entire logical source subtree. The
    /// synchronous caller holds the root's SQLite cut until this returns.
    pub async fn capture_facet_mutation(
        &self,
        root: &str,
        epoch: u64,
        source: Option<&[String]>,
        destination: &[String],
    ) -> anyhow::Result<Arc<crate::facet_snapshot::Mutation>> {
        use crate::facet_snapshot::{Database, Image};
        let state = crate::facet_snapshot::root(root, epoch);
        let mut image = Image::new();
        if let Some(source) = source {
            let source_cell = crate::engine_api::facet_cell(root, source);
            if !state.covered(&source_cell) {
                let snapshot_dir = self.data_dir.join("facet-snapshots");
                asyncrt::fs().create_dir_all(&snapshot_dir)?;
                let directory = Arc::new(tempfile::tempdir_in(snapshot_dir)?);
                for (index, suffix) in self
                    .facet_subtree(root, epoch, &source_cell)
                    .await?
                    .into_iter()
                    .enumerate()
                {
                    let from = format!("{source_cell}{suffix}");
                    let (from_path, _) = self
                        .facets
                        .open_stream(
                            self.replication.as_ref(),
                            |cell, epoch| self.db_path(cell, epoch),
                            root,
                            epoch,
                            from.clone(),
                        )
                        .await?;
                    let from_vfs = match &self.replication {
                        Some(replication) => replication.ltx().activation_vfs(&from, epoch)?,
                        None => None,
                    };
                    let path = directory.path().join(format!("{index}.sqlite"));
                    let snapshot = path.clone();
                    crate::asyncrt::blocking(move || {
                        copy_database(&from_path, from_vfs.as_deref(), &snapshot, None)
                    })
                    .await
                    .map_err(|error| anyhow!("facet snapshot task: {error}"))??;
                    image.insert(
                        suffix,
                        Database {
                            path,
                            directory: directory.clone(),
                        },
                    );
                }
            }
            image = state.overlay(&source_cell, image);
        }
        anyhow::ensure!(!state.is_closing(), "facet root stopped during snapshot");
        let to = crate::engine_api::facet_cell(root, destination);
        Ok(state.add(root.to_string(), epoch, to, destination.to_vec(), image))
    }

    /// Close/delete has been ordered by the facet manager. Persist only the
    /// captured image; source continuations are now free to change their DBs.
    pub async fn apply_facet_mutation(
        &self,
        mutation: Arc<crate::facet_snapshot::Mutation>,
    ) -> anyhow::Result<()> {
        let state = crate::facet_snapshot::root(&mutation.root, mutation.epoch);
        let result = async {
            crate::facet_snapshot::prove(mutation.previous.clone())
                .await
                .map_err(anyhow::Error::msg)?;
            let _access = state.changing().await;
            anyhow::ensure!(!state.is_closing(), "facet root is stopping");
            self.facets
                .delete(
                    self.replication.as_ref(),
                    |cell| self.data_dir.join(cell),
                    &mutation.root,
                    mutation.epoch,
                    &mutation.names,
                )
                .await?;
            for (suffix, database) in &mutation.image {
                let to = format!("{}{suffix}", mutation.destination);
                let (to_path, _) = self
                    .facets
                    .open_stream(
                        self.replication.as_ref(),
                        |cell, epoch| self.db_path(cell, epoch),
                        &mutation.root,
                        mutation.epoch,
                        to.clone(),
                    )
                    .await?;
                let to_vfs = match &self.replication {
                    Some(replication) => replication.ltx().activation_vfs(&to, mutation.epoch)?,
                    None => None,
                };
                let source = database.clone();
                crate::asyncrt::blocking(move || {
                    let _directory = &source.directory;
                    copy_database(&source.path, None, &to_path, to_vfs.as_deref())
                })
                .await
                .map_err(|error| anyhow!("facet copy task: {error}"))??;
                if let Some(replication) = &self.replication {
                    replication
                        .ensure_durable(&to, mutation.epoch, false)
                        .await?;
                }
            }
            Ok::<_, anyhow::Error>(())
        }
        .await;
        let _access = state.changing().await;
        state.finish(
            &mutation,
            result
                .as_ref()
                .map(|_| ())
                .map_err(|error| format!("facet mutation: {error:#}")),
        );
        result
    }

    /// workerd's `cloneFacet` (server/server.c++ `cloneFacet`,
    /// `cloneFacetImpl`): delete `destination` and everything below it, then
    /// copy `source`'s whole subtree onto it, each nested facet keeping its
    /// name, so the copy of `source/<n>` is `destination/<n>`. A stream with
    /// no data is not copied, which leaves its destination empty, as workerd
    /// leaves a destination with no file. The isolate has already aborted
    /// `destination`; `source` keeps running, and each of its databases is
    /// read in one read transaction, a consistent snapshot of its committed
    /// state. The copy is written through SQLite's backup API into the
    /// destination's own activated stream, so its replication captures it
    /// like any write. Returns once every copied stream is durable.
    pub async fn clone_facet(
        &self,
        root: &str,
        epoch: u64,
        source: &[String],
        destination: &[String],
    ) -> anyhow::Result<()> {
        if source == destination {
            return Ok(());
        }
        let source_cell = crate::engine_api::facet_cell(root, source);
        let destination_cell = crate::engine_api::facet_cell(root, destination);
        let streams = self.facet_subtree(root, epoch, &source_cell).await?;
        self.delete_facet(root, epoch, destination).await?;
        for suffix in streams {
            let from = format!("{source_cell}{suffix}");
            let to = format!("{destination_cell}{suffix}");
            self.copy_facet_stream(root, epoch, from, to.clone())
                .await?;
            if let Some(replication) = &self.replication {
                replication.ensure_durable(&to, epoch, false).await?;
            }
        }
        Ok(())
    }

    /// The streams of `cell`'s subtree that hold data, as suffixes of
    /// `cell` (`""` for `cell` itself): the resident ones and, with
    /// replication, those in the bucket; without it, those with a local
    /// database file.
    async fn facet_subtree(
        &self,
        root: &str,
        epoch: u64,
        cell: &str,
    ) -> anyhow::Result<std::collections::BTreeSet<String>> {
        let below = format!("{cell}/");
        let mut streams: std::collections::BTreeSet<String> = self
            .facets
            .resident(root, epoch)
            .into_iter()
            .filter(|stream| stream == cell || stream.starts_with(&below))
            .collect();
        match &self.replication {
            Some(replication) => streams.extend(replication.ltx().streams_with_data(cell).await?),
            None => {
                let mut pending = vec![cell.to_string()];
                while let Some(stream) = pending.pop() {
                    if crate::asyncrt::fs()
                        .metadata(&self.db_path(&stream, epoch))
                        .is_ok()
                    {
                        streams.insert(stream.clone());
                    }
                    let children = self.data_dir.join(&stream).join("facets");
                    if let Ok(entries) = crate::asyncrt::fs().read_dir(&children) {
                        for entry in entries {
                            if let Some(name) = entry.file_name.to_str() {
                                pending.push(format!("{stream}/facets/{name}"));
                            }
                        }
                    }
                }
            }
        }
        Ok(streams
            .into_iter()
            .map(|stream| stream[cell.len()..].to_string())
            .collect())
    }

    /// Copy one facet stream's committed database onto another, activating
    /// both. The source is read in a single backup step, so the copy is one
    /// read transaction's snapshot even while the source's own facet writes.
    async fn copy_facet_stream(
        &self,
        root: &str,
        epoch: u64,
        from: String,
        to: String,
    ) -> anyhow::Result<()> {
        let open = |stream: String| {
            self.facets.open_stream(
                self.replication.as_ref(),
                |cell, epoch| self.db_path(cell, epoch),
                root,
                epoch,
                stream,
            )
        };
        let (from_path, _) = open(from.clone()).await?;
        let (to_path, _) = open(to.clone()).await?;
        let vfs = |stream: &str| -> anyhow::Result<Option<String>> {
            match &self.replication {
                Some(replication) => replication.ltx().activation_vfs(stream, epoch),
                None => Ok(None),
            }
        };
        let (from_vfs, to_vfs) = (vfs(&from)?, vfs(&to)?);
        crate::asyncrt::blocking(move || -> anyhow::Result<()> {
            let open = |path: &std::path::Path,
                        flags: rusqlite::OpenFlags,
                        vfs: Option<&str>|
             -> rusqlite::Result<rusqlite::Connection> {
                match vfs {
                    Some(vfs) => rusqlite::Connection::open_with_flags_and_vfs(path, flags, vfs),
                    None => rusqlite::Connection::open_with_flags(path, flags),
                }
            };
            let source = open(
                &from_path,
                rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY,
                from_vfs.as_deref(),
            )?;
            let mut destination =
                open(&to_path, rusqlite::OpenFlags::default(), to_vfs.as_deref())?;
            destination.pragma_update(None, "journal_mode", "WAL")?;
            let backup = rusqlite::backup::Backup::new(&source, &mut destination)?;
            // `step(-1)` copies every page in one step, under one read
            // transaction of the source.
            loop {
                match backup.step(-1)? {
                    rusqlite::backup::StepResult::Done => break,
                    rusqlite::backup::StepResult::More => {}
                    _ => std::thread::sleep(std::time::Duration::from_millis(5)),
                }
            }
            Ok(())
        })
        .await
        .map_err(|error| anyhow::anyhow!("facet clone task failed: {error}"))??;
        Ok(())
    }

    /// Prove every committed write of a facet's stream durable.
    pub async fn prove_facet(&self, stream: &str, epoch: u64) -> anyhow::Result<()> {
        self.await_durable(stream, epoch, 0).await.map(|_| ())
    }

    pub(crate) fn db_path(&self, cell: &str, epoch: u64) -> PathBuf {
        // A runtime without replication has no remote epoch namespace, so it
        // keeps its only SQLite family at the existing e1 path across logical
        // ownership epochs. The stable path survives a restart, needs no
        // multi-file SQLite family move, and remains compatible with older
        // releases.
        let epoch = if self.replication.is_some() { epoch } else { 1 };
        self.data_dir
            .join(cell)
            .join("ltx")
            .join(format!("e{epoch}"))
            .join("db.sqlite")
    }

    pub fn alarm_covered(&self, cell: &str, alarm: celld_logic::wake::AlarmSnapshot) -> bool {
        match (alarm.at_ms(), &self.wake) {
            (None, _) => true,
            (Some(_), Some(wake)) if self.replication.is_some() => wake.covered(cell, alarm),
            (Some(_), None) => false,
            (Some(_), Some(_)) => false,
        }
    }

    pub fn node(&self) -> &str {
        &self.node
    }

    pub fn region(&self) -> &str {
        &self.region
    }
}

fn require_cell_scope_capacity(data_dir: &Path) -> anyhow::Result<()> {
    asyncrt::fs()
        .create_dir_all(data_dir)
        .with_context(|| format!("create data directory {}", data_dir.display()))?;
    let reported = asyncrt::filesystem_name_max(data_dir)
        .with_context(|| format!("read NAME_MAX for {}", data_dir.display()))?
        .with_context(|| {
            format!(
                "the filesystem does not report NAME_MAX for {}",
                data_dir.display()
            )
        })?;
    let name_max = usize::try_from(reported).context("NAME_MAX does not fit usize")?;
    require_cell_scope_name_max(name_max)
}

pub(crate) fn require_cell_scope_name_max(name_max: usize) -> anyhow::Result<()> {
    anyhow::ensure!(
        name_max >= celld_logic::cell::MAX_CELL_SCOPE,
        "the data filesystem supports {name_max}-byte names, but celld requires {}",
        celld_logic::cell::MAX_CELL_SCOPE
    );
    Ok(())
}

// Both sides use SQLite backup, including fault-in VFS reads. A captured
// image is an ordinary closed file and never shares a mutable source WAL.
fn copy_database(
    from: &Path,
    from_vfs: Option<&str>,
    to: &Path,
    to_vfs: Option<&str>,
) -> anyhow::Result<()> {
    let open = |path: &Path, flags, vfs: Option<&str>| match vfs {
        Some(vfs) => rusqlite::Connection::open_with_flags_and_vfs(path, flags, vfs),
        None => rusqlite::Connection::open_with_flags(path, flags),
    };
    let source = open(from, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY, from_vfs)?;
    let mut destination = open(to, rusqlite::OpenFlags::default(), to_vfs)?;
    destination.pragma_update(None, "journal_mode", "WAL")?;
    let backup = rusqlite::backup::Backup::new(&source, &mut destination)?;
    loop {
        match backup.step(-1)? {
            rusqlite::backup::StepResult::Done => break,
            rusqlite::backup::StepResult::More => {}
            _ => std::thread::sleep(std::time::Duration::from_millis(5)),
        }
    }
    Ok(())
}

#[cfg(test)]
mod generation_dispatch_tests {
    use super::dispatch_generation_position;

    #[test]
    fn zero_generation_resolves_current_and_draining_resolves_exactly() {
        assert_eq!(
            dispatch_generation_position(0, 3, [1, 2].into_iter()).unwrap(),
            None
        );
        assert_eq!(
            dispatch_generation_position(3, 3, [1, 2].into_iter()).unwrap(),
            None
        );
        assert_eq!(
            dispatch_generation_position(2, 3, [1, 2].into_iter()).unwrap(),
            Some(1)
        );
    }

    #[test]
    fn expired_nonzero_generation_fails_instead_of_current_fallback() {
        let error = dispatch_generation_position(1, 3, [2].into_iter()).unwrap_err();
        assert!(error.to_string().contains("generation 1 has retired"));
        assert!(dispatch_generation_position(4, 3, [].into_iter()).is_err());
    }
}
