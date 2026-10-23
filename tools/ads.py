"""MARS: NASA/SAO ADS literature search and literature reviews.

``astroquery.nasa_ads`` exposes exactly one query method -- confirmed by
reading its source (astroquery 0.4.11): there is no ``query_advanced``.
``ADS.query_simple(query_string)`` passes ``query_string`` straight through as
the ``q`` parameter to ADS's own Solr-backed search API. ADS's own
search-syntax guide (https://ui.adsabs.harvard.edu/help/search/search-syntax)
explicitly warns that unfielded, bare-word queries "may not produce the
expected results" -- ADS is not a natural-language search engine, it is a
fielded query language (``author:"Last, F."``, ``title:"..."``,
``year:2015-2020``, ...) with real boolean precedence rules.

This module builds that fielded query string from structured parameters
(``author=``, ``title=``, ``year=``, ...) rather than asking a caller to
hand-write ADS syntax correctly -- the same fix applied to search_mast's
filters and search_ned's table vocabulary. ``query=`` remains available as an
escape hatch for anything the structured parameters don't cover: second-order
operators (``similar(...)``, ``trending(...)``, ``topn(N, query, sort)``),
proximity search, wildcards -- see ``algorithms.catalogs.ads`` and the ADS guide for
the full syntax those support.

Confirmed by reading astroquery.nasa_ads.core's source, not live -- no
ADS_DEV_KEY is configured in this environment, so this module's behavior
against the real API has not been verified end-to-end:

- Default fields, sort (``'date desc'``), and row count (10) come from
  ``astroquery.nasa_ads.conf``; this module overrides ``ADS.ADS_FIELDS``/
  ``ADS.SORT``/``ADS.NROWS``/``ADS.NSTART`` per call rather than depending on
  those defaults.
- A missing API token and a zero-result response are both raised as a plain
  ``RuntimeError`` with different messages (``_get_token``, ``_parse_response``
  in astroquery's source) -- distinguished here by message text, since
  astroquery gives no distinct exception type for either.
- Most ADS fields come back as single-element lists per row (some, like
  ``author``, genuinely multi-valued) -- ``algorithms.catalogs.ads.flatten_value``
  collapses both cases; this is read from astroquery's response-parsing code
  (``_get_data_from_xml``), not observed on a real response.

Get a token from https://ui.adsabs.harvard.edu/user/settings/token and set it
in the ``ADS_DEV_KEY`` environment variable before relying on this module.
"""

from __future__ import annotations

import re
from typing import Optional, Union

import numpy as np
from astropy.table import Column, Table, vstack
from astroquery.nasa_ads import ADS

from algorithms.catalogs.ads import (
    ADS_REVIEW_FIELDS,
    ADS_SEARCH_FIELDS,
    flatten_value,
    format_citation,
)
from tools import artifacts
from tools.config import PREVIEW_ROWS
from tools.models import ToolResult, ToolWarning

__all__ = [
    "search_ads",
    "get_citing_papers",
    "get_referenced_papers",
    "build_literature_review",
]

#: MARS-side safety ceiling on total rows fetched in one call. Not a
#: discovered ADS server-side limit -- no token was available to confirm one
#: -- just a bound so a very broad topic doesn't page indefinitely.
_MAX_RESULTS_CEILING = 500
_PAGE_SIZE = 50

#: ADS's query-translation endpoint for ``object:``; see ``_translate_objects``.
_OBJECTS_PATH = "/v1/objects/query"
_OBJECT_CLAUSE = re.compile(r"\bobject:")
#: A quoted phrase, so ``title:"object: a study"`` is not taken for a clause.
_QUOTED_PHRASE = re.compile(r'"(?:\\.|[^"\\])*"')
#: The objects service's reply to a query with no ``object:`` clause it can
#: parse (live: ``object:""``, or a quoted phrase containing ``object:``).
_NO_OBJECTS_FOUND = "No identifiers/objects found"


def _invalid_input(message: str) -> ToolResult:
    return ToolResult(status="error", errors=[{"code": "invalid_input", "message": message}])


def _object_name_error(object_name: Optional[str]) -> Optional[ToolResult]:
    """Refuse an ``object_name`` the objects service cannot translate.

    Confirmed live (2026-10-22): the service splits a name at an escaped
    double quote and returns a query the search rejects. No object name needs
    one.
    """
    if object_name and '"' in object_name:
        return _invalid_input("object_name must not contain a double quote (\")")
    return None


def _quote(value: str) -> str:
    return value.replace('"', '\\"')


def _build_query(
    query: Optional[str],
    author: Optional[str],
    first_author_only: bool,
    title: Optional[str],
    abstract: Optional[str],
    year: Optional[Union[str, int]],
    bibcode: Optional[str],
    object_name: Optional[str],
    doctype: Optional[str],
) -> Optional[str]:
    """Assemble a fielded ADS query string from structured parameters.

    Returns ``None`` if nothing was given -- an empty/bare query would be
    exactly the unfielded search ADS's own docs warn against.

    Each clause is parenthesized before joining with AND, standard practice
    for combining Solr-style fielded clauses. The 400 that combining
    ``abs:"..."`` with ``object:"..."`` once produced was not a grouping
    problem: confirmed live (2026-10-22) that the search endpoint rejects
    ``object:`` in every form, grouped or not, so ``_paged_query`` translates
    it first (``_translate_objects``).
    """
    clauses: list[str] = []
    if query:
        clauses.append(query)
    if author:
        key = "first_author" if first_author_only else "author"
        clauses.append(ADS_SEARCH_FIELDS[key].format(value=_quote(author)))
    if title:
        clauses.append(ADS_SEARCH_FIELDS["title"].format(value=_quote(title)))
    if abstract:
        clauses.append(ADS_SEARCH_FIELDS["abstract"].format(value=_quote(abstract)))
    if year:
        clauses.append(ADS_SEARCH_FIELDS["year"].format(value=year))
    if bibcode:
        clauses.append(ADS_SEARCH_FIELDS["bibcode"].format(value=bibcode))
    if object_name:
        clauses.append(ADS_SEARCH_FIELDS["object"].format(value=_quote(object_name)))
    if doctype:
        clauses.append(ADS_SEARCH_FIELDS["doctype"].format(value=doctype))
    if not clauses:
        return None
    return " AND ".join(f"({c})" for c in clauses)


def _describe_error(exc: Exception) -> str:
    """Extend an exception's message with ADS's own error body, if any.

    ``requests.Response.raise_for_status()`` raises an ``HTTPError`` carrying
    the triggering ``Response`` as ``exc.response`` -- confirmed by reading
    ``requests``'s source (``raise HTTPError(msg, response=self)``). A bare
    ``str(exc)`` on a 400 is just "400 Client Error: BAD REQUEST for url:
    ...", which gives no way to tell what was wrong with the query. Solr-backed
    APIs like ADS's typically put the actual parse error in the response body;
    surfacing it here is what makes a 400 fixable instead of a dead end.
    """
    message = str(exc)
    response = getattr(exc, "response", None)
    if response is None:
        return message
    try:
        body = response.json()
    except Exception:
        body = response.text[:500] if getattr(response, "text", None) else None
    return f"{message} | ADS response body: {body}" if body else message


def _missing_token_result() -> ToolResult:
    return ToolResult(
        status="error",
        errors=[
            {
                "code": "dependency_missing",
                "message": "No ADS API token configured. Get one from "
                "https://ui.adsabs.harvard.edu/user/settings/token and set it "
                "in the ADS_DEV_KEY environment variable.",
            }
        ],
    )


def _translate_objects(query_string: str) -> tuple[Optional[str], Optional[ToolResult]]:
    """Rewrite ``object:`` clauses through ADS's objects service.

    Confirmed live (2026-10-22): ``/v1/search/query`` rejects ``object:`` in
    every form, alone or grouped, with ``undefined field object``. The ADS UI
    first sends the whole query to ``POST /v1/objects/query``, which returns it
    with each ``object:`` clause expanded to ``=abs:``/``simbid:``/``nedid:``
    clauses the search does accept; astroquery has no method for that
    endpoint. A query with no ``object:`` clause outside a quoted phrase is
    returned unchanged without a call. Translation also adds
    ``database:astronomy``, as the ADS UI's object search does.

    Returns ``(translated, None)`` or ``(None, error_result)``, like
    ``_paged_query``. The service answers 200 with an ``Error`` key when it
    cannot translate; "No identifiers/objects found" is a clause it cannot
    parse (``invalid_input``), and any other ``Error`` is the service failing.
    A name SIMBAD/NED cannot resolve is not an error: it translates to
    ``simbid:"0"``/``nedid:"0"`` and searches only ``=abs:``. A reply with no
    query in it is one MARS cannot read.
    """
    if not _OBJECT_CLAUSE.search(_QUOTED_PHRASE.sub('""', query_string)):
        return query_string, None
    try:
        token = ADS._get_token()
    except RuntimeError:
        return None, _missing_token_result()
    try:
        response = ADS._request(
            "POST", ADS.SERVER + _OBJECTS_PATH, json={"query": [query_string]},
            headers={"Authorization": "Bearer " + token},
            timeout=ADS.TIMEOUT, cache=False,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        return None, ToolResult(
            status="error",
            errors=[{"code": "provider_unavailable", "message": _describe_error(exc)}],
        )

    translated = body.get("query") if isinstance(body, dict) else None
    if isinstance(translated, str) and translated.strip():
        return translated, None
    if isinstance(body, dict) and _NO_OBJECTS_FOUND in str(body.get("Error Info", "")):
        return None, _invalid_input(
            f"ADS found no object: clause it could translate in {query_string!r} -- "
            "give object: a name, e.g. object:\"M31\""
        )
    if isinstance(body, dict) and "Error" in body:
        return None, ToolResult(
            status="error",
            errors=[{
                "code": "provider_unavailable",
                "message": f"ADS objects service could not translate object: -- {body}",
            }],
        )
    return None, ToolResult(
        status="error",
        errors=[{
            "code": "unusable_response",
            "message": f"ADS objects service returned no translated query: {str(body)[:500]}",
        }],
    )


def _paged_query(
    query_string: str, sort: str, max_results: int
) -> tuple[Optional[Table], Optional[ToolResult]]:
    """Run ``ADS.query_simple``, paging via NSTART/NROWS up to ``max_results``.

    Returns ``(table, None)`` on success (``table`` may be a single page or a
    stacked multi-page table) or ``(None, error_result)`` -- exactly one is
    not ``None``, so a caller checks ``error`` first. ``object:`` clauses are
    translated first (``_translate_objects``).
    """
    query_string, error = _translate_objects(query_string)
    if error is not None:
        return None, error

    ADS.ADS_FIELDS = ADS_REVIEW_FIELDS
    ADS.SORT = sort

    pages: list[Table] = []
    start = 0
    remaining = min(max_results, _MAX_RESULTS_CEILING)

    while remaining > 0:
        page_size = min(_PAGE_SIZE, remaining)
        ADS.NROWS = page_size
        ADS.NSTART = start
        try:
            page = ADS.query_simple(query_string)
        except RuntimeError as exc:
            message = str(exc)
            if "No API token found" in message:
                return None, _missing_token_result()
            if "No results returned" in message:
                break
            return None, ToolResult(
                status="error",
                errors=[{"code": "provider_unavailable", "message": message}],
            )
        except Exception as exc:
            return None, ToolResult(
                status="error",
                errors=[{"code": "provider_unavailable", "message": _describe_error(exc)}],
            )

        if page is None or len(page) == 0:
            break
        pages.append(page)
        remaining -= len(page)
        start += len(page)
        if len(page) < page_size:
            break  # short page: ADS has no more results

    if not pages:
        return None, ToolResult(status="not_found", count=0)

    return _stack_pages(pages), None


def _stack_pages(pages: list[Table]) -> Table:
    """Stack result pages whose columns astropy typed differently.

    astroquery builds each page's columns from per-row lists, so one page's
    field can be a 2-D ``str`` column (every row held a one-element list) and
    the next a 1-D ``object`` column (some row lacked the field and got
    ``[None]``). Confirmed live (2026-10-22): ``vstack`` refuses the mix. A
    column whose dtype kind or cell shape differs between pages (string widths
    alone stack fine) is rebuilt as 1-D ``object`` cells holding each row's
    list, which ``flatten_value`` and the ECSV writer already handle.
    """
    if len(pages) == 1:
        return pages[0]
    for name in pages[0].colnames:
        if len({(page[name].dtype.kind, page[name].shape[1:]) for page in pages}) > 1:
            for page in pages:
                cells = np.empty(len(page), dtype=object)
                for i, cell in enumerate(page[name]):
                    cells[i] = cell.tolist() if hasattr(cell, "tolist") else cell
                page.replace_column(name, Column(cells, name=name))
    return vstack(pages)


def _flatten_rows(table: Table) -> list[dict]:
    return [
        {field: flatten_value(row[field]) for field in table.colnames} for row in table
    ]


def _ceiling_warning(max_results: int) -> list[ToolWarning]:
    if max_results > _MAX_RESULTS_CEILING:
        return [
            ToolWarning(
                code="max_results_capped",
                message=f"max_results capped at {_MAX_RESULTS_CEILING} -- a "
                "MARS-side safety limit, not a confirmed ADS server-side limit",
            )
        ]
    return []


def search_ads(
    query: Optional[str] = None,
    *,
    author: Optional[str] = None,
    first_author_only: bool = False,
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
    bibcode: Optional[str] = None,
    object_name: Optional[str] = None,
    doctype: Optional[str] = None,
    sort: str = "date desc",
    max_results: int = 20,
) -> ToolResult:
    """Search ADS with a fielded query built from structured parameters.

    Pass any combination of ``author``/``title``/``abstract``/``year``/
    ``bibcode``/``object_name``/``doctype``; they combine with AND. ``year``
    accepts a single year or a range (``"2015-2020"``). ``query=`` is a raw
    ADS query string, for anything the structured parameters don't cover
    (second-order operators, proximity search, wildcards) -- combined with
    the others via AND if both are given. At least one parameter is required.
    """
    refused = _object_name_error(object_name)
    if refused is not None:
        return refused
    query_string = _build_query(
        query, author, first_author_only, title, abstract, year, bibcode,
        object_name, doctype,
    )
    if not query_string:
        return ToolResult(
            status="error",
            errors=[
                {
                    "code": "invalid_input",
                    "message": "at least one search parameter is required",
                }
            ],
        )

    table, error = _paged_query(query_string, sort, max_results)
    if error is not None:
        return error

    artifact = artifacts.write_table(table, f"ads_{query_string}", subdir="ads")
    rows = _flatten_rows(table)
    return ToolResult(
        status="ok",
        count=len(table),
        preview=rows[:PREVIEW_ROWS],
        columns=ADS_REVIEW_FIELDS,
        artifact=artifact,
        warnings=_ceiling_warning(max_results),
    )


def get_citing_papers(
    bibcode: str, *, sort: str = "citation_count desc", max_results: int = 20
) -> ToolResult:
    """Return papers that cite ``bibcode`` (ADS's ``citations()`` operator)."""
    if not bibcode or not bibcode.strip():
        return ToolResult(
            status="error",
            errors=[{"code": "invalid_input", "message": "bibcode must not be blank"}],
        )

    table, error = _paged_query(f"citations(bibcode:{bibcode})", sort, max_results)
    if error is not None:
        return error

    artifact = artifacts.write_table(table, f"ads_citations_of_{bibcode}", subdir="ads")
    rows = _flatten_rows(table)
    return ToolResult(
        status="ok",
        count=len(table),
        preview=rows[:PREVIEW_ROWS],
        columns=ADS_REVIEW_FIELDS,
        artifact=artifact,
        warnings=_ceiling_warning(max_results),
    )


def get_referenced_papers(
    bibcode: str, *, sort: str = "date desc", max_results: int = 20
) -> ToolResult:
    """Return papers ``bibcode`` cites (ADS's ``references()`` operator)."""
    if not bibcode or not bibcode.strip():
        return ToolResult(
            status="error",
            errors=[{"code": "invalid_input", "message": "bibcode must not be blank"}],
        )

    table, error = _paged_query(f"references(bibcode:{bibcode})", sort, max_results)
    if error is not None:
        return error

    artifact = artifacts.write_table(table, f"ads_references_of_{bibcode}", subdir="ads")
    rows = _flatten_rows(table)
    return ToolResult(
        status="ok",
        count=len(table),
        preview=rows[:PREVIEW_ROWS],
        columns=ADS_REVIEW_FIELDS,
        artifact=artifact,
        warnings=_ceiling_warning(max_results),
    )


def build_literature_review(
    query: Optional[str] = None,
    *,
    author: Optional[str] = None,
    first_author_only: bool = False,
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
    object_name: Optional[str] = None,
    doctype: Optional[str] = None,
    sort: str = "citation_count desc",
    max_papers: int = 30,
) -> ToolResult:
    """Search ADS and write a Markdown literature review with full citations.

    Takes the same fielded-query parameters as ``search_ads``. Defaults to
    ``sort="citation_count desc"`` so the most-cited (typically most
    foundational) papers lead the review; pass ``sort="date desc"`` for a
    chronological one instead. Writes two artifacts: the review itself
    (Markdown, one numbered entry per paper with its citation and abstract)
    and the underlying data table.
    """
    refused = _object_name_error(object_name)
    if refused is not None:
        return refused
    query_string = _build_query(
        query, author, first_author_only, title, abstract, year, None,
        object_name, doctype,
    )
    if not query_string:
        return ToolResult(
            status="error",
            errors=[
                {
                    "code": "invalid_input",
                    "message": "at least one search parameter is required",
                }
            ],
        )

    table, error = _paged_query(query_string, sort, max_papers)
    if error is not None:
        return error

    rows = _flatten_rows(table)
    lines = [
        f"# Literature review: {query_string}",
        "",
        f"{len(rows)} paper(s), sorted by `{sort}`.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.append(f"{i}. {format_citation(row)}")
        abstract_text = row.get("abstract")
        if abstract_text:
            lines.append("")
            lines.append(f"   {abstract_text}")
        lines.append("")

    review_artifact = artifacts.write_text(
        "\n".join(lines), f"ads_review_{query_string}", subdir="ads"
    )
    data_artifact = artifacts.write_table(
        table, f"ads_review_{query_string}_data", subdir="ads"
    )

    return ToolResult(
        status="ok",
        count=len(rows),
        preview=rows[:PREVIEW_ROWS],
        columns=ADS_REVIEW_FIELDS,
        artifacts=[review_artifact, data_artifact],
        warnings=_ceiling_warning(max_papers),
    )
