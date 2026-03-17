// view: grpc-services
// scope: all types annotated with @PekkoGrpcGenerated (gRPC service stubs/impls)
// description: Pekko gRPC service surface — generated stubs and service types per artifact.
//              The app uses Apache Pekko gRPC (formerly Akka gRPC) as its primary API protocol.
//              control-center and platform layers each expose gRPC services.
//
// Columns: artifact, layer, typeFqn, typeKind

MATCH (t:Type)-[:ANNOTATED_BY]->(av:Value:Annotation)-[:OF_TYPE]->(at:Type)
WHERE t.fqn STARTS WITH 'com.avanade'
  AND at.fqn IN [
    'org.apache.pekko.grpc.PekkoGrpcGenerated',
    'io.grpc.stub.annotations.GrpcGenerated',
    'io.grpc.stub.annotations.RpcMethod'
  ]
MATCH (art:Artifact)-[:CONTAINS*1..3]->(t)
WHERE art.fileName IS NOT NULL
RETURN
  art.fileName   AS artifact,
  CASE
    WHEN art.fileName CONTAINS 'control-center' THEN 'control-center'
    WHEN art.fileName CONTAINS 'platform'       THEN 'platform'
    ELSE 'unknown'
  END AS layer,
  t.fqn          AS typeFqn,
  CASE
    WHEN 'Interface' IN labels(t) THEN 'interface'
    WHEN 'Class'     IN labels(t) THEN 'class'
    WHEN 'Enum'      IN labels(t) THEN 'enum'
    ELSE 'type'
  END AS typeKind
ORDER BY layer, artifact, typeFqn;
