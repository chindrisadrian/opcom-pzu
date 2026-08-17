"""Pure OPCOM PZU logic: CSV parsing, statistics, and injection windows.

The module does not import anything from Home Assistant, so it can be tested separately.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any

URL_TEMPLATE = (
    "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/"
    "{d:02d}/{m:02d}/{y:04d}/ro?resolution=15"
)

ZONE = "Romania"
RESOLUTION_TAG = "PT15M"
SLOT_MINUTES = 15
MIN_SLOTS = 92  # a day has 96 intervals, 92 or 100 during daylight saving time changes

WINDOW_SPECS: tuple[tuple[float, str], ...] = (
    (0.5, "best_window_30m"),
    (1.0, "best_window_1h"),
    (2.0, "best_window_2h"),
    (3.0, "best_window_3h"),
    (4.0, "best_window_4h"),
)


def build_url(day: date) -> str:
    """The URL of the CSV export for a delivery day."""
    return URL_TEMPLATE.format(d=day.day, m=day.month, y=day.year)


def _num(raw: str) -> float:
    """Number from CSV. The OPCOM export uses a decimal point, but we also accept the
    Romanian format (1.234,56) in case the source changes."""
    s = raw.strip().strip('"').replace(" ", "").replace("\xa0", "")
    if not s:
        raise ValueError("empty")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def parse_csv(text: str, day: date, tz: tzinfo) -> list[dict[str, Any]]:
    """OPCOM CSV -> list of intervals with local timestamps.

    Useful rows look like this:
        "Romania","1","1074.94","1153.1","912.8","1153.1","PT15M"
    The header, notes, and the ROPEX summary table are ignored.

    Timestamps are built starting from local midnight converted to UTC,
    adding 15 minutes in UTC — this ensures daylight saving time changes are correct.
    """
    rows: dict[int, dict[str, Any]] = {}
    for fields in csv.reader(io.StringIO(text)):
        if len(fields) < 3 or fields[0].strip().lower() != ZONE.lower():
            continue
        if len(fields) >= 7 and fields[6].strip() and fields[6].strip().upper() != RESOLUTION_TAG:
            continue
        try:
            interval = int(fields[1].strip().strip('"'))
            price = _num(fields[2])
        except ValueError:
            continue
        if not 1 <= interval <= 200:
            continue
        try:
            volume: float | None = _num(fields[3])
        except (ValueError, IndexError):
            volume = None
        rows[interval] = {"price": price, "volume": volume}

    if not rows:
        return []

    midnight_utc = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(timezone.utc)

    out: list[dict[str, Any]] = []
    for interval in sorted(rows):
        start_utc = midnight_utc + timedelta(minutes=SLOT_MINUTES * (interval - 1))
        end_utc = start_utc + timedelta(minutes=SLOT_MINUTES)
        start_l, end_l = start_utc.astimezone(tz), end_utc.astimezone(tz)
        item = rows[interval]
        out.append(
            {
                "interval": interval,
                "start": start_l.isoformat(),
                "end": end_l.isoformat(),
                "hour": start_l.strftime("%H:%M"),
                "value": round(item["price"], 2),
                "volume": round(item["volume"], 1) if item["volume"] is not None else None,
                "ts": start_utc.timestamp(),
            }
        )
    return out


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * pct / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def day_stats(slots: list[dict[str, Any]]) -> dict[str, Any]:
    if not slots:
        return {}
    vals = sorted(s["value"] for s in slots)
    best = max(slots, key=lambda s: s["value"])
    worst = min(slots, key=lambda s: s["value"])
    return {
        "min": round(vals[0], 2),
        "max": round(vals[-1], 2),
        "mean": round(sum(vals) / len(vals), 2),
        "median": round(percentile(vals, 50), 2),
        "p75": round(percentile(vals, 75), 2),
        "p90": round(percentile(vals, 90), 2),
        "max_at": best["start"],
        "max_hour": best["hour"],
        "min_at": worst["start"],
        "min_hour": worst["hour"],
        "slots": len(slots),
    }


def _daymark(iso_start: str, ref: datetime | None) -> str:
    """Suffix ' (tomorrow)' if the interval is on a different day than `ref`."""
    if ref is None:
        return ""
    return "" if iso_start[:10] == ref.strftime("%Y-%m-%d") else " (tomorrow)"


def best_window(
    slots: list[dict[str, Any]], hours: float, ref: datetime | None = None
) -> dict[str, Any] | None:
    """Continuous window of `hours` hours with the highest average (sliding window)."""
    n = int(round(hours * 60 / SLOT_MINUTES))
    if n <= 0 or len(slots) < n:
        return None
    running = sum(s["value"] for s in slots[:n])
    best_i, best_sum = 0, running
    for i in range(1, len(slots) - n + 1):
        running += slots[i + n - 1]["value"] - slots[i - 1]["value"]
        if running > best_sum:
            best_sum, best_i = running, i
    win = slots[best_i : best_i + n]
    frm, to = win[0]["hour"], win[-1]["end"][11:16]
    return {
        "start": win[0]["start"],
        "end": win[-1]["end"],
        "from": frm,
        "to": to,
        "label": f"{frm} - {to}{_daymark(win[0]['start'], ref)}",
        "avg": round(best_sum / n, 2),
        "min": round(min(s["value"] for s in win), 2),
        "max": round(max(s["value"] for s in win), 2),
        "hours": hours,
    }


def top_slots(
    slots: list[dict[str, Any]], count: int, ref: datetime | None = None
) -> list[dict[str, Any]]:
    ranked = sorted(slots, key=lambda s: s["value"], reverse=True)[:count]
    ranked.sort(key=lambda s: s["ts"])
    return [
        {
            "start": s["start"],
            "end": s["end"],
            "hour": s["hour"],
            "value": s["value"],
            "label": s["hour"] + _daymark(s["start"], ref),
        }
        for s in ranked
    ]


def compact(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reduced form for entity attributes and for the card."""
    return [
        {"interval": s["interval"], "start": s["start"], "hour": s["hour"], "value": s["value"]}
        for s in slots
    ]


def build_payload(
    today_slots: list[dict[str, Any]],
    tomorrow_slots: list[dict[str, Any]],
    now: datetime,
    top: int = 8,
) -> dict[str, Any]:
    """All derived values used by the entities and the card."""
    now_ts = now.timestamp()

    current = next(
        (s for s in today_slots if s["ts"] <= now_ts < s["ts"] + SLOT_MINUTES * 60), None
    )
    horizon = [
        s for s in (today_slots + tomorrow_slots) if s["ts"] + SLOT_MINUTES * 60 > now_ts
    ]

    payload: dict[str, Any] = {
        "state": current["value"] if current else None,
        "last_update": now.isoformat(timespec="seconds"),
        "today_valid": len(today_slots) >= MIN_SLOTS,
        "tomorrow_valid": len(tomorrow_slots) >= MIN_SLOTS,
        "raw_today": compact(today_slots),
        "raw_tomorrow": compact(tomorrow_slots),
        "today": day_stats(today_slots),
        "tomorrow": day_stats(tomorrow_slots),
        "horizon_slots": len(horizon),
        "horizon_end": horizon[-1]["end"] if horizon else None,
        "best_slots": top_slots(horizon, top, now),
        "current_interval": current["interval"] if current else None,
        "current_hour": current["hour"] if current else None,
        "current_rank_today": None,
        "current_percentile_today": None,
        "next_peak": None,
        "horizon_mean": None,
        "horizon_max": None,
        "horizon_p75": None,
        "horizon_p90": None,
    }

    if current and today_slots:
        desc = sorted((s["value"] for s in today_slots), reverse=True)
        rank = desc.index(current["value"]) + 1
        payload["current_rank_today"] = rank
        payload["current_percentile_today"] = round(
            100.0 * (len(desc) - rank) / max(len(desc) - 1, 1), 1
        )

    for hours, key in WINDOW_SPECS:
        payload[key] = best_window(horizon, hours, now)

    if horizon:
        hv = sorted(s["value"] for s in horizon)
        payload["horizon_mean"] = round(sum(hv) / len(hv), 2)
        payload["horizon_max"] = round(hv[-1], 2)
        payload["horizon_p75"] = round(percentile(hv, 75), 2)
        payload["horizon_p90"] = round(percentile(hv, 90), 2)
        nxt = max(horizon, key=lambda s: s["value"])
        payload["next_peak"] = {
            "start": nxt["start"],
            "hour": nxt["hour"],
            "value": nxt["value"],
            "label": nxt["hour"] + _daymark(nxt["start"], now),
        }

    return payload
