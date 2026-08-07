import json
from pathlib import Path

from app.schemas import DefinitionsPayload, ExamplesPayload


ROOT = Path(__file__).resolve().parents[1]


def test_seed_definitions_are_valid():
    payload = json.loads((ROOT / "data" / "definitions_seed.json").read_text(encoding="utf-8"))
    parsed = DefinitionsPayload.model_validate(payload)
    assert len(parsed.broad_categories) == 3
    assert sum(len(item.specific_types) for item in parsed.broad_categories) == 6


def test_seed_examples_are_valid_and_balanced():
    payload = json.loads((ROOT / "data" / "examples_seed.json").read_text(encoding="utf-8"))
    parsed = ExamplesPayload.model_validate(payload)
    assert len(parsed.examples) == 30
    counts = {}
    for item in parsed.examples:
        counts[item.specific_type] = counts.get(item.specific_type, 0) + 1
    assert set(counts.values()) == {5}
