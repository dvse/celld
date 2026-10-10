use super::*;
#[tokio::test]
async fn r7_02_attempt_packets_do_not_consume_logical_arguments() {
    for _ in 0..1000 {
        let source = create(vec![1, 255, 15], vec![]).unwrap();
        let logical = owned(source.as_ref().to_vec()).unwrap();
        let first = fork(&logical).await.unwrap();
        let second = fork(&logical).await.unwrap();
        let (_, a) = header(&first).unwrap().unwrap();
        let (_, b) = header(&second).unwrap().unwrap();
        assert_ne!(a.id, b.id);
        // First attempt was received then refused by a stale owner.
        adopt(&first).unwrap();
        assert!(inspect(&logical).is_ok());
        // A retry may decode locally and owns a different packet.
        adopt(&second).unwrap();
        let failed_before_dispatch = fork(&logical).await.unwrap();
        drop(failed_before_dispatch);
        assert!(inspect(&logical).is_ok());
        let next = fork(&logical).await.unwrap();
        assert!(adopt(&next).is_ok());
        drop(logical);
        assert!(inspect(source.as_ref()).is_err());
    }
}
