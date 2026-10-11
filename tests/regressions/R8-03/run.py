import os,pathlib,subprocess,sys
sys.exit(subprocess.call(['python3', 'run.py'],cwd=pathlib.Path(__file__).resolve().parent.parent/'R9-03',env=os.environ.copy()))
