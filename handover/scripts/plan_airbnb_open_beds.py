#!/usr/bin/env python3
"""Plan which male Airbnb listings to open vs block each night.

Target: empty unblocked Airbnb beds == max(0, 22 - male_occupied)
male_occupied = cash + Airbnb male confirmed + Booking pianist9 male
Never touch listing (5). Never cancel reservations. No Booking/price changes.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/workspace/multi-ota")
AIRBNB_PATH = ROOT / "airbnb-raw.json"
PIANIST9_PATH = ROOT / "pianist9-raw.json"
FALLBACK_PATH = ROOT / "fallback-named-stays.json"
OUT_PATH = ROOT / "airbnb-open-plan.json"

SALE_CAP = 22  # max occupied for sale (one of 23 spare)
WINDOW_END = date(2026, 11, 2)
TZ_SH = timezone(timedelta(hours=8))

# Cash: already here; checkout mornings → occupies nights where date < checkout.
# No bed numbers in outputs. Mouloud out Oct 3 → gone for nights >= Oct 3.
# Do not invent Rafik/Léo as cash.
CASH = [
    ("Abdel", date(2026, 10, 30)),
    ("Vincent", date(2026, 10, 6)),  # may extend
    ("Kliton", date(2026, 10, 4)),  # may extend
    ("Bruno", date(2026, 10, 30)),
    ("Kamel", date(2026, 10, 17)),
    ("Mouloud", date(2026, 10, 3)),
    ("Nabile's friend", None),  # no exit
    ("Amin", date(2026, 10, 16)),
]

# Historical preferred open / blocked sets (baseline when male_listings absent)
HIST_OPEN = {1, 4, 9, 13, 16, 18, 21, 22, 23, 25, 26}
HIST_BLOCKED = {2, 3, 6, 7, 8, 11, 12, 14, 15, 17, 24}
NEVER_TOUCH = {5}
# May not exist unless seen in data
MAYBE_MISSING = {10, 19, 20}

# When needing FEWER empty open beds, block empty listings in this order
BLOCK_ORDER = [21, 24, 2, 3, 6, 8, 14, 15, 17, 26, 22, 23, 25, 1, 4, 9, 13, 16, 18]
# When needing MORE empty open beds, open empty listings in this order
OPEN_ORDER = [12, 7, 11]

LISTING_RE = re.compile(r"\((\d+)\)\s*$")
SKIP_STATUS = re.compile(
    r"cancel|request|inquiry|pending|declin|awaiting|expired|withdraw",
    re.I,
)
OK_STATUS = re.compile(r"confirmed|accepted|currently hosting|ok|hosting", re.I)
FEMALE_TITLE = re.compile(r"female|femme|femmes|women|woman", re.I)
MALE_TITLE = re.compile(r"male|homme|hommes|dortoir(?!e\s*femme)", re.I)


def classify_side(rec: dict) -> str | None:
    """Prefer listing-title gender; fall back to side/classification fields."""
    listing = str(rec.get("listing") or rec.get("listing_title") or rec.get("title") or "")
    if FEMALE_TITLE.search(listing):
        return "female"
    if MALE_TITLE.search(listing) or LISTING_RE.search(listing.strip()):
        # numbered Metro 5 dorm titles without female keyword are male
        return "male"
    side = (rec.get("side") or rec.get("classification") or "").lower().strip()
    if side in {"male", "female"}:
        return side
    return None


def status_counts(status: str) -> bool:
    s = (status or "").strip()
    if not s:
        return True
    if SKIP_STATUS.search(s):
        return False
    if OK_STATUS.search(s):
        return True
    # unknown statuses: exclude to avoid overcount
    return False


def today_shanghai() -> date:
    return datetime.now(timezone.utc).astimezone(TZ_SH).date()


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_listing_number(title: str | None) -> int | None:
    if not title:
        return None
    m = LISTING_RE.search(title.strip())
    return int(m.group(1)) if m else None


def occupies(night: date, check_in: date | None, check_out: date | None) -> bool:
    """Night occupancy: inclusive check-in, exclusive checkout morning."""
    if check_in is None:
        # cash already here
        if check_out is None:
            return True
        return night < check_out
    if check_out is None:
        return night >= check_in
    return check_in <= night < check_out


def dparse(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(str(s)[:10])


def cash_count(night: date) -> int:
    n = 0
    for _name, checkout in CASH:
        if occupies(night, None, checkout):
            n += 1
    return n


def listing_open_state_from_male_listings(
    male_listings: list[dict], night: date
) -> dict[int, bool] | None:
    """Return {listing_number: is_open} for the night if usable per-date info exists."""
    if not male_listings:
        return None
    state: dict[int, bool] = {}
    has_per_date = False
    for ml in male_listings:
        num = ml.get("number")
        if num is None and ml.get("listing"):
            num = parse_listing_number(str(ml.get("listing")))
        if num is None:
            continue
        num = int(num)
        # Prefer per-date maps
        for key in ("open_by_date", "availability", "calendar", "dates"):
            by = ml.get(key)
            if isinstance(by, dict) and by:
                has_per_date = True
                iso = night.isoformat()
                if iso in by:
                    val = by[iso]
                    if isinstance(val, bool):
                        state[num] = val
                    elif isinstance(val, dict):
                        if "open" in val:
                            state[num] = bool(val["open"])
                        elif "blocked" in val:
                            state[num] = not bool(val["blocked"])
                        elif "available" in val:
                            state[num] = bool(val["available"])
                    elif isinstance(val, str):
                        state[num] = val.lower() in {"open", "available", "true", "1"}
                break
        else:
            # blocked_dates / open_dates lists
            if "blocked_dates" in ml or "open_dates" in ml:
                has_per_date = True
                iso = night.isoformat()
                if "blocked_dates" in ml:
                    blocked = {str(x)[:10] for x in (ml.get("blocked_dates") or [])}
                    state[num] = iso not in blocked
                if "open_dates" in ml:
                    opened = {str(x)[:10] for x in (ml.get("open_dates") or [])}
                    state[num] = iso in opened
            elif "status" in ml or "open" in ml or "blocked" in ml:
                # static status across window
                if "open" in ml:
                    state[num] = bool(ml["open"])
                elif "blocked" in ml:
                    state[num] = not bool(ml["blocked"])
                else:
                    st = str(ml.get("status") or "").lower()
                    if st in {"open", "available", "listed"}:
                        state[num] = True
                    elif st in {"blocked", "closed", "unavailable", "snoozed"}:
                        state[num] = False
    if not state:
        return None
    # If only static statuses and no per-date, still usable as baseline
    return state if (has_per_date or state) else None


def baseline_open_set(all_listings: set[int], male_listings: list | None) -> dict[int, bool]:
    """Map listing -> currently considered open (True) / blocked (False). Listing 5 omitted from actions."""
    state: dict[int, bool] = {}
    for n in all_listings:
        if n in NEVER_TOUCH:
            continue
        if n in HIST_OPEN:
            state[n] = True
        elif n in HIST_BLOCKED:
            state[n] = False
        else:
            # Unknown listing: treat as blocked (safer) unless historically open
            state[n] = False
    if male_listings:
        # Overlay any static statuses from male_listings (per-night overlay applied later)
        for ml in male_listings:
            num = ml.get("number")
            if num is None and ml.get("listing"):
                num = parse_listing_number(str(ml.get("listing")))
            if num is None or int(num) in NEVER_TOUCH:
                continue
            num = int(num)
            if "open" in ml and not any(
                k in ml for k in ("open_by_date", "availability", "calendar", "dates", "blocked_dates", "open_dates")
            ):
                state[num] = bool(ml["open"])
            elif "blocked" in ml and not any(
                k in ml for k in ("open_by_date", "availability", "calendar", "dates", "blocked_dates", "open_dates")
            ):
                state[num] = not bool(ml["blocked"])
            elif "status" in ml and not any(
                k in ml for k in ("open_by_date", "availability", "calendar", "dates", "blocked_dates", "open_dates")
            ):
                st = str(ml.get("status") or "").lower()
                if st in {"open", "available", "listed"}:
                    state[num] = True
                elif st in {"blocked", "closed", "unavailable", "snoozed"}:
                    state[num] = False
    return state


def ordered_block_candidates(empty_open: list[int]) -> list[int]:
    empty = set(empty_open)
    out: list[int] = []
    for n in BLOCK_ORDER:
        if n in empty and n not in NEVER_TOUCH:
            out.append(n)
            empty.discard(n)
    for n in sorted(empty):
        if n not in NEVER_TOUCH:
            out.append(n)
    return out


def ordered_open_candidates(empty_blocked: list[int]) -> list[int]:
    """Only (12), (7), (11) may be newly opened. If still short of target, report shortfall."""
    empty = set(empty_blocked)
    out: list[int] = []
    for n in OPEN_ORDER:
        if n in empty and n not in NEVER_TOUCH:
            out.append(n)
    return out


def load_airbnb_male_stays(data: dict) -> list[dict]:
    stays = []
    for r in data.get("reservations") or []:
        side = classify_side(r)
        if side != "male":
            continue
        if not status_counts(r.get("status") or ""):
            continue
        ci, co = dparse(r.get("check_in")), dparse(r.get("check_out"))
        if not ci or not co:
            continue
        listing = r.get("listing") or r.get("listing_title") or r.get("title") or ""
        num = parse_listing_number(listing)
        if num is None and r.get("listing_number") is not None:
            try:
                num = int(r["listing_number"])
            except (TypeError, ValueError):
                num = None
        beds = int(r.get("beds") or r.get("adults") or 1)
        stays.append(
            {
                "guest": (r.get("guest") or "").strip(),
                "listing_number": num,
                "listing": listing,
                "check_in": ci,
                "check_out": co,
                "beds": beds,
            }
        )
    return stays


def load_pianist9_stays() -> list[dict]:
    data = load_json(PIANIST9_PATH)
    stays_raw: list = []
    used_fallback = False
    if data and data.get("login_ok") and (data.get("stays") or []):
        stays_raw = list(data.get("stays") or [])
    else:
        used_fallback = True
        fb = load_json(FALLBACK_PATH) or []
        if isinstance(fb, list):
            stays_raw = [s for s in fb if s.get("channel") == "pianist9" and s.get("side") == "male"]
        elif isinstance(fb, dict):
            stays_raw = [
                s
                for s in (fb.get("stays") or fb.get("entries") or [])
                if s.get("channel") == "pianist9" and s.get("side") == "male"
            ]
    out = []
    for s in stays_raw:
        status = (s.get("status") or "ok").lower()
        if SKIP_STATUS.search(status) or status in {"cancelled", "canceled", "no-show", "noshow"}:
            continue
        ci, co = dparse(s.get("check_in")), dparse(s.get("check_out"))
        if not ci or not co:
            continue
        out.append(
            {
                "guest": (s.get("guest") or "").strip(),
                "check_in": ci,
                "check_out": co,
                "beds": int(s.get("beds") or 1),
                "fallback": used_fallback,
            }
        )
    return out


def discover_listings(airbnb_stays: list[dict], male_listings: list | None) -> set[int]:
    found: set[int] = set(HIST_OPEN) | set(HIST_BLOCKED) | set(NEVER_TOUCH)
    for s in airbnb_stays:
        if s.get("listing_number") is not None:
            found.add(int(s["listing_number"]))
    if male_listings:
        for ml in male_listings:
            num = ml.get("number")
            if num is None and ml.get("listing"):
                num = parse_listing_number(str(ml.get("listing")))
            if num is not None:
                found.add(int(num))
    # Drop maybe-missing unless observed in stays / male_listings
    observed = {s["listing_number"] for s in airbnb_stays if s.get("listing_number") is not None}
    if male_listings:
        for ml in male_listings:
            num = ml.get("number")
            if num is None and ml.get("listing"):
                num = parse_listing_number(str(ml.get("listing")))
            if num is not None:
                observed.add(int(num))
    for n in list(MAYBE_MISSING):
        if n not in observed:
            found.discard(n)
    return found


def count_stays_on_night(stays: list[dict], night: date) -> int:
    total = 0
    for s in stays:
        if occupies(night, s["check_in"], s["check_out"]):
            total += int(s.get("beds") or 1)
    return total


def booked_listings_on_night(airbnb_stays: list[dict], night: date) -> set[int]:
    booked: set[int] = set()
    for s in airbnb_stays:
        num = s.get("listing_number")
        if num is None:
            continue
        if occupies(night, s["check_in"], s["check_out"]):
            booked.add(int(num))
    return booked


def plan_night(
    night: date,
    cash_n: int,
    airbnb_n: int,
    pianist9_n: int,
    open_state: dict[int, bool],
    booked: set[int],
    all_listings: set[int],
) -> dict:
    male_occupied = cash_n + airbnb_n + pianist9_n
    target = max(0, SALE_CAP - male_occupied)
    over_22 = max(0, male_occupied - SALE_CAP)

    empty_open: list[int] = []
    empty_blocked: list[int] = []
    for n in all_listings:
        if n in NEVER_TOUCH:
            continue  # unavailable inventory when empty; guest already in airbnb_n if booked
        if n in booked:
            continue  # occupied — never block/cancel
        is_open = open_state.get(n, False)
        if is_open:
            empty_open.append(n)
        else:
            empty_blocked.append(n)

    current_empty_open = len(empty_open)
    actions: list[dict] = []
    shortfall = 0

    if current_empty_open > target:
        need_block = current_empty_open - target
        for n in ordered_block_candidates(empty_open):
            if need_block <= 0:
                break
            actions.append(
                {
                    "listing": n,
                    "action": "block",
                    "reason": f"reduce empty open {current_empty_open}→{target} (occupied {male_occupied})",
                }
            )
            need_block -= 1
        # If somehow still over (shouldn't — all empty_open are blockable except we never touch 5), ignore
    elif current_empty_open < target:
        need_open = target - current_empty_open
        opened = 0
        for n in ordered_open_candidates(empty_blocked):
            if opened >= need_open:
                break
            actions.append(
                {
                    "listing": n,
                    "action": "open",
                    "reason": f"raise empty open {current_empty_open}→{target} (occupied {male_occupied})",
                }
            )
            opened += 1
        shortfall = max(0, need_open - opened)

    return {
        "date": night.isoformat(),
        "male_occupied": male_occupied,
        "cash": cash_n,
        "airbnb_male": airbnb_n,
        "pianist9": pianist9_n,
        "target_empty_open": target,
        "current_empty_open": current_empty_open,
        "actions": actions,
        "shortfall": shortfall,
        "over_22": over_22,
    }


def build_plan() -> dict:
    computed_at = datetime.now(TZ_SH).isoformat(timespec="seconds")
    start = today_shanghai()
    end = WINDOW_END
    if start > end:
        # empty window
        return {
            "computed_at": computed_at,
            "window": [start.isoformat(), end.isoformat()],
            "nights": [],
            "summary": {
                "nights_needing_actions": 0,
                "nights_short_of_22": [],
                "nights_over_22": [],
                "actions_flat": [],
            },
            "blocker": "window start after end",
        }

    airbnb = load_json(AIRBNB_PATH)
    if airbnb is None:
        return {
            "computed_at": computed_at,
            "window": [start.isoformat(), end.isoformat()],
            "nights": [],
            "summary": {
                "nights_needing_actions": 0,
                "nights_short_of_22": [],
                "nights_over_22": [],
                "actions_flat": [],
            },
            "blocker": "airbnb-raw.json missing",
        }
    if not airbnb.get("login_ok"):
        return {
            "computed_at": computed_at,
            "window": [start.isoformat(), end.isoformat()],
            "nights": [],
            "summary": {
                "nights_needing_actions": 0,
                "nights_short_of_22": [],
                "nights_over_22": [],
                "actions_flat": [],
            },
            "blocker": airbnb.get("blocker") or "airbnb login_ok false",
        }

    male_listings = airbnb.get("male_listings") or None
    airbnb_stays = load_airbnb_male_stays(airbnb)
    pianist9_stays = load_pianist9_stays()
    all_listings = discover_listings(airbnb_stays, male_listings)
    base_state = baseline_open_set(all_listings, male_listings)

    nights_out: list[dict] = []
    night = start
    while night <= end:
        cash_n = cash_count(night)
        airbnb_n = count_stays_on_night(airbnb_stays, night)
        pianist9_n = count_stays_on_night(pianist9_stays, night)
        booked = booked_listings_on_night(airbnb_stays, night)

        # Per-night open overlay from male_listings if present
        open_state = dict(base_state)
        if male_listings:
            per = listing_open_state_from_male_listings(male_listings, night)
            if per:
                for n, is_open in per.items():
                    if n in NEVER_TOUCH:
                        continue
                    open_state[n] = is_open
                    all_listings.add(n)

        nights_out.append(
            plan_night(
                night,
                cash_n,
                airbnb_n,
                pianist9_n,
                open_state,
                booked,
                all_listings,
            )
        )
        night += timedelta(days=1)

    actions_flat = []
    short_nights = []
    over_nights = []
    needing = 0
    for row in nights_out:
        if row["actions"]:
            needing += 1
        if row["shortfall"] > 0:
            short_nights.append({"date": row["date"], "short_by": row["shortfall"]})
        if row["over_22"] > 0:
            over_nights.append({"date": row["date"], "over_by": row["over_22"]})
        for a in row["actions"]:
            actions_flat.append(
                {"date": row["date"], "listing": a["listing"], "action": a["action"]}
            )

    return {
        "computed_at": computed_at,
        "window": [start.isoformat(), end.isoformat()],
        "nights": nights_out,
        "summary": {
            "nights_needing_actions": needing,
            "nights_short_of_22": short_nights,
            "nights_over_22": over_nights,
            "actions_flat": actions_flat,
        },
    }


def print_summary(plan: dict) -> None:
    summ = plan.get("summary") or {}
    window = plan.get("window") or ["?", "?"]
    blocker = plan.get("blocker")
    print(f"Airbnb open-bed plan  window {window[0]} → {window[1]}")
    if blocker:
        print(f"BLOCKER: {blocker}  (no actions)")
        return
    print(
        f"nights needing actions: {summ.get('nights_needing_actions', 0)}  |  "
        f"actions: {len(summ.get('actions_flat') or [])}"
    )
    over = summ.get("nights_over_22") or []
    short = summ.get("nights_short_of_22") or []
    if over:
        bits = ", ".join(f"{x['date']} +{x['over_by']}" for x in over)
        print(f"nights over 22: {bits}")
    else:
        print("nights over 22: none")
    if short:
        bits = ", ".join(f"{x['date']} short {x['short_by']}" for x in short)
        print(f"nights short of 22: {bits}")
    else:
        print("nights short of 22: none")
    # peek a few high-signal nights
    for row in plan.get("nights") or []:
        if row.get("over_22") or row.get("shortfall") or row.get("actions"):
            acts = ",".join(f"{a['action'][0]}{a['listing']}" for a in row["actions"][:8])
            if len(row["actions"]) > 8:
                acts += f"+{len(row['actions'])-8}"
            print(
                f"  {row['date']}: occ={row['male_occupied']} "
                f"(cash{row['cash']}+ab{row['airbnb_male']}+p9{row['pianist9']}) "
                f"empty_open {row['current_empty_open']}→{row['target_empty_open']} "
                f"[{acts}]"
            )


def main() -> None:
    plan = build_plan()
    OUT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print_summary(plan)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
