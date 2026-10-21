"""Source adapters. All language-specific work ends at build time."""
import json
import math
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import yaml
import regex
from opencc import OpenCC

from .format import hard_boundary


def segments(surface, units):
    characters = regex.findall(r"\X", surface)
    if len(characters) == len(units):
        return [{"base": char, "annotate": True, "units": [unit]} for char, unit in zip(characters, units)]
    return [{"base": surface, "annotate": True, "units": units}]


class Collection:
    def __init__(self):
        self.entries = {}
        self.counts = Counter()
        self.exclusions = []
        self.alias_conflicts = []

    def add(self, surface, units, origin, *, priority=0, require_han=True):
        self.counts["input"] += 1
        if not surface or require_han and not regex.search(r"\p{Script=Han}|〇", surface):
            reason = "no_written_form"
        elif hard_boundary(surface):
            reason = "hard_boundary"
        elif not units or any(not u.strip() for u in units):
            reason = "no_reading"
        else:
            reason = None
        if reason:
            self.counts["excluded"] += 1
            self.exclusions.append({"origin": origin, "surface": surface, "reason": reason})
            return
        segs = segments(surface, [unicodedata.normalize("NFC", u) for u in units])
        key = json.dumps(segs, ensure_ascii=False, sort_keys=True)
        candidates = self.entries.setdefault(surface, {})
        if key in candidates:
            self.counts["duplicate"] += 1
            candidates[key]["priority"] = max(candidates[key]["priority"], priority)
        else:
            self.counts["output"] += 1
            candidates[key] = {"priority": priority, "segments": segs}

    def finish(self, frequencies=None, aliases=()):
        native = self.entries
        native_cost = {}
        mode = "uniform"
        unknown = 1
        converters = [OpenCC(c) for c in aliases]
        variants = {}
        reverse = {}
        for surface in native:
            variants[surface] = {c.convert(surface) for c in converters} - {surface}
            for alias in variants[surface]:
                reverse.setdefault(alias, set()).add(surface)
        if frequencies is not None:
            mode = "weighted"
            mass = {}
            for surface in native:
                freq = frequencies.get(surface, 0)
                if freq > 0:
                    self.counts["frequency_exact"] += 1
                else:
                    values = {frequencies[a] for a in variants[surface]
                              if frequencies.get(a, 0) > 0 and reverse[a] == {surface}}
                    if len(values) == 1:
                        freq = values.pop()
                        self.counts["frequency_alias"] += 1
                    else:
                        self.counts["frequency_missing"] += 1
                mass[surface] = max(freq, 1)
            total = sum(mass.values()) + 1
            unknown = round(math.log(total) * 1_000_000)
            native_cost = {s: round(-math.log(m / total) * 1_000_000) for s, m in mass.items()}
        output = {s: dict(c) for s, c in native.items()}
        costs = dict(native_cost)
        for surface, forms in variants.items():
            for alias in sorted(forms):
                if hard_boundary(alias):
                    continue
                target = output.setdefault(alias, {})
                for c in native[surface].values():
                    bases = [seg["base"] for seg in c["segments"]]
                    # Preserve fine correspondence only when whole-word conversion
                    # agrees with independently converted segment boundaries.
                    chosen = next((conv for conv in converters if conv.convert(surface) == alias), None)
                    converted = [chosen.convert(base) for base in bases]
                    if "".join(converted) == alias:
                        segs = [part for seg, base in zip(c["segments"], converted)
                                for part in segments(base, seg["units"])]
                    else:
                        segs = segments(alias, [u for seg in c["segments"] for u in seg["units"]])
                    key = json.dumps(segs, ensure_ascii=False, sort_keys=True)
                    if target and key not in target:
                        self.alias_conflicts.append({"surface": surface, "alias": alias, "reason": "reading_or_mapping"})
                    if key not in target:
                        target[key] = {**c, "segments": segs}
                    else:
                        target[key]["priority"] = max(target[key]["priority"], c["priority"])
                if mode == "weighted":
                    cost = native_cost[surface]
                    if alias in costs and costs[alias] != cost:
                        self.alias_conflicts.append({"surface": surface, "alias": alias, "reason": "cost"})
                    # Native cost is authoritative; colliding generated aliases
                    # use the least assertive source cost, never sum frequencies.
                    if alias not in native:
                        costs[alias] = max(cost, costs.get(alias, 0))
        result = []
        for surface, candidates in sorted(output.items()):
            values = [{"id": f"r{i+1}", **c} for i, (_, c) in enumerate(sorted(candidates.items()))]
            result.append({"surface": surface, **({"cost": costs[surface]} if mode == "weighted" else {}), "candidates": values})
            for c in values:
                self.counts["fine_candidates" if all(len(s["base"]) == 1 for s in c["segments"]) else "coarse_candidates"] += 1
        self.counts.update({"native_surfaces": len(native), "surfaces": len(result), "alias_surfaces": len(output)-len(native),
                            "alias_conflicts": len(self.alias_conflicts),
                            "multi_candidate_surfaces": sum(len(v) > 1 for v in output.values())})
        assert self.counts["input"] == self.counts["output"] + self.counts["duplicate"] + self.counts["excluded"]
        return result, {"mode": mode, **({"unknownCost": unknown, "rule": "negative-log-v1"} if mode == "weighted" else {})}


def lines(path):
    for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if line:
            yield n, line


def pinyin(paths):
    data = Collection()
    defaults = {}
    # Only the explicitly documented common-reading table supplies priorities.
    for raw in (paths["pinyin"] / "kMandarin_8105.txt").read_text("utf-8").splitlines():
        if any(marker in raw for marker in ("?", "->", "<-")):
            continue
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, reading = line.split(":", 1)
        if re.fullmatch(r"U\+[0-9A-Fa-f]+", key) and re.fullmatch(r"[a-züêā-ǜḿńňǹ]+", reading.strip()):
            defaults[chr(int(key[2:], 16))] = reading.strip()
    for n, line in lines(paths["pinyin"] / "pinyin.txt"):
        data.counts["character_source_records"] += 1
        key, readings = line.split(":", 1)
        surface = chr(int(key[2:], 16))
        for reading in readings.strip().split(","):
            data.add(surface, [reading], f"pinyin.txt:{n}", priority=int(defaults.get(surface) == reading), require_han=False)
    for n, line in lines(paths["phrases"] / "large_pinyin.txt"):
        data.counts["phrase_source_records"] += 1
        surface, reading = line.split(":", 1)
        data.add(surface, reading.split(), f"large_pinyin.txt:{n}")
    frequencies = {}
    for line in (paths["jieba"] / "jieba/dict.txt").read_text("utf-8").splitlines():
        data.counts["frequency_source_records"] += 1
        surface, freq, *_ = line.split()
        frequencies[surface] = int(freq)
    return data, *data.finish(frequencies, ("s2t", "t2s"))


def rime_rows(path):
    text = path.read_text("utf-8")
    header, body = text.split("...", 1)
    meta = yaml.safe_load(header)
    columns = meta.get("columns", ["text", "code", "weight"])
    if not {"text", "code"}.issubset(columns) or len(set(columns)) != len(columns):
        raise ValueError("Unsupported Rime columns")
    for n, raw in enumerate(body.splitlines(), header.count("\n") + 2):
        value = raw.split("#", 1)[0].strip()
        if not value:
            continue
        values = value.split("\t")
        if len(values) > len(columns):
            raise ValueError(f"Unexpected columns: {path.name}:{n}")
        yield n, dict(zip(columns, values))


def rime_priority(weight, base):
    if not weight:
        return base
    if weight.endswith("%"):
        return round(base * float(weight[:-1]) / 100)
    return round(float(weight))


def cantonese(paths):
    data = Collection()
    frequencies = {}
    for _, line in lines(paths["cantonese"] / "essay-cantonese.txt"):
        surface, freq = line.split("\t")
        frequencies[surface] = int(freq)
    for filename in ("jyut6ping3.chars.dict.yaml", "jyut6ping3.words.dict.yaml"):
        for n, row in rime_rows(paths["cantonese"] / filename):
            data.counts["reading_source_records"] += 1
            surface, code = row["text"], row.get("code", "")
            units = code.split()
            if units and not all(re.fullmatch(r"[a-z]+[1-6]", u) for u in units):
                data.counts["input"] += 1
                data.counts["excluded"] += 1
                data.exclusions.append({"origin": f"{filename}:{n}", "surface": surface, "code": code, "reason": "unsupported_code"})
                continue
            data.add(surface, units, f"{filename}:{n}",
                     priority=rime_priority(row.get("weight", ""), frequencies.get(surface, 0)))
    return data, *data.finish(frequencies, ("t2s",))


def prepare_puj(paths):
    root = paths["pujbase"]
    target = root / "data/pujcorpora"
    if not (target / "std").exists():
        shutil.copytree(paths["pujcorpora"], target, dirs_exist_ok=True)
    lib = root / "libpuj"
    subprocess.run([sys.executable, "-m", "grpc_tools.protoc", f"-I{lib}", f"--python_out={lib}",
                    *[str(lib / f"{name}.proto") for name in ("entries", "accents", "phrases")]], check=True)
    sys.path[:0] = [str(root), str(lib)]
    subprocess.run([sys.executable, "generate_entries_db.py"], cwd=lib, check=True)
    from libpuj.convert import load_accents
    return load_accents(root / "dist/accents.pb")


def teochew(paths, accent_id, accents):
    from libpuj.pujcommon import Pronunciation, Sentence
    data = Collection()
    accent = accents[accent_id]
    entries = yaml.safe_load((paths["pujbase"] / "data/entries.yml").read_text("utf-8"))
    for chars, readings in entries:
        for raw, details in readings.items():
            data.counts["character_source_records"] += 1
            initial, final, tone, category, freq, ref = raw.split(",")
            details = details or {}
            standard = Pronunciation("" if initial == "0" else initial, final, int(tone))
            nasal = details.get("nasalize")
            if nasal == "always" or isinstance(nasal, list) and accent_id in nasal:
                standard.final += "nn"
            override = details.get("aka_replace", {}).get(accent_id)
            alternate = details.get("aka", {}).get(accent_id)
            if override or alternate:
                data.counts["regional_character_records"] += 1
            prons = [] if override else [accent.fuzzy_result(standard)]
            for variants in (override, alternate):
                if variants:
                    for raw_pron in variants.split("/"):
                        a, b, c = raw_pron.split(",")
                        prons.append(Pronunciation("" if a == "0" else a, b, int(c)))
            for surface in sorted(set(chars.split(","))):
                for pron in prons:
                    data.add(surface, [pron.to_written()], f"entries.yml:{chars}:{raw}",
                             priority={0: 3, 1: 2, 2: 1, 3: 0, -1: 0}[int(freq)])
    files = sorted((paths["pujcorpora"] / "std").rglob("*.std.yml")) + [paths["pujbase"] / "data/phrases.yml"]
    for path in files:
        for n, record in enumerate(yaml.safe_load(path.read_text("utf-8")), 1):
            data.counts["phrase_source_records"] += 1
            key, details = next(iter(record.items()))
            surfaces, readings, _cmn, _classes, _tags = key.split("|")
            details = details or {}
            regional = [v for mapping in details.get("accents", []) for k, v in mapping.items() if k == accent_id]
            if regional:
                data.counts["regional_phrase_records"] += 1
            values = [r for group in regional for r in group] if regional else readings.split("/")
            for reading in values:
                units, separators, prefix = [], [], []
                def word(raw, hyphens):
                    pron = Pronunciation.from_combination(raw)
                    if not regional:
                        pron = accent.fuzzy_result(pron)
                    output = pron.to_written()
                    if not output:
                        raise ValueError(f"Unconvertible pronunciation {path.name}:{n}: {raw}")
                    units.append("".join(prefix) + output)
                    prefix.clear()
                def separator(value):
                    separators.append(value)
                    # PUJ hyphens encode source-provided linking/light-tone
                    # notation. Preserve them on a real syllable, never as a
                    # separate empty-reading unit; do not calculate sandhi.
                    if units:
                        units[-1] += value
                    else:
                        prefix.append(value)
                Sentence.for_each_word_in_sentence(reading, word, separator)
                if any(not re.fullmatch(r"[\s-]*", s) for s in separators):
                    raise ValueError(f"Unsupported pronunciation separator: {path.name}:{n}: {reading}")
                for surface in surfaces.split("/"):
                    data.add(surface, units, f"{path.name}:{n}")
    return data, *data.finish()
