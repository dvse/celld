// Copyright 2026 Deno Land Inc. Apache-2.0 license.
//! Provisional wire references travel with their bytes, including while an
//! output gate waits. Dropping an undelivered packet releases those references.
#![allow(clippy::disallowed_methods)]
use crate::{
    capability::Route,
    capability_session::{self, Session},
};
use anyhow::{Context, Result};
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, OnceLock, Weak,
    },
};
// 1/2 are structured-clone tags; 3 is the loader-props envelope.
const TAG: u8 = 4;
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Metadata {
    id: String,
    routes: Vec<Route>,
    session: Option<String>,
    transfer: Option<String>,
}
struct Owner {
    meta: Metadata,
    remaining: Mutex<Vec<Route>>,
    transferred: AtomicBool,
    delivery: Mutex<Weak<Delivery>>,
}
struct Delivery(Arc<Owner>);
impl Drop for Delivery {
    fn drop(&mut self) {
        self.0.release();
    }
}
static PACKETS: OnceLock<Mutex<HashMap<String, Weak<Owner>>>> = OnceLock::new();
fn packets() -> &'static Mutex<HashMap<String, Weak<Owner>>> {
    PACKETS.get_or_init(Default::default)
}
impl Owner {
    fn release(&self) {
        if self.transferred.swap(true, Ordering::AcqRel) {
            return;
        }
        for route in self.remaining.lock().unwrap().drain(..) {
            match &self.meta.session {
                Some(session) => capability_session::release_remote(route.clone(), session.clone()),
                None => capability_session::release_local(route.clone()),
            }
        }
    }
}
impl Drop for Owner {
    fn drop(&mut self) {
        packets().lock().unwrap().remove(&self.meta.id);
        self.release();
    }
}
pub struct Buffer {
    data: Vec<u8>,
    _owner: Option<Arc<Owner>>,
    _delivery: Option<Arc<Delivery>>,
}
impl AsRef<[u8]> for Buffer {
    fn as_ref(&self) -> &[u8] {
        &self.data
    }
}
impl AsMut<[u8]> for Buffer {
    fn as_mut(&mut self) -> &mut [u8] {
        &mut self.data
    }
}
fn header(bytes: &[u8]) -> Result<Option<(usize, Metadata)>> {
    if bytes.starts_with(&[3, TAG]) {
        return Ok(header(&bytes[1..])?.map(|(offset, meta)| (offset + 1, meta)));
    }
    if bytes.first() != Some(&TAG) {
        return Ok(None);
    }
    anyhow::ensure!(bytes.len() >= 5, "truncated RPC packet");
    let size = u32::from_le_bytes(bytes[1..5].try_into().unwrap()) as usize;
    anyhow::ensure!(
        size <= 8 * 1024 * 1024 && bytes.len() > 5 + size,
        "invalid RPC packet header"
    );
    Ok(Some((
        5 + size,
        serde_json::from_slice(&bytes[5..5 + size])?,
    )))
}
fn encode(meta: &Metadata, payload: &[u8]) -> Result<Vec<u8>> {
    let head = serde_json::to_vec(meta)?;
    let mut bytes = Vec::with_capacity(5 + head.len() + payload.len());
    bytes.push(TAG);
    bytes.extend_from_slice(&(head.len() as u32).to_le_bytes());
    bytes.extend(head);
    bytes.extend_from_slice(payload);
    Ok(bytes)
}
fn tracked(data: Vec<u8>, meta: Metadata) -> Buffer {
    let mut table = packets().lock().unwrap();
    let owner = match table.get(&meta.id).and_then(Weak::upgrade) {
        Some(owner) => owner,
        None => {
            let owner = Arc::new(Owner {
                remaining: Mutex::new(meta.routes.clone()),
                meta,
                transferred: AtomicBool::new(false),
                delivery: Mutex::new(Weak::new()),
            });
            table.insert(owner.meta.id.clone(), Arc::downgrade(&owner));
            owner
        }
    };
    Buffer {
        data,
        _owner: Some(owner),
        _delivery: None,
    }
}
// The source V8 buffer can remain reachable after its host operation is
// canceled. Native delivery has its own last-owner edge, independent of GC.
fn delivered(mut buffer: Buffer) -> Buffer {
    if let Some(owner) = &buffer._owner {
        let mut weak = owner.delivery.lock().unwrap();
        let delivery = weak.upgrade().unwrap_or_else(|| {
            let d = Arc::new(Delivery(owner.clone()));
            *weak = Arc::downgrade(&d);
            d
        });
        buffer._delivery = Some(delivery);
    }
    buffer
}
/// Created only by the trusted harness after its complete graph encoded.
pub(crate) fn create(payload: Vec<u8>, routes: Vec<Route>) -> Result<Buffer> {
    for route in &routes {
        crate::capability::preflight(route)?;
    }
    let meta = Metadata {
        id: crate::capability::random_id(),
        routes,
        session: None,
        transfer: None,
    };
    let bytes = encode(&meta, &payload)?;
    Ok(tracked(bytes, meta))
}
/// Preserve the owner when bytes cross a native queue or enter a V8 backing store.
pub fn buffer(data: Vec<u8>) -> Result<Buffer> {
    match header(&data)? {
        Some((_, meta)) => {
            // An unknown packet must have arrived on an authenticated session via
            // receive(). It cannot mint references by presenting route-shaped data.
            let existing = packets()
                .lock()
                .unwrap()
                .get(&meta.id)
                .and_then(Weak::upgrade);
            anyhow::ensure!(existing.is_some(), "RPC packet has no native owner");
            Ok(delivered(tracked(data, meta)))
        }
        None => Ok(Buffer {
            data,
            _owner: None,
            _delivery: None,
        }),
    }
}
/// Wrap a newly serialized loader-props transfer without losing its source
/// owner or tying native queue cancellation to collection of the source buffer.
pub(crate) fn loader(data: Vec<u8>) -> Result<Buffer> {
    let owner = match header(&data)? {
        Some((_, meta)) => Some(
            packets()
                .lock()
                .unwrap()
                .get(&meta.id)
                .and_then(Weak::upgrade)
                .context("loader props packet has no owner")?,
        ),
        None => None,
    };
    let mut wrapped = Vec::with_capacity(data.len() + 1);
    wrapped.push(3);
    wrapped.extend(data);
    Ok(Buffer {
        data: wrapped,
        _owner: owner,
        _delivery: None,
    })
}
pub fn owned(data: Vec<u8>) -> Result<Bytes> {
    Ok(Bytes::from_owner(buffer(data)?))
}
pub fn receive(data: Vec<u8>, session: &Session, transfer: &str) -> Result<Bytes> {
    let Some((_, meta)) = header(&data)? else {
        return Ok(data.into());
    };
    anyhow::ensure!(
        meta.session.as_deref() == Some(&session.id) && meta.transfer.as_deref() == Some(transfer),
        "RPC packet session mismatch"
    );
    for route in &meta.routes {
        crate::capability::verify_peer_route(route)?;
        anyhow::ensure!(
            route.node == session.peer && route.process == session.process,
            "RPC packet exporter mismatch"
        );
    }
    session.received(transfer)?;
    Ok(Bytes::from_owner(delivered(tracked(data, meta))))
}
/// The logical call keeps its source packet. Each proven-safe routing attempt
/// gets new owned references; settlement of one attempt cannot consume another.
pub async fn fork(data: &Bytes) -> Result<Bytes> {
    let Some((offset, meta)) = header(data)? else {
        return Ok(data.clone());
    };
    let owner = packet_owner(&meta.id)?;
    anyhow::ensure!(
        meta.session.is_none() && !owner.transferred.load(Ordering::Acquire),
        "cannot fork a consumed RPC packet"
    );
    anyhow::ensure!(
        *owner.remaining.lock().unwrap() == meta.routes,
        "cannot fork a partially decoded RPC packet"
    );
    let mut retained = Vec::with_capacity(meta.routes.len());
    for route in &meta.routes {
        retained.push(crate::capability::retain_local(route).await?);
    }
    let mut attempt = create(data[offset..].to_vec(), meta.routes)?;
    if data.first() == Some(&3) {
        attempt.data.insert(0, 3);
    }
    // create() now owns precisely these references. Any earlier error or
    // cancellation drops the retained guards instead.
    for reference in retained {
        reference.transfer();
    }
    Ok(Bytes::from_owner(delivered(attempt)))
}

pub fn bind(data: &[u8], session: &Session, transfer: &str) -> Result<Bytes> {
    let Some((offset, mut meta)) = header(data)? else {
        return Ok(Bytes::copy_from_slice(data));
    };
    let owner = packets()
        .lock()
        .unwrap()
        .get(&meta.id)
        .and_then(Weak::upgrade)
        .context("RPC packet already released")?;
    anyhow::ensure!(
        meta.session.is_none() && !owner.transferred.load(Ordering::Acquire),
        "RPC packet already transferred"
    );
    session.bind(transfer, &meta.routes)?;
    owner.transferred.store(true, Ordering::Release);
    meta.session = Some(session.id.clone());
    meta.transfer = Some(transfer.into());
    let mut bytes = encode(&meta, &data[offset..])?;
    if data.first() == Some(&3) {
        bytes.insert(0, 3);
    }
    Ok(bytes.into())
}
pub(crate) fn inspect(data: &[u8]) -> Result<(usize, Option<String>)> {
    let Some((offset, meta)) = header(data)? else {
        return Ok((0, None));
    };
    let owner = packet_owner(&meta.id)?;
    anyhow::ensure!(
        !owner.transferred.load(Ordering::Acquire),
        "RPC packet was already consumed"
    );
    Ok((offset, meta.session))
}
fn packet_owner(id: &str) -> Result<Arc<Owner>> {
    packets()
        .lock()
        .unwrap()
        .get(id)
        .and_then(Weak::upgrade)
        .context("RPC packet released before decode")
}
/// Each successfully revived handle takes precisely one wire reference. A
/// later decode failure releases only the still-unclaimed remainder.
pub(crate) fn take(data: &[u8], route: &Route) -> Result<()> {
    let (_, meta) = header(data)?.context("RPC packet missing")?;
    let owner = packet_owner(&meta.id)?;
    anyhow::ensure!(
        !owner.transferred.load(Ordering::Acquire),
        "RPC packet consumed"
    );
    let mut remaining = owner.remaining.lock().unwrap();
    let index = remaining
        .iter()
        .position(|r| r == route)
        .context("RPC route not owned by packet")?;
    remaining.swap_remove(index);
    Ok(())
}
pub(crate) fn cancel(data: &[u8]) -> Result<()> {
    if let Some((_, meta)) = header(data)? {
        packet_owner(&meta.id)?.release();
    }
    Ok(())
}
pub(crate) fn adopt(data: &[u8]) -> Result<(usize, Option<String>)> {
    let Some((offset, meta)) = header(data)? else {
        return Ok((0, None));
    };
    let owner = packets()
        .lock()
        .unwrap()
        .get(&meta.id)
        .and_then(Weak::upgrade)
        .context("RPC packet released before decode")?;
    anyhow::ensure!(
        owner.remaining.lock().unwrap().is_empty(),
        "RPC packet has unclaimed references"
    );
    anyhow::ensure!(
        !owner.transferred.swap(true, Ordering::AcqRel),
        "RPC packet was already consumed"
    );
    Ok((offset, meta.session))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn loader_and_packet_formats_are_unambiguous() {
        let raw = vec![255, 15, 111, 34, 3, 116, 97, 103, 34];
        assert!(header(&raw).unwrap().is_none());
        let plain = loader(raw.clone()).unwrap();
        assert!(header(plain.as_ref()).unwrap().is_none());
        assert_eq!(&plain.as_ref()[1..], &raw);
        let source = create(vec![1, 255, 15], vec![]).unwrap();
        assert_eq!(source.as_ref()[0], 4);
        let wrapped = loader(source.as_ref().to_vec()).unwrap();
        let owner = source._owner.as_ref().unwrap().clone();
        drop(source);
        let native = owned(wrapped.as_ref().to_vec()).unwrap();
        let view = buffer(native.to_vec()).unwrap();
        drop(native);
        assert!(!owner.transferred.load(Ordering::Acquire));
        let (offset, _) = adopt(&view.as_ref()[1..]).unwrap();
        assert_eq!(&view.as_ref()[1 + offset..], &[1, 255, 15]);
        assert!(owner.transferred.load(Ordering::Acquire));
        assert!(header(&[4, 255, 255, 255, 255]).is_err());
        assert!(header(&[3, 4]).is_err());
    }
    #[test]
    fn wrapped_props_queue_cancellation_does_not_wait_for_v8_gc() {
        let source = create(vec![1, 255], vec![]).unwrap();
        let owner = source._owner.as_ref().unwrap().clone();
        let wrapped = loader(source.as_ref().to_vec()).unwrap();
        let native = owned(wrapped.as_ref().to_vec()).unwrap();
        drop(native);
        assert!(owner.transferred.load(Ordering::Acquire));
        assert!(adopt(&wrapped.as_ref()[1..]).is_err());
    }
    #[test]
    fn canceled_native_delivery_releases_without_source_gc() {
        let source = create(vec![1, 255], vec![]).unwrap();
        let owner = source._owner.as_ref().unwrap().clone();
        let native = owned(source.as_ref().to_vec()).unwrap();
        let copy = native.clone();
        drop(native);
        assert!(!owner.transferred.load(Ordering::Acquire));
        drop(copy);
        assert!(owner.transferred.load(Ordering::Acquire));
        assert!(adopt(source.as_ref()).is_err());
    }
    #[test]
    fn receiver_v8_backing_store_keeps_delivery_until_adoption() {
        let source = create(vec![1, 255], vec![]).unwrap();
        let native = owned(source.as_ref().to_vec()).unwrap();
        let receiver = buffer(native.to_vec()).unwrap();
        drop(native);
        let (offset, session) = adopt(receiver.as_ref()).unwrap();
        assert_eq!(&receiver.as_ref()[offset..], &[1, 255]);
        assert!(session.is_none());
        assert!(adopt(receiver.as_ref()).is_err());
    }
}

#[cfg(test)]
#[path = "../../tests/regressions/R7-02/attempts.rs"]
mod retry_tests;
