R4-06: repeated capabilities retain graph identity (workerd jsg/ser.c++:424–426).
The baseline creates four handles for one wire owner and disposes the target
while an explicit duplicate is still live. This exercises an object, a Map,
an array and a cycle, and checks no premature or repeated disposal. Workerd
can defer final cleanup beyond the observation window; the test does not
require an immediate final disposer, nor claim to verify eventual cleanup.
Run `python3 ../http_case.py` with the regression contract environment.
