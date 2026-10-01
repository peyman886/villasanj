"""Place-alias cases (ROADMAP M2 criterion 4, with the text and money tables)."""

import pytest

from villasanj.catalog.domain.gazetteer import Gazetteer, Place, PlaceKind, place_key

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
ARABIC_YEH = "\N{ARABIC LETTER YEH}"

GAZETTEER = Gazetteer(
    [
        Place("ramsar", "رامسر", PlaceKind.CITY),
        Place("tonekabon", "تنکابن", PlaceKind.CITY),
        Place(
            "kelardasht",
            "کلاردشت",
            PlaceKind.CITY,
            aliases=frozenset({"Kelardasht", "Kelar Dasht"}),
        ),
        Place("sefid-tameshk", "سفیدتمشک", PlaceKind.LOCALITY, parent="ramsar"),
        Place("sadat-shahr", f"سادات{ZWNJ}شهر", PlaceKind.LOCALITY, parent="ramsar"),
        Place("lorsanur", "لرسانور", PlaceKind.LOCALITY, parent="ramsar"),
        Place("zaki-mahalleh", f"زکی{ZWNJ}محله", PlaceKind.LOCALITY, parent="ramsar"),
    ]
)


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("کلاردشت", "kelardasht"),
        ("کلار دشت", "kelardasht"),
        (f"کلار{ZWNJ}دشت", "kelardasht"),
        ("Kelardasht", "kelardasht"),
        ("kelar dasht", "kelardasht"),
        ("سفید تمشک", "sefid-tameshk"),
        ("سفیدتمشک", "sefid-tameshk"),
        ("ساداتشهر", "sadat-shahr"),
        ("سادات شهر", "sadat-shahr"),
        ("روستای لرسانور", "lorsanur"),
        ("شهر رامسر", "ramsar"),
        ("زکی محله", "zaki-mahalleh"),
        (f"سف{ARABIC_YEH}دتمشک", "sefid-tameshk"),  # Arabic yeh
        ("تله کابین رامسر،سفیدتمشک", "sefid-tameshk"),  # locality beats city
        ("رامسر - سفید تمشک", "sefid-tameshk"),
        ("تنکابن", "tonekabon"),
        ("  تنکابن ", "tonekabon"),
    ],
)
def test_resolves_spelling_variants(text: str, slug: str) -> None:
    place = GAZETTEER.resolve(text)
    assert place is not None
    assert place.slug == slug


@pytest.mark.parametrize(
    "text",
    ["بلوار امام خمینی", "بر جاده اصلی خط دریا", "", None, "مرکز شهر"],
)
def test_unknown_or_non_place_text_resolves_to_nothing(text: str | None) -> None:
    assert GAZETTEER.resolve(text) is None


def test_key_ignores_spacing_prefixes_and_case() -> None:
    assert place_key("روستای  لرسانور") == place_key("لرسانور")
    assert place_key("Kelar Dasht") == place_key("kelardasht")


def test_ambiguous_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="ambiguous"):
        Gazetteer([Place("a", "شیرود", PlaceKind.CITY), Place("b", "شی رود", PlaceKind.LOCALITY)])
