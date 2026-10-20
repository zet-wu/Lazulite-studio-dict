import argparse
import importlib.metadata
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from . import __version__
from .fetch import ROOT, fetch
from .format import extract_package, read_directory


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def validate(path):
    with tempfile.TemporaryDirectory() as tmp:
        extract_package(path, tmp)
        manifest, _, entries = read_directory(tmp)
        count = sum(1 for _ in entries)
    return {"id": manifest["id"], "version": manifest["version"], "entries": count}


def build():
    from .convert import cantonese, pinyin, prepare_puj, teochew
    paths = fetch()
    sources = json.loads((ROOT / "sources.json").read_text())
    config = json.loads((ROOT / "packages.json").read_text())
    dist = ROOT / "dist"
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    # Entire release is promoted only after all required packages pass.
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        staging = Path(tmp)
        accents = prepare_puj(paths)
        report = {}
        for package in config["packages"]:
            started = time.monotonic()
            ident = package["id"]
            print(f"Building {ident}", flush=True)
            if ident == "zh-pinyin":
                data, entries, scoring = pinyin(paths)
            elif ident == "yue-jyutping":
                data, entries, scoring = cantonese(paths)
            else:
                data, entries, scoring = teochew(paths, package["accent"], accents)
            manifest = {k: package[k] for k in ("id", "name", "language", "region", "notation")}
            manifest.update(formatVersion=1, version=config["version"], readingPolicy="fixed",
                            entries="entries.jsonl", entryCount=len(entries), scoring=scoring,
                            sources=package["sources"])
            notices = {name: sources[name] for name in package["sources"]}
            notices["build"] = {"converterVersion": __version__, "changes": "Fixed regional readings, structured segmentation, deduplication and optional cost/orthographic aliases."}
            contents = {"manifest.json": dump(manifest), "entries.jsonl": "".join(dump(e) for e in entries),
                        "sources.json": dump(notices)}
            for name in package["sources"]:
                for filename in sources[name]["licenses"]:
                    contents[f"licenses/{name}-{filename.replace('/', '-')}"] = (paths[name] / filename).read_text("utf-8")
            for filename in package["notices"]:
                contents[f"licenses/{filename}"] = (ROOT / "licenses" / filename).read_text("utf-8")
            if package.get("aliases"):
                metadata = importlib.metadata.distribution("opencc-python-reimplemented")
                license_path = next(p for p in metadata.files if p.name == "LICENSE.txt")
                contents["licenses/opencc-LICENSE.txt"] = metadata.locate_file(license_path).read_text()
                notices["opencc"] = {"version": metadata.version, "configurations": package["aliases"],
                                     "repository": "https://github.com/yichen0831/opencc-python"}
                contents["sources.json"] = dump(notices)
            filename = f"{ident}-{config['version']}.zip"
            archive = staging / filename
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for name, text in sorted(contents.items()):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, text.encode("utf-8"))
            validate(archive)
            report[ident] = {**dict(data.counts), "zipBytes": archive.stat().st_size,
                             "uncompressedBytes": sum(len(s.encode("utf-8")) for s in contents.values()),
                             "seconds": round(time.monotonic()-started, 3)}
            (reports / f"{ident}-exclusions.jsonl").write_text("".join(dump(x) for x in data.exclusions))
            (reports / f"{ident}-conflicts.jsonl").write_text("".join(dump(x) for x in data.alias_conflicts))
            print(json.dumps(report[ident], ensure_ascii=False), flush=True)
            del entries, data, contents
        if dist.exists():
            shutil.rmtree(dist)
        dist.mkdir()
        for path in staging.glob("*.zip"):
            path.rename(dist / path.name)
    (reports / "build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["fetch", "build", "validate", "report"])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "build":
        build()
    elif args.command == "validate":
        for path in args.paths or sorted((ROOT / "dist").glob("*.zip")):
            print(validate(path))
    else:
        print((ROOT / "reports/build.json").read_text())


if __name__ == "__main__":
    main()
