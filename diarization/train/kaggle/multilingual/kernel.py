"""Kaggle entry for the multilingual run: same kernel as the base notebook,
with Russian, more Romanian, VoxConverse test, Simsamu and room echo added.
It clones the branch and runs train/kaggle/kernel.py with DATA_PROFILE set,
so both notebooks share one source file."""

import os
import runpy
import subprocess

subprocess.run("git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge /tmp/repo",
               shell=True, check=True)
os.environ["DATA_PROFILE"] = "multilingual"
runpy.run_path("/tmp/repo/diarization/train/kaggle/kernel.py", run_name="__main__")
