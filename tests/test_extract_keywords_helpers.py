"""Unit tests for pure helper functions in scripts/extract_keywords.py.

These tests do not require a database connection, spaCy, or YAKE.
"""

import argparse
from datetime import date
from pathlib import Path

import pytest

import scripts.extract_keywords as ek


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

def test_normalize_text_lowercase_and_accents():
    assert ek.normalize_text("Santiago del Estero") == "santiago del estero"


def test_normalize_text_strips_punctuation_and_extra_spaces():
    assert ek.normalize_text("  ¡Hola,   Mundo!  ") == "hola mundo"


def test_normalize_text_removes_combining_diacritics():
    assert ek.normalize_text("niño") == "nino"


def test_normalize_text_preserves_hyphens():
    assert ek.normalize_text("bien-estar") == "bien-estar"


def test_normalize_text_empty_and_none():
    assert ek.normalize_text("") == ""
    assert ek.normalize_text(None) == ""


def test_normalize_text_spanish_special_chars():
    assert ek.normalize_text("¿Cómo estás?") == "como estas"


# ---------------------------------------------------------------------------
# clean_display
# ---------------------------------------------------------------------------

def test_clean_display_collapses_whitespace():
    assert ek.clean_display("  La   Banda  ") == "La Banda"


def test_clean_display_empty_and_none():
    assert ek.clean_display("") == ""
    assert ek.clean_display(None) == ""


def test_clean_display_preserves_case_and_punctuation():
    assert ek.clean_display("  ¡Hola, Mundo!  ") == "¡Hola, Mundo!"


# ---------------------------------------------------------------------------
# count_alias_occurrences
# ---------------------------------------------------------------------------

def test_count_alias_occurrences_basic():
    doc = "paro docente en la provincia de santiago del estero"
    assert ek.count_alias_occurrences(doc, "paro docente") == 1


def test_count_alias_occurrences_multiple():
    doc = "paro docente y mas paro docente en la escuela"
    assert ek.count_alias_occurrences(doc, "paro docente") == 2


def test_count_alias_occurrences_word_boundaries():
    doc = "paro docente y parodocente"
    assert ek.count_alias_occurrences(doc, "paro docente") == 1


def test_count_alias_occurrences_no_match():
    assert ek.count_alias_occurrences("transporte publico", "paro docente") == 0


def test_count_alias_occurrences_hyphen_as_word_boundary():
    # Hyphen is a \w character, so it should be part of the word.
    doc = "bien-estar y bien estar"
    assert ek.count_alias_occurrences(doc, "bien estar") == 1


# ---------------------------------------------------------------------------
# is_omitted_keyword / filter_omitted_hits
# ---------------------------------------------------------------------------

def test_is_omitted_keyword_true():
    assert ek.is_omitted_keyword("leer mas", {"leer mas", "ver mas"})


def test_is_omitted_keyword_false():
    assert not ek.is_omitted_keyword("paro docente", {"leer mas"})


def test_filter_omitted_hits_removes_matches():
    hits = [
        ek.KeywordHit(
            keyword="Leer más",
            normalized_keyword="leer mas",
            canonical_keyword=None,
            normalized_canonical_keyword=None,
            keyword_type="topic",
            extractor_source="spacy",
            score=1.0,
            occurrences=5,
        ),
        ek.KeywordHit(
            keyword="Paro docente",
            normalized_keyword="paro docente",
            canonical_keyword=None,
            normalized_canonical_keyword=None,
            keyword_type="topic",
            extractor_source="spacy",
            score=1.0,
            occurrences=3,
        ),
    ]
    omitted = {"leer mas"}
    result = ek.filter_omitted_hits(hits, omitted)
    assert len(result) == 1
    assert result[0].normalized_keyword == "paro docente"


def test_filter_omitted_hits_empty_omitted_list():
    hits = [
        ek.KeywordHit(
            keyword="Paro docente",
            normalized_keyword="paro docente",
            canonical_keyword=None,
            normalized_canonical_keyword=None,
            keyword_type="topic",
            extractor_source="spacy",
            score=1.0,
            occurrences=3,
        ),
    ]
    assert ek.filter_omitted_hits(hits, set()) == hits


def test_filter_omitted_hits_empty_hits():
    assert ek.filter_omitted_hits([], {"leer mas"}) == []


# ---------------------------------------------------------------------------
# build_alias_map
# ---------------------------------------------------------------------------

def _make_entry(canonical, aliases, enabled=True, keyword_type="topic", priority=0):
    return ek.DictionaryEntry(
        canonical=canonical,
        normalized=ek.normalize_text(canonical),
        keyword_type=keyword_type,
        category=None,
        priority=priority,
        enabled=enabled,
        aliases=tuple(aliases),
        normalized_aliases=tuple(ek.normalize_text(a) for a in aliases),
    )


def test_build_alias_map_maps_aliases_to_entry():
    entry = _make_entry("La Banda", ["La Banda", "ciudad de La Banda"])
    alias_map = ek.build_alias_map([entry])
    assert alias_map["la banda"] is entry
    assert alias_map["ciudad de la banda"] is entry


def test_build_alias_map_skips_disabled_entries():
    enabled = _make_entry("La Banda", ["La Banda"])
    disabled = _make_entry("Termas", ["Termas"], enabled=False)
    alias_map = ek.build_alias_map([enabled, disabled])
    assert "la banda" in alias_map
    assert "termas" not in alias_map


# ---------------------------------------------------------------------------
# canonicalize_hit / canonicalize_hits
# ---------------------------------------------------------------------------

def _make_hit(
    normalized_keyword,
    keyword=None,
    extractor_source="spacy",
    score=1.0,
    occurrences=1,
    keyword_type=None,
):
    return ek.KeywordHit(
        keyword=keyword or normalized_keyword,
        normalized_keyword=normalized_keyword,
        canonical_keyword=None,
        normalized_canonical_keyword=None,
        keyword_type=keyword_type,
        extractor_source=extractor_source,
        score=score,
        occurrences=occurrences,
    )


def test_canonicalize_hit_replaces_with_entry():
    entry = _make_entry("La Banda", ["La Banda", "ciudad de La Banda"], keyword_type="place")
    alias_map = ek.build_alias_map([entry])
    hit = _make_hit("ciudad de la banda")
    result = ek.canonicalize_hit(hit, alias_map)
    assert result.keyword == "La Banda"
    assert result.normalized_keyword == "la banda"
    assert result.canonical_keyword == "La Banda"
    assert result.normalized_canonical_keyword == "la banda"
    assert result.keyword_type == "place"
    assert result.extractor_source == "spacy"


def test_canonicalize_hit_passes_through_unknown():
    hit = _make_hit("desconocido", keyword="Desconocido", keyword_type="topic")
    result = ek.canonicalize_hit(hit, {})
    assert result is hit


def test_canonicalize_hits_list():
    entry = _make_entry("La Banda", ["La Banda"], keyword_type="place")
    alias_map = ek.build_alias_map([entry])
    hits = [
        _make_hit("la banda"),
        _make_hit("otro"),
    ]
    results = ek.canonicalize_hits(hits, alias_map)
    assert len(results) == 2
    assert results[0].canonical_keyword == "La Banda"
    assert results[1].canonical_keyword is None


# ---------------------------------------------------------------------------
# merge_hits
# ---------------------------------------------------------------------------

def test_merge_hits_aggregates_same_key():
    hits = [
        _make_hit("paro docente", keyword="Paro docente", extractor_source="dictionary", score=1.5, occurrences=2),
        _make_hit("paro docente", keyword="Paro docente", extractor_source="dictionary", score=1.2, occurrences=3),
    ]
    result = ek.merge_hits(hits)
    assert len(result) == 1
    assert result[0].occurrences == 5
    assert result[0].score == 1.5


def test_merge_hits_different_keys_remain_separate():
    hits = [
        _make_hit("paro docente", keyword="Paro docente", extractor_source="dictionary", score=1.5, occurrences=2),
        _make_hit("transporte publico", keyword="Transporte público", extractor_source="dictionary", score=1.0, occurrences=1),
    ]
    result = ek.merge_hits(hits)
    assert len(result) == 2


def test_merge_hits_zero_and_none_scores_regression_for_issue_1():
    """A hit with score=0.0 and another with score=None must merge to 0.0.

    This is a regression test for issue #1 where truthiness caused a zero
    score to be discarded in favor of None.
    """
    hits = [
        _make_hit("tema", keyword="Tema", extractor_source="dictionary", score=0.0, occurrences=1),
        _make_hit("tema", keyword="Tema", extractor_source="dictionary", score=None, occurrences=1),
    ]
    result = ek.merge_hits(hits)
    assert len(result) == 1
    assert result[0].score == 0.0


def test_merge_hits_both_none_scores():
    hits = [
        _make_hit("tema", keyword="Tema", extractor_source="spacy", score=None, occurrences=1),
        _make_hit("tema", keyword="Tema", extractor_source="spacy", score=None, occurrences=1),
    ]
    result = ek.merge_hits(hits)
    assert len(result) == 1
    assert result[0].score is None


def test_merge_hits_prefers_canonical_when_first_has_none():
    hits = [
        _make_hit("santiago", keyword="Santiago", extractor_source="spacy", score=1.0, occurrences=1),
        ek.KeywordHit(
            keyword="Santiago del Estero",
            normalized_keyword="santiago",
            canonical_keyword="Santiago del Estero",
            normalized_canonical_keyword="santiago del estero",
            keyword_type="place",
            extractor_source="spacy",
            score=1.2,
            occurrences=1,
        ),
    ]
    result = ek.merge_hits(hits)
    assert len(result) == 1
    assert result[0].canonical_keyword == "Santiago del Estero"
    assert result[0].normalized_canonical_keyword == "santiago del estero"


def test_merge_hits_empty():
    assert ek.merge_hits([]) == []


# ---------------------------------------------------------------------------
# month_start_from_string
# ---------------------------------------------------------------------------

def test_month_start_from_string_valid():
    assert ek.month_start_from_string("2024-03") == date(2024, 3, 1)


def test_month_start_from_string_leading_trailing_whitespace():
    assert ek.month_start_from_string("  2024-03  ") == date(2024, 3, 1)


def test_month_start_from_string_invalid_format():
    with pytest.raises(argparse.ArgumentTypeError):
        ek.month_start_from_string("2024/03")


def test_month_start_from_string_invalid_month():
    with pytest.raises(argparse.ArgumentTypeError):
        ek.month_start_from_string("2024-13")


def test_month_start_from_string_empty():
    with pytest.raises(argparse.ArgumentTypeError):
        ek.month_start_from_string("")


def test_month_start_from_string_none():
    with pytest.raises(argparse.ArgumentTypeError):
        ek.month_start_from_string(None)


# ---------------------------------------------------------------------------
# month_bounds
# ---------------------------------------------------------------------------

def test_month_bounds_regular_month():
    start, end = ek.month_bounds(date(2024, 3, 1))
    assert start == date(2024, 3, 1)
    assert end == date(2024, 4, 1)


def test_month_bounds_february_leap_year():
    start, end = ek.month_bounds(date(2024, 2, 1))
    assert start == date(2024, 2, 1)
    assert end == date(2024, 3, 1)


def test_month_bounds_december_rollover():
    start, end = ek.month_bounds(date(2024, 12, 1))
    assert start == date(2024, 12, 1)
    assert end == date(2025, 1, 1)


def test_month_bounds_exclusive_end():
    # 31-day month ends at the first day of the next month.
    start, end = ek.month_bounds(date(2024, 5, 1))
    assert end == date(2024, 6, 1)


# ---------------------------------------------------------------------------
# load_keyword_config
# ---------------------------------------------------------------------------

def test_load_keyword_config(tmp_path):
    yaml = pytest.importorskip("yaml")
    config_path = tmp_path / "dictionary.yml"
    config_path.write_text(
        """
version: 1
language: es
omitted_keywords:
  - leer mas
  - ver mas
entries:
  - canonical: "La Banda"
    type: "place"
    category: "territorio"
    priority: 9
    enabled: true
    aliases:
      - "La Banda"
      - "ciudad de La Banda"
  - canonical: "Disabled Entry"
    type: "topic"
    priority: 0
    enabled: false
    aliases:
      - "Disabled Entry"
""",
        encoding="utf-8",
    )

    entries, omitted = ek.load_keyword_config(config_path)
    assert omitted == {"leer mas", "ver mas"}
    assert len(entries) == 2

    la_banda = entries[0]
    assert la_banda.canonical == "La Banda"
    assert la_banda.normalized == "la banda"
    assert la_banda.keyword_type == "place"
    assert la_banda.priority == 9
    assert la_banda.enabled is True
    assert la_banda.aliases == ("La Banda", "ciudad de La Banda")
    assert la_banda.normalized_aliases == ("la banda", "ciudad de la banda")

    disabled = entries[1]
    assert disabled.canonical == "Disabled Entry"
    assert disabled.enabled is False


def test_load_keyword_config_missing_file(tmp_path):
    missing = tmp_path / "missing.yml"
    with pytest.raises(RuntimeError):
        ek.load_keyword_config(missing)


def test_load_keyword_config_skips_empty_canonical(tmp_path):
    yaml = pytest.importorskip("yaml")
    config_path = tmp_path / "dictionary.yml"
    config_path.write_text(
        """
entries:
  - canonical: ""
    type: "topic"
    aliases: []
  - canonical: "Valid"
    type: "topic"
    aliases:
      - "Valid"
""",
        encoding="utf-8",
    )

    entries, _omitted = ek.load_keyword_config(config_path)
    assert len(entries) == 1
    assert entries[0].canonical == "Valid"


def test_load_keyword_config_inserts_canonical_into_aliases(tmp_path):
    yaml = pytest.importorskip("yaml")
    config_path = tmp_path / "dictionary.yml"
    config_path.write_text(
        """
entries:
  - canonical: "La Banda"
    type: "place"
    aliases:
      - "ciudad de La Banda"
""",
        encoding="utf-8",
    )

    entries, _omitted = ek.load_keyword_config(config_path)
    assert entries[0].aliases == ("La Banda", "ciudad de La Banda")
    assert entries[0].normalized_aliases == ("la banda", "ciudad de la banda")
