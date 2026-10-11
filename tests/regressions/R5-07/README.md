# R5-07 — stored graph fidelity

Storage reload and restore parameters must preserve own `__proto__`, sparse membership/length, extra array keys, cycles and capability aliases (including Map keys). Calling two aliases must use one restored target. Plain data is the control. Workerd `stored-value.c++:35–45,58–75`, `frankenvalue.c++:316–329` and `worker-rpc.c++:939–945` use the V8 object graph with external-reference handlers.
