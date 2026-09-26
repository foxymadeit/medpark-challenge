"""Hugging Face files, from the Hub or from a local mirror.

A mirror is a folder laid out as <mirror>/<org>/<name>/<path in repo>, which is what

    huggingface-cli download <org>/<name> --repo-type dataset --local-dir <mirror>/<org>/<name>

leaves behind. With a mirror nothing touches the network, so the data build and the
bench can run on an offline box once the files are copied in.
"""

from __future__ import annotations

from pathlib import Path


class Hub:
    def __init__(self, mirror: Path | None = None, cache: Path | None = None):
        self.mirror = mirror.expanduser().resolve() if mirror else None
        self.cache = str(cache) if cache else None  # None = the usual ~/.cache/huggingface

    def _local(self, repo: str, path: str = "") -> Path:
        assert self.mirror is not None
        local = self.mirror / repo / path
        if not local.exists():
            raise FileNotFoundError(f"{repo}/{path} not in mirror {self.mirror}; download it there first")
        return local

    def file(self, repo: str, path: str, repo_type: str = "dataset") -> Path:
        if self.mirror:
            return self._local(repo, path)
        from huggingface_hub import hf_hub_download

        return Path(hf_hub_download(repo, path, repo_type=repo_type, cache_dir=self.cache))

    def list(self, repo: str, prefix: str, suffix: str = ".parquet") -> list[str]:
        """Repo-relative paths under `prefix` ending in `suffix`, sorted."""
        if self.mirror:
            root = self._local(repo)
            files = (p.relative_to(root).as_posix() for p in root.rglob(f"*{suffix}") if p.is_file())
        else:
            from huggingface_hub import HfApi

            files = HfApi().list_repo_files(repo, repo_type="dataset")
        return sorted(f for f in files if f.startswith(prefix) and f.endswith(suffix))

    def snapshot(self, repo: str, patterns: list[str]) -> Path:
        """Local root of a repo holding at least `patterns` (a mirror is assumed to hold them)."""
        if self.mirror:
            return self._local(repo)
        from huggingface_hub import snapshot_download

        return Path(snapshot_download(repo, repo_type="dataset", cache_dir=self.cache, allow_patterns=patterns))
