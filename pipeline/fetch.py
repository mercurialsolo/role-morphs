"""Read every board in data/companies.yaml and write one snapshot per run.

    uv run python -m pipeline.fetch

Output goes to data/postings/<YYYY-MM-DD>.json, one file per run, so the series
is append-only and a row's first appearance stays recoverable. A board that
fails is reported and skipped; one dead slug does not lose the whole run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

from pipeline.ats import FetchError, fetch

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.yaml"
POSTINGS_DIR = ROOT / "data" / "postings"


def load_companies() -> list[dict]:
    with COMPANIES.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["companies"]


def first_seen_index() -> dict[str, str]:
    """Map posting url -> the earliest snapshot date it appeared in.

    Rebuilt from the snapshots on disk rather than stored separately, so the
    files on disk are the only state and a deleted snapshot cannot silently
    corrupt the index.
    """
    index: dict[str, str] = {}
    for path in sorted(POSTINGS_DIR.glob("*.json")):
        date = path.stem
        for posting in json.loads(path.read_text(encoding="utf-8"))["postings"]:
            index.setdefault(posting["url"], posting.get("first_seen", date))
    return index


def run(today: str) -> int:
    POSTINGS_DIR.mkdir(parents=True, exist_ok=True)
    seen = first_seen_index()

    postings: list[dict] = []
    failures: list[str] = []

    for company in load_companies():
        try:
            results = fetch(company["name"], company["ats"], company["slug"])
        except FetchError as error:
            failures.append(str(error))
            print(f"  SKIP {company['name']}: {error}", file=sys.stderr)
            continue

        for posting in results:
            record = posting.to_dict()
            record["segment"] = company["segment"]
            record["first_seen"] = seen.get(posting.url, today)
            postings.append(record)

        print(f"  {company['name']}: {len(results)} postings")

    snapshot = {
        "fetched_at": today,
        "company_count": len(load_companies()),
        "failed_boards": failures,
        "posting_count": len(postings),
        "postings": sorted(postings, key=lambda p: (p["company"], p["title"])),
    }

    out = POSTINGS_DIR / f"{today}.json"
    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(postings)} postings from {len(load_companies()) - len(failures)} boards -> {out.relative_to(ROOT)}")

    # A run where every board failed is a broken run, not an empty week.
    return 1 if failures and not postings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="snapshot date, YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()
    return run(args.date)


if __name__ == "__main__":
    raise SystemExit(main())
