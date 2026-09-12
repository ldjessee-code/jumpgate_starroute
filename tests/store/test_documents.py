"""JsonStore round-trip and path safety."""

from __future__ import annotations

import pytest

from starroute.store.documents import JsonStore
from starroute.store.etag import compute_etag


def test_put_echoes_computed_etag(tmp_path):
    store = JsonStore(tmp_path)
    written = store.put("settings", "iron-ash", {"id": "iron-ash", "reality": 0, "updated_by": "jumpgate"})
    assert written["etag"] == compute_etag({"id": "iron-ash", "reality": 0, "updated_by": "jumpgate"})
    loaded = store.get("settings", "iron-ash")
    assert loaded is not None
    assert loaded["etag"] == written["etag"]
    assert loaded["id"] == "iron-ash"


def test_rewrite_same_hashed_fields_keeps_tag(tmp_path):
    store = JsonStore(tmp_path)
    first = store.put("settings", "iron-ash", {"id": "iron-ash", "reality": 1, "updated_at": "t1"})
    second = store.put("settings", "iron-ash", {"id": "iron-ash", "reality": 1, "updated_at": "t2"})
    assert first["etag"] == second["etag"]


def test_rejects_path_traversal(tmp_path):
    store = JsonStore(tmp_path)
    with pytest.raises(ValueError, match="unsafe"):
        store.path_for("settings", "../secret")
    with pytest.raises(ValueError, match="unsafe"):
        store.path_for("..", "iron-ash")
    with pytest.raises(ValueError, match="unsafe"):
        store.path_for("settings", "foo/bar")


def test_missing_get_is_none(tmp_path):
    store = JsonStore(tmp_path)
    assert store.get("settings", "missing") is None
