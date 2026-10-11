# logic/lease-continuity

Nineteen imported lease continuity checks.

The shared runner compiles the original assertion bytes against the current
checkout, records the new production-source pins, and runs each exact filter.
It does not assert that the historical frozen-binary pins still match. Build
wall/CPU limits are 90/60 seconds; ordinary component tests are bounded at
10 seconds and 10 CPU seconds. Linux child address spaces are limited to 1 GiB and their CPU affinity to one core;
macOS uses wall/CPU bounds because its address-space accounting differs. Original
pin manifests and the original portable runner are preserved as evidence.
