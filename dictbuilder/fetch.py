"""Fetch configured snapshots; content is editable and is not hash-locked."""
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fetch():
    sources = json.loads((ROOT / "sources.json").read_text())
    for name, source in sources.items():
        target = ROOT / ".cache" / name / source["commit"]
        if target.is_dir():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        archive = target.parent / "download.tar.gz"
        url = f"https://codeload.github.com/{source['repository']}/tar.gz/{source['commit']}"
        print(f"Fetching {name} {source['commit']}", flush=True)
        urllib.request.urlretrieve(url, archive)
        staging = target.parent / "extract"
        staging.mkdir(exist_ok=True)
        try:
            with tarfile.open(archive) as tar:
                tar.extractall(staging, filter="data")
            children = list(staging.iterdir())
            if len(children) != 1:
                raise ValueError("Expected a single archive root")
            children[0].rename(target)
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging)
    return {name: ROOT / ".cache" / name / source["commit"] for name, source in sources.items()}


if __name__ == "__main__":
    fetch()
