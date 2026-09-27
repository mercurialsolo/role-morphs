# Role morphs

Which jobs are changing shape, what the evidence for each one is, and where you can check it yourself.

The official statistics cannot see this yet. US federal employment data is still counted in the [2018 Standard Occupational Classification](https://www.bls.gov/soc/2028/2028_soc_revision.htm), which has no code for an AI engineer, a forward deployed engineer or an interpretability researcher, and the next revision is not in use until 2028. Job specs move years before the codes do. This repository reads the specs.

It exists because the underlying claim deserved to be checkable rather than asserted. Every row carries a source URL and an evidence grade, and the pipeline goes back to live job boards on a schedule so the counts age in public.

## What is here

| Path | What it is |
|---|---|
| `data/role-morphs.json` | 31 hand-built rows: a role, what it became, and the source. The seed dataset |
| `data/schema.json` | JSON Schema for a row. `evidence_type` is the part that matters |
| `data/companies.yaml` | The 20 job boards the pipeline reads, with the ATS that serves each |
| `data/aliases.json` | Extra title phrasings that count as a row's new role |
| `data/postings/<date>.json` | One snapshot per pipeline run. Append-only, so a role's first appearance stays recoverable. About 1.8 MB a week |
| `data/matches.json` | How many live postings carry each row's new role, with examples |
| `pipeline/` | The fetcher, the ATS adapters, and the matcher |
| `app/` | A browser tool over `data/`. No build step, no framework |

## Evidence grades

Rows are not equally strong, and the schema says so rather than flattening them.

| Grade | Means |
|---|---|
| `Named study` | A published study observed it |
| `Job posting` | An employer is hiring for it today, with the posting linked |
| `Research team page` | A team describes its own composition this way |
| `Industry reporting` | A journalist or practitioner reported it |
| `Vendor claim` | The company selling the thing says so. Weakest observed grade |
| `Argued only` | Nobody observed this. It is an argument, and the row's `note` says what is missing |

Two rows in the seed data are `Argued only`. They are kept, labelled, and tested for that label, because dropping them would make the dataset look better evidenced than it is.

## Running it

```bash
uv sync --extra dev
uv run pytest                      # the data file is the product, so it is what gets tested
uv run python -m pipeline.fetch    # read every board, write data/postings/<today>.json
uv run python -m pipeline.match    # count live postings per row, write data/matches.json
```

The fetcher needs no keys. Every endpoint in `data/companies.yaml` is a public JSON feed that an applicant tracking system publishes so that open roles can be syndicated.

## What is scraped, and what is not

We read structured fields and the posting URL: title, team, location, identifier, publication date. **We do not store posting bodies.** That text is the employer's, and this repository is public. If you want the body, follow the URL to the employer's own page, which is where they intended you to read it.

No HTML is parsed, no rate limits are pushed, no login is bypassed. If a board stops serving its feed, the pipeline reports the failure and skips it.

## What this does not cover yet

**Fortune 500.** Most large non-tech employers run Workday or SuccessFactors, which publish no clean public feed and whose terms prohibit scraping. Rather than break that, the plan for phase 2 is published aggregates that already do the counting legitimately: [Indeed Hiring Lab](https://www.hiringlab.org/), Lightcast, and the [Anthropic Economic Index](https://www.anthropic.com/economic-index). The twenty boards here are labs, AI product companies, the data-supplier industry, and a handful of larger technology employers.

**Classification.** `pipeline/match.py` is a keyword match over posting titles, not a classifier. A title contains one of a row's terms or it does not, and the output records which term fired so any number can be argued with. A row with zero matches means these boards do not spell the role that way today, not that the role is absent. Rows whose new name is a common English job word (`Agent`, `Hypothesis`) are excluded from default matching and searched on aliases only, so noise does not get counted as evidence.

**Causation.** Nothing here shows AI caused a role to change. It shows which roles are being advertised with which shapes, over time.

## Known tradeoffs

Snapshots are kept whole rather than diffed, at roughly 1.8 MB a week. That buys reproducibility: any past count can be recomputed from the file it came from, and a role's first appearance is recoverable without trusting an index. If the repository gets uncomfortably large, compress the older ones rather than deleting them.

## Adding a row

Open a pull request against `data/role-morphs.json`. A row needs:

- a `source_url` a stranger can open,
- an honest `evidence_type` (if nobody observed it, it is `Argued only` and needs a `note`),
- a `date_observed` of the month you checked.

`uv run pytest` enforces all of that. Rows that overstate their evidence are the one thing that would make this dataset worthless, so that is what the tests guard.

Board additions go in `data/companies.yaml`; check the slug returns HTTP 200 first. New title phrasings go in `data/aliases.json`.

## Provenance

The seed rows come from research for [The Jobs They Are A-Changin'](https://mercurialsolo.github.io/posts/roles-in-the-agent-era/), scanned off career pages, research-team pages and industry reporting between March and September 2026. Of the 31: 4 rest on a named study, 10 on job postings, 13 on industry reporting, 1 on a research team page, 1 on a vendor's own claim, and 2 on argument alone.

## Licence

Code is MIT (`LICENSE`). Data is CC BY 4.0 (`data/LICENSE`): use it, and say where it came from.
