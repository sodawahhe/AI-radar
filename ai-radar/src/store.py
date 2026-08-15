"""
data/snapshots/YYYY-MM-DD.jsonl <-> 内存 SQLite

规格来源：PROJECT_SPEC_V2.md §3.3

JSONL 是持久层（每次运行结束提交进 git，见 §7）。SQLite 是查询层，
只存在于内存中，从不落盘、从不提交 —— 每次运行时从当前已有的 JSONL
文件重建，用于计算 7 天前的星数（§3.4 momentum 公式）。

首次运行时 snapshots 目录里没有任何历史文件，build_memory_db() 返回
一个有 schema 但零行的空连接；star_growth() 在这种情况下对所有仓库
返回 0 —— 这是预期行为，不是错误：首次运行的排序完全由
adoption / freshness / relevance 决定，从第二次运行起 momentum 才开始生效。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

# 快照记录额外持久化 contributors / releases_90d 两个字段（§3.3 示例未列出，
# 是本实现对 §3.4 adoption 公式所需数据的必要扩展 —— 只有 Top 20 候选会有
# 非 null 值，其余记录中这两个字段为 null，代表"未补抓"而非"值为零"）。
SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_date TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    stars         INTEGER NOT NULL,
    forks         INTEGER NOT NULL,
    open_issues   INTEGER,
    watchers      INTEGER,
    pushed_at     TEXT,
    created_at    TEXT,
    license       TEXT,
    language      TEXT,
    topics        TEXT,       -- JSON-encoded list
    description   TEXT,
    contributors  INTEGER,    -- 仅 Top 20 有值，见 §3.3
    releases_90d  INTEGER,    -- 仅 Top 20 有值，见 §3.3
    PRIMARY KEY (snapshot_date, full_name)
);
"""


def snapshot_path(snapshots_dir: Path, snapshot_date: str) -> Path:
    return snapshots_dir / f"{snapshot_date}.jsonl"


def write_snapshot(snapshots_dir: Path, snapshot_date: str, records: Iterable[dict]) -> Path:
    """把一批仓库记录写入当日 JSONL 快照文件（整体覆盖写；同一天内多次运行以
    最后一次为准 —— Phase 0 手动重跑时不会在文件里堆积重复行）。"""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(snapshots_dir, snapshot_date)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def read_snapshot(snapshots_dir: Path, snapshot_date: str) -> list[dict]:
    path = snapshot_path(snapshots_dir, snapshot_date)
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def list_available_dates(snapshots_dir: Path) -> list[str]:
    if not snapshots_dir.exists():
        return []
    return sorted(p.stem for p in snapshots_dir.glob("*.jsonl"))


def build_memory_db(snapshots_dir: Path, dates: Iterable[str] | None = None) -> sqlite3.Connection:
    """把若干天的 JSONL 快照载入内存 SQLite，供 score.py 查询历史星数。
    dates 为 None 时载入目录下全部快照文件；目录不存在或为空时返回
    一个有 schema 但零行的连接（不是 None），调用方无需做 None 判断。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(SNAPSHOT_SCHEMA)
    dates = list(dates) if dates is not None else list_available_dates(snapshots_dir)
    for d in dates:
        for rec in read_snapshot(snapshots_dir, d):
            conn.execute(
                "INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    d,
                    rec["full_name"],
                    rec.get("stars", 0),
                    rec.get("forks", 0),
                    rec.get("open_issues"),
                    rec.get("watchers"),
                    rec.get("pushed_at"),
                    rec.get("created_at"),
                    rec.get("license"),
                    rec.get("language"),
                    json.dumps(rec.get("topics", [])),
                    rec.get("description"),
                    rec.get("contributors"),
                    rec.get("releases_90d"),
                ),
            )
    conn.commit()
    return conn


def star_growth(
    conn: sqlite3.Connection,
    full_name: str,
    current_date: str,
    current_stars: int,
    lookback_days: int = 7,
) -> int:
    """返回过去 lookback_days 天内的星数增长（§3.4 momentum 的分子）。

    找不到对应历史快照时（项目首次被追踪、或系统刚上线不满 7 天）返回 0，
    绝不返回负数或 None —— momentum 公式需要一个可直接参与归一化的非负数值。
    """
    target = (date.fromisoformat(current_date) - timedelta(days=lookback_days)).isoformat()
    row = conn.execute(
        "SELECT stars FROM snapshots WHERE full_name = ? AND snapshot_date <= ? "
        "ORDER BY snapshot_date DESC LIMIT 1",
        (full_name, target),
    ).fetchone()
    if row is None:
        return 0
    return max(current_stars - row[0], 0)
