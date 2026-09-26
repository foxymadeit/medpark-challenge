"""Dev-time ASR training: data build, Parakeet fine-tune, zero-shot bench.

Runs the same on a local box and on Kaggle; the Kaggle kernels in scripts/ are thin
wrappers that pass /kaggle paths. Unlike asr_llm, importing this package does not
switch Hugging Face offline: building data and fetching base weights may need the Hub.
Nothing here is imported at meeting runtime.

    python -m asr_train.build_data --help
    python -m asr_train.finetune --help
    python -m asr_train.zeroshot --help
"""
