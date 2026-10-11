R4-06: repeated capabilities retain graph identity (workerd jsg/ser.c++:424–426).
The baseline creates four handles for one wire owner and disposes the target
while an explicit duplicate is still live. This exercises an object, a Map,
an array and a cycle, and checks exact final disposal count.
Run `python3 ../http_case.py` with the regression contract environment.
