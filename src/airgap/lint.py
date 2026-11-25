"""Policy checks for manifests going into restricted environments.

Each rule returns findings with a severity. `--profile airgap` makes registry and digest
rules errors, because a disconnected cluster can't pull from the internet and a mutable
tag there is a supply-chain risk."""

from __future__ import annotations

from dataclasses import dataclass

from .manifests import containers, pod_spec


@dataclass
class Finding:
    severity: str  # error | warning
    rule: str
    resource: str
    message: str


def _ref(d: dict) -> str:
    return f"{d['kind']}/{d.get('metadata', {}).get('name', '?')}"


def lint(docs: list[dict], profile: str = "standard", internal_registry: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    strict = profile == "airgap"
    workloads = [d for d in docs if pod_spec(d) is not None]
    for d in workloads:
        ref, ps = _ref(d), pod_spec(d)
        psc = ps.get("securityContext", {}) or {}
        if ps.get("automountServiceAccountToken") is not False:
            out.append(Finding("warning", "sa-token", ref, "automountServiceAccountToken should be false"))
        if ps.get("hostNetwork") or ps.get("hostPID"):
            out.append(Finding("error", "host-namespaces", ref, "hostNetwork/hostPID are not allowed"))
        for v in ps.get("volumes", []) or []:
            if "hostPath" in v:
                out.append(Finding("error", "host-path", ref, f"hostPath volume '{v.get('name')}' is not allowed"))
        for c in containers(d):
            cref = f"{ref}:{c.get('name')}"
            img = c.get("image", "")
            if "@sha256:" not in img:
                tag = img.rsplit(":", 1)[1] if ":" in img.split("/")[-1] else ""
                if tag in ("", "latest"):
                    out.append(Finding("error", "mutable-tag", cref, f"image '{img}' has no tag or uses latest"))
                elif strict:
                    out.append(Finding("error", "digest-pin", cref, f"image '{img}' must be pinned by digest"))
            if strict and internal_registry and not img.startswith(internal_registry + "/"):
                out.append(Finding("error", "registry", cref, f"image '{img}' is not from {internal_registry}"))
            if strict and c.get("imagePullPolicy") == "Always":
                out.append(Finding("error", "pull-policy", cref, "imagePullPolicy Always can't work offline"))
            res = c.get("resources", {}) or {}
            if not res.get("requests") or not res.get("limits"):
                out.append(Finding("error", "resources", cref, "set resource requests and limits"))
            if not c.get("readinessProbe") or not c.get("livenessProbe"):
                out.append(Finding("warning", "probes", cref, "add readiness and liveness probes"))
            sc = c.get("securityContext", {}) or {}
            if not (sc.get("runAsNonRoot") or psc.get("runAsNonRoot")):
                out.append(Finding("error", "non-root", cref, "runAsNonRoot must be true"))
            if sc.get("allowPrivilegeEscalation") is not False:
                out.append(Finding("error", "privilege-escalation", cref, "allowPrivilegeEscalation must be false"))
            if sc.get("privileged"):
                out.append(Finding("error", "privileged", cref, "privileged containers are not allowed"))
            if "ALL" not in ((sc.get("capabilities") or {}).get("drop") or []):
                out.append(Finding("error", "capabilities", cref, "drop ALL capabilities"))
            if not sc.get("readOnlyRootFilesystem"):
                out.append(Finding("warning", "read-only-fs", cref, "use a read-only root filesystem"))
    kinds = {d["kind"] for d in docs}
    if workloads and "NetworkPolicy" not in kinds:
        out.append(Finding("error", "network-policy", "release", "no NetworkPolicy: pods can talk to anything"))
    multi = [d for d in workloads if d["kind"] == "Deployment" and (d["spec"].get("replicas") or 1) > 1]
    if multi and "PodDisruptionBudget" not in kinds:
        out.append(Finding("warning", "pdb", "release", "multi-replica Deployments without a PodDisruptionBudget"))
    for d in docs:
        if d["kind"] == "Secret" and (d.get("data") or d.get("stringData")):
            out.append(Finding("error", "inline-secret", _ref(d), "secret values must not be in manifests"))
    return out
