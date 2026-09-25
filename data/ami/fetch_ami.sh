#!/usr/bin/env bash
# Download AMI audio (WAV) for the meetings used in eval. Needs internet once.
# Usage: ./fetch_ami.sh [Mix-Headset|Array1-01] [meeting ...]
set -euo pipefail
cd "$(dirname "$0")"
kind="${1:-Mix-Headset}"; shift || true
meetings=("${@:-ES2011a IS1008a ES2004a IS1009a TS3003a EN2002a}")
for m in ${meetings[@]}; do
  out="$m.$kind.wav"
  [ -s "$out" ] && continue
  echo "downloading $out"
  curl -fL -o "$out" "https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/$m/audio/$m.$kind.wav"
done
