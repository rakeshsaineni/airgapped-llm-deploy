"""Build and verify an offline bundle: every image saved as a tarball, the chart, and a
manifest of SHA-256 checksums. The bundle crosses the air gap on approved media, and
`verify` runs on the inside before anything is loaded."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
import time
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str]], None]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(image: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", image) + ".tar"


def build(images: list[str], chart_dir: Path, out: Path, runner: Runner = run) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for img in images:
        tar = out / "images" / safe_name(img)
        tar.parent.mkdir(exist_ok=True)
        runner(["docker", "pull", img])
        runner(["docker", "save", "-o", str(tar), img])
        files.append({"path": str(tar.relative_to(out)), "image": img})
    chart_tgz = out / f"{chart_dir.name}.tgz"
    with tarfile.open(chart_tgz, "w:gz") as t:
        t.add(chart_dir, arcname=chart_dir.name)
    files.append({"path": chart_tgz.name, "image": None})
    for f in files:
        f["sha256"] = sha256(out / f["path"])
        f["bytes"] = (out / f["path"]).stat().st_size
    manifest = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files}
    (out / "bundle-manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def verify(bundle: Path) -> list[str]:
    """Return problems; an empty list means every file is present and unmodified."""
    manifest = json.loads((bundle / "bundle-manifest.json").read_text())
    problems = []
    for f in manifest["files"]:
        p = bundle / f["path"]
        if not p.exists():
            problems.append(f"missing: {f['path']}")
        elif sha256(p) != f["sha256"]:
            problems.append(f"checksum mismatch: {f['path']}")
    listed = {f["path"] for f in manifest["files"]}
    extra = [str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()
             and p.name != "bundle-manifest.json" and str(p.relative_to(bundle)) not in listed]
    problems += [f"unexpected file: {e}" for e in extra]
    return problems


def load_and_push(bundle: Path, registry: str, runner: Runner = run) -> dict[str, str]:
    """Inside the air gap: load each tarball, retag to the internal registry and push.
    Returns {original image: internal image} for the values override."""
    if verify(bundle):
        raise RuntimeError("bundle failed verification; refusing to load")
    mapping = {}
    for f in json.loads((bundle / "bundle-manifest.json").read_text())["files"]:
        if not f["image"]:
            continue
        src = f["image"]
        name = src.split("@")[0]
        parts = name.split("/")
        internal = f"{registry}/{'/'.join(parts[1:] if len(parts) > 2 or '.' in parts[0] else parts)}"
        if "@" in src:  # keep the digest reference meaningful by tagging with a short digest
            internal = internal.split(":")[0] + ":" + src.split("@sha256:")[1][:12]
        runner(["docker", "load", "-i", str(bundle / f["path"])])
        runner(["docker", "tag", src, internal])
        runner(["docker", "push", internal])
        mapping[src] = internal
    return mapping
