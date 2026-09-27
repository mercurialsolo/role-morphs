"""Adapters for the public job-board APIs.

Each adapter takes a board slug and returns a list of Posting. Only structured
fields and the posting URL are kept. Posting bodies are deliberately dropped:
that text is the employer's, and this repository is public.

Adding an ATS means writing one function that returns Posting objects and
registering it in ADAPTERS. Nothing else in the pipeline needs to change.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable

USER_AGENT = "role-morphs/0.1 (+https://github.com/mercurialsolo/role-morphs)"
TIMEOUT = 30


@dataclass(frozen=True)
class Posting:
    """One open role, as the employer's own board describes it."""

    company: str
    title: str
    team: str | None
    location: str | None
    url: str
    posting_id: str
    published_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)


class FetchError(RuntimeError):
    """A board could not be read. Carries the slug so the caller can report it."""


def _get_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise FetchError(f"{url} returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise FetchError(f"{url} unreachable: {error}") from error
    except json.JSONDecodeError as error:
        raise FetchError(f"{url} returned invalid JSON: {error}") from error


def fetch_greenhouse(company: str, slug: str) -> list[Posting]:
    payload = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    postings = []
    for job in payload.get("jobs", []):
        location = (job.get("location") or {}).get("name")
        postings.append(
            Posting(
                company=company,
                title=job["title"].strip(),
                team=None,  # the list endpoint does not carry a department
                location=location,
                url=job["absolute_url"],
                posting_id=str(job["id"]),
                published_at=job.get("updated_at"),
            )
        )
    return postings


def fetch_ashby(company: str, slug: str) -> list[Posting]:
    payload = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    postings = []
    for job in payload.get("jobs", []):
        if not job.get("isListed", True):
            continue
        postings.append(
            Posting(
                company=company,
                title=job["title"].strip(),
                team=job.get("team") or job.get("department"),
                location=job.get("location"),
                url=job["jobUrl"],
                posting_id=job["id"],
                published_at=job.get("publishedAt"),
            )
        )
    return postings


def fetch_lever(company: str, slug: str) -> list[Posting]:
    payload = _get_json(f"https://api.lever.co/v0/postings/{slug}")
    postings = []
    for job in payload:
        categories = job.get("categories") or {}
        postings.append(
            Posting(
                company=company,
                title=job["text"].strip(),
                team=categories.get("team") or categories.get("department"),
                location=categories.get("location"),
                url=job["hostedUrl"],
                posting_id=job["id"],
                published_at=job.get("createdAt") and str(job["createdAt"]),
            )
        )
    return postings


ADAPTERS: dict[str, Callable[[str, str], list[Posting]]] = {
    "greenhouse": fetch_greenhouse,
    "ashby": fetch_ashby,
    "lever": fetch_lever,
}


def fetch(company: str, ats: str, slug: str) -> list[Posting]:
    if ats not in ADAPTERS:
        raise FetchError(f"{company}: no adapter for ATS {ats!r}")
    return ADAPTERS[ats](company, slug)
