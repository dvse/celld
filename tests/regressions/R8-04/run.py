import os,pathlib,subprocess,sys
sys.exit(subprocess.call(['python3', 'http_runner.py'],cwd=pathlib.Path(__file__).resolve().parent.parent/'R9-04',env=os.environ.copy()))
