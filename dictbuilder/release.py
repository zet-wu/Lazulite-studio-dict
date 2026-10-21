"""Prepare drafts, or explicitly publish a reviewed draft. Public assets are immutable."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from .fetch import ROOT


def api(endpoint, *args):
    return json.loads(subprocess.check_output(["gh", "api", endpoint, *args], text=True))


def expected_assets():
    config = json.loads((ROOT / "packages.json").read_text())
    return {f"{p['id']}-{config['version']}.zip": p["id"] for p in config["packages"]}


def assets(directory):
    # The build has validated these packages. The handoff only needs files.
    files = [Path(directory) / name for name in sorted(expected_assets())]
    missing = [p.name for p in files if not p.is_file()]
    if missing:
        raise ValueError("缺少必需词典文件：" + ", ".join(missing))
    return files


def release(tag, commit, directory, publish=False):
    # The source job resolves and validates the Git ref once for the workflow.
    config = json.loads((ROOT / "packages.json").read_text())
    pages = api("repos/{owner}/{repo}/releases", "--paginate", "--slurp")
    existing = next((r for page in pages for r in page if r["tag_name"] == tag), None)
    if existing and not existing["draft"]:
        raise ValueError("版本已公开；请使用新标签")
    if existing and existing["target_commitish"] != commit:
        raise ValueError("不能把另一提交的产物写入同一草稿")
    if publish:
        if not existing or not set(expected_assets()).issubset(a["name"] for a in existing["assets"]):
            raise ValueError("草稿或必需词典文件缺失")
        subprocess.run(["gh", "release", "edit", tag, "--draft=false"], check=True)
        return
    files = assets(directory)
    if not existing:
        notes = f"""Lazulite Studio 注音词典 {tag}

源码提交：{commit}
词典内容版本：{config['version']}

四个 ZIP 均可直接在 Studio 的「注音词典」中导入，无需解压。
汉语拼音和粤语粤拼使用外部权重增强；潮州府城与汕头市区为独立的固定口音包。
读音不计算连续变调。来源、署名、许可与转换说明保存在每个 ZIP 内。
数据更新独立于 Studio；符合格式 v1 的自定义修改包也可导入。

生成工具、来源版本和构建方式见本仓库 README；数据许可按包内具体来源分别适用。
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.txt"
            path.write_text(notes, encoding="utf-8")
            subprocess.run(["gh", "release", "create", tag, "--target", commit, "--draft",
                            "--title", f"注音词典 {tag}", "--notes-file", str(path)], check=True)
    for path in files:
        subprocess.run(["gh", "release", "upload", tag, str(path), "--clobber"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default="dist")
    parser.add_argument("--publish-reviewed", action="store_true")
    args = parser.parse_args()
    release(os.environ["RELEASE_TAG"], os.environ["RELEASE_COMMIT"], args.assets, args.publish_reviewed)
