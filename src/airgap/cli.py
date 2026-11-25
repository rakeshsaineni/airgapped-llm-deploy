"""airgap images | lint | bundle | verify | push   (reads `helm template` output)"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bundle as b
from .lint import lint
from .manifests import images, load


def _read(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="airgap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("images", help="list images in rendered manifests")
    i.add_argument("manifests")
    li = sub.add_parser("lint", help="policy checks on rendered manifests")
    li.add_argument("manifests")
    li.add_argument("--profile", choices=["standard", "airgap"], default="standard")
    li.add_argument("--registry", help="internal registry every image must come from (airgap profile)")
    bu = sub.add_parser("bundle", help="save images + chart + checksums for transfer")
    bu.add_argument("manifests")
    bu.add_argument("--chart", default="charts/llm-stack")
    bu.add_argument("--out", default="bundle")
    ve = sub.add_parser("verify", help="check a bundle against its checksums")
    ve.add_argument("bundle")
    pu = sub.add_parser("push", help="load, retag and push a verified bundle to the internal registry")
    pu.add_argument("bundle")
    pu.add_argument("--registry", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "images":
        print("\n".join(images(load(_read(a.manifests)))))
    elif a.cmd == "lint":
        findings = lint(load(_read(a.manifests)), a.profile, a.registry)
        for f in findings:
            print(f"{f.severity.upper():7} {f.rule:22} {f.resource:45} {f.message}")
        errors = sum(f.severity == "error" for f in findings)
        print(f"\n{errors} error(s), {len(findings) - errors} warning(s)")
        return 1 if errors else 0
    elif a.cmd == "bundle":
        m = b.build(images(load(_read(a.manifests))), Path(a.chart), Path(a.out))
        print(json.dumps(m, indent=1))
    elif a.cmd == "verify":
        problems = b.verify(Path(a.bundle))
        print("\n".join(problems) or "bundle OK: all checksums match")
        return 1 if problems else 0
    elif a.cmd == "push":
        print(json.dumps(b.load_and_push(Path(a.bundle), a.registry), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
