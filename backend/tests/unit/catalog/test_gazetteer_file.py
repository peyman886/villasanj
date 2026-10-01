"""The curated gazetteer file: schema checks and observed spellings (ROADMAP M2 criterion 4)."""

from pathlib import Path

import pytest

from villasanj.catalog.domain.gazetteer import PlaceKind
from villasanj.catalog.infrastructure.gazetteer_file import load_gazetteer
from villasanj.shared.application.errors import ConfigurationError

CONFIG = Path(__file__).resolve().parents[4] / "config" / "gazetteer.toml"
GAZETTEER = load_gazetteer(CONFIG)


def test_v1_has_the_planned_size() -> None:
    assert 100 <= len(GAZETTEER) <= 200


# Spellings as published on the platforms (2026-10-01), with the place we expect.
@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("سفید تمشک", "sefid-tameshk"),
        ("روستای سفید تمشک", "sefid-tameshk"),
        ("تله کابین رامسر،سفیدتمشک", "sefid-tameshk"),
        ("اربه کله", "arbeh-kaleh"),
        ("روستای اربکله", "arbeh-kaleh"),
        ("ساداتشهر", "sadat-shahr"),
        ("رامسر ساداتشهر", "sadat-shahr"),
        ("کتالم و سادات شهر", "katalom-sadat-shahr"),
        ("ketalem", "katalom-sadat-shahr"),
        ("شیرود - خزر کنار", "khazar-kenar"),
        ("شیرود،کاسگرمحله", "kasgar-mahalleh"),
        ("منطقه دوهزار - روستای برسه", "barseh"),
        ("صفا محله (لاتمحله)", "lat-mahalleh"),
        ("خیابان شهید منتظری(تنگدره)", "tangdareh"),
        ("طلارسر", "talarsar"),
        ("میانحاله", "mian-haleh"),
        ("نعمت اباد", "nemat-abad"),
        ("روستای قنبراباد", "ghanbar-abad"),
        ("شهرک چهارصد دستگاه", "chaharsad-dastgah"),
        ("محله رمک", "ramak"),
        ("روستا پتک", "patak"),
        ("shiroud", "shirud"),
    ],
)
def test_resolves_observed_spellings(text: str, slug: str) -> None:
    place = GAZETTEER.resolve(text)
    assert place is not None
    assert place.slug == slug


@pytest.mark.parametrize(
    "text",
    [
        "بلوار معلم",
        "میدان شهید رجایی",
        "محله",
        "بر جاده اصلی خط دریا که از سمت چالوس بعد از شیرود و از سمت رشت بعد از رامسر",
        "جاده جواهرده",
        "لپاسر",  # probably لپاسرک, but typo merges are not guessed
    ],
)
def test_streets_sentences_and_typos_stay_unresolved(text: str) -> None:
    assert GAZETTEER.resolve(text) is None


def test_localities_have_city_parents() -> None:
    sefid = GAZETTEER.get("sefid-tameshk")
    assert sefid is not None
    assert sefid.kind is PlaceKind.LOCALITY
    assert sefid.parent == "ramsar"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('version = 1\n[[places]]\nslug = "a"\nname_fa = "الف"\nkind = "town"\n', "kind"),
        (
            'version = 1\n[[places]]\nslug = "a"\nname_fa = "الف"\nkind = "locality"\n'
            'parent = "nowhere"\n',
            "not a city",
        ),
        (
            'version = 1\n[[places]]\nslug = "a"\nname_fa = "الف"\nkind = "city"\n'
            '[[places]]\nslug = "a"\nname_fa = "ب"\nkind = "city"\n',
            "duplicate",
        ),
        (
            'version = 1\n[[places]]\nslug = "a"\nname_fa = "شیرود"\nkind = "city"\n'
            '[[places]]\nslug = "b"\nname_fa = "شی رود"\nkind = "locality"\n',
            "ambiguous",
        ),
        ("version = ", "invalid gazetteer"),
    ],
)
def test_invalid_files_are_rejected(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "gazetteer.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigurationError, match=message):
        load_gazetteer(path)


def test_missing_file_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_gazetteer(tmp_path / "absent.toml")
