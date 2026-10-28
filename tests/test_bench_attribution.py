"""A sourced value does not establish the author of the paper it is paired with."""

import pytest

from tests.conftest_bench import BARE_TASK, MINIMAL_TASK, finished, run_directory, manifest, write_task
from tools.bench.graders import load_evidence
from tools.bench.graders.answer import grade


TASK = BARE_TASK + """expect:
  answer:
    must_source_attribution:
      - because: Author names must come from metadata for the cited paper.
"""
BIBCODE = "2017MNRAS.469.1299T"
OTHER = "2017MNRAS.469.1300J"


def _grade(tmp_path, answer, events, task_body=TASK):
    task = write_task(tmp_path, task_body)
    evidence = load_evidence(run_directory(tmp_path, answer=answer,
        manifest_body=manifest(), events=events))
    return grade(task, evidence)


def _metadata(*, bibcode=BIBCODE, year=2017, **fields):
    return finished("search_ads", {"status": "ok", "preview": [
        {"bibcode": bibcode, "year": year, **fields}]})


@pytest.mark.parametrize("answer", [
    "Publication year (2017).", "Publication Year (2017).",
    "The catalog measurements (2017) were returned by the tool.",
    "Observations (2017) are available.", "Reference epoch (2017).",
])
def test_parenthesized_dates_are_not_fabricated_authors(tmp_path, answer):
    result = _grade(tmp_path, answer, [])
    assert result.passed is True
    assert result.metrics["unsourced_attributions"] == []


@pytest.mark.parametrize("answer", [
    "According to Year (2017), the decline was measured.",
    "Date (2017) reported the decline.", "Year et al. 2017 measured it.",
    "Year & Jones (2017) measured it.",
])
def test_explicit_author_context_is_checked_even_for_temporal_label_surnames(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is False


@pytest.mark.parametrize("answer", [
    "Jones et al. 2017 measured 0.670%/yr.",
    "Jones et al. (2017) measured 0.670%/yr.",
    "Jones (2017) measured 0.670%/yr.",
    "| Reference | Rate |\n| --- | --- |\n| Jones et al. 2017 | 0.670%/yr |",
])
def test_sourced_numbers_do_not_excuse_an_invented_author(tmp_path, answer):
    result = _grade(tmp_path, answer, [finished("search_ned", {"status": "ok", "preview": [
        {"Refcode": BIBCODE, "rate": .670}]})])
    assert result.passed is False
    assert "must_source_attribution" in {failure.check for failure in result.failures}
    assert result.metrics["unsourced_numbers"] == []
    assert result.metrics["unsourced_attributions"]


@pytest.mark.parametrize("fields", [
    {"first_author": "Trotter, A. S."},
    {"author": ["Trotter, A. S.", "Smith, B."]},
    {"authors": ["Trotter, A. S.", "Smith, B."]},
])
def test_returned_author_metadata_supports_the_citation(tmp_path, fields):
    result = _grade(tmp_path, f"Trotter et al. (2017), `{BIBCODE}`.", [_metadata(**fields)])
    assert result.passed is True
    assert result.metrics["unsourced_attributions"] == []
    assert result.metrics["attribution_checked"] is True


def test_an_author_from_another_paper_cannot_be_attached_to_a_sourced_bibcode(tmp_path):
    result = _grade(tmp_path, f"Jones et al. 2017: `{BIBCODE}`.", [
        _metadata(bibcode=OTHER, first_author="Jones, B."),
        finished("search_ned", {"status": "ok", "preview": [{"Refcode": BIBCODE}]})])
    assert result.passed is False


@pytest.mark.parametrize("answer", ["Trotter et al. 2016.", "Smith et al. 2017."])
def test_wrong_year_or_nonleading_author_does_not_match_metadata(tmp_path, answer):
    result = _grade(tmp_path, answer, [_metadata(author=["Trotter, A.", "Smith, B."])])
    assert result.passed is False


def test_a_named_second_author_also_requires_evidence(tmp_path):
    answer = "Trotter & Jones (2017)."
    result = _grade(tmp_path, answer, [_metadata(author=["Trotter, A.", "Smith, B."])])
    assert result.passed is False


def test_two_returned_authors_support_a_paired_citation(tmp_path):
    result = _grade(tmp_path, "Trotter & Smith (2017).", [_metadata(author=["Trotter, A.", "Smith, B."])])
    assert result.passed is True


@pytest.mark.parametrize("events", [
    [finished("get_paper_abstract", {"status": "ok", "preview": [
        {"bibcode": BIBCODE, "abstract": "Trotter et al. 2017 are discussed here."}]})],
    [finished("read_text_file", {"status": "ok", "preview": [
        {"bibcode": BIBCODE, "year": 2017, "first_author": "Trotter, A."}]})],
    [finished("search_ads", {"status": "error", "preview": [
        {"bibcode": BIBCODE, "year": 2017, "first_author": "Trotter, A."}]})],
])
def test_abstract_mentions_local_files_and_failed_queries_do_not_establish_authorship(tmp_path, events):
    assert _grade(tmp_path, "Trotter et al. 2017.", events).passed is False


@pytest.mark.parametrize("answer", [
    "From memory, Trotter et al. 2017; this is background knowledge.",
    "The attribution 'Trotter et al. 2017' is not verified.",
    f"Only the identifier `{BIBCODE}` was returned; no author name is established.",
    "In 2017 the database was updated. The value is 0.670%/yr.",
])
def test_background_disclaimers_and_nonclaims_are_not_false_failures(tmp_path, answer):
    result = _grade(tmp_path, answer, [finished("search_ned", {"status": "ok", "preview": [{"rate": .670}]})])
    assert result.passed is True


@pytest.mark.parametrize("answer", [
    "From memory, the object is bright. Jones et al. 2017 measured it.",
    "From memory, Trotter et al. 2017; Jones et al. 2017 measured it.",
    "It was not Trotter et al. 2017 but Jones et al. 2017.",
])
def test_unrelated_background_and_negation_do_not_hide_an_asserted_author(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is False


def test_tasks_without_the_hard_check_still_report_unverified_authors(tmp_path):
    result = _grade(tmp_path, "Jones et al. 2017.", [], task_body=MINIMAL_TASK)
    assert result.passed is True
    assert result.metrics["attribution_checked"] is False
    assert result.metrics["unsourced_attributions"]


@pytest.mark.parametrize("answer", [
    "No change was measured by Jones et al. 2017.",
    "Not only Jones et al. 2017 measured this.",
    '"Jones et al. 2017" reported no variability.',
])
def test_negating_a_scientific_result_does_not_excuse_its_author(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is False


def test_query_metadata_is_not_a_returned_paper_record(tmp_path):
    result = _grade(tmp_path, "Jones et al. 2017.", [finished("search_ads", {
        "status": "ok", "count": 0, "query": {"first_author": "Jones", "year": 2017}, "preview": []})])
    assert result.passed is False


@pytest.mark.parametrize("answer", [
    "Jones et al. 2017 measured 0.670%/yr, but the exact flux was not returned.",
    "Jones et al. 2017 measured 0.670%/yr, and the source name is from memory.",
    "Not Jones et al. (2017) alone, but also Trotter et al. (2017), measured it.",
    "No Jones et al. (2017) measurement was missed.",
])
def test_unrelated_trailing_disclosures_and_focus_negation_do_not_hide_an_author(tmp_path, answer):
    result = _grade(tmp_path, answer, [_metadata(first_author="Trotter, A.")])
    assert result.passed is False
    assert any("Jones" in claim for claim in result.metrics["unsourced_attributions"])


@pytest.mark.parametrize("answer", [
    "Jones et al. 2017 used interpolation.",
    "Jones et al. 2017 did not use interpolation.",
    "Jones et al. 2017 analyzed training data.",
    "The study of interpolation is by Jones et al. 2017.",
    "Jones et al. 2017 measured the decline, a flux not returned by this tool.",
    "Not from memory, Jones et al. 2017 measured the decline.",
    "Jones et al. 2017 measured the decline, not from memory.",
])
def test_method_words_and_unrelated_qualifications_are_still_author_assertions(tmp_path, answer):
    result = _grade(tmp_path, answer, [])
    assert result.passed is False
    assert result.metrics["unsourced_attributions"] == ["Jones et al. 2017"]


@pytest.mark.parametrize("answer", [
    "From memory, Jones et al. 2017 measured the decline.",
    "As general background: Jones et al. 2017 measured the decline.",
    "Jones et al. 2017 (from memory) measured the decline.",
    "Jones et al. 2017 is not independently verified.",
])
def test_explicit_citation_qualifications_remain_disclaimed(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is True


@pytest.mark.parametrize("author", ["Dr. Jones", "Prof. Jones", "A. Jones", "\nJones", "\n  Jones"])
def test_honorifics_and_wrapped_prose_keep_the_explicit_paper_association(tmp_path, author):
    answer = f"The paper {BIBCODE} was written by {author} et al. 2017."
    result = _grade(tmp_path, answer, [
        _metadata(first_author="Trotter, A."),
        _metadata(bibcode=OTHER, first_author="Jones, A."),
    ])
    assert result.passed is False
    assert result.metrics["unsourced_attributions"] == ["Jones et al. 2017"]


@pytest.mark.parametrize("answer", [
    f"The paper {BIBCODE} was written by Dr. Trotter et al. 2017.",
    f"The paper {BIBCODE} was written by\nTrotter et al. 2017.",
    f"Trotter et al. 2017 wrote {BIBCODE}. Jones et al. 2017 measured it.",
    f"Trotter et al. 2017 wrote {BIBCODE}.\n\nJones et al. 2017 measured it.",
    f"| {BIBCODE} | Trotter et al. 2017 |\n| {OTHER} | Jones et al. 2017 |",
    f"Trotter et al. 2017 wrote {BIBCODE}\n- Jones et al. 2017 measured it.",
])
def test_association_preserves_supported_authors_and_independent_blocks(tmp_path, answer):
    result = _grade(tmp_path, answer, [
        _metadata(first_author="Trotter, A."),
        _metadata(bibcode=OTHER, first_author="Jones, A."),
    ])
    assert result.passed is True


def test_abbreviations_in_a_markdown_row_cannot_hide_its_bibcode(tmp_path):
    answer = f"| {BIBCODE} | By Dr. Jones et al. 2017 |"
    assert _grade(tmp_path, answer, [
        _metadata(first_author="Trotter, A."),
        _metadata(bibcode=OTHER, first_author="Jones, A."),
    ]).passed is False


@pytest.mark.parametrize("ending", ["|b|.", "|b|"])
def test_absolute_value_prose_does_not_merge_independent_paper_sentences(tmp_path, ending):
    answer = f"The paper {BIBCODE} was written by Jones et al. 2017. {OTHER} gives {ending}"
    assert _grade(tmp_path, answer, [
        _metadata(first_author="Trotter, A."),
        _metadata(bibcode=OTHER, first_author="Jones, A."),
    ]).passed is False


@pytest.mark.parametrize("answer", [
    "Jones et al. 2017 (from memory, not independently verified) measured the decline.",
    "Jones et al. 2017 (general background, not independently verified this session) measured it.",
    "Jones et al. 2017 (from memory, and not independently verified) measured it.",
    f"| {BIBCODE} | From memory, Jones et al. 2017 |",
    f"Paper | Author\n--- | ---\n{BIBCODE} | From memory, Jones et al. 2017",
    f"Author | Paper\n--- | ---\nFrom memory, Jones et al. 2017 | {BIBCODE}",
])
def test_combined_and_table_cell_qualifications_remain_explicit_disclaimers(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is True


@pytest.mark.parametrize("answer", [
    "Jones et al. 2017 were not confirmed by later observations.",
    "Jones et al. 2017 was not established at high significance.",
    "Jones et al. 2017 is not independently verified by later observations.",
    '"Jones et al. 2017" was not confirmed by later observations.',
])
def test_negating_confirmation_of_a_finding_still_asserts_its_author(tmp_path, answer):
    assert _grade(tmp_path, answer, []).passed is False


def test_unbounded_markdown_rows_keep_independent_identifiers(tmp_path):
    answer = f"Paper | Author\n--- | ---\n{BIBCODE} | Jones et al. 2017\n{OTHER} | Another row"
    assert _grade(tmp_path, answer, [
        _metadata(first_author="Trotter, A."),
        _metadata(bibcode=OTHER, first_author="Jones, A."),
    ]).passed is False
