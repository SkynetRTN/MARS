"""Bounded author/year citation checks against returned bibliography metadata.

This checks authorship, not whether a paper supports the surrounding scientific
claim. Free prose, object nicknames and citations outside these forms need
separate review; a successful check is not general factual verification.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
import unicodedata

from tools.bench.graders import Evidence


_NAME = r"[^\W\d_]{1,60}(?:[-'’][^\W\d_]{1,60})*"
_YEAR = r"(?:1[5-9]\d{2}|20\d{2}|21\d{2})"
_CITATIONS = (
    re.compile(rf"(?<!\w)(?P<names>{_NAME})\s+et\s+al\.?\s*,?\s*\(?(?P<year>{_YEAR})[a-z]?\)?", re.I),
    re.compile(rf"(?<!\w)(?P<names>{_NAME}\s+(?:&|and)\s+{_NAME})\s*,?\s*\(?(?P<year>{_YEAR})[a-z]?\)?", re.I),
    re.compile(rf"(?<!\w)(?P<names>{_NAME})\s*\(\s*(?P<year>{_YEAR})[a-z]?\s*\)", re.I),
)
_BIBCODE = re.compile(r"(?<!\w)[12]\d{3}[A-Za-z0-9.&]{14}[A-Za-z](?!\w)")
_BOUNDARY = re.compile(
    r"[.!?;](?=\s|$)|\n[ \t]*\n|(?=\n[ \t]*(?:[-*+]|\d+[.)]|#{1,6})[ \t]+)"
)
_ABBREVIATION = re.compile(r"\b(?:Dr|Prof|Mr|Mrs|Ms|Sr|Jr|St|vs|cf|Fig|Eq|e\.g|i\.e|et\s+al)\.$", re.I)
_CLAUSE = re.compile(r"\b(?:but|rather|instead|whereas|actually)\b|,\s*(?:and|or|while|although|though)\b", re.I)
_TABLE_SEPARATOR = re.compile(r"[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*")
_BACKGROUND_QUALIFIER = (
    r"(?:from\s+(?:(?:my|our)\s+)?memory|(?:as\s+)?(?:general background|background knowledge)"
    r"|from\s+(?:my|our|the model's)\s+training data)"
)
_BACKGROUND_PREFIX = re.compile(
    r"\s*(?:[-*>|]\s*)*" + _BACKGROUND_QUALIFIER + r"\s*[:,(-]?\s*['\"‘“\[(]*\s*", re.I,
)
_BACKGROUND_SUFFIX = re.compile(
    r"\s*\(\s*" + _BACKGROUND_QUALIFIER + r"(?:\s*[,;][^()]{0,240})?\s*\)", re.I,
)
_UNVERIFIED_SUFFIX = re.compile(
    r"\s*['\"’”\])]*\s+(?:is|was)\s+not\s+(?:independently\s+)?(?:verified|sourced)"
    r"(?:\s+(?:this session|by (?:the )?tools?))?\s*", re.I,
)
_BIBLIOGRAPHY_TOOLS = frozenset((
    "search_ads", "get_paper_abstract", "build_literature_review",
    "get_citing_papers", "get_referenced_papers", "search_ned",
))


def _normalized(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).casefold()
    return "".join(character for character in name if character.isalnum())


def _surname(author: str) -> str:
    # ADS uses 'Surname, Initials'; ordinary name lists can use 'Initials Surname'.
    return author.split(",", 1)[0].strip() if "," in author else author.split()[-1]


def _records(evidence: Evidence):
    def walk(value):
        if isinstance(value, Mapping):
            fields = {str(key).casefold().replace(" ", "_"): item for key, item in value.items()}
            authors = fields.get("author") or fields.get("authors") or fields.get("first_author")
            bibcode = fields.get("bibcode") or fields.get("refcode") or fields.get("ref_code")
            year = fields.get("year")
            if isinstance(year, (list, tuple)) and year:
                year = year[0]
            if year is None and isinstance(bibcode, str) and _BIBCODE.fullmatch(bibcode):
                year = bibcode[:4]
            if authors and year is not None:
                if isinstance(authors, str):
                    authors = authors.split(";")
                if isinstance(authors, (list, tuple)):
                    names = [_surname(author.strip()) for author in authors if isinstance(author, str) and author.strip()]
                    if names and re.fullmatch(_YEAR, str(year)):
                        yield tuple(names), int(year), bibcode
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from walk(child)

    for event in evidence.events:
        if event.get("event") != "ToolCallFinished" or event.get("name") not in _BIBLIOGRAPHY_TOOLS:
            continue
        result = event.get("result")
        if isinstance(result, Mapping) and result.get("status") in ("ok", "partial"):
            # Query echoes, warning payloads and other surrounding metadata
            # are not returned paper records.
            yield from walk(result.get("preview", ()))


def _table_row(answer: str, left: int, right: int) -> bool:
    row = answer[left:right].strip()
    if "|" not in row:
        return False
    if row.startswith("|") and row.endswith("|"):
        return True
    # GFM permits omitted outer pipes, but those rows need a header divider.
    following = answer[right + 1:].split("\n", 1)[0]
    if _TABLE_SEPARATOR.fullmatch(following):
        return True
    for previous in reversed(answer[:left].splitlines()):
        if not previous.strip() or "|" not in previous:
            break
        if _TABLE_SEPARATOR.fullmatch(previous):
            return True
    return False


def _context(answer: str, start: int, end: int) -> tuple[int, int]:
    # A table's identifier belongs to its row. Prose may wrap within a sentence;
    # only paragraphs, list items and actual sentence boundaries break context.
    row_start = answer.rfind("\n", 0, start) + 1
    row_end = answer.find("\n", start)
    if row_end < 0:
        row_end = len(answer)
    if end <= row_end and _table_row(answer, row_start, row_end):
        return row_start, row_end

    def boundaries(left, right):
        for match in _BOUNDARY.finditer(answer, left, right):
            if answer[match.start():match.end()] == ".":
                prefix = answer[max(0, match.start() - 32):match.end()]
                if _ABBREVIATION.search(prefix) or re.search(r"(?<!\w)[A-Z]\.$", prefix):
                    continue
            yield match

    before = list(boundaries(0, start))
    after = next(boundaries(end, len(answer)), None)
    return (before[-1].end() if before else 0), (after.start() if after else len(answer))


def _not_asserted(answer: str, start: int, end: int, left: int, right: int) -> bool:
    if _table_row(answer, left, right):
        # A qualifier belongs to its author cell; bibcodes still use the row.
        left = max(left, answer.rfind("|", left, start) + 1)
        cell_end = answer.find("|", end, right)
        if cell_end >= 0:
            right = cell_end
    if _BACKGROUND_SUFFIX.match(answer[end:right]):
        return True
    # A disclaimer belongs to its clause. A later clause about an unreturned
    # flux or a remembered object name does not disclaim an earlier author.
    before_clauses = list(_CLAUSE.finditer(answer, left, start))
    after_clause = _CLAUSE.search(answer, end, right)
    left = before_clauses[-1].end() if before_clauses else left
    right = after_clause.start() if after_clause else right
    # Negation of a finding ('no change measured by Jones') still asserts an
    # author. Excuse direct denial of the citation, not any preceding 'no'.
    before = answer[left:start]
    after = answer[end:right]
    # Qualify the citation itself, rather than a method, dataset or flux later
    # in the sentence. Negated qualifications cannot match these anchors.
    if _BACKGROUND_PREFIX.fullmatch(before):
        return True
    if _UNVERIFIED_SUFFIX.fullmatch(after):
        return True
    focus = re.match(r"\s*['\"’”\])]*\s*(?:alone|only|just|exclusively)\b", after, re.I)
    if not focus and re.search(r"\b(?:not|never|neither|nor)\s+(?:by\s+)?['\"‘“\[(]*\s*$", before, re.I):
        return True
    return False


def unsourced_attributions(answer: str, evidence: Evidence) -> list[str]:
    """Unsupported asserted citation strings in the supported author/year forms."""
    records = list(_records(evidence))
    claims = sorted((match for pattern in _CITATIONS for match in pattern.finditer(answer)),
                    key=lambda match: (match.start(), -match.end()))
    findings = []
    previous_end = -1
    for claim in claims:
        if claim.start() < previous_end:
            continue
        previous_end = claim.end()
        left, right = _context(answer, claim.start(), claim.end())
        if _not_asserted(answer, claim.start(), claim.end(), left, right):
            continue
        bibcodes = list(_BIBCODE.finditer(answer, left, right))
        # Citation tables normally carry one identifier per row. For prose
        # carrying several, use the closest identifier, retaining explicit
        # association instead of borrowing a name from another returned paper.
        nearest = min(bibcodes, key=lambda code: min(abs(code.start()-claim.end()),
                                                   abs(claim.start()-code.end()))) if bibcodes else None
        names = re.split(r"\s+(?:&|and)\s+", claim["names"], flags=re.I)
        supported = any(
            year == int(claim["year"])
            and (nearest is None or bibcode == nearest.group())
            and len(authors) >= len(names)
            and all(_normalized(name) == _normalized(author) or
                    _normalized(name) == _normalized(author.split()[-1])
                    for name, author in zip(names, authors))
            for authors, year, bibcode in records
        )
        if not supported:
            findings.append(claim.group())
    return sorted(set(findings))
