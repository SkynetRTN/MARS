"""AUD-02 gates immutable scanner references and exact validation-tool pins."""

from pathlib import Path
import re


def test_ci_and_release_twine_versions_are_exact_and_identical():
    root = Path(__file__).resolve().parents[1] / ".github/workflows"
    pins = [re.findall(r"uvx twine@(\d+\.\d+\.\d+) check --strict", (root/name).read_text())
            for name in ("ci.yml", "release.yml")]
    assert pins == [["6.2.0"], ["6.2.0"]]


def test_both_secret_scans_use_the_verified_multiarch_digest():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/secret-scan.yml"
    text = path.read_text()
    refs = re.findall(r"zricethezav/gitleaks@sha256:([a-f0-9]{64})", text)
    assert refs == ["c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"] * 2
    assert "zricethezav/gitleaks:v" not in text


def test_actionlint_uses_its_verified_immutable_digest():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/workflow-safety.yml"
    text = path.read_text()
    assert "rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667" in text
    assert "rhysd/actionlint:" not in text
