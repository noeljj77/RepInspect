import pytest

from app.services.ai.grounding import (
    Grounding,
    SymbolRef,
    ground_file_explanation,
    ground_overview,
    ground_technologies,
)
from app.services.ai.schemas import (
    OVERVIEW_SECTIONS,
    RawCitation,
    RawFileExplanation,
    RawFinding,
    RawKeySymbol,
    RawOverview,
    RawSection,
    RawTechnologies,
    RawTechnology,
)

MAIN = (
    "from fastapi import FastAPI\n"  # 1
    "\n"  # 2
    "app = FastAPI()\n"  # 3
    "\n"  # 4
    "\n"  # 5
    '@app.get("/health")\n'  # 6
    "def health():\n"  # 7
    '    return {"status": "ok"}\n'  # 8
)
FILES = {
    "backend/app/main.py": MAIN,
    "backend/app/util.py": "def helper():\n    return 1\n\n\ndef helper_two():\n    return 2\n",
    "other/main.py": "x = 1\n",
    "README.md": "# Demo\n\nA demo project that converts things.\n",
    "web/src/App.tsx": "export default function App() { return null }\n",
}
MAIN_PATH = "backend/app/main.py"


@pytest.fixture
def g() -> Grounding:
    return Grounding(FILES, FILES.get)


def cite(path=MAIN_PATH, start=1, end=1, quote="from fastapi import FastAPI") -> RawCitation:
    return RawCitation(path=path, start_line=start, end_line=end, quote=quote)


# --- resolving paths ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        MAIN_PATH,
        f"./{MAIN_PATH}",
        f"/{MAIN_PATH}",
        "backend\\app\\main.py",
        f"`{MAIN_PATH}`",
        f" {MAIN_PATH} ",
        "app/main.py",
    ],
)
def test_paths_are_resolved_forgivingly(g, raw):
    assert g.resolve_path(raw) == MAIN_PATH


@pytest.mark.parametrize(
    "raw", ["main.py", "nope.py", "backend/app/missing.py", "../../etc/passwd", ""]
)
def test_ambiguous_or_unknown_paths_do_not_resolve(g, raw):
    assert g.resolve_path(raw) is None  # "main.py" matches two files, so it is not guessed


# --- citations ----------------------------------------------------------------------------------------


def test_a_correct_citation_reports_the_lines_the_quote_really_covers(g):
    result = g.verify_citation(cite(start=6, end=8, quote='@app.get("/health")\ndef health():'))

    assert (result.path, result.start_line, result.end_line) == (
        MAIN_PATH,
        6,
        7,
    )  # not line 8: it was not quoted


def test_whitespace_differences_in_the_quote_do_not_matter(g):
    result = g.verify_citation(
        cite(start=7, end=8, quote='def health():   return   {"status": "ok"}')
    )

    assert result is not None and (result.start_line, result.end_line) == (7, 8)


def test_line_number_prefixes_in_the_quote_are_ignored(g):
    result = g.verify_citation(cite(start=3, end=3, quote="3| app = FastAPI()"))

    assert result is not None and result.start_line == 3


def test_a_quote_a_line_or_two_off_is_still_accepted(g):
    assert g.verify_citation(cite(start=5, end=5, quote="app = FastAPI()")) is not None


def test_wrong_line_numbers_are_corrected_when_the_quote_exists_elsewhere(g):
    result = g.verify_citation(cite(start=40, end=42, quote="return {'status'".replace("'", '"')))

    assert (result.start_line, result.end_line) == (8, 8)


def test_a_multi_line_quote_at_wrong_lines_is_relocated_to_its_true_span(g):
    result = g.verify_citation(
        cite(start=1, end=2, quote='def health():\n    return {"status": "ok"}')
    )

    assert (result.start_line, result.end_line) == (7, 8)


def test_the_occurrence_nearest_the_claim_is_chosen(g):
    files = {"a.py": "x = 1\n" + "y = 2\n" * 10 + "x = 1\n"}
    grounding = Grounding(files, files.get)

    near_end = grounding.verify_citation(cite("a.py", start=11, end=11, quote="x = 1"))
    near_start = grounding.verify_citation(cite("a.py", start=1, end=1, quote="x = 1"))

    assert near_end.start_line == 12 and near_start.start_line == 1


def test_a_quote_that_is_not_in_the_file_is_rejected(g):
    assert g.verify_citation(cite(start=3, end=3, quote="app = Flask(__name__)")) is None


def test_a_quote_found_only_in_another_file_is_rejected(g):
    assert g.verify_citation(cite(path=MAIN_PATH, quote="def helper_two():")) is None


def test_an_unknown_file_is_rejected(g):
    assert g.verify_citation(cite(path="requirements.txt", quote="django==5.0")) is None


def test_a_path_with_the_wrong_prefix_is_repaired_when_it_is_unambiguous(g):
    assert (
        g.verify_citation(cite(path="app/main.py", start=3, end=3, quote="app = FastAPI()")).path
        == MAIN_PATH
    )


@pytest.mark.parametrize("quote", ["", "  ", "x", "app"])
def test_empty_or_trivial_quotes_prove_nothing(g, quote):
    assert g.verify_citation(cite(quote=quote)) is None


def test_reversed_and_out_of_range_lines_are_tolerated(g):
    reversed_range = g.verify_citation(cite(start=8, end=6, quote='return {"status": "ok"}'))
    past_the_end = g.verify_citation(cite(start=900, end=950, quote="app = FastAPI()"))

    assert reversed_range is not None and past_the_end.start_line == 3


def test_the_final_newline_is_not_counted_as_a_line(g):
    assert len(g.lines(MAIN_PATH)) == 8


def test_unreadable_files_cannot_be_cited():
    grounding = Grounding(["gone.py"], lambda path: None)

    assert grounding.verify_citation(cite("gone.py", quote="anything here")) is None


def test_long_quotes_are_shortened_for_display(g):
    result = g.verify_citation(cite(start=1, end=8, quote=MAIN))

    assert result is not None and len(result.quote) <= 300


# --- mentions of files ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "See backend/app/main.py for the app.",
        "Defined in app/util.py and README.md.",
        "The entry point main.py starts it.",
        "Built with Next.js, Node.js and Vue.js.",
        "Docs at https://example.com/docs/guide.md and example.com/api/spec.json.",
        "Version v1.2.3 released, e.g. today.",
        "A plain sentence with no files at all.",
    ],
)
def test_real_files_urls_and_product_names_are_not_flagged(g, text):
    assert g.ungrounded_paths(text) == []


def test_invented_files_are_found(g):
    text = "It reads backend/app/missing.py and config.yaml, then util.py."

    assert g.ungrounded_paths(text) == ["backend/app/missing.py", "config.yaml"]


def test_a_path_is_reported_once_and_not_again_as_its_own_tail(g):
    assert g.ungrounded_paths("Check src/made_up/server.py and src/made_up/server.py.") == [
        "src/made_up/server.py"
    ]


# --- findings -------------------------------------------------------------------------------------------------


def test_a_finding_with_a_confirmed_citation_is_verified(g):
    finding, dropped = g.ground_finding(
        RawFinding(
            statement="Creates the app.", citations=[cite(start=3, end=3, quote="app = FastAPI()")]
        )
    )

    assert finding.verified is True and dropped == 0 and finding.ungrounded_paths == []


def test_a_finding_without_citations_is_unverified(g):
    finding, dropped = g.ground_finding(
        RawFinding(statement="Probably uses a cache.", citations=[])
    )

    assert finding.verified is False and finding.citations == [] and dropped == 0


def test_invented_citations_are_dropped_and_counted(g):
    good = cite(start=3, end=3, quote="app = FastAPI()")
    bad = cite(path="requirements.txt", quote="django==5.0")
    finding, dropped = g.ground_finding(
        RawFinding(statement="Uses FastAPI.", citations=[bad, good, bad])
    )

    assert [c.path for c in finding.citations] == [MAIN_PATH]
    assert finding.verified is True and dropped == 2


def test_a_finding_whose_only_citation_is_invented_is_unverified(g):
    finding, dropped = g.ground_finding(
        RawFinding(
            statement="Uses Django.", citations=[cite(path="requirements.txt", quote="django==5.0")]
        )
    )

    assert finding.verified is False and dropped == 1


def test_a_finding_mentioning_a_nonexistent_file_is_never_verified(g):
    finding, _ = g.ground_finding(
        RawFinding(
            statement="Settings live in config/settings.py.",
            citations=[cite(start=3, end=3, quote="app = FastAPI()")],
        )
    )

    assert finding.verified is False and finding.ungrounded_paths == ["config/settings.py"]


def test_duplicate_citations_are_merged_and_the_count_is_limited(g):
    same = cite(start=3, end=3, quote="app = FastAPI()")
    lines = [
        cite(start=n, end=n, quote=text)
        for n, text in enumerate(MAIN.split("\n")[:8], 1)
        if text.strip()
    ]
    finding, _ = g.ground_finding(RawFinding(statement="x", citations=[same, same, *lines]))

    assert len(finding.citations) == 4
    assert len({(c.start_line, c.end_line) for c in finding.citations}) == 4


def test_overlong_statements_are_shortened(g):
    finding, _ = g.ground_finding(RawFinding(statement="word " * 300, citations=[]))

    assert len(finding.statement) <= 500


# --- whole overview -----------------------------------------------------------------------------------------------


def section(key, summary="Summary.", determined=True, findings=()):
    return RawSection(key=key, summary=summary, determined=determined, findings=list(findings))


def finding(statement="Creates the app.", citations=None):
    return RawFinding(
        statement=statement,
        citations=[cite(start=3, end=3, quote="app = FastAPI()")]
        if citations is None
        else citations,
    )


def test_every_section_is_present_in_order_with_its_title(g):
    result = ground_overview(RawOverview(sections=[section("running"), section("purpose")]), g)

    assert [(s.key, s.title) for s in result.sections] == OVERVIEW_SECTIONS
    assert len(result.sections) == 10


def test_sections_the_model_skipped_are_marked_undetermined(g):
    result = ground_overview(RawOverview(sections=[section("purpose")]), g)

    skipped = next(s for s in result.sections if s.key == "frontend")
    assert (skipped.determined, skipped.summary, skipped.findings) == (False, "", [])


def test_a_repeated_section_keeps_the_first(g):
    raw = RawOverview(sections=[section("purpose", "First."), section("purpose", "Second.")])

    assert ground_overview(raw, g).sections[0].summary == "First."


def test_a_section_that_says_nothing_is_not_determined_even_if_the_model_claims_it_is(g):
    result = ground_overview(
        RawOverview(sections=[section("data", summary="", determined=True)]), g
    )

    assert next(s for s in result.sections if s.key == "data").determined is False


def test_findings_are_grounded_and_removed_citations_are_totalled(g):
    bad = cite(path="nope.py", quote="invented code")
    raw = RawOverview(
        sections=[
            section("purpose", findings=[finding(citations=[bad]), finding()]),
            section("backend", findings=[finding(citations=[bad])]),
        ]
    )

    result = ground_overview(raw, g)

    assert result.removed_citations == 2
    assert [f.verified for f in result.sections[0].findings] == [False, True]


def test_findings_per_section_are_limited_and_blank_ones_removed(g):
    findings = [finding(f"Fact {i}.") for i in range(10)] + [finding("   ")]

    result = ground_overview(RawOverview(sections=[section("purpose", findings=findings)]), g)

    assert len(result.sections[0].findings) == 6


def test_an_invented_file_in_a_summary_is_recorded(g):
    result = ground_overview(
        RawOverview(sections=[section("modules", summary="Key code is in src/ghost/engine.py.")]), g
    )

    assert next(s for s in result.sections if s.key == "modules").ungrounded_paths == [
        "src/ghost/engine.py"
    ]


def test_overlong_summaries_are_shortened(g):
    result = ground_overview(RawOverview(sections=[section("purpose", summary="x " * 1000)]), g)

    assert len(result.sections[0].summary) <= 900


# --- technologies ---------------------------------------------------------------------------------------------------


def tech(name, **overrides):
    values = {
        "what_it_is": "A thing.",
        "plausible_reason": "It may be fast.",
        "advantages": ["Fast"],
        "alternatives": ["Other"],
        "trade_offs": ["Costly"],
    }
    values.update(overrides)
    return RawTechnology(name=name, **values)


def test_only_detected_technologies_are_kept_under_their_canonical_names():
    raw = RawTechnologies(
        technologies=[tech("fastapi"), tech("Kubernetes"), tech(" FastAPI "), tech("SQLAlchemy")]
    )

    result = ground_technologies(raw, ["FastAPI", "SQLAlchemy", "Docker"])

    assert [t.name for t in result.technologies] == [
        "FastAPI",
        "SQLAlchemy",
    ]  # no invented or repeated ones


def test_technology_lists_are_cleaned_and_limited():
    raw = RawTechnologies(
        technologies=[tech("FastAPI", advantages=["a", "", "  ", "b", "c", "d", "e", "f", "g"])]
    )

    advantages = ground_technologies(raw, ["FastAPI"]).technologies[0].advantages

    assert advantages == ["a", "b", "c", "d", "e"]


# --- file explanations ------------------------------------------------------------------------------------------------


SYMBOLS = [
    SymbolRef("health", "health", "function", 7),
    SymbolRef("save", "User.save", "method", 12),
]


def explanation(**overrides) -> RawFileExplanation:
    values = {
        "purpose": "Defines the health endpoint.",
        "determined": True,
        "inputs_outputs": "Returns a status.",
        "findings": [finding()],
        "key_symbols": [RawKeySymbol(name="health", explanation="Reports status.")],
    }
    values.update(overrides)
    return RawFileExplanation(**values)


def test_key_symbols_must_exist_and_match_by_either_name(g):
    raw = explanation(
        key_symbols=[
            RawKeySymbol(name="health", explanation="Reports status."),
            RawKeySymbol(name="User.save", explanation="Saves a user."),
            RawKeySymbol(name="save", explanation="Repeated under a short name."),
            RawKeySymbol(name="invented_function", explanation="Does magic."),
            RawKeySymbol(name="health", explanation="Listed twice."),
            RawKeySymbol(name="User.save", explanation="   "),
        ]
    )

    result = ground_file_explanation(raw, SYMBOLS, g)

    assert [(s.qualified_name, s.kind, s.start_line) for s in result.key_symbols] == [
        ("health", "function", 7),
        ("User.save", "method", 12),
    ]


def test_file_findings_are_grounded_like_overview_findings(g):
    bad = cite(path="nope.py", quote="invented code")
    result = ground_file_explanation(
        explanation(findings=[finding(), finding(citations=[bad])]), SYMBOLS, g
    )

    assert [f.verified for f in result.findings] == [True, False]
    assert result.removed_citations == 1


def test_invented_files_in_the_purpose_are_recorded_and_empty_purpose_is_undetermined(g):
    result = ground_file_explanation(
        explanation(purpose="It wraps lib/hidden/core.py."), SYMBOLS, g
    )
    empty = ground_file_explanation(explanation(purpose="  ", determined=True), SYMBOLS, g)

    assert result.ungrounded_paths == ["lib/hidden/core.py"]
    assert empty.determined is False
