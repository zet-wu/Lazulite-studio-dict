import importlib
import json
import zipfile
import pytest

release = importlib.import_module("dictbuilder.release")


@pytest.mark.parametrize("draft,target,message", [
    (False, "abc", "已经公开|已公开"),
    (True, "other", "另一提交"),
])
def test_refuses_public_or_different_commit_release(monkeypatch, draft, target, message):
    tag = "v" + json.loads((release.ROOT / "packages.json").read_text())["version"]
    def api(endpoint, *_):
        if "matching-refs" in endpoint:
            return []
        return [[{"tag_name": tag, "draft": draft, "target_commitish": target}]]
    monkeypatch.setattr(release, "api", api)
    with pytest.raises(ValueError, match=message):
        release.release(tag, "abc", "unused")


def test_refuses_mislabeled_asset_content_version(tmp_path):
    version = json.loads((release.ROOT / "packages.json").read_text())["version"]
    for name, ident in release.expected_assets().items():
        manifest = {"formatVersion": 1, "id": ident, "version": version + "-edited",
                    "name": "fixture", "language": "test", "region": "test", "notation": "test",
                    "entries": "entries.jsonl", "readingPolicy": "fixed", "scoring": {"mode": "uniform"}}
        entry = {"surface": "字", "candidates": [{"id": "1", "priority": 0,
                 "segments": [{"base": "字", "annotate": True, "units": ["test"]}]}]}
        with zipfile.ZipFile(tmp_path / name, "w") as z:
            for path, text in {"manifest.json": json.dumps(manifest), "entries.jsonl": json.dumps(entry),
                               "sources.json": "{}", "licenses/NOTICE": "Original CC0 test fixture."}.items():
                z.writestr(path, text)
    with pytest.raises(ValueError, match="内容版本"):
        release.assets(tmp_path)
