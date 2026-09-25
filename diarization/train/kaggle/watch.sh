#!/bin/sh
# Follow the Kaggle run from a laptop: phases, the minute-by-minute heartbeat
# (% done, minutes left, OK or WARNING), downloads, training and epoch lines.
#   sh train/kaggle/watch.sh
kaggle kernels logs -f "${1:-coflaz/secure-mom-titanet-finetune}" 2>&1 | grep --line-buffered -E \
  '=== phase|\[heartbeat\]|WARN|FAILED|Traceback|got .* MB|pieces|skip |\[train\]|\[val\]|\[epoch\]|\[save\]|sherpa-onnx loads|run report|done$'
