"""Parametrize contention from the rank table + embargo matrix."""

from __future__ import annotations

import pytest

from starroute.mapgen.politics import (
    DEESCALATE,
    ESCALATE,
    RANKS,
    TransitionIllegal,
    embargo_contention,
    next_contention,
)


@pytest.mark.parametrize(
    "current,action,expected",
    [
        ("none", "expand_claim", "claim"),
        ("claim", "expand_claim", "claim"),
        ("none", "open_trade", "cooperative"),
        ("claim", "open_trade", "cooperative"),
        ("cooperative", "open_trade", "cooperative"),
        ("claim", "escalate", "competitive_trade"),
        ("cooperative", "escalate", "competitive_trade"),
        ("competitive_trade", "escalate", "games"),
        ("games", "escalate", "skirmish"),
        ("skirmish", "escalate", "war"),
        ("war", "escalate", "subjugation"),
        ("subjugation", "escalate", "subjugation"),
        ("war", "deescalate", "skirmish"),
        ("cooperative", "deescalate", "none"),
        ("none", "deescalate", "none"),
        ("none", "raid", "skirmish"),
        ("claim", "raid", "skirmish"),
        ("skirmish", "raid", "skirmish"),
        ("war", "raid", "war"),
        ("none", "embargo", "competitive_trade"),
        ("claim", "embargo", "competitive_trade"),
        ("cooperative", "embargo", "competitive_trade"),
        ("war", "embargo", "war"),
        ("competitive_trade", "propaganda", "competitive_trade"),
    ],
)
def test_transitions(current, action, expected):
    assert next_contention(current, action) == expected


def test_none_escalate_illegal():
    with pytest.raises(TransitionIllegal):
        next_contention("none", "escalate")


def test_escalate_table_matches_ranks():
    for state, nxt in ESCALATE.items():
        if nxt is None:
            continue
        if state == "subjugation":
            assert nxt == "subjugation"
            continue
        assert RANKS[nxt] == RANKS[state] + 1 or (state == "cooperative" and nxt == "competitive_trade")


def test_deescalate_never_skips_to_none_from_war():
    assert DEESCALATE["war"] == "skirmish"
    assert next_contention("war", "deescalate") != "none"


def test_embargo_matrix():
    assert embargo_contention("none") == "competitive_trade"
    assert embargo_contention("games") == "games"
    assert embargo_contention("subjugation") == "subjugation"
