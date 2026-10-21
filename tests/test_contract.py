import io
import json
import zipfile
from pathlib import Path

import pytest

from dictbuilder.convert import Collection, rime_priority, rime_rows
from dictbuilder.format import extract_package, read_directory, validate_entry, validate_manifest


def candidate(base, units):
    return {"id": "r1", "priority": 0, "segments": [{"base": base, "annotate": True, "units": units}]}


def test_unicode_units_and_coarse_mapping():
    entry = {"surface": "𠮷漢\U000e0100", "candidates": [candidate("𠮷漢\U000e0100", ["khṳ́", "lóng"])]}
    assert validate_entry(entry, "uniform") == entry
    broken = {"surface": "重庆", "candidates": [candidate("重", ["chóng"])]}
    with pytest.raises(ValueError, match="重组"):
        validate_entry(broken, "uniform")
    for cost in [-1, True, float("nan")]:
        with pytest.raises(ValueError):
            validate_entry({**entry, "cost": cost}, "weighted")


def test_surface_deduplication_cost_aliases_and_complete_accounting():
    c = Collection()
    c.add("重庆", ["chóng", "qìng"], "a")
    c.add("重庆", ["chóng", "qìng"], "duplicate")
    c.add("重庆", ["zhòng", "qìng"], "alternative")
    c.add("重 庆", ["x"], "boundary")
    entries, score = c.finish({"重庆": 10}, ("s2t",))
    assert c.counts["input"] == 4 and c.counts["duplicate"] == 1 and c.counts["excluded"] == 1
    by_surface = {e["surface"]: e for e in entries}
    assert set(by_surface) == {"重庆", "重慶"}
    assert by_surface["重庆"]["cost"] == by_surface["重慶"]["cost"]
    assert len(by_surface["重庆"]["candidates"]) == 2
    assert score["unknownCost"] > by_surface["重庆"]["cost"]
    for e in entries:
        validate_entry(e, "weighted")


def test_rime_columns_defaults_percent_zero_and_missing_codes(tmp_path):
    path = tmp_path / "source.yaml"
    path.write_text("---\nname: test\ncolumns: [text, weight, code]\n...\n重\\t0%\\tzung6\n慶\\t\\thing3\n詞\\t3\n".replace("\\t", "\t"))
    rows = list(rime_rows(path))
    assert rows[0][1] == {"text": "重", "weight": "0%", "code": "zung6"}
    assert rows[-1][1].get("code", "") == ""
    assert rime_priority("", 100) == 100
    assert rime_priority("3%", 200) == 6
    assert rime_priority("0%", 200) == 0
    assert rime_priority("8", 200) == 8


def test_arbitrary_publisher_editable_counts_and_archive_boundary(tmp_path):
    manifest = {"formatVersion": 1, "id": "my-dictionary", "name": "私有包", "version": "same",
                "language": "custom", "region": "custom", "notation": "custom", "readingPolicy": "fixed",
                "entries": "entries.jsonl", "entryCount": 999, "scoring": {"mode": "uniform"}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("sources.json", "{}")
        z.writestr("licenses/NOTICE", "CC0 fixture")
        z.writestr("entries.jsonl", json.dumps({"surface": "新", "candidates": [candidate("新", ["edited"])]}))
    stream.seek(0)
    extract_package(stream, tmp_path / "ok")
    _, _, entries = read_directory(tmp_path / "ok")
    assert list(entries)[0]["candidates"][0]["segments"][0]["units"] == ["edited"]
    with zipfile.ZipFile(stream, "a") as z:
        z.writestr("../escape", "bad")
    stream.seek(0)
    with pytest.raises(ValueError):
        extract_package(stream, tmp_path / "bad")

def test_equal_graphemes_normalize_before_dedup_and_preserve_unequal_units():
    c = Collection()
    c.add("𠮷漢\U000e0100", ["ka-", "nâng"], "a")
    c.add("𠮷漢\U000e0100", ["ka-", "nâng"], "b", priority=3)
    c.add("人人", ["nâng"], "unequal")
    c.add("令", ["a", "b"], "single")
    entries, _ = c.finish()
    by = {e["surface"]: e["candidates"] for e in entries}
    assert len(by["𠮷漢\U000e0100"]) == 1
    assert by["𠮷漢\U000e0100"][0]["priority"] == 3
    assert by["𠮷漢\U000e0100"][0]["segments"] == [
        {"base": "𠮷", "annotate": True, "units": ["ka-"]},
        {"base": "漢\U000e0100", "annotate": True, "units": ["nâng"]}]
    assert by["人人"][0]["segments"][0]["base"] == "人人"
    assert by["令"][0]["segments"][0]["units"] == ["a", "b"]
