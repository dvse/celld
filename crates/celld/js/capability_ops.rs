// Copyright 2026 Deno Land Inc. Apache-2.0 license.
use super::*;

pub(super) fn export(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let Some(slot) = crate::pool::current_slot() else {
        // Direct engine embeddings/tests have no routable Slot. Their local
        // markers remain usable, but no fake cross-isolate route is minted.
        // A configured node must always have a live dispatch slot.
        if !crate::capability::configured() {
            rv.set(v8::null(scope).into());
            return;
        }
        return loader_throw(scope, "capability export requires a live isolate turn");
    };
    let token = args.get(0).to_rust_string_lossy(scope);
    let context = require_event_context!(scope);
    // A target can be serialized from a different event in this same heap.
    // The harness records its originating actor; validate that storage here
    // rather than lending it the serializing caller's identity.
    let storage_scope = if args.length() > 1 {
        args.get(1)
            .is_string()
            .then(|| args.get(1).to_rust_string_lossy(scope))
    } else {
        context
            .egress
            .lock()
            .unwrap()
            .last()
            .map(|frame| frame.storage.clone())
    };
    if storage_scope
        .as_deref()
        .is_some_and(|cell| storage::activation_epoch(cell).is_none())
    {
        return loader_throw(
            scope,
            "capability actor activation is not live in this isolate",
        );
    }
    let identity = match storage_scope
        .as_deref()
        .map(storage::storage_identity)
        .transpose()
    {
        Ok(identity) => identity.flatten(),
        Err(error) => return loader_throw(scope, &format!("capability storage identity: {error}")),
    };
    let owner_scope = identity.as_ref().map(|id| id.root_scope.clone());
    let epoch = storage_scope.as_deref().and_then(storage::activation_epoch);
    match crate::capability::export(slot, token, storage_scope, owner_scope, epoch) {
        Ok(route) => rv.set(v8::String::new(scope, &route).unwrap().into()),
        Err(error) => loader_throw(scope, &error.to_string()),
    }
}
pub(super) fn call(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    request(scope, args, &mut rv, false, false);
}
pub(super) fn release(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    request(scope, args, &mut rv, true, false);
}
// Typed AbortSignal subscriptions run while application work is active, but
// cannot themselves keep a receiving event alive.
pub(super) fn signal_wait(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    request(scope, args, &mut rv, false, true);
}
pub(super) fn signal_active(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let active = parse_request_id(&args.get(0).to_rust_string_lossy(scope))
        .is_some_and(|id| do_call_cancels().lock().unwrap().contains_key(&id));
    rv.set(v8::Boolean::new(scope, active).into());
}
fn request(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    rv: &mut v8::ReturnValue<v8::Value>,
    release: bool,
    unrefed: bool,
) {
    let context = require_event_context!(scope);
    if !release {
        if let Err(error) = context.charge_subrequest() {
            return loader_throw(scope, &error);
        }
    }
    let route = match serde_json::from_str(&args.get(0).to_rust_string_lossy(scope)) {
        Ok(route) => route,
        Err(error) => return loader_throw(scope, &format!("invalid capability route: {error}")),
    };
    let path = if release {
        vec![]
    } else {
        match serde_json::from_str::<Vec<String>>(&args.get(1).to_rust_string_lossy(scope)) {
            Ok(path) if path.len() <= 128 => path,
            _ => return loader_throw(scope, "invalid capability path"),
        }
    };
    let value = args.get(2);
    let bytes = if release || value.is_null() {
        None
    } else {
        match view_bytes(value) {
            Some(bytes) if bytes.len() <= 8 * 1024 * 1024 => Some(bytes),
            _ => return loader_throw(scope, "invalid or oversized capability arguments"),
        }
    };
    let order_value = args.get(if release { 1 } else { 3 });
    let order = if order_value.is_undefined() || order_value.is_null() {
        None
    } else {
        match serde_json::from_str::<crate::capability::CallOrder>(
            &order_value.to_rust_string_lossy(scope),
        ) {
            Ok(order) => Some(order),
            Err(error) => {
                return loader_throw(scope, &format!("invalid capability ordering: {error}"))
            }
        }
    };
    let mut request = crate::capability::Request {
        route,
        order,
        path,
        args: match bytes {
            Some(bytes) => match crate::capability_packet::owned(bytes) {
                Ok(bytes) => Some(bytes),
                Err(error) => return loader_throw(scope, &error.to_string()),
            },
            None => None,
        },
        release,
        session: if args.get(if release { 2 } else { 4 }).is_string() {
            Some(
                args.get(if release { 2 } else { 4 })
                    .to_rust_string_lossy(scope),
            )
        } else {
            None
        },
        transfer: None,
        prepared_wire: None,
    };
    if let Err(error) = crate::capability::prepare_request(&mut request) {
        return loader_throw(scope, &error.to_string());
    }
    if release {
        // Reference teardown has no application output and cannot depend on
        // a dying actor's driver or failed output gate. The authenticated
        // session owns delivery, just as native packet-discard releases do.
        asyncrt::spawn(async move {
            let _ = crate::capability::call(request).await;
        });
        return;
    }
    let gate = egress_gate_request(&context, celld_logic::Channel::Service);
    // The sequence slot is owned from here: a failed or canceled output gate
    // resolves it at the callee instead of leaving a gap in the lane.
    let slot = crate::capability::CallerOrderSlot::new(
        &request.route,
        request.order.as_ref(),
        request.session.as_deref(),
    );
    let pending = async move {
        await_egress_gate(gate)
            .await
            .map_err(|e| format!("capability output gate failed: {e}"))?;
        crate::capability::call_ordered(request, slot)
            .await
            .map_err(crate::capability::op_failure)
    };
    if unrefed {
        let request_id = next_request_id();
        let (cancel_tx, cancel_rx) = tokio::sync::oneshot::channel();
        do_call_cancels().lock().unwrap().insert(request_id, cancel_tx);
        let guard = DoCallCancelGuard::new(request_id);
        let id = asyncrt::enqueue_unrefed(async move {
            let _guard = guard;
            tokio::select! {
                result = pending => result,
                _ = cancel_rx => Err("AbortSignal subscription canceled".into()),
            }
        });
        let promise = promise_for(scope, id);
        attach_cancel_id(scope, promise, request_id);
        rv.set(promise);
    } else {
        let id = asyncrt::enqueue(pending);
        rv.set(promise_for(scope, id));
    }
}

fn invoke<'s>(
    tc: &mut v8::PinScope<'s, '_>,
    route: &crate::capability::Route,
    operation: crate::WorkerRpcOperation,
    release: bool,
    started: &str,
) -> Result<v8::Local<'s, v8::Value>> {
    let token = crate::capability::validate(route)?;
    let f = internal_function(
        tc,
        if release {
            "__releaseCapability"
        } else {
            "__dispatchCapability"
        },
    )?;
    let token = v8::String::new(tc, &token).unwrap();
    let (path, args) = match operation {
        crate::WorkerRpcOperation::Get { path } => (path, v8::null(tc).into()),
        crate::WorkerRpcOperation::Call { path, args } => (path, rpc_bytes_value(tc, args)),
    };
    let path: Vec<v8::Local<v8::Value>> = path
        .iter()
        .map(|p| v8::String::new(tc, p).unwrap().into())
        .collect();
    let path = v8::Array::new_with_elements(tc, &path);
    let recv = v8::undefined(tc).into();
    let started = v8::String::new(tc, started).unwrap();
    let result = f
        .call(tc, recv, &[token.into(), path.into(), args, started.into()])
        .ok_or_else(|| anyhow!("capability dispatch threw"));
    result
}

pub(super) fn begin(
    tc: &mut v8::PinScope,
    props: bytes::Bytes,
    operation: crate::WorkerRpcOperation,
    release: bool,
    reply: tokio::sync::oneshot::Sender<Result<bytes::Bytes>>,
) -> Begun {
    let invocation = match serde_json::from_slice::<crate::capability::Invocation>(&props) {
        Ok(invocation) => invocation,
        Err(error) => {
            let _ = reply.send(Err(error.into()));
            return Begun::Nothing;
        }
    };
    let route = invocation.route;
    let started_ticket = invocation.started;
    if let Err(error) = crate::capability::validate(&route) {
        let _ = reply.send(Err(error));
        return Begun::Nothing;
    }
    if let Some(scope) = route.storage_scope.clone() {
        return start_cell_event(tc, &scope, Answer::Rpc(reply), None, None, false, |tc| {
            invoke(tc, &route, operation, release, &started_ticket)
        });
    }
    let runtime_state = actor_runtime_state(tc);
    let context = IoContext::tracked(&runtime_state);
    let guard = CurrentGuard::enter(context.clone());
    let previous = install_io_context(tc, &context);
    context.begin_cpu_turn();
    let started = (|| {
        begin_event_context(tc)?;
        let ret = invoke(tc, &route, operation, release, &started_ticket)?;
        match ret.try_cast::<v8::Promise>() {
            Ok(promise) => Ok(promise),
            Err(_) => resolved_promise(tc, ret),
        }
    })();
    let result = match started {
        Ok(promise) => {
            tc.perform_microtask_checkpoint();
            Begun::Running(Box::new(InFlight {
                runtime_state,
                promise: v8::Global::new(tc, promise),
                context: context.clone(),
                scope: None,
                writes_before: None,
                request_id: None,
                active_request_id: None,
                reply: Some(Answer::Rpc(reply)),
                gated_reply: None,
                background: None,
                completed_cell_event: false,
                ops: HashSet::new(),
                io_context_ops: HashSet::new(),
                adopted_ops: HashMap::new(),
                cancel_own_ops: false,
                unrefed_ops: HashSet::new(),
                alarm: None,
                alarm_timed_out: false,
                started: Instant::now(),
                trace: None,
                failure: None,
                tail_report: None,
            }))
        }
        Err(error) => {
            let _ = end_event_context(tc);
            let _ = context.finish_cpu_turn();
            let _ = reply.send(Err(error));
            Begun::Nothing
        }
    };
    restore_io_context(tc, previous);
    drop(guard);
    result
}

/// Transfer a sampled actor/facet output proof into the ordinary reply gate.
pub(super) fn gate_reply(context: &Arc<IoContext>) {
    let gate = egress_gate_request(context, celld_logic::Channel::Service);
    let (send, receive) = tokio::sync::oneshot::channel();
    register_arm_gate_with_current_event(receive, Some(context.clone()));
    asyncrt::spawn(async move {
        let _ = send.send(await_egress_gate(gate).await);
    })
    .detach();
}

pub(super) fn revoke(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    let route = match serde_json::from_str::<crate::capability::Route>(
        &args.get(0).to_rust_string_lossy(scope),
    ) {
        Ok(route) => route,
        Err(_) => return loader_throw(scope, "invalid capability revoke route"),
    };
    // Revocation is allowed after cell storage closes, but never from a
    // different heap. The opaque bearer remains necessary as well.
    if let Err(error) = crate::capability::revoke(&route) {
        loader_throw(scope, &error.to_string());
    }
}

// One-shot acknowledgement issued after the target method's synchronous entry.
pub(super) fn started(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    crate::capability::acknowledge_start(&args.get(0).to_rust_string_lossy(scope));
}

/// The secret that names restore control operations. Every node of a fleet
/// derives the same value from the fleet key, so a persistent restore can
/// cross processes; an unconfigured engine uses a per-process random value.
pub(super) fn restore_control_token(
    scope: &mut v8::PinScope,
    _args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let token = crate::capability::restore_control_token();
    rv.set(v8::String::new(scope, &token).unwrap().into());
}


pub(super) fn packet(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let result = (|| -> Result<_> {
        let routes: Vec<String> = serde_json::from_str(&args.get(1).to_rust_string_lossy(scope))?;
        let routes = routes
            .into_iter()
            .map(|r| serde_json::from_str(&r))
            .collect::<std::result::Result<Vec<_>, _>>()?;
        crate::capability_packet::create(view_bytes(args.get(0)).context("packet bytes")?, routes)
    })();
    match result {
        Ok(buffer) => rv.set(rpc_buffer_value(scope, buffer)),
        Err(error) => loader_throw(scope, &format!("RPC packet: {error}")),
    }
}
pub(super) fn packet_loader(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let result = view_bytes(args.get(0))
        .context("loader props bytes")
        .and_then(crate::capability_packet::loader);
    match result {
        Ok(buffer) => rv.set(rpc_buffer_value(scope, buffer)),
        Err(error) => loader_throw(scope, &format!("loader props: {error}")),
    }
}
pub(super) fn packet_inspect(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    match crate::capability_packet::inspect(&view_bytes(args.get(0)).unwrap_or_default()) {
        Ok(value) => rv.set(
            v8::String::new(scope, &serde_json::to_string(&value).unwrap())
                .unwrap()
                .into(),
        ),
        Err(error) => loader_throw(scope, &format!("RPC packet inspection: {error}")),
    }
}
pub(super) fn packet_take(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    let result = (|| -> Result<()> {
        let route = serde_json::from_str(&args.get(1).to_rust_string_lossy(scope))?;
        crate::capability_packet::take(&view_bytes(args.get(0)).unwrap_or_default(), &route)
    })();
    if let Err(error) = result {
        loader_throw(scope, &format!("RPC packet reference: {error}"));
    }
}
pub(super) fn packet_cancel(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    _rv: v8::ReturnValue<v8::Value>,
) {
    if let Err(error) =
        crate::capability_packet::cancel(&view_bytes(args.get(0)).unwrap_or_default())
    {
        loader_throw(scope, &format!("RPC packet cancellation: {error}"));
    }
}
pub(super) fn packet_adopt(
    scope: &mut v8::PinScope,
    args: v8::FunctionCallbackArguments,
    mut rv: v8::ReturnValue<v8::Value>,
) {
    let bytes = view_bytes(args.get(0)).unwrap_or_default();
    match crate::capability_packet::adopt(&bytes) {
        Ok(value) => rv.set(
            v8::String::new(scope, &serde_json::to_string(&value).unwrap())
                .unwrap()
                .into(),
        ),
        Err(error) => loader_throw(scope, &format!("RPC packet adoption: {error}")),
    }
}

pub(super) fn cancel(
    tc: &mut v8::PinScope,
    props: bytes::Bytes,
    reply: tokio::sync::oneshot::Sender<Result<bytes::Bytes>>,
) -> Begun {
    let result = (|| -> Result<bytes::Bytes> {
        let invocation: crate::capability::Invocation = serde_json::from_slice(&props)?;
        crate::capability::validate(&invocation.route)?;
        let function = internal_function(tc, "__cancelCapabilityCall")?;
        let ticket = v8::String::new(tc, &invocation.started).unwrap();
        let recv = v8::undefined(tc).into();
        function
            .call(tc, recv, &[ticket.into()])
            .context("capability cancellation threw")?;
        tc.perform_microtask_checkpoint();
        Ok(bytes::Bytes::new())
    })();
    let _ = reply.send(result);
    Begun::Nothing
}
