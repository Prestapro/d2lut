"""Tests for robust estimate aggregation in pipeline."""

from __future__ import annotations

import sqlite3
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_pipeline_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py"
    spec = spec_from_file_location("run_pipeline", script_path)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_tables(conn: sqlite3.Connection, extended: bool) -> None:
    conn.execute(
        """
        CREATE TABLE observed_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variant_key TEXT NOT NULL,
            price_fg REAL NOT NULL,
            confidence REAL,
            observed_at TEXT
        )
        """
    )
    if extended:
        conn.execute(
            """
            CREATE TABLE price_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_key TEXT NOT NULL UNIQUE,
                price_fg REAL NOT NULL,
                confidence REAL NOT NULL,
                observation_count INTEGER DEFAULT 0,
                min_price REAL,
                max_price REAL,
                std_dev REAL,
                price_tier TEXT,
                first_observed TEXT,
                last_observed TEXT,
                updated_at TEXT
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE price_estimates (
                variant_key TEXT PRIMARY KEY,
                price_fg REAL NOT NULL,
                observation_count INTEGER DEFAULT 0,
                updated_at TEXT
            )
            """
        )


def test_update_estimates_uses_robust_price_and_staleness(tmp_path):
    module = _load_pipeline_module()
    db_path = tmp_path / "pipeline.db"
    conn = sqlite3.connect(db_path)
    _create_tables(conn, extended=True)

    values = [10.0, 10.0, 10.0, 1000.0]
    for value in values:
        conn.execute(
            "INSERT INTO observed_prices (variant_key, price_fg, confidence, observed_at) VALUES (?, ?, ?, ?)",
            ("rune:jah", value, 1.0, "2026-01-01T00:00:00"),
        )
    conn.commit()
    conn.close()

    updated = module.update_estimates(db_path)
    assert updated == 1

    check = sqlite3.connect(db_path)
    row = check.execute(
        "SELECT price_fg, confidence, observation_count, price_tier FROM price_estimates WHERE variant_key = ?",
        ("rune:jah",),
    ).fetchone()
    check.close()

    assert row is not None
    assert 100.0 <= row[0] <= 120.0
    assert row[1] < 0.4
    assert row[2] == 4
    assert row[3] == "HIGH"


def test_update_estimates_supports_minimal_schema(tmp_path):
    module = _load_pipeline_module()
    db_path = tmp_path / "pipeline-minimal.db"
    conn = sqlite3.connect(db_path)
    _create_tables(conn, extended=False)
    conn.execute(
        "INSERT INTO observed_prices (variant_key, price_fg, confidence, observed_at) VALUES (?, ?, ?, ?)",
        ("unique:shako", 12.0, 0.8, "2026-03-01 10:00:00"),
    )
    conn.commit()
    conn.close()

    updated = module.update_estimates(db_path)
    assert updated == 1

    check = sqlite3.connect(db_path)
    row = check.execute(
        "SELECT variant_key, price_fg, observation_count FROM price_estimates"
    ).fetchone()
    check.close()

    assert row is not None
    assert row[0] == "unique:shako"
    assert row[1] == 12.0
    assert row[2] == 1
