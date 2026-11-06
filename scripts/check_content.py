"""Basic completion check for Russian stage content; run after editorial corrections."""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = [200, 800, 1100, 1400, 1600, 1800, 2000, 1200]
REQUIRED = {
    "schema_version", "id", "locale", "sentence", "cloze", "answer",
    "accepted_answers", "lemma", "meaning", "part_of_speech",
}
SPECIFIC = {"reading", "morphology", "verb", "pronunciation", "usage"}


def limits(text, word_cap, char_cap):
    text = unicodedata.normalize("NFC", text)
    words = re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text)
    return len(words) <= word_cap and sum(not c.isspace() for c in text) <= char_cap


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def check(stage):
    count = COUNTS[int(stage)]
    cards = json.loads((ROOT / f"cards/ru-RU/{stage}.json").read_text())
    expected = [f"ru-{stage}-{i:04d}" for i in range(1, count + 1)]
    assert isinstance(cards, list) and len(cards) == count, "Incorrect stage count"
    assert [c["common"]["id"] for c in cards] == expected, "Incorrect ordered IDs"
    rows = []
    for line in (ROOT / f"coverage/ru-RU/{stage}.md").read_text().splitlines():
        cells = [v.strip().strip('`') for v in line.split('|')[1:-1]]
        if cells and re.fullmatch(r"ru-\d{2}-\d{4}", cells[0]):
            assert len(cells) == 3 and all(cells), "Incomplete coverage row"
            rows.append(cells[0])
    assert rows == expected, "Coverage must have one ordered row per card"
    seen_ids, seen_sentences = set(), set()
    for path in sorted((ROOT / "cards/ru-RU").glob("[0-9][0-9].json")):
        if path.stem >= stage:
            continue
        for card in json.loads(path.read_text()):
            seen_ids.add(card["common"]["id"])
            seen_sentences.add(card["common"]["sentence"])
    caps = (12, 90) if int(stage) <= 1 else (16, 120) if stage == "02" else (20, 150)
    for card in cards:
        assert set(card) == {"common", "language_specific"}, "Incorrect card regions"
        c, s = card["common"], card["language_specific"]
        label = c["id"]
        assert REQUIRED <= set(c) <= REQUIRED | {"register", "note"}, label + ": common keys"
        assert type(c["schema_version"]) is int and c["schema_version"] == 2, label + ": version"
        assert c["locale"] == "ru-RU", label + ": locale"
        for key in set(c) - {"schema_version", "accepted_answers"}:
            assert isinstance(c[key], str) and c[key].strip(), label + ": " + key
        assert isinstance(c["accepted_answers"], list), label + ": variants"
        assert isinstance(s, dict) and {"reading"} <= set(s) <= SPECIFIC, label + ": specific keys"
        assert all(isinstance(v, str) and v.strip() for v in s.values()), label + ": support values"
        assert all(unicodedata.is_normalized("NFC", v) for v in strings(card)), label + ": NFC"
        assert s["reading"].replace('\u0301', '') == c["cloze"], label + ": reading alignment"
        assert c["answer"] == c["cloze"] and c["sentence"].count(c["cloze"]) == 1, label + ": cloze alignment"
        start = c["sentence"].index(c["cloze"])
        end = start + len(c["cloze"])
        assert not unicodedata.combining(c["cloze"][0]), label + ": cloze start"
        assert end == len(c["sentence"]) or not unicodedata.combining(c["sentence"][end]), label + ": cloze end"
        assert limits(c["sentence"], *caps), label + ": sentence caps"
        for answer in [c["cloze"], c["answer"], *c["accepted_answers"]]:
            assert isinstance(answer, str) and answer.strip() and limits(answer, 5, 40), label + ": answer caps"
        assert len(c["accepted_answers"]) == len(set(c["accepted_answers"])), label + ": duplicate variants"
        assert c["id"] not in seen_ids and c["sentence"] not in seen_sentences, label + ": duplicate"
        seen_ids.add(c["id"])
        seen_sentences.add(c["sentence"])
    print(f"PASS: stage {stage}, {count} cards and coverage rows; fields, alignment, caps and duplicates checked.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {f"{i:02d}" for i in range(8)}:
        raise SystemExit("Usage: .venv/bin/python scripts/check_content.py NN")
    check(sys.argv[1])
