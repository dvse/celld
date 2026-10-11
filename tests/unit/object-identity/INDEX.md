# object-identity

12 cases; 12 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [ambiguous namespace never selects first match](ambiguous-namespace-never-selects-first-match.case.json) | no | cargo |
| [colliding class rejects unsigned tampered and foreign ids](colliding-class-rejects-unsigned-tampered-and-foreign-ids.case.json) | no | cargo |
| [duplicate declaration in one script is still an error](duplicate-declaration-in-one-script-is-still-an-error.case.json) | no | cargo |
| [expired nonzero generation fails instead of current fallback](expired-nonzero-generation-fails-instead-of-current-fallback.case.json) | no | cargo |
| [migrated bound class is registered once](migrated-bound-class-is-registered-once.case.json) | no | cargo |
| [migrated unbound class has namespace without env binding](migrated-unbound-class-has-namespace-without-env-binding.case.json) | no | cargo |
| [random ids and uppercase id input select source](random-ids-and-uppercase-id-input-select-source.case.json) | no | cargo |
| [removed source cannot be reinterpreted as remaining singleton](removed-source-cannot-be-reinterpreted-as-remaining-singleton.case.json) | no | cargo |
| [same named class routes by existing namespace signature](same-named-class-routes-by-existing-namespace-signature.case.json) | no | cargo |
| [shared reserved classes keep one fleet wide config](shared-reserved-classes-keep-one-fleet-wide-config.case.json) | no | cargo |
| [unambiguous nonhex legacy scope and missing class are preserved](unambiguous-nonhex-legacy-scope-and-missing-class-are-preserved.case.json) | no | cargo |
| [zero generation resolves current and draining resolves exactly](zero-generation-resolves-current-and-draining-resolves-exactly.case.json) | no | cargo |
