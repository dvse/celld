import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from upstream_issue import run
raise SystemExit(run(287,Path(__file__).resolve().parent))
