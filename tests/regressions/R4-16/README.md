R4-16: V8 graph serialization preserves own __proto__ data properties,
array length, holes and extra enumerable properties (workerd jsg/ser.c++).
A nested RpcTarget forces celld's lifted envelope. Baseline loses data keys
and trailing holes, and fails to revive the extra array capability.
