# Adapter provenance

The global-scope and actor-KV test modules and selected WPT assertion files run
unchanged original assertions through small HTTP wrappers. Their hashes and
reference configurations are retained.

The four object-contract HTTP probes are authored selected observations. The
stub probe follows actor-stub identity/receiver behaviour; the prefix-list,
rollback and SQL probes add specific storage value observations. In particular,
the imported actor-kv-test.js does not contain the rollback or SQL assertion
bodies. Those probes are not claimed as literal upstream ports or as the full
upstream suite. Their headers distinguish implementation and reference roles.

Imported finding fixtures and expected outputs are unchanged. The shared HTTP
adapter replaces only process/deployment setup so celld's internal listener
stays inside the tests lane's range. Node harness tests execute the supplied
command against this branch's production JavaScript source.
