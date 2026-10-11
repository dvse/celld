#!/usr/bin/env python3
"""Compatibility entry: source-matched, owned phase-2 matrix only."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).parent/'phase2/matrix.py'),run_name='__main__')
