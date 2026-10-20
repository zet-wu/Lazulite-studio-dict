"""Checks against actual complete outputs; invoke after build --all."""
import json
import zipfile

from dictbuilder.fetch import ROOT
from dictbuilder.release import assets
from dictbuilder.convert import prepare_puj, teochew
from dictbuilder.fetch import fetch


def entries(name):
    config = json.loads((ROOT / "packages.json").read_text())
    with zipfile.ZipFile(ROOT / "dist" / f"{name}-{config['version']}.zip") as z:
        return {e["surface"]: e for e in map(json.loads, z.read("entries.jsonl").splitlines())}


def test_complete_release_and_accounting():
    assert len(assets(ROOT / "dist")) == 4
    report = json.loads((ROOT / "reports/build.json").read_text())
    for result in report.values():
        assert result["input"] == result["output"] + result.get("duplicate", 0) + result.get("excluded", 0)
        assert result["surfaces"] >= result["native_surfaces"]


def test_regional_rules_produce_real_differences_and_keep_overrides():
    a, b = entries("teochew-chaozhou-puj"), entries("teochew-shantou-puj")
    assert set(a) == set(b)
    assert any(a[s] != b[s] for s in a)
    # Source contains iak -> iek only for the Chaozhou rules.
    def units(e):
        return {u for c in e["candidates"] for s in c["segments"] for u in s["units"]}
    assert "liék" in units(a["䴕"]) and "liák" in units(b["䴕"])
    assert all("cost" not in e for e in a.values())


def test_explicit_regional_phrase_is_not_converted_twice_and_keeps_light_marker(tmp_path):
    accents = prepare_puj(fetch())
    data = tmp_path / "data"
    data.mkdir()
    (data / "entries.yml").write_text("[]\n")
    # Original contract fixture, not a production dictionary correction.
    (data / "phrases.yml").write_text(
        "- 测试|iau1--nang5|||:\n"
        "    accents:\n"
        "      - ChaoZhou_FuCheng: [iau1--nang5]\n"
        "- 本词|iau1-nang5|||:\n", encoding="utf-8")
    collection, result, _ = teochew({"pujbase": tmp_path, "pujcorpora": tmp_path}, "ChaoZhou_FuCheng", accents)
    values = {e["surface"]: e["candidates"][0]["segments"][0]["units"] for e in result}
    assert values["测试"] == ["iau--", "nâng"]
    assert values["本词"][0] == "ieu-"
    assert collection.counts["regional_phrase_records"] == 1
