"""只读 ICS 日历接入（M4.5-F-C + P2-2）：data/*.ics，开始前 15 分钟提醒一次。

支持浮动本地时间与 Z(UTC)；全天事件不提醒；RRULE 支持 FREQ=DAILY/WEEKLY
（可含 INTERVAL 与 BYDAY，BYDAY 仅在 WEEKLY 下生效），每次 occurrence 只报一次。
文件每 5 分钟重扫一次。
"""

from __future__ import annotations

import datetime
from pathlib import Path

_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def parse_ics(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for ln in lines:
        if ln[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += ln[1:]
        else:
            unfolded.append(ln)
    events: list[dict] = []
    cur: dict | None = None
    for ln in unfolded:
        if ln.startswith("BEGIN:VEVENT"):
            cur = {}
        elif ln.startswith("END:VEVENT"):
            if cur and cur.get("dtstart"):
                events.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            key, _, val = ln.partition(":")
            key = key.split(";")[0].upper()
            val = val.strip()
            if key == "UID":
                cur["uid"] = val
            elif key == "SUMMARY":
                cur["summary"] = val
            elif key == "DTSTART":
                cur["dtstart"] = val
            elif key == "RRULE":
                cur["rrule"] = val
    return events


def _expand_rrule(rrule: str, start: datetime.datetime,
                  now: datetime.datetime, horizon_days: int = 7) -> list[datetime.datetime]:
    """展开未来 horizon_days 天内的重复事件（DAILY/WEEKLY，支持 INTERVAL/BYDAY）。"""
    parts = {}
    for chunk in rrule.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip().upper()] = v.strip().upper()
    freq = parts.get("FREQ", "")
    interval = max(1, int(parts.get("INTERVAL", "1") or 1))
    out: list[datetime.datetime] = []
    horizon = now + datetime.timedelta(days=horizon_days)
    if freq == "DAILY":
        occ = start
        while occ < horizon:
            if occ >= now:
                out.append(occ)
            occ += datetime.timedelta(days=interval)
    elif freq == "WEEKLY":
        byday = [d for d in parts.get("BYDAY", "").split(",") if d in _WEEKDAYS]
        weekdays = [_WEEKDAYS[d] for d in byday] or [start.weekday()]
        occ = start
        weeks = 0
        while occ < horizon:
            if weeks % interval == 0 and occ >= now and occ.weekday() in weekdays:
                out.append(occ)
            occ += datetime.timedelta(days=1)
            if occ.weekday() == 0:
                weeks += 1
    return out


def _parse_dt(value: str) -> datetime.datetime | None:
    v = value.strip()
    try:
        if v.endswith("Z"):
            # 转本地时间并去掉 tzinfo：与调用方的 naive now 保持同一口径
            return datetime.datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
        if "T" in v:
            return datetime.datetime.strptime(v, "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    return None  # 全天日期（8 位）不提醒


class CalendarWatch:
    def __init__(self, data_dir: Path, lead_min: float = 15.0, rescan_s: float = 300.0):
        self.data_dir = Path(data_dir)
        self.lead_s = lead_min * 60
        self.rescan_s = rescan_s
        self._events: list[dict] = []
        self._seen: set[str] = set()
        self._last_scan = -1e18

    def scan(self, now: datetime.datetime) -> list[tuple[str, datetime.datetime]]:
        """返回新进入提醒窗口的事件 (summary, start)；每个事件只报一次。"""
        if now.timestamp() - self._last_scan >= self.rescan_s:
            self._last_scan = now.timestamp()
            self._events = []
            for f in self.data_dir.glob("*.ics"):
                try:
                    self._events += parse_ics(f.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
        out: list[tuple[str, datetime.datetime]] = []
        for ev in self._events:
            summary = ev.get("summary") or "日程"
            base_uid = str(ev.get("uid") or f"{summary}|{ev.get('dtstart', '')}")
            start = _parse_dt(str(ev.get("dtstart", "")))
            if start is None:
                continue
            # P2-2：重复事件展开未来 occurrence，每个只报一次
            occurrences = _expand_rrule(str(ev.get("rrule", "")), start, now) \
                if ev.get("rrule") else [start]
            for occ in occurrences:
                uid = f"{base_uid}|{occ.date().isoformat()}"
                if uid in self._seen:
                    continue
                delta = (occ - now).total_seconds()
                if 0 <= delta <= self.lead_s:
                    self._seen.add(uid)
                    out.append((summary, occ))
        return out
