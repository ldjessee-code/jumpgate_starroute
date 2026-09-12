"""Strong etag: digest excludes etag and updated_at."""

from __future__ import annotations

from starroute.schemas.setting import SettingDocument
from starroute.store.etag import canonical_bytes, compute_etag, etag_header_ok, strip_cas_fields


def _setting(**kwargs) -> dict:
    base = SettingDocument(id="iron-ash", title="Iron Ash", reality=1).model_dump(by_alias=True)
    base.update(kwargs)
    return base


def test_same_body_minus_etag_same_tag():
    a = _setting(etag='"sha256-deadbeef0000"', updated_at="2026-09-12T18:00:00Z")
    b = _setting(etag='"sha256-ffffffffffff"', updated_at="2026-09-12T19:00:00Z")
    assert compute_etag(a) == compute_etag(b)
    assert canonical_bytes(a) == canonical_bytes(b)


def test_flipping_etag_in_file_does_not_change_tag():
    doc = _setting(reality=2, updated_by="jumpgate")
    tag = compute_etag(doc)
    doc["etag"] = '"sha256-not-the-real-one"'
    assert compute_etag(doc) == tag


def test_updated_at_alone_does_not_change_tag():
    a = _setting(reality=1, updated_at="2026-01-01T00:00:00Z")
    b = _setting(reality=1, updated_at="2026-12-31T23:59:59Z")
    assert compute_etag(a) == compute_etag(b)


def test_reality_or_actor_changes_tag():
    base = _setting(reality=1, updated_by="jumpgate")
    other_stop = _setting(reality=2, updated_by="jumpgate")
    other_actor = _setting(reality=1, updated_by="worldstack")
    assert compute_etag(base) != compute_etag(other_stop)
    assert compute_etag(base) != compute_etag(other_actor)


def test_tag_shape_is_strong_quoted():
    tag = compute_etag(_setting())
    assert tag.startswith('"sha256-')
    assert tag.endswith('"')
    assert not tag.startswith("W/")
    assert len(tag) == len('"sha256-') + 12 + 1  # 12 hex + closing quote


def test_strip_cas_fields_drops_only_etag_and_updated_at():
    doc = _setting(etag='"x"', updated_at="now", updated_by="jumpgate")
    stripped = strip_cas_fields(doc)
    assert "etag" not in stripped
    assert "updated_at" not in stripped
    assert stripped["updated_by"] == "jumpgate"
    assert stripped["reality"] == 1


def test_etag_header_ok():
    assert etag_header_ok(None) == (False, "missing")
    assert etag_header_ok("") == (False, "missing")
    assert etag_header_ok('W/"sha256-abc"') == (False, "weak")
    assert etag_header_ok('w/"sha256-abc"') == (False, "weak")
    ok, reason = etag_header_ok('"sha256-abc"')
    assert ok is True and reason is None
