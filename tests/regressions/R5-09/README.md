# R5-09 — Abort attribute reflection

Compare exact descriptor keys/attributes and values before and after abort in both compatibility modes. A copied legacy descriptor is a readonly snapshot, while the original remains dynamic. Prototype getters retain branding. Includes strict assignment, Reflect.set and forged-receiver controls. Workerd `jsg/resource.h:1471–1483` uses V8 SetNativeDataProperty; rusty_v8's set_accessor_with_configuration calls that same API.
