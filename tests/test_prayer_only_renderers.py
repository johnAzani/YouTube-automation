from __future__ import annotations

from tools import deep_dive, shorts


def test_longform_renderer_catalog_is_prayer_only() -> None:
    assert deep_dive.SCRIPTS
    assert all("psalm" in key.lower() or "prayer" in key.lower()
               for key in deep_dive.SCRIPTS)
    assert all("enron" not in key.lower() and "johnstown" not in key.lower()
               for key in deep_dive.SCRIPTS)


def test_short_renderer_catalog_is_prayer_only() -> None:
    assert shorts.SCRIPTS
    assert all(key.lower().startswith("short-") for key in shorts.SCRIPTS)
    assert all("enron" not in key.lower() and "johnstown" not in key.lower()
               for key in shorts.SCRIPTS)


def test_renderer_scene_data_has_no_finance_or_disaster_story_traces() -> None:
    forbidden = ("enron", "johnstown", "accounting scandal", "corporate collapse")
    catalogs = (deep_dive.SCRIPTS, shorts.SCRIPTS)
    for catalog in catalogs:
        serialized = repr(catalog).lower()
        assert not any(term in serialized for term in forbidden)
