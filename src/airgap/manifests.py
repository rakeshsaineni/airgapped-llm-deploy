"""Read rendered Kubernetes manifests and pull out what matters for air-gapped installs."""

from __future__ import annotations

from collections.abc import Iterator

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}


def load(text: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(text) if isinstance(d, dict) and d.get("kind")]


def pod_spec(doc: dict) -> dict | None:
    if doc.get("kind") not in WORKLOAD_KINDS:
        return None
    spec = doc.get("spec", {})
    if doc["kind"] == "CronJob":
        spec = spec.get("jobTemplate", {}).get("spec", {})
    return spec.get("template", {}).get("spec")


def containers(doc: dict) -> Iterator[dict]:
    ps = pod_spec(doc) or {}
    yield from ps.get("initContainers", []) or []
    yield from ps.get("containers", []) or []


def images(docs: list[dict]) -> list[str]:
    return sorted({c["image"] for d in docs for c in containers(d) if c.get("image")})
