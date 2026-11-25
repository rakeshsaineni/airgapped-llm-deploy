from pathlib import Path

from airgap.bundle import build, load_and_push, verify
from airgap.cli import main
from airgap.lint import lint
from airgap.manifests import images, load

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def rules(findings, severity="error"):
    return {f.rule for f in findings if f.severity == severity}


def test_hardened_manifest_passes_airgap_profile():
    docs = load((FIX / "good.yaml").read_text())
    assert not rules(lint(docs, "airgap", "registry.plant.internal:5000"))


def test_risky_manifest_is_caught():
    found = rules(lint(load((FIX / "bad.yaml").read_text()), "airgap", "registry.plant.internal:5000"))
    assert {"mutable-tag", "registry", "pull-policy", "resources", "non-root", "privilege-escalation", "privileged",
            "capabilities", "host-namespaces", "host-path", "network-policy", "inline-secret"} <= found


def test_tags_are_fine_by_default_but_not_air_gapped():
    doc = load((FIX / "good.yaml").read_text())
    doc[0]["spec"]["template"]["spec"]["containers"][0]["image"] = "ghcr.io/x/app:1.2.3"
    assert "digest-pin" not in rules(lint(doc))
    assert "digest-pin" in rules(lint(doc, "airgap"))


def test_image_listing():
    assert images(load((FIX / "bad.yaml").read_text())) == ["someorg/llm-app:latest"]


def fake_docker(calls):
    def runner(cmd):
        calls.append(cmd)
        if cmd[:2] == ["docker", "save"]:
            Path(cmd[3]).write_bytes(f"fake image {cmd[4]}".encode())
    return runner


def test_bundle_verify_detects_tampering_and_push_retags(tmp_path):
    calls = []
    imgs = ["ghcr.io/rakeshsaineni/insurance-rag-agent:0.1.0", "docker.io/ollama/ollama:0.5.7"]
    m = build(imgs, ROOT / "charts" / "llm-stack", tmp_path / "b", runner=fake_docker(calls))
    assert len(m["files"]) == 3 and verify(tmp_path / "b") == []
    mapping = load_and_push(tmp_path / "b", "registry.plant.internal:5000", runner=fake_docker(calls))
    assert mapping["docker.io/ollama/ollama:0.5.7"] == "registry.plant.internal:5000/ollama/ollama:0.5.7"
    assert ["docker", "push", "registry.plant.internal:5000/rakeshsaineni/insurance-rag-agent:0.1.0"] in calls
    tar = next((tmp_path / "b" / "images").glob("*ollama*"))
    tar.write_bytes(b"swapped by someone")
    assert any("checksum mismatch" in p for p in verify(tmp_path / "b"))
    (tmp_path / "b" / "extra.sh").write_text("echo hi")
    assert any("unexpected file" in p for p in verify(tmp_path / "b"))


def test_cli_lint_exit_codes(capsys):
    assert main(["lint", str(FIX / "good.yaml")]) == 0
    assert main(["lint", str(FIX / "bad.yaml")]) == 1
    assert "inline-secret" in capsys.readouterr().out


def test_values_files_are_valid_yaml():
    import yaml

    for f in ("values.yaml", "values-airgap.yaml"):
        assert yaml.safe_load((ROOT / "charts" / "llm-stack" / f).read_text())
