import os,subprocess,sys
sys.exit(subprocess.call(['python3','http_runner.py' if os.environ['CELLD_TEST_RUNTIME']=='workerd' else 'fleet.py']))
