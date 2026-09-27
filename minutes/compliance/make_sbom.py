"""Write compliance/sbom.json (CycloneDX 1.5): the Python packages the minutes
pipeline imports at run time, the fonts and logo it embeds, and the local
tools it calls. Run it again whenever a dependency or asset changes.

  python compliance/make_sbom.py
"""

import hashlib
import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECT = ("python-docx", "rapidfuzz")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def requirements(name: str, seen: set) -> None:
    """Add a package and everything it needs at run time (no extras)."""
    key = name.lower().replace("_", "-")
    if key in seen:
        return
    seen.add(key)
    for req in metadata.requires(name) or []:
        if "extra ==" in req:
            continue
        marker = req.split(";", 1)[1] if ";" in req else ""
        if "python_version <" in marker:   # backports this Python does not need
            continue
        requirements(re.split(r"[ <>=!~;\[(]", req, maxsplit=1)[0], seen)


def packages() -> list:
    seen: set = set()
    for name in DIRECT:
        requirements(name, seen)
    out = []
    for key in sorted(seen):
        dist = metadata.distribution(key)
        version = dist.version
        out.append({"type": "library", "name": dist.metadata["Name"], "version": version,
                    "purl": f"pkg:pypi/{key}@{version}",
                    "licenses": [{"license": {"name": dist.metadata.get("License-Expression") or dist.metadata.get("License") or "see package"}}],
                    "scope": "required"})
    return out


def files() -> list:
    out = []
    for path in sorted((ROOT / "template" / "fonts").glob("*.ttf")):
        family = "Montserrat" if path.name.startswith("Montserrat") else "PT Serif"
        out.append({"type": "file", "name": f"template/fonts/{path.name}", "description": f"{family} font, embedded in every PDF",
                    "licenses": [{"license": {"id": "OFL-1.1"}}],
                    "hashes": [{"alg": "SHA-256", "content": sha256(path)}]})
    for name in ("logo.pdf", "logo.png", "medpark-mom.cls"):
        path = ROOT / "template" / name
        out.append({"type": "file", "name": f"template/{name}",
                    "description": "Medpark logo, from medpark.md (see template/NOTICE.md)" if name.startswith("logo") else "Minutes document class",
                    "hashes": [{"alg": "SHA-256", "content": sha256(path)}]})
    return out


def tool(cmd: list, name: str, description: str) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        first = next(l for l in (r.stdout + r.stderr).splitlines() if "version" in l.lower() or "XeTeX" in l)
    except (OSError, StopIteration, subprocess.TimeoutExpired):
        first = "not installed on the machine that wrote this file"
    return {"type": "application", "name": name, "version": first.replace("Warning: client version is ", "").strip(), "description": description}


def main() -> None:
    bom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "component": {"type": "application", "name": "secure-mom-minutes", "version": "0.1.0",
                                   "description": "Offline minutes of meeting for Medpark: transcript to PDF and DOCX in RO, RU and EN"}},
        "components": packages() + files() + [
            tool(["xelatex", "--version"], "XeTeX (TeX Live)", "Compiles the PDF; run with shell escape off and paranoid file access"),
            tool(["ollama", "--version"], "Ollama", "Local model server on 127.0.0.1; the model and its digest are recorded in each report.json"),
        ],
    }
    out = Path(__file__).with_name("sbom.json")
    out.write_text(json.dumps(bom, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{out}: {len(bom['components'])} components")


if __name__ == "__main__":
    main()
