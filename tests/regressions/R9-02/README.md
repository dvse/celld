R9-02 (also R8-02): recursively enforce STORAGE channel usage in captured props.
Reference: workerd src/workerd/server/channel-token.c++:39–139.
Two deployed workers have different persistence flags. Direct, one-level and
two-level forwarded channels are stored and embedded in restore parameters.
All six non-opted-in paths reject with DataCloneError; all opted-in paths work.
The reviewed opaque-props regression began after def239b: the baseline remains
a control, not fabricated evidence that this exact introduced defect predates it.
Run the case.json command with the contract environment on the fleet host, ports 9700–9799.
