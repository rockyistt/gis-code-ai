import json
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
SYN_PATH = ROOT / "data/processed/synonym_map_initial.json"

# Check for anonymized data first, fall back to regular data
STEP_ANON = ROOT / "data/processed/step_level_instructions_weighted_anonymized.jsonl"
STEP_REGULAR = ROOT / "data/processed/step_level_instructions_weighted.jsonl"
STEP_IN = STEP_ANON if STEP_ANON.exists() else STEP_REGULAR
STEP_OUT = ROOT / "data/processed/step_level_instructions_normalized.jsonl"

FILE_ANON = ROOT / "data/processed/file_level_instructions_aggregated_anonymized.jsonl"
FILE_REGULAR = ROOT / "data/processed/file_level_instructions_aggregated.jsonl"
FILE_IN = FILE_ANON if FILE_ANON.exists() else FILE_REGULAR
FILE_OUT = ROOT / "data/processed/file_level_instructions_aggregated_normalized.jsonl"

WORD_SPLIT_RE = re.compile(r"[A-Za-z0-9_]+|[^A-Za-z0-9_]+")
DIGIT_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}


def load_alias_map(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    alias_map: Dict[str, str] = {}
    for entry in data:
        canonical = entry["canonical"].lower()
        alias_map[canonical] = canonical
        for a in entry.get("aliases", []):
            alias_map[a.lower()] = canonical
    return alias_map


def normalize_text(text: str, alias_map: Dict[str, str]) -> str:
    parts: List[str] = []
    for tok in WORD_SPLIT_RE.findall(text):
        if tok.isalnum() or tok.replace("_", "").isalnum():
            lower = tok.lower()
            lower = DIGIT_WORDS.get(lower, lower)
            norm = alias_map.get(lower, lower)
            parts.append(norm)
        else:
            parts.append(tok)
    return "".join(parts)


def process_jsonl(src: Path, dst: Path, alias_map: Dict[str, str]) -> int:
    count = 0
    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            obj = json.loads(line)
            instr = obj.get("instruction", "")
            obj["instruction_normalized"] = normalize_text(instr, alias_map)
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    alias_map = load_alias_map(SYN_PATH)
    print(f"Using step input: {STEP_IN.name}")
    print(f"Using file input: {FILE_IN.name}")
    step_count = process_jsonl(STEP_IN, STEP_OUT, alias_map)
    file_count = process_jsonl(FILE_IN, FILE_OUT, alias_map)
    print(f"Normalized {step_count} step-level instructions -> {STEP_OUT}")
    print(f"Normalized {file_count} file-level instructions -> {FILE_OUT}")


if __name__ == "__main__":
    main()
