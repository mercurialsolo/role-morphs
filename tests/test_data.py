"""The data file is the product, so it is what gets tested.

Run with `uv run pytest`. These checks run in CI on every push and before every
committed pipeline run, so a bad row fails loudly instead of shipping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
MORPHS = json.loads((ROOT / "data" / "role-morphs.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "data" / "schema.json").read_text(encoding="utf-8"))
ALIASES = json.loads((ROOT / "data" / "aliases.json").read_text(encoding="utf-8"))
COMPANIES = yaml.safe_load((ROOT / "data" / "companies.yaml").read_text(encoding="utf-8"))["companies"]

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def test_morphs_match_schema():
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(MORPHS), key=str)
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_ids_are_unique():
    ids = [row["id"] for row in MORPHS]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate ids: {sorted(duplicates)}"


def test_was_becomes_pairs_are_unique():
    pairs = [(row["discipline"], row["was"], row["becomes"]) for row in MORPHS]
    duplicates = {p for p in pairs if pairs.count(p) > 1}
    assert not duplicates, f"duplicate role pairs: {sorted(duplicates)}"


@pytest.mark.parametrize("row", MORPHS, ids=lambda r: r["id"])
def test_every_row_is_checkable(row):
    """A row without a resolvable source is an opinion, and must be graded as one."""
    if row["source_url"] is None:
        assert row["evidence_type"] == "Argued only", (
            f"{row['id']} has no source but claims evidence grade {row['evidence_type']!r}"
        )
        return
    assert row["source_url"].startswith(("http://", "https://"))
    assert " " not in row["source_url"]


@pytest.mark.parametrize("row", MORPHS, ids=lambda r: r["id"])
def test_argued_rows_declare_themselves(row):
    """The weakest evidence type has to say what it is missing."""
    if row["evidence_type"] == "Argued only":
        assert row["note"], f"{row['id']} is argued only and must carry a note saying so"


def test_alias_keys_are_real_rows():
    known = {row["id"] for row in MORPHS}
    unknown = (set(ALIASES["aliases"]) | set(ALIASES["too_generic"])) - known
    assert not unknown, f"aliases reference unknown row ids: {sorted(unknown)}"


def test_unsearchable_rows_are_argued_only():
    """A row with no honest search term must be one with nothing to look for.

    `too_generic` rows are searched on aliases alone. A row with neither its own
    name nor an alias is unsearchable, which is acceptable only when no source
    observed the role in the first place. Anything else is a missing alias.
    """
    grades = {row["id"]: row["evidence_type"] for row in MORPHS}
    for row_id in ALIASES["too_generic"]:
        if not ALIASES["aliases"].get(row_id):
            assert grades[row_id] == "Argued only", (
                f"{row_id} has no searchable term but claims evidence grade "
                f"{grades[row_id]!r}; add an alias or downgrade the row"
            )


def test_company_slugs_are_well_formed():
    assert COMPANIES, "no companies configured"
    for company in COMPANIES:
        assert set(company) == {"name", "ats", "slug", "segment"}, company
        assert company["ats"] in {"greenhouse", "ashby", "lever"}, company
        assert SLUG.match(company["slug"]), company


def test_company_entries_are_unique():
    keys = [(c["ats"], c["slug"]) for c in COMPANIES]
    duplicates = {k for k in keys if keys.count(k) > 1}
    assert not duplicates, f"duplicate boards: {sorted(duplicates)}"
