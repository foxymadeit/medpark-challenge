"""Runs the backend's fake minutes stage, leaving an item to confirm for
medical meetings only, so one e2e test sees the confirmation step and the
other sees the plain send countdown."""

import os
import sys

args = sys.argv[1:]
fake = os.environ["E2E_FAKE_MINUTES"]
if args[args.index("--type") + 1] == "medical":
    os.environ["FAKE_CONFIRM"] = "1"
os.execv(sys.executable, [sys.executable, fake, *args])
