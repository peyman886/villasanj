"""ADR-0007 verifier and renderer: the LLM writes slots; code writes every number and direction."""

import pytest

from tests.fakes.llm import NOW
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, SourceRef
from villasanj.shared.domain.slots import (
    Comparison,
    Fact,
    Relation,
    SlotError,
    SummaryPoint,
    ViolationCode,
    render,
    verify_points,
    verify_span,
    verify_text,
)

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
SOURCE = Provenance(ProvenanceMethod.OBSERVED, NOW, SourceRef("p", "https://p.test/1"), "s1")
FACTS = {
    "F1": Fact("F1", "۳٬۲۰۰٬۰۰۰ تومان", SOURCE),
    "F2": Fact("F2", "۴۰۰ متر", SOURCE),
}
COMPARISONS = {"C1": Comparison("C1", Relation.CHEAPER, SOURCE)}


def codes(text: str) -> list[ViolationCode]:
    return [v.code for v in verify_text(text, FACTS, COMPARISONS)]


@pytest.mark.parametrize(
    "text",
    [
        "این ویلا برای دو شب {F1} است و تا دریا {F2} فاصله دارد.",
        "روی این پلتفرم {C1} است.",
        # "بزرگ" without "تر" describes; it compares nothing.
        f"ویلایی دنج با حیاط بزرگ و منظره{ZWNJ}ی جنگل.",
        f"برای خانواده{ZWNJ}ها بهتر است.",  # subjective comparatives are prose
    ],
)
def test_clean_texts_pass(text: str) -> None:
    assert codes(text) == []


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("قیمت ۳ میلیون است", ViolationCode.DIGIT_OUTSIDE_SLOT),
        ("قیمت 3 است", ViolationCode.DIGIT_OUTSIDE_SLOT),
        ("قیمت \N{ARABIC-INDIC DIGIT THREE} است", ViolationCode.DIGIT_OUTSIDE_SLOT),
        ("قیمتش حدود سه میلیون است", ViolationCode.MONEY_WORD_OUTSIDE_SLOT),
        (f"فقط چند هزار تومان گران{ZWNJ}تر", ViolationCode.MONEY_WORD_OUTSIDE_SLOT),
        ("ده درصد تخفیف دارد", ViolationCode.MONEY_WORD_OUTSIDE_SLOT),
        (f"این ویلا ارزان{ZWNJ}تر است", ViolationCode.COMPARATIVE_OUTSIDE_SLOT),
        ("این ویلا ارزانتر است", ViolationCode.COMPARATIVE_OUTSIDE_SLOT),
        (f"به دریا نزدیک{ZWNJ}ترین است", ViolationCode.COMPARATIVE_OUTSIDE_SLOT),
        (f"هزینه{ZWNJ}ی کمتری دارد", ViolationCode.COMPARATIVE_OUTSIDE_SLOT),
        ("قیمت {F9} است", ViolationCode.UNKNOWN_SLOT),
    ],
)
def test_violations_are_caught(text: str, code: ViolationCode) -> None:
    assert code in codes(text)


def test_digits_inside_slots_are_fine_but_unknown_slots_are_not() -> None:
    assert codes("{F1} و {C1}") == []
    assert codes("{F1} {C7}") == [ViolationCode.UNKNOWN_SLOT]


def test_render_fills_slots_and_lists_them_for_provenance_links() -> None:
    rendered = render("دو شب {F1}؛ روی این پلتفرم {C1} و تا دریا {F2}.", FACTS, COMPARISONS)
    assert (
        rendered.text == f"دو شب ۳٬۲۰۰٬۰۰۰ تومان؛ روی این پلتفرم ارزان{ZWNJ}تر و تا دریا ۴۰۰ متر."
    )
    assert rendered.used == ("F1", "C1", "F2")


def test_render_refuses_a_text_that_fails_verification() -> None:
    with pytest.raises(SlotError) as caught:
        render("قیمت ۳ میلیون و {F9}", FACTS, COMPARISONS)
    found = {v.code for v in caught.value.violations}
    assert found == {
        ViolationCode.UNKNOWN_SLOT,
        ViolationCode.DIGIT_OUTSIDE_SLOT,
        ViolationCode.MONEY_WORD_OUTSIDE_SLOT,
    }
    assert "unknown_slot" in str(caught.value)


def test_every_relation_renders_its_own_word() -> None:
    words = {Comparison("C1", r, SOURCE).text for r in Relation}
    assert len(words) == len(Relation)


def test_summary_points_must_cite_known_reviews_and_label_single_opinions() -> None:
    known = {"R1", "R2", "R3"}
    good = [
        SummaryPoint("تمیز", ("R1", "R2")),
        SummaryPoint("سروصدا", ("R3",), single_opinion=True),
    ]
    assert verify_points(good, known) == []
    bad = [
        SummaryPoint("بدون منبع", ()),
        SummaryPoint("منبع ناشناخته", ("R1", "R9")),
        SummaryPoint("یک نفر گفته", ("R2", "R2")),  # the same review twice is still one opinion
    ]
    assert [v.code for v in verify_points(bad, known)] == [
        ViolationCode.NO_CITATION,
        ViolationCode.UNKNOWN_REVIEW,
        ViolationCode.SINGLE_OPINION_NOT_LABELLED,
    ]


def test_claim_spans_must_be_verbatim_after_normalization() -> None:
    source = f"ویلا دارای استخر سرپوشیده و  فاصله{ZWNJ}ی ۵ دقیقه تا دریا"
    assert verify_span("استخر سرپوشیده", source) == []
    assert verify_span(f"فاصله{ZWNJ}ی ۵ دقیقه", source) == []
    assert verify_span("استخر روباز", source)[0].code is ViolationCode.SPAN_NOT_IN_SOURCE
    assert verify_span("", source) != []
