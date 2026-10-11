# Provenance index

These files preserve origins and historical qualification notes. Active test
categories and case headers live in the behaviour tree documented by
`../../README.md`; historical paths in original documents are not active paths.

- `PATH-MIGRATION.json`: every relocated path and all 610 original case aliases.
- `../SOURCES.json`: 463 imported files, current paths, origin and SHA-256.
- `COUNTS.json`: original 461-reviewed / 114-excluded case census.
- `IDENTICAL-SOURCES.json` and `DEDUPLICATION.md`: shared source and case audit.
- `SCRATCH-AUDIT.json`: all 262 tests-scratch vendor files already present.
- `ADAPTERS.md`: unchanged upstream assertions versus authored observations.
- `RUNNERS.md` and runner/source manifests: original execution prerequisites.
- `reorganize.py`: one-time migration record, not a recurring test entry point.

`../materialize-source.py` can reconstruct original relative imports in a new
artifact directory, without executing historical deployment/cleanup scripts.
