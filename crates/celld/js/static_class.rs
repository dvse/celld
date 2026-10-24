// Copyright 2026 Deno Land Inc. Apache-2.0 license.
//! Sealed references to classes in an immutable deployed script graph. The
//! importing node creates a local facet heap; actor ownership remains with
//! the parent and does not follow a stateless service's placement.
use super::*;
use serde::{Deserialize, Serialize};

type ConfigKey = (String, String, String);
static CONFIGS: OnceLock<Mutex<HashMap<ConfigKey, Weak<WorkerConfig>>>> = OnceLock::new();
static RETIRED: OnceLock<Mutex<HashSet<crate::generation::GenerationId>>> = OnceLock::new();

pub(crate) fn retire_generation(generation: crate::generation::GenerationId) {
    RETIRED
        .get_or_init(Mutex::default)
        .lock()
        .unwrap()
        .insert(generation);
}

pub(super) fn generation_available(generation: crate::generation::GenerationId) -> bool {
    generation == 0
        || !RETIRED
            .get_or_init(Mutex::default)
            .lock()
            .unwrap()
            .contains(&generation)
}

pub(crate) fn register(config: &Arc<WorkerConfig>) {
    RETIRED
        .get_or_init(Mutex::default)
        .lock()
        .unwrap()
        .remove(&config.generation);
    let (Some(version), Some(graph)) = (&config.static_version, &config.static_graph) else {
        return;
    };
    let mut configs = CONFIGS.get_or_init(Mutex::default).lock().unwrap();
    configs.retain(|_, config| config.strong_count() > 0);
    configs.insert(
        (config.script_name.clone(), version.clone(), graph.clone()),
        Arc::downgrade(config),
    );
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClassReference {
    script: String,
    version: String,
    graph: String,
    name: String,
    allow_storage: bool,
    seal: String,
}

pub(super) fn reference(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let name = args.get(0).to_rust_string_lossy(scope);
    let result = (|| -> Result<Option<String>> {
        anyhow::ensure!(
            cell_registry_has(scope, "doExports", &name)?,
            "static class is not a Durable Object export"
        );
        let bundle = scope
            .get_slot::<Arc<BundleFs>>()
            .cloned()
            .context("static class has no deployment config")?;
        let config = &bundle.config;
        let (Some(version), Some(graph)) = (&config.static_version, &config.static_graph) else {
            return Ok(None);
        };
        let auth = crate::capability::peer_auth()
            .context("static class references require a configured node")?;
        let mut reference = ClassReference {
            script: config.script_name.clone(),
            version: version.clone(),
            graph: graph.clone(),
            name,
            allow_storage: config.compat.allow_irrevocable_stub_storage,
            seal: String::new(),
        };
        reference.seal = auth.seal_static_class(&serde_json::to_vec(&reference)?);
        Ok(Some(serde_json::to_string(&reference)?))
    })();
    match result {
        Ok(Some(reference)) => rv.set(v8::String::new(scope, &reference).unwrap().into()),
        Ok(None) => rv.set(v8::null(scope).into()),
        Err(error) => loader_throw(scope, &error.to_string()),
    }
}

pub(super) fn load(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let serialized = args.get(0).to_rust_string_lossy(scope);
    let resolved = (|| -> Result<(Arc<WorkerConfig>, String)> {
        let mut reference: ClassReference = serde_json::from_str(&serialized)?;
        let seal = std::mem::take(&mut reference.seal);
        let auth = crate::capability::peer_auth()
            .context("static class references require a configured node")?;
        anyhow::ensure!(
            auth.verify_static_class(&serde_json::to_vec(&reference)?, &seal),
            "invalid static class reference signature"
        );
        let key = (reference.script, reference.version, reference.graph);
        let config = CONFIGS
            .get_or_init(Mutex::default)
            .lock()
            .unwrap()
            .get(&key)
            .and_then(Weak::upgrade)
            .context("static class deployment graph is no longer available on this node")?;
        anyhow::ensure!(
            generation_available(config.generation),
            "static class source generation has retired"
        );
        Ok((config, reference.name))
    })();
    let (config, name) = match resolved {
        Ok(value) => value,
        Err(error) => return loader_throw(scope, &error.to_string()),
    };
    let owner = match scope.get_slot::<LoaderOwner>().cloned() {
        Some(owner) => owner,
        None => return loader_throw(scope, "static class import has no loader owner"),
    };
    let (loaded, state) = tokio::sync::watch::channel(LoaderState::Loading);
    let id = match admit_loaded_worker(owner, state) {
        Ok(id) => id,
        Err(error) => return loader_throw(scope, &error),
    };
    {
        let mut registry = loader_registry().lock().unwrap();
        let entry = registry.get_mut(&id).unwrap();
        entry.static_class = Some(name);
        entry.static_generation = Some(config.generation);
    }
    // Exactly the selected immutable config, including services, bindings,
    // compatibility and its local generation. No reconstructed ambient env.
    asyncrt::op_handle().spawn(async move {
        let state = match tokio::task::spawn_blocking(move || Worker::load_config(config)).await {
            Ok(Ok(worker)) => LoaderState::Ready(crate::pool::Slot::loaded_worker(worker)),
            Ok(Err(error)) => {
                LoaderState::Failed(Arc::from(format!("static class load failed: {error}")))
            }
            Err(error) => {
                LoaderState::Failed(Arc::from(format!("static class task failed: {error}")))
            }
        };
        loaded.send_replace(state);
    });
    rv.set(v8::Number::new(scope, id as f64).into());
}
