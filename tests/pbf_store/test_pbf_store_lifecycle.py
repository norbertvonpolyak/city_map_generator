"""M2 store lifecycle: validation, interrupted builds, stale temp files, locking, explicit paths."""

from __future__ import annotations

import os
import shutil
import sqlite3

import pytest

from generator.core import pbf_store
from pbf_synthetic import build_store_dataset, write_pbf


@pytest.fixture
def pbf(tmp_path):
    builder, _ = build_store_dataset()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    return write_pbf(source_dir / "synthetic.osm.pbf", builder)


@pytest.fixture
def built_store(tmp_path, pbf):
    store_dir = tmp_path / "store"
    pbf_store.build_store(pbf, store_dir)
    return store_dir


def _tampered_copy(store_dir, target_dir, sql, params=()):
    target_dir.mkdir()
    shutil.copy2(store_dir / pbf_store.STORE_FILENAME, target_dir / pbf_store.STORE_FILENAME)
    conn = sqlite3.connect(target_dir / pbf_store.STORE_FILENAME)
    conn.execute(sql, params)
    conn.commit()
    conn.close()
    return target_dir


def _snapshot(path):
    return sorted(
        (str(p.relative_to(path)), p.stat().st_size, p.stat().st_mtime_ns) for p in path.rglob("*") if p.is_file()
    )


def test_valid_store_opens_with_source_check(built_store, pbf):
    with pbf_store.PbfStoreReader(built_store, pbf_path=pbf, verify_sha256=True) as reader:
        assert reader.meta["status"] == "complete"


def test_missing_store_is_rejected(tmp_path):
    with pytest.raises(pbf_store.StoreValidationError, match="not found"):
        pbf_store.PbfStoreReader(tmp_path / "nowhere")


@pytest.mark.parametrize(
    "sql,params,message",
    [
        ("DELETE FROM meta WHERE key = 'status'", (), "not marked complete"),
        ("UPDATE meta SET value = 'building' WHERE key = 'status'", (), "not marked complete"),
        ("UPDATE meta SET value = '999' WHERE key = 'schema_version'", (), "schema_version"),
        ("UPDATE meta SET value = '999' WHERE key = 'preprocess_version'", (), "preprocess_version"),
        ("UPDATE meta SET value = 'x' WHERE key = 'tag_rules_hash'", (), "tag_rules_hash"),
    ],
)
def test_reader_rejects_invalid_metadata(built_store, tmp_path, sql, params, message):
    target = _tampered_copy(built_store, tmp_path / "tampered", sql, params)
    with pytest.raises(pbf_store.StoreValidationError, match=message):
        pbf_store.PbfStoreReader(target)


def test_reader_rejects_different_tag_rules(built_store):
    production = pbf_store.TagRules.from_production()
    changed = pbf_store.TagRules(
        {**production.layer_tags, "extra": {"amenity": ["bench"]}}, production.road_key, production.road_pattern,
    )
    with pytest.raises(pbf_store.StoreValidationError, match="tag_rules_hash"):
        pbf_store.PbfStoreReader(built_store, rules=changed)


def test_reader_rejects_changed_source_pbf(built_store, pbf):
    stat = pbf.stat()
    os.utime(pbf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    with pytest.raises(pbf_store.StoreValidationError, match="size or modification time"):
        pbf_store.PbfStoreReader(built_store, pbf_path=pbf)
    pbf_store.PbfStoreReader(built_store).close()


def test_sha256_verification_is_optional_and_strict(built_store, tmp_path, pbf):
    target = _tampered_copy(built_store, tmp_path / "sha", "UPDATE meta SET value = 'deadbeef' WHERE key = 'pbf_sha256'")
    pbf_store.PbfStoreReader(target, pbf_path=pbf).close()
    with pytest.raises(pbf_store.StoreValidationError, match="SHA-256"):
        pbf_store.PbfStoreReader(target, pbf_path=pbf, verify_sha256=True)


def test_interrupted_build_keeps_previous_store(built_store, pbf, monkeypatch):
    final_path = built_store / pbf_store.STORE_FILENAME
    before_hash = pbf_store.file_sha256(final_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(pbf_store, "_finalize_relations", _boom)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        pbf_store.build_store(pbf, built_store)

    assert pbf_store.file_sha256(final_path) == before_hash
    assert not list(built_store.glob(f"{pbf_store.BUILD_FILE_PREFIX}*"))
    assert not (built_store / pbf_store.LOCK_FILENAME).exists()
    pbf_store.PbfStoreReader(built_store, pbf_path=pbf).close()

    monkeypatch.undo()
    pbf_store.build_store(pbf, built_store)
    pbf_store.PbfStoreReader(built_store, pbf_path=pbf).close()


def test_interrupted_first_build_publishes_nothing(tmp_path, pbf, monkeypatch):
    store_dir = tmp_path / "fresh"
    monkeypatch.setattr(pbf_store, "_write_pass_b", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(RuntimeError, match="stop"):
        pbf_store.build_store(pbf, store_dir)
    assert not (store_dir / pbf_store.STORE_FILENAME).exists()
    assert not list(store_dir.glob(f"{pbf_store.BUILD_FILE_PREFIX}*"))
    with pytest.raises(pbf_store.StoreValidationError):
        pbf_store.PbfStoreReader(store_dir)


def test_stale_build_files_are_removed_and_never_read(built_store, pbf):
    stale = built_store / f"{pbf_store.BUILD_FILE_PREFIX}dead.sqlite"
    stale.write_bytes(b"partial")
    with pbf_store.PbfStoreReader(built_store) as reader:
        assert reader.store_path.name == pbf_store.STORE_FILENAME
    result = pbf_store.build_store(pbf, built_store)
    assert not stale.exists()
    assert result.counts["stale_build_files_removed"] == 1


def test_existing_lock_blocks_build_unless_forced(built_store, pbf):
    final_path = built_store / pbf_store.STORE_FILENAME
    before_hash = pbf_store.file_sha256(final_path)
    lock = built_store / pbf_store.LOCK_FILENAME
    lock.write_text('{"pid": 1}')

    with pytest.raises(pbf_store.StoreLockedError):
        pbf_store.build_store(pbf, built_store)
    assert lock.exists()
    assert pbf_store.file_sha256(final_path) == before_hash

    pbf_store.build_store(pbf, built_store, force=True)
    assert not lock.exists()


def test_build_writes_only_inside_explicit_store_dir(tmp_path, pbf):
    before = _snapshot(tmp_path)
    store_dir = tmp_path / "explicit_store"
    pbf_store.build_store(pbf, store_dir)
    after = [entry for entry in _snapshot(tmp_path) if not entry[0].startswith("explicit_store")]
    assert after == before
    assert [p.name for p in store_dir.iterdir()] == [pbf_store.STORE_FILENAME]


def test_missing_pbf_is_rejected(tmp_path):
    with pytest.raises(pbf_store.PbfStoreError, match="PBF not found"):
        pbf_store.build_store(tmp_path / "absent.osm.pbf", tmp_path / "store")
    assert not (tmp_path / "store").exists()
