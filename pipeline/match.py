"""Count how many live postings carry each taxonomy row's new role.

    uv run python -m pipeline.match

This is deliberately a keyword match over posting titles, not a classifier. A
title either contains one of the row's terms or it does not, and the output
records which term fired so any count can be argued with. Nothing here decides
what a job "really" is.

The limits are the point: a row with zero matches is not evidence the role does
not exist, only that these twenty boards do not spell it this way today. The
output carries `method` so a reader can see what the number is worth.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MORPHS = ROOT / "data" / "role-morphs.json"
ALIASES = ROOT / "data" / "aliases.json"
POSTINGS_DIR = ROOT / "data" / "postings"
OUT = ROOT / "data" / "matches.json"


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def latest_snapshot() -> dict:
    snapshots = sorted(POSTINGS_DIR.glob("*.json"))
    if not snapshots:
        raise SystemExit("no snapshots in data/postings; run pipeline.fetch first")
    return json.loads(snapshots[-1].read_text(encoding="utf-8"))


def terms_for(row: dict, alias_map: dict[str, list[str]], too_generic: set[str]) -> list[str]:
    """The strings that count as this row's new role appearing in a title.

    A row's own `becomes` is the default term. Rows in `too_generic` are
    searched on their aliases only: matching 'Agent' or 'Hypothesis' against
    titles would count noise as evidence.
    """
    terms = list(alias_map.get(row["id"], []))
    if row["id"] not in too_generic:
        terms.insert(0, row["becomes"])
    seen, out = set(), []
    for term in (normalise(t) for t in terms):
        if len(term) >= 4 and term not in seen:
            seen.add(term)
            out.append(term)
    return out


def _dedupe(hits: list[dict]) -> list[dict]:
    """One entry per (company, title); boards repeat a role across locations."""
    seen, out = set(), []
    for hit in hits:
        key = (hit["company"], normalise(hit["title"]))
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out


def run() -> int:
    rows = json.loads(MORPHS.read_text(encoding="utf-8"))
    alias_file = json.loads(ALIASES.read_text(encoding="utf-8")) if ALIASES.exists() else {}
    alias_map = alias_file.get("aliases", {})
    too_generic = set(alias_file.get("too_generic", []))
    snapshot = latest_snapshot()

    titles = [(normalise(p["title"]), p) for p in snapshot["postings"]]

    results = []
    for row in rows:
        terms = terms_for(row, alias_map, too_generic)
        hits = []
        for haystack, posting in titles:
            fired = next((term for term in terms if term in haystack), None)
            if fired:
                hits.append(
                    {
                        "company": posting["company"],
                        "segment": posting["segment"],
                        "title": posting["title"],
                        "url": posting["url"],
                        "matched_term": fired,
                        "first_seen": posting["first_seen"],
                    }
                )

        by_segment: dict[str, int] = {}
        for hit in hits:
            by_segment[hit["segment"]] = by_segment.get(hit["segment"], 0) + 1

        # Boards publish one posting per location, so a single role can appear
        # four times. distinct_roles is the number worth quoting; match_count
        # is kept because it is what the raw snapshot actually contains.
        distinct = {(hit["company"], normalise(hit["title"])) for hit in hits}

        results.append(
            {
                "id": row["id"],
                "discipline": row["discipline"],
                "layer": row["layer"],
                "was": row["was"],
                "becomes": row["becomes"],
                "evidence_type": row["evidence_type"],
                "terms": terms,
                "searchable": bool(terms),
                "distinct_roles": len(distinct),
                "match_count": len(hits),
                "companies": sorted({hit["company"] for hit in hits}),
                "by_segment": dict(sorted(by_segment.items())),
                "examples": _dedupe(sorted(hits, key=lambda h: h["company"]))[:10],
            }
        )

    payload = {
        "method": (
            "Case-insensitive substring match of each row's `becomes` value (plus "
            "any aliases in data/aliases.json) against posting titles only. Not a "
            "classifier. `distinct_roles` counts one per (company, title) and is "
            "the number worth quoting; `match_count` is the raw posting count, which "
            "boards inflate by listing a role once per location. Zero matches means "
            "these boards do not use the phrase, not that the role is absent."
        ),
        "snapshot_date": snapshot["fetched_at"],
        "posting_count": snapshot["posting_count"],
        "board_count": snapshot["company_count"] - len(snapshot["failed_boards"]),
        "rows_with_matches": sum(1 for r in results if r["distinct_roles"]),
        "rows_unsearchable": sum(1 for r in results if not r["searchable"]),
        "rows": sorted(results, key=lambda r: -r["distinct_roles"]),
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"{payload['rows_with_matches']} of {len(results)} rows matched at least one live posting")
    for row in payload["rows"][:10]:
        if row["distinct_roles"]:
            print(f"  {row['distinct_roles']:>4}  {row['becomes']}")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
