"""Public dictionary v1 boundary validation. No content fingerprints."""
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

import regex

HARD_BOUNDARIES = frozenset(',，、.。!！?？:：;；()（）[]［］{}｛｝「」『』【】〈〉《》“”"…⋯')
MAX_BYTES = 512 * 1024 * 1024
MAX_LINE = 1024 * 1024


def hard_boundary(text):
    return any(c.isspace() or c in HARD_BOUNDARIES for c in text)


def nonempty(value, maximum=1000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum and '\x00' not in value


def integer(value):
    return type(value) is int and abs(value) <= 2**53 - 1


def read_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"重复 JSON 字段：{key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def validate_manifest(m):
    if not isinstance(m, dict) or m.get("formatVersion") != 1 or type(m["formatVersion"]) is not int:
        raise ValueError("仅支持词典格式 v1")
    if not isinstance(m.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", m["id"]):
        raise ValueError("词典 ID 无效")
    if any(not nonempty(m.get(k)) for k in ("version", "name", "language", "region", "notation")):
        raise ValueError("词典说明不完整")
    if m.get("entries") != "entries.jsonl" or m.get("readingPolicy") != "fixed":
        raise ValueError("需要固定读音与 entries.jsonl")
    score = m.get("scoring")
    if not isinstance(score, dict) or score.get("mode") not in ("uniform", "weighted"):
        raise ValueError("评分模式无效")
    if score["mode"] == "weighted" and (not integer(score.get("unknownCost")) or score["unknownCost"] <= 0):
        raise ValueError("未命中代价无效")
    return m


def validate_entry(entry, mode):
    if not isinstance(entry, dict) or not nonempty(entry.get("surface"), 1024) or hard_boundary(entry["surface"]):
        raise ValueError("词条正文为空、过长或跨句读边界")
    if mode == "weighted":
        if not integer(entry.get("cost")) or entry["cost"] < 0:
            raise ValueError("增强模式需要非负整数 cost")
    elif "cost" in entry:
        raise ValueError("基础模式不能携带 cost")
    candidates = entry.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 1024:
        raise ValueError("读音候选无效")
    ids = set()
    ends = {0, *(m.end() for m in regex.finditer(r"\X", entry["surface"]))}
    for candidate in candidates:
        if not isinstance(candidate, dict) or not nonempty(candidate.get("id")) or candidate["id"] in ids or not integer(candidate.get("priority")):
            raise ValueError("候选标识或优先级无效")
        ids.add(candidate["id"])
        segments = candidate.get("segments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= 1024:
            raise ValueError("正文对应段无效")
        offset, bases = 0, []
        for segment in segments:
            if not isinstance(segment, dict) or not nonempty(segment.get("base"), 1024) or type(segment.get("annotate")) is not bool:
                raise ValueError("正文对应段字段无效")
            units = segment.get("units")
            if not isinstance(units, list) or len(units) > 1024 or any(not nonempty(u, 4096) for u in units):
                raise ValueError("读音单元无效")
            if bool(units) != segment["annotate"]:
                raise ValueError("标注段须有读音，不标注段须为空列表")
            bases.append(segment["base"])
            offset += len(segment["base"])
            if offset not in ends:
                raise ValueError("正文对应段切断字素")
        if "".join(bases) != entry["surface"]:
            raise ValueError("对应段无法重组正文")
    return entry


def read_directory(directory):
    directory = Path(directory)
    paths = list(directory.rglob("*"))
    if any(p.is_symlink() for p in paths) or sum(p.stat().st_size for p in paths if p.is_file()) > MAX_BYTES:
        raise ValueError("词典资源越界或过大")
    manifest = validate_manifest(read_json((directory / "manifest.json").read_text("utf-8")))
    sources = read_json((directory / "sources.json").read_text("utf-8"))
    if not isinstance(sources, (list, dict)) or not any(p.is_file() for p in (directory / "licenses").rglob("*")):
        raise ValueError("来源或许可信息缺失")
    seen = set()
    def entries():
        with (directory / "entries.jsonl").open("rb") as stream:
            while line := stream.readline(MAX_LINE + 1):
                if len(line) > MAX_LINE:
                    raise ValueError("词条记录过大")
                entry = validate_entry(read_json(line.decode("utf-8")), manifest["scoring"]["mode"])
                if entry["surface"] in seen:
                    raise ValueError("正文重复，应在同一词条保留全部候选")
                seen.add(entry["surface"])
                if len(seen) > 2_000_000:
                    raise ValueError("词条数量超过资源限制")
                yield entry
        if not seen:
            raise ValueError("词典没有可用词条")
    return manifest, sources, entries()


def extract_package(archive, target):
    target = Path(target)
    with zipfile.ZipFile(archive) as z:
        files = z.infolist()
        if len(files) > 256 or sum(f.file_size for f in files) > MAX_BYTES:
            raise ValueError("压缩包超过资源限制")
        names = set()
        for f in files:
            if f.flag_bits & 1:
                raise ValueError("词典压缩包不能加密")
            name = f.filename
            path = PurePosixPath(name)
            if (not name or "\\" in name or ":" in name or "\x00" in name or path.is_absolute()
                    or any(p in ("", ".", "..") for p in name.rstrip("/").split("/"))
                    or stat.S_ISLNK(f.external_attr >> 16) or name.casefold() in names):
                raise ValueError("压缩包路径无效或重复")
            names.add(name.casefold())
            if not (name in ("manifest.json", "entries.jsonl", "sources.json") or name.startswith("licenses/")):
                raise ValueError("压缩包含格式外文件")
        if not {"manifest.json", "entries.jsonl", "sources.json"}.issubset(names):
            raise ValueError("压缩包缺少必需文件")
        z.extractall(target)
    return target
