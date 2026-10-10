R4-08: workerd basics.h:630–642,759–765 has branded readonly Abort
attributes. Both compatibility-controlled placement modes are exercised.
The baseline has public setters and unbranded accessors in both modes.
Run `python3 run.py` with the regression contract environment.

Oracle detail: workerd reflects legacy instance properties as readonly data
descriptors; prototype properties are accessors. The regression accepts either
readonly descriptor shape and checks getter brands where present, plus the
method brand in both modes. Celld's instance properties remain accessors; exact
legacy descriptor representation is a remaining reflection difference.
