"""Per-tick decision engine for Plant HMI alarm ack/shelve (phase 6B). Split out of
`plant_alarm_state.py` (same feature: that module owns the store file/lock/mutations,
this one owns the per-snapshot decision) purely to keep both files under 200 lines.

`annotate_from_store(active_alarms, now)` is the one entry point the snapshot builder
calls once per poll: it reads, decides and persists inside a single `plant_alarm_state.
locked_store()` critical section (rule C2 - no other writer, including an ack/shelve POST,
can interleave and be lost to a stale rewrite). It only writes to disk when a section
actually changed value (rule M3): while an alarm stays continuously active its
`last_seen`/`active_points` entries are reused byte-for-byte tick to tick (never refreshed
with "now" or a live-updating message), so a steady-state poll costs no IO at all - a write
only happens when a key genuinely appears, disappears, gets acked/shelved/pruned, or a
shelve expires. `annotate_alarms(active_alarms, store, now)` is the pure decision function
(no I/O) used directly by unit tests; `annotate_from_store` is a thin locked wrapper.
"""

import logging
from typing import Dict, List, Tuple

from . import plant_historian_store as historian
from .plant_alarm_state import (
    LAST_SEEN_TTL_S,
    locked_store,
    occurrence_key,
    point_key,
    read_store,
    write_store,
)

logger = logging.getLogger(__name__)


def _journal_expiry(pkey: str, shelf: Dict, now: float) -> None:
    """Rule "Low": an auto-expired shelve still gets a journal row, `by` folded into
    the message since the historian schema has no separate actor column."""
    try:
        historian.insert_alarm_journal(now, shelf.get("code") or pkey.split("|", 1)[0],
                                        shelf.get("tag"), None, shelf.get("pid"),
                                        "unshelved", "tự động hết hạn tạm tắt (expiry)")
    except Exception:
        logger.exception("plant alarm state: expiry journal write failed for %s", pkey)


def annotate_alarms(active_alarms: List[Dict], store: Dict, now: float) -> Tuple[Dict, Dict, List[Tuple[str, Dict]]]:
    """Pure decision (no I/O): given the current on-delay-filtered `active_alarms` (each
    has code/tag/severity/message/pid/since) and the store's current sections, returns
    `(result, new_sections, expired_shelves)`. `result` = {"alarms", "cleared_unacked",
    "shelved"}; `new_sections` = the possibly-updated acks/shelves/last_seen/active_points
    to persist (identical-by-value to the input when nothing changed); `expired_shelves` =
    [(point_key, shelf_dict), ...] that just crossed `until` this call, for journaling.
    """
    acks: Dict = store.get("acks") or {}
    shelves: Dict = store.get("shelves") or {}
    last_seen: Dict = store.get("last_seen") or {}

    active_occurrence_keys = set()
    active_points: Dict = {}
    alarms_out: List[Dict] = []
    shelved_out: List[Dict] = []
    new_last_seen: Dict = {}

    for a in active_alarms:
        okey = occurrence_key(a["code"], a.get("tag"), a.get("pid"), a.get("since"))
        pkey = point_key(a["code"], a.get("tag"), a.get("pid"))
        active_occurrence_keys.add(okey)
        active_points[pkey] = {"code": a["code"], "tag": a.get("tag"), "pid": a.get("pid")}

        shelf = shelves.get(pkey)
        if shelf and shelf.get("until", 0) > now:
            shelved_out.append({"key": pkey, "code": a["code"], "tag": a.get("tag"),
                                 "until": shelf["until"], "reason": shelf.get("reason"),
                                 "by": shelf.get("by"), "severity": a.get("severity"),
                                 "message": a.get("message")})
            continue  # H5: a shelved occurrence never enters last_seen -> never cleared_unacked

        existing = last_seen.get(okey)  # frozen snapshot (rule M3): never refreshed while active
        new_last_seen[okey] = existing if existing is not None else {
            "code": a["code"], "tag": a.get("tag"), "severity": a.get("severity"),
            "message": a.get("message"), "pid": a.get("pid"), "since": a.get("since"),
            "last_seen_ts": now,
        }
        ack_entry = acks.get(okey)
        alarms_out.append({**a, "key": okey, "point_key": pkey, "acked": ack_entry is not None,
                            "acked_at": ack_entry.get("acked_at") if ack_entry else None,
                            "shelved": False})

    cleared_out: List[Dict] = []
    for okey, rec in last_seen.items():
        if okey in active_occurrence_keys or okey in acks:
            continue  # still active (handled above) or already acked: nothing to surface
        if now - rec.get("last_seen_ts", 0) > LAST_SEEN_TTL_S:
            continue  # bounded 24 h: drop stale bookkeeping
        new_last_seen[okey] = rec  # carry forward until acked, dropped, or re-raised
        cleared_out.append({**rec, "key": okey, "acked": False, "cleared": True})

    pruned_acks = {k: v for k, v in acks.items()
                   if k in active_occurrence_keys or now - v.get("acked_at", 0) <= LAST_SEEN_TTL_S}
    kept_shelves, expired = {}, []
    for pkey, shelf in shelves.items():
        if shelf.get("until", 0) > now:
            kept_shelves[pkey] = shelf
        else:
            expired.append((pkey, shelf))

    alarms_out.sort(key=lambda a: (a["severity"] != "HI", a["since"]))
    shelved_out.sort(key=lambda s: s["until"])
    cleared_out.sort(key=lambda c: c["last_seen_ts"], reverse=True)

    new_sections = {"acks": pruned_acks, "shelves": kept_shelves,
                    "last_seen": new_last_seen, "active_points": active_points}
    result = {"alarms": alarms_out, "cleared_unacked": cleared_out, "shelved": shelved_out}
    return result, new_sections, expired


def annotate_from_store(active_alarms: List[Dict], now: float) -> Dict:
    """Locked read + pure decision + conditional write, called once per snapshot poll
    (rule C2: the whole cycle is one critical section, so an ack/shelve/unshelve POST can
    never interleave and be undone by a stale rewrite). See module docstring for the
    write-avoidance rule (M3)."""
    with locked_store():
        store = read_store()
        result, new_sections, expired = annotate_alarms(active_alarms, store, now)
        old_sections = {k: store.get(k, {}) for k in new_sections}
        if new_sections != old_sections:
            write_store({**store, **new_sections})
        for pkey, shelf in expired:
            _journal_expiry(pkey, shelf, now)
    return result
