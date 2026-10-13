"""Team-name normalizer. Stdlib only."""
from __future__ import annotations

import json
from pathlib import Path

_ALIAS_PATH = Path(__file__).with_name("teams_alias.json")

def _load_aliases() -> dict[str, list[str]]:
    try:
        return json.loads(_ALIAS_PATH.read_text())
    except FileNotFoundError:
        return {}


def canonical_name(raw: str) -> str:
    raw = (raw or "").strip()
    aliases = _load_aliases()
    for canon, variants in aliases.items():
        if raw.lower() == canon.lower() or raw.lower() in [v.lower() for v in variants]:
            return canon
    return raw
