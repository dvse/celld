import os,pathlib,subprocess,sys
root=pathlib.Path(os.environ.get('CELLD_REPO',pathlib.Path(__file__).resolve().parents[3]))
env=dict(os.environ,CARGO_BUILD_JOBS='4',CARGO_INCREMENTAL='0',CARGO_PROFILE_DEV_DEBUG='0')
sys.exit(subprocess.run(['cargo','test','--locked','-p','celld','--lib','r6_04_','--','--test-threads=1'],cwd=root,env=env).returncode)
