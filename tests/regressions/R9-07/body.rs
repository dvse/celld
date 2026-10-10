use super::disconnect_body;
use futures_util::{StreamExt, stream};
#[tokio::test]
async fn disconnect_is_terminal_error_not_eof() {
    use std::sync::{Arc, atomic::{AtomicUsize, Ordering}};
    struct DropCount(Arc<AtomicUsize>);
    impl Drop for DropCount { fn drop(&mut self) { self.0.fetch_add(1, Ordering::SeqCst); } }
    for _ in 0..1000 {
        let drops = Arc::new(AtomicUsize::new(0));
        let guard = DropCount(drops.clone());
        let source = stream::unfold(guard, |guard| async move {
            std::future::pending::<()>().await;
            Some((Ok(vec![1]), guard))
        });
        let mut body = disconnect_body(Box::pin(source), async {});
        assert!(body.next().await.unwrap().unwrap_err().contains("disconnected"));
        assert_eq!(drops.load(Ordering::SeqCst), 1);
        assert!(body.next().await.is_none());
    }
}
#[tokio::test]
async fn full_body_keeps_normal_eof() {
    let mut body = disconnect_body(Box::pin(stream::iter([Ok(vec![1]), Ok(vec![2])])), std::future::pending());
    assert_eq!(body.next().await, Some(Ok(vec![1])));
    assert_eq!(body.next().await, Some(Ok(vec![2])));
    assert!(body.next().await.is_none());
}
#[tokio::test]
async fn source_error_is_preserved_and_terminal() {
    let mut body = disconnect_body(Box::pin(stream::iter([Err("source broke".into()), Ok(vec![2])])), std::future::pending());
    assert_eq!(body.next().await, Some(Err("source broke".into())));
    assert!(body.next().await.is_none());
}
