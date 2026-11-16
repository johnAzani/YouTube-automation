"""The owner's standing order stays written where every session reads it.

On 16 November 2026 the owner said the three priorities must be applied to all
work without his repeating them. A sentence in a chat is gone when the chat is;
these files are not. This fails if they are removed or emptied.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ORDERS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
STATE = (ROOT / "STATE.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize("priority", [
    "Protection of all ten channels",
    "Revenue intelligence",
    "Intelligence of the automation",
])
def test_the_three_priorities_are_named(priority):
    assert priority in ORDERS


def test_protection_comes_first_when_they_pull_apart():
    assert "this comes first when the three pull apart" in _flat(ORDERS)


@pytest.mark.parametrize("rule", [
    "Never raise how many videos a channel publishes a day",
    "Never make the channels more alike",
    "Never weaken a check that refuses a video",
    "Prayer stays prayer",
    "Never do anything meant to hide from YouTube",
    "Only long-form watch hours count toward the Partner Programme",
    "Never write real revenue figures into the repository",
    "Do not tell the owner something works until it has been seen to work",
])
def test_the_rules_that_follow_from_it_are_kept(rule):
    assert rule in _flat(ORDERS)


def test_the_order_says_it_is_not_to_be_asked_for_again():
    assert "does not want to repeat them" in _flat(ORDERS)


def test_the_first_notice_in_state_points_to_it():
    notice = STATE.split("## ⚠️ CRITICAL NOTICE", 1)[1].split("\n---", 1)[0]
    assert "STANDING ORDER" in notice
    assert "`AGENTS.md`" in notice
    for word in ("protection of all ten channels", "revenue intelligence",
                 "intelligence of the automation"):
        assert word in notice


def test_what_the_orders_point_to_exists():
    for path in re.findall(r"`((?:docs|content|scripts|tests)/[\w./-]+)`", ORDERS):
        assert (ROOT / path).exists(), path
    assert (ROOT / "scripts" / "channel_protection.py").is_file()
