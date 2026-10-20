import importlib
import json
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
