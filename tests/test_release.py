import importlib
import json

import pytest

release = importlib.import_module("dictbuilder.release")


@pytest.mark.parametrize("draft,target,message", [
    (False, "abc", "已公开"),
    (True, "other", "另一提交"),
])
def test_refuses_public_or_different_commit_release(monkeypatch, draft, target, message):
    tag = "preview-release"
    monkeypatch.setattr(release, "api", lambda *_: [[{
        "tag_name": tag, "draft": draft, "target_commitish": target,
    }]])
    with pytest.raises(ValueError, match=message):
        release.release(tag, "abc", "unused")


@pytest.mark.parametrize("tag", ["0.1.0", "preview-2026-10-21"])
def test_prepare_accepts_independent_tag_and_uploads_only_required_files(tmp_path, monkeypatch, tag):
    expected = release.expected_assets()
    # Release handoff fixture: ZIP structure is covered by build/contract tests.
    for name in expected:
        (tmp_path / name).write_bytes(b"built package")
    (tmp_path / "build-report.json").write_text("{}")
    monkeypatch.setattr(release, "api", lambda *_: [[]])
    calls, notes = [], []
    def run(command, **_):
        calls.append(command)
        if command[:3] == ["gh", "release", "create"]:
            notes.append(release.Path(command[command.index("--notes-file") + 1]).read_text())
    monkeypatch.setattr(release.subprocess, "run", run)
    release.release(tag, "abc", tmp_path)
    assert calls[0][:6] == ["gh", "release", "create", tag, "--target", "abc"]
    assert {release.Path(c[4]).name for c in calls[1:]} == set(expected)
    assert all(c[:4] == ["gh", "release", "upload", tag] for c in calls[1:])
    version = json.loads((release.ROOT / "packages.json").read_text())["version"]
    assert f"词典内容版本：{version}" in notes[0]


def test_publish_reviewed_draft_with_extra_attachment(tmp_path, monkeypatch):
    tag = "reviewed-preview"
    names = [*release.expected_assets(), "release-notes.txt"]
    existing = {"tag_name": tag, "draft": True, "target_commitish": "abc",
                "assets": [{"name": name} for name in names]}
    monkeypatch.setattr(release, "api", lambda *_: [[existing]])
    calls = []
    monkeypatch.setattr(release.subprocess, "run", lambda command, **_: calls.append(command))
    release.release(tag, "abc", tmp_path, publish=True)
    assert calls == [["gh", "release", "edit", tag, "--draft=false"]]
    existing["assets"].pop(0)
    calls.clear()
    with pytest.raises(ValueError, match="缺失"):
        release.release(tag, "abc", tmp_path, publish=True)
    assert not calls


def test_missing_build_output_is_reported(tmp_path):
    with pytest.raises(ValueError, match="缺少必需词典文件"):
        release.assets(tmp_path)
