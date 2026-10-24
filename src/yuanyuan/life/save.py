"""SQLite 存档（T2.1/T2.5）：KV 结构 + 损坏自愈（损坏时备份为 .corrupt-* 并重新开始）"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


def _init_kv_table(conn: sqlite3.Connection) -> None:
    # 固定建表语句（无任何外部输入参与拼接）；数据读写全部走参数化查询
    conn.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()


class Save:
    """单连接 + 线程锁：AI 工作线程也会读写存档（check_same_thread=False + Lock）。"""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._open()

    def _open(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            try:
                _init_kv_table(conn)
            except sqlite3.DatabaseError:
                conn.close()  # 必须先释放句柄，否则 Windows 上无法改名/删除
                raise
            return conn
        except sqlite3.DatabaseError:
            self._quarantine()
            conn = sqlite3.connect(self.path, check_same_thread=False)
            _init_kv_table(conn)
            return conn

    def _quarantine(self) -> None:
        bad = self.path.with_name(f"{self.path.name}.corrupt-{int(time.time())}")
        try:
            self.path.rename(bad)
            print(f"⚠ 存档损坏，已备份为 {bad.name}，从新存档开始", flush=True)
        except OSError:
            try:
                self.path.unlink()
                print("⚠ 存档损坏且无法改名备份，已删除重建", flush=True)
            except OSError as e:
                print(f"⚠ 存档损坏且无法清理（{e}）", flush=True)

    def get(self, key: str, default=None):
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT value FROM kv WHERE key = ?", (key,)
                ).fetchone()
            except sqlite3.DatabaseError:
                return default
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return default

    def set(self, key: str, value) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
