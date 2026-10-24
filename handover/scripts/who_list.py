#!/usr/bin/env python3
"""Who is in: names and dates only. No bed numbers."""
from __future__ import annotations
import csv, json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import escape
from pathlib import Path

ROOT = Path("/workspace/multi-ota")
OUT_CSV = Path("/workspace/multi-ota-calendar.csv")
OUT_HTML = Path("/workspace/multi-ota-calendar.html")
MALE_CAP, FEMALE_CAP = 23, 8
EXCLUDE = {
    "imane nazih",
    # Confirmed no-shows 2026-10-05 (still "Currently hosting" on Airbnb UI)
    "isabelle lhomme",
    "yenni herrera sanabria",
    "oscar & yenni herrera sanabria",
}
# Per-night no-shows (guest keeps their other nights). Lowercased guest -> nights (ISO).
# 2026-10-06 ~18:00 Paris, per Royce: Airbnb HMXQ5CBZFM / HMTAMJN8M3 did not show Oct 6.
NO_SHOW_NIGHTS = {
    "yhonny alexander gomez martinez": {"2026-10-06"},
    "amboara ricardo ramahefanirina": {"2026-10-06"},
}

def shared_couple_female(guest: str, beds: int) -> tuple[str, int]:
    """Oscar Herrera Sanabria is male and cannot sleep in the women's dorm.
    The shared Airbnb stay is on the female listing, but only Yenni counts,
    as one woman. Do not add that Oscar to the male bed count.
    Oscar Andres Gallo Mosquera is a different male guest; leave him alone.
    """
    low = " ".join((guest or "").lower().split())
    if "herrera sanabria" in low and "yenni" in low and "gallo" not in low:
        return "Yenni Herrera Sanabria", 1
    return guest, beds
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# name, checkout exclusive or None, note, optional check_in (None = already here)
CASH = [
    ("Abdel", date(2026, 10, 30), "", None),
    ("Vincent", None, "open-ended / never-ending per Royce 2026-10-06", None),
    ("Kliton", None, "open-ended, €175 due", None),
    ("Mmada", date(2026, 10, 9), "", None),
    ("Karim", date(2026, 10, 7), "", date(2026, 10, 6)),
    ("Bruno", date(2026, 10, 30), "", None),
    ("Kamel", date(2026, 10, 17), "", None),
    ("Mouloud", date(2026, 10, 3), "", None),
    ("Nabile's friend", date(2026, 10, 8), "left 8 Oct (Royce, to free a bed for Walid)", None),
    ("Amin", date(2026, 10, 16), "", None),
    ("Nader", date(2026, 10, 15), "", date(2026, 10, 5)),
    ("Ruben", date(2026, 10, 16), "left early per Royce (Oct 17); not staying Oct 16+", date(2026, 10, 8)),
    ("Khaldoun", date(2026, 10, 16), "cash, extended to 16 Oct morning per Royce", date(2026, 10, 8)),
    ("Gabriel", date(2026, 10, 12), "cash", date(2026, 10, 9)),
]

# Female cash guests use the same tuple format and stay out of the male count.
CASH_FEMALE = [
    ("Keti", date(2026, 10, 28), "cash, extended to 28 Oct morning per Royce 2026-10-23", date(2026, 9, 23)),
    ("Valeriia", date(2026, 10, 10), "out 10 Oct, not staying night of 10 Oct (Royce)", date(2026, 10, 5)),
]

def today_shanghai() -> date:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()

def fmt(d: str | None) -> str:
    if not d or d == "open":
        return "no exit"
    y, m, day = d.split("-")
    return f"{int(day)} {MONTHS[int(m)-1]}"

def load(path):
    p = ROOT / path
    if not p.exists():
        return None
    return json.loads(p.read_text())

def in_window(ci: date, co: date, start: date, end: date) -> bool:
    return ci < end and co > start

def rows_for(start: date, end: date):
    male, female = [], []
    for name, checkout, note, check_in in CASH:
        if checkout is not None and checkout <= start:
            continue
        if check_in is not None and check_in >= end:
            continue
        already = check_in is None or check_in <= start
        ci_val = "already here" if already else check_in.isoformat()
        here = True if check_in is None else (check_in <= start and (checkout is None or start < checkout))
        male.append({
            "guest": name, "source": "cash", "side": "male",
            "check_in": ci_val,
            "check_out": checkout.isoformat() if checkout else "open",
            "note": note, "beds": 1,
            "here_tonight": here,
        })
    for name, checkout, note, check_in in CASH_FEMALE:
        if checkout is not None and checkout <= start:
            continue
        if check_in is not None and check_in >= end:
            continue
        already = check_in is None or check_in <= start
        ci_val = "already here" if already else check_in.isoformat()
        here = True if check_in is None else (check_in <= start and (checkout is None or start < checkout))
        female.append({
            "guest": name, "source": "cash", "side": "female",
            "check_in": ci_val,
            "check_out": checkout.isoformat() if checkout else "open",
            "note": note, "beds": 1,
            "here_tonight": here,
        })

    def add_stay(bucket, guest, source, side, ci, co, beds=1):
        guest, beds = shared_couple_female(guest, int(beds))
        if guest.lower() in EXCLUDE:
            return
        skip = NO_SHOW_NIGHTS.get(" ".join(guest.lower().split()))
        if skip:
            # split the stay around no-show nights; each remaining run is added on its own
            d, d_end, run = date.fromisoformat(ci), date.fromisoformat(co), None
            runs = []
            while d < d_end:
                if d.isoformat() in skip:
                    if run: runs.append(run); run = None
                else:
                    run = [run[0], d + timedelta(days=1)] if run else [d, d + timedelta(days=1)]
                d += timedelta(days=1)
            if run: runs.append(run)
            for r0, r1 in runs:
                _add_stay(bucket, guest, source, side, r0.isoformat(), r1.isoformat(), beds,
                          "no-show " + ", ".join(fmt(x) for x in sorted(skip)))
            return
        _add_stay(bucket, guest, source, side, ci, co, beds)

    def _add_stay(bucket, guest, source, side, ci, co, beds=1, note=""):
        if not in_window(date.fromisoformat(ci), date.fromisoformat(co), start, end):
            return
        src = source
        if source == "airbnb" and date.fromisoformat(ci) > start:
            src = "airbnb_soon"
        bucket.append({
            "guest": guest, "source": src, "side": side,
            "check_in": ci, "check_out": co, "note": note,
            "beds": beds,
            "here_tonight": date.fromisoformat(ci) <= start < date.fromisoformat(co),
        })

    air = load("airbnb-raw.json") or {}
    air_ok = bool(air.get("login_ok"))
    for r in air.get("reservations") or []:
        side = (r.get("side") or r.get("classification") or "").lower()
        if side not in ("male", "female"):
            listing = (r.get("listing") or "").lower()
            if "female" in listing or "femme" in listing:
                side = "female"
            elif "male" in listing or "homme" in listing:
                side = "male"
            else:
                continue
        guest_name = (r.get("guest") or "").strip()
        if guest_name.lower().startswith("tatiana quillivic"):
            side = "female"
        status = (r.get("status") or "").lower()
        if "cancel" in status or "request" in status:
            continue
        bucket = male if side == "male" else female
        beds = int(r.get("beds") or r.get("adults") or 1)
        add_stay(bucket, (r.get("guest") or "").strip(), "airbnb", side, r["check_in"][:10], r["check_out"][:10], beds)

    def booking(path, channel, side, hotel):
        data = load(path) or {}
        blocker = (data.get("blocker") or data.get("url") or "")
        ok = bool(data.get("login_ok")) and not any(x in blocker.lower() for x in ("denied", "protected", "locked", "timeout"))
        stays = data.get("stays") or []
        if not ok or not stays:
            fb = load("fallback-named-stays.json") or []
            stays = [s for s in fb if s.get("channel") == channel]
            ok = False
        bucket = male if side == "male" else female
        for s in stays:
            guest = (s.get("guest") or "").strip()
            if guest.lower() in EXCLUDE:
                continue
            status = (s.get("status") or "ok").lower()
            if status in {"cancelled", "canceled", "no-show", "noshow"}:
                continue
            add_stay(bucket, guest, channel, side, s["check_in"][:10], s["check_out"][:10], int(s.get("beds") or 1))
        return ok, blocker

    p9_ok, p9_block = booking("pianist9-raw.json", "pianist9", "male", "16844588")
    rb_ok, rb_block = booking("royceb-raw.json", "royceb", "female", "16840329")

    agoda = load("agoda-stays.json") or []
    if isinstance(agoda, dict):
        agoda = agoda.get("stays") or []
    for s in agoda:
        guest = (s.get("guest") or "").strip()
        side = (s.get("side") or "").lower()
        if side not in ("male", "female"):
            continue
        status = (s.get("status") or "ok").lower()
        if status in {"cancelled", "canceled", "no-show", "noshow"}:
            continue
        bucket = male if side == "male" else female
        add_stay(bucket, guest, "agoda", side, s["check_in"][:10], s["check_out"][:10], int(s.get("beds") or 1))

    return male, female, air_ok, p9_ok, rb_ok, p9_block, rb_block

def tonight(rows):
    return sum(int(r["beds"]) for r in rows if r["here_tonight"])

def on_night(r, d: date) -> bool:
    if r["check_in"] == "already here":
        if r["check_out"] in ("open", "", None):
            return True
        return d < date.fromisoformat(r["check_out"])
    if r["check_out"] in ("open", "", None):
        return date.fromisoformat(r["check_in"]) <= d
    return date.fromisoformat(r["check_in"]) <= d < date.fromisoformat(r["check_out"])

# Short codes stay in the page JSON. Labels are only for the tap panel.
# Airbnb "still to come" is the same source as Airbnb.
WHO_SOURCES = (
    ("C", "Cash", ("cash",)),
    ("A", "Airbnb", ("airbnb", "airbnb_soon")),
    ("P", "Booking pianist9", ("pianist9",)),
    ("R", "Booking royceb", ("royceb",)),
    ("G", "Agoda", ("agoda",)),
)

def who_on(rows, d: date):
    """People in on this night, grouped by source. One name per stay, no beds."""
    code_of = {}
    for code, _label, keys in WHO_SOURCES:
        for key in keys:
            code_of[key] = code
    grouped = {code: [] for code, _label, _keys in WHO_SOURCES}
    for r in rows:
        if not on_night(r, d):
            continue
        code = code_of.get(r["source"])
        if not code:
            continue
        name = (r.get("guest") or "").strip()
        if not name or name in grouped[code]:
            continue
        grouped[code].append(name)
    return [[code, names] for code, _label, _keys in WHO_SOURCES if (names := grouped[code])]

def daily(male, female, start: date, days: int = 31):
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        m = sum(int(r["beds"]) for r in male if on_night(r, d))
        f = sum(int(r["beds"]) for r in female if on_night(r, d))
        out.append({"date": d, "male": m, "female": f, "open_male": MALE_CAP - m, "open_female": FEMALE_CAP - f})
    return out

AMBER = "#e6a23c"
GREEN = "#3d9a5b"
BOOKED_MALE = "#3b82f6"
BOOKED_FEMALE = "#f97316"

# --- On-sale layers (men's chart). See ONSALE_README.md.
# Drawn client-side by ONSALE_JS from chart-data row fields:
#   "bm" = beds on sale on Booking.com that night (men, from boo_onsale.json)
#   "am" = men's Airbnb listings open and unbooked that night (from airbnb_onsale.json)
# A missing field means unknown and draws nothing.
BOO_SALE_FILL = "#003580"
BOO_SALE_STROKE = "#8fb8ff"
AIRBNB_SALE_FILL = "#ff5a5f"
AIRBNB_SALE_STROKE = "#ffb3b5"


def load_boo_onsale():
    """{"men": {iso: n}, "women": {iso: n}} from boo_onsale.json (missing file -> empty)."""
    data = load("boo_onsale.json") or {}
    out = {}
    for side in ("men", "women"):
        out[side] = {str(k)[:10]: int(v) for k, v in (data.get(side) or {}).items() if v is not None}
    return out


def load_airbnb_onsale():
    """{"men": {iso: n}} from airbnb_onsale.json (missing file -> empty)."""
    data = load("airbnb_onsale.json") or {}
    return {"men": {str(k)[:10]: int(v) for k, v in (data.get("men") or {}).items() if v is not None}}


def airbnb_onsale_source_line():
    """Tiny line under the men's legend, e.g. 'Airbnb on sale read from the Airbnb host calendar at 11:43 Paris, Oct 6'."""
    data = load("airbnb_onsale.json") or {}
    label = data.get("read_at_label")
    if not label:
        return ""
    return f'<p class="capnote" id="am-src" style="font-size:11px">Airbnb on sale read from the Airbnb host calendar at {escape(label)}</p>'


def inject_onsale(rows, onsale=None, airbnb=None):
    """Set/refresh row["bm"] (boo_onsale.json) and row["am"] (airbnb_onsale.json) in parsed chart-data rows.

    Nights absent from a file get no key (unknown). Women are not drawn, so no "bf"/"af". Returns rows.
    """
    onsale = onsale if onsale is not None else load_boo_onsale()
    airbnb = airbnb if airbnb is not None else load_airbnb_onsale()
    for key, men in (("bm", onsale.get("men") or {}), ("am", airbnb.get("men") or {})):
        for r in rows:
            if r.get("d") in men:
                r[key] = int(men[r["d"]])
            else:
                r.pop(key, None)
    return rows


def adjust_onsale(field, check_in, check_out, delta, why="", rows=None):
    """Routine helper: move men's on-sale counts by `delta` for every night check_in <= night < check_out.

    field "am" -> airbnb_onsale.json (new men's Airbnb booking: delta=-1, cancellation: delta=+1)
    field "bm" -> boo_onsale.json (new pianist9 men's stay: -1, cancellation: +1)
    Floors at 0. Nights not in the file stay unknown. If parsed chart-data `rows` are given, they are
    re-injected so the page matches the file. Returns {night: (old, new)}.
    """
    fname = {"am": "airbnb_onsale.json", "bm": "boo_onsale.json"}[field]
    path = ROOT / fname
    data = json.loads(path.read_text(encoding="utf-8"))
    men = data.setdefault("men", {})
    ci, co = date.fromisoformat(str(check_in)[:10]), date.fromisoformat(str(check_out)[:10])
    changed = {}
    d = ci
    while d < co:
        k = d.isoformat()
        if k in men and men[k] is not None:
            old = int(men[k]); new = max(0, old + int(delta))
            men[k] = new; changed[k] = (old, new)
        d += timedelta(days=1)
    if changed and isinstance(data.get("adjustments"), list):
        data["adjustments"].append({"at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(timespec="seconds"),
                                    "nights": f"{ci.isoformat()}..{co.isoformat()}", "delta": int(delta), "why": why})
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if rows is not None:
        inject_onsale(rows)
    return changed


def load_open_inventory():
    """Channel inventory still for sale, not people already in.

    Male Airbnb: airbnb-open-plan.json current_empty_open (empty listings that are open).
    Male Booking.com: booking-rooms-to-sell.json rooms_to_sell.
    A night with no saved figure is 0. Female Booking.com is unknown, so it is not read.
    Female Airbnb is used only when a night actually has a female empty-open field.
    """
    plan = load("airbnb-open-plan.json") or {}
    airbnb_male, airbnb_female = {}, {}
    for n in plan.get("nights") or []:
        day = str(n.get("date") or "")[:10]
        if not day:
            continue
        if n.get("current_empty_open") is not None:
            airbnb_male[day] = int(n["current_empty_open"])
        for key in ("current_empty_open_female", "female_empty_open", "female_open"):
            if n.get(key) is not None:
                airbnb_female[day] = int(n[key])
                break
    book = load("booking-rooms-to-sell.json") or {}
    booking_male = {}
    raw = book.get("rooms_to_sell") or {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if value is None:
                continue
            booking_male[str(key)[:10]] = int(value)
    return {
        "airbnb_male": airbnb_male,
        "airbnb_female": airbnb_female,
        "booking_male": booking_male,
    }


def fit_stack(occupied, airbnb, booking, cap):
    """Keep occupied + Airbnb open + Booking open from drawing past cap.

    Shrink amber (Airbnb open) first, then green (Booking open).
    If occupied alone is over the cap, draw it at the cap and both opens at 0.
    """
    occ, ab, bk = max(0, int(occupied)), max(0, int(airbnb)), max(0, int(booking))
    raw = (occ, ab, bk)
    if occ >= cap:
        drawn = (min(occ, cap), 0, 0)
        reason = None if drawn == raw else ("occupied over cap" if occ > cap else "open over cap")
        return drawn[0], drawn[1], drawn[2], reason
    overflow = occ + ab + bk - cap
    if overflow <= 0:
        return occ, ab, bk, None
    ab -= min(ab, overflow)
    overflow = occ + ab + bk - cap
    if overflow > 0:
        bk -= min(bk, overflow)
    return occ, ab, bk, "open over cap"


def attach_open(days):
    inv = load_open_inventory()
    out = []
    for d in days:
        iso = d["date"].isoformat()
        m_ab = int(inv["airbnb_male"].get(iso, 0))
        m_bk = int(inv["booking_male"].get(iso, 0))
        f_ab = int(inv["airbnb_female"].get(iso, 0))
        mo, ma, mb, mnote = fit_stack(d["male"], m_ab, m_bk, MALE_CAP)
        fo, fa, fb, fnote = fit_stack(d["female"], f_ab, 0, FEMALE_CAP)
        row = dict(d)
        row.update({
            "label": f"{d['date'].day} {MONTHS[d['date'].month - 1]}",
            "male_booked": mo,
            "male_airbnb": ma,
            "male_booking": mb,
            "male_airbnb_raw": m_ab,
            "male_booking_raw": m_bk,
            "male_airbnb_known": iso in inv["airbnb_male"],
            "male_booking_known": iso in inv["booking_male"],
            "male_trim": mnote,
            "female_booked": fo,
            "female_airbnb": fa,
            "female_booking": fb,
            "female_airbnb_raw": f_ab,
            "female_airbnb_known": iso in inv["airbnb_female"],
            "female_trim": fnote,
        })
        out.append(row)
    return out


def chart_svg(series, cap, booked_fill, aria):
    """One SVG path per colour so the page stays small, plus a booked count on every night.

    A path cannot carry a number, so each booked segment also gets a <text> label.
    Tall segments (at least 16px) keep the count inside the bar. Shorter ones still
    show the integer just above that segment.
    """
    n = max(len(series), 1)
    slot, bar_w, left, top, plot_h = 20, 12, 22, 6, 100
    bottom = 22
    width = left + 2 + n * slot
    height = top + plot_h + bottom
    peak = max(int(cap), 1)
    base = top + plot_h
    cap_y = top + plot_h - (plot_h * (float(cap) / peak))
    paths = {booked_fill: [], AMBER: [], GREEN: []}
    # Men's chart: the old full-width "Airbnb open"/"Booking open" stack (m[1], m[2]) is
    # not drawn any more. Its place is taken by thin on-sale bars (Boo on sale "bm",
    # Airbnb on sale "am") that ONSALE_JS draws in the browser from chart-data, so this
    # SVG depends only on the booked counts and old patch scripts keep regenerating it
    # byte-for-byte. Women's chart is unchanged.
    stack_open = booked_fill != BOOKED_MALE
    labels = []
    for i, item in enumerate(series):
        x = left + i * slot + (slot - bar_w) / 2.0
        cursor = float(base)
        booked_geom = None
        booked_n = int(item["booked"])
        # Bar height stays the clipped stack. The label is the real occupied count,
        # which can sit above the cap (Oct 5 female is 9 on a bar drawn at 8).
        label_n = int(item["real"]) if "real" in item else booked_n
        layers = ((booked_n, booked_fill), (int(item["airbnb"]), AMBER), (int(item["booking"]), GREEN))
        if not stack_open:
            layers = layers[:1]
        for value, fill in layers:
            if value <= 0:
                continue
            h = plot_h * (float(value) / peak)
            y = cursor - h
            if y < cap_y:
                y = cap_y
                h = cursor - y
            if h <= 0:
                continue
            paths[fill].append(f"M{x:.0f},{y:.0f}h{bar_w}v{h:.0f}h-{bar_w}z")
            if fill == booked_fill:
                booked_geom = (y, h)
            cursor = y
        if label_n <= 0:
            continue
        cx = x + bar_w / 2.0
        if booked_geom is not None and booked_geom[1] >= 16:
            y, h = booked_geom
            ty = y + h / 2.0 + 3.5
            labels.append(
                f'<text x="{cx:.0f}" y="{ty:.0f}" text-anchor="middle" fill="#f8fafc" font-size="9" font-weight="700" pointer-events="none">{label_n}</text>'
            )
        else:
            y = booked_geom[0] if booked_geom is not None else float(base)
            ty = y - 2
            if ty < top + 8:
                ty = top + 8
            labels.append(
                f'<text x="{cx:.0f}" y="{ty:.0f}" text-anchor="middle" fill="#f8fafc" font-size="9" font-weight="700" stroke="#0c0e12" stroke-width="2" paint-order="stroke" pointer-events="none">{label_n}</text>'
            )
    days = []
    for i, item in enumerate(series):
        day = str(item["label"]).split()[0]
        x = left + i * slot + slot / 2.0
        days.append(f'<tspan x="{x:.0f}" y="{base+12}">{escape(day)}</tspan>')
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(aria)}" data-left="{left}" data-slot="{slot}" data-n="{n}">',
        f'<line x1="{left}" y1="{base}" x2="{left+n*slot}" y2="{base}" stroke="#3f4654"/>',
        f'<line x1="{left}" y1="{cap_y:.0f}" x2="{left+n*slot}" y2="{cap_y:.0f}" stroke="#e4e4e7" stroke-dasharray="4 3"/>',
        f'<text x="{left-2}" y="{cap_y+3:.0f}" text-anchor="end" fill="#a1a1aa" font-size="11">{cap}</text>',
        f'<text x="{left-2}" y="{base}" text-anchor="end" fill="#a1a1aa" font-size="11">0</text>',
        f'<rect class="hi" x="0" y="0" width="{slot}" height="{height}" fill="none" stroke="#f4f4f5" visibility="hidden"/>',
    ]
    for fill, cmds in paths.items():
        if cmds:
            chunks.append(f'<path fill="{fill}" d="{"".join(cmds)}"/>')
    chunks.extend(labels)
    chunks.append(f'<text fill="#a1a1aa" font-size="9">{"".join(days)}</text></svg>')
    return "".join(chunks)



ONSALE_LEGEND_MALE = (
    '<p class="legend">'
    f'<span><i style="background:{BOOKED_MALE}"></i>Blue = booked (all sources)</span>'
    f'<span><i style="background:{BOO_SALE_FILL};box-shadow:inset 0 0 0 1px {BOO_SALE_STROKE}"></i>Boo on sale</span>'
    f'<span><i style="background:{AIRBNB_SALE_FILL}"></i>Airbnb on sale</span>'
    '</p>\n<p class="capnote" id="am-note">Airbnb on sale: not tracked yet.</p>'
)
ONSALE_CAPNOTE_MALE = (
    f'<p class="capnote">Dashed line is the cap, {MALE_CAP}; we sell at most {MALE_CAP - 1}. '
    'Thin bars on top of blue = beds still on sale that night (navy Boo, coral Airbnb). '
    'Bars crossing the dashed line = more beds on sale than free: overbooking risk.</p>'
)

# Draws the thin on-sale bars over the men's SVG from chart-data "bm"/"am".
# Kept as its own <script> so incremental patches (JSON/SVG/table/stamp) never touch it.
# Stack per night: blue booked (server SVG) -> navy Boo "bm" -> coral Airbnb "am".
# Same scale as the booked bars (100px = cap). Stacks may rise above the dashed cap line:
# the SVG grows upward to fit, up to MAXOVER beds over the cap; anything taller is clipped
# with a small "+N" label. The cap line is redrawn on top so crossings stay visible.
ONSALE_JS = """<script id="onsale-js">
(function () {
  var el = document.getElementById("chart-data");
  var svg = document.querySelector('.chart svg[aria-label^="Male"]');
  if (!el || !svg || svg.getAttribute("data-onsale")) return;
  var rows = JSON.parse(el.textContent);
  var NS = "http://www.w3.org/2000/svg";
  var left = +svg.getAttribute("data-left") || 22, slot = +svg.getAttribute("data-slot") || 20;
  var TOP = 6, PLOT = 100, BASE = TOP + PLOT, THIN = 8, MAXOVER = 15, LBL = 10;
  var LAYERS = [["bm", "%BF%", "%BS%"], ["am", "%AF%", "%AS%"]];
  svg.setAttribute("data-onsale", "1");
  var vb = (svg.getAttribute("viewBox") || "").split(/\\s+/).map(Number);
  if (vb.length !== 4) vb = [0, 0, +svg.getAttribute("width") || 644, +svg.getAttribute("height") || 128];
  var labels = Array.prototype.slice.call(svg.querySelectorAll("text[pointer-events=none]"));
  function n(r, k) { return typeof r[k] === "number" && r[k] > 0 ? r[k] : 0; }
  function capOf(r) { return (r.m && r.m[3]) || 23; }
  function usedOf(r) { var c = capOf(r); return Math.max(0, Math.min((r.m && r.m[0]) || 0, c)); }
  var over = 0;
  rows.forEach(function (r) { over = Math.max(over, usedOf(r) + n(r, "bm") + n(r, "am") - capOf(r)); });
  over = Math.min(over, MAXOVER);
  var LIMIT = TOP - PLOT * over / 23;
  var g = document.createElementNS(NS, "g");
  g.setAttribute("class", "onsale");
  g.setAttribute("pointer-events", "none");
  var minY = TOP;
  function txt(x, y, s, inside, fill) {
    minY = Math.min(minY, y - 8);
    var t = document.createElementNS(NS, "text");
    t.setAttribute("x", String(Math.round(x)));
    t.setAttribute("y", String(Math.round(y)));
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("fill", fill || "#f8fafc");
    t.setAttribute("font-size", "9");
    t.setAttribute("font-weight", "700");
    if (!inside) { t.setAttribute("stroke", "#0c0e12"); t.setAttribute("stroke-width", "2"); t.setAttribute("paint-order", "stroke"); }
    t.textContent = s;
    g.appendChild(t);
  }
  var anyAm = false;
  rows.forEach(function (r, i) {
    if (typeof r.am === "number") anyAm = true;
    var vals = LAYERS.map(function (L) { return n(r, L[0]); });
    if (!(vals[0] > 0 || vals[1] > 0)) return;
    var cap = capOf(r), used = usedOf(r);
    var cx = left + i * slot + slot / 2;
    var bh = PLOT * used / cap, cursor = BASE - bh;
    if (used > 0) {
      labels.forEach(function (t) {
        if (+t.getAttribute("x") !== Math.round(cx) || !t.hasAttribute("stroke")) return;
        if (bh >= 11) {
          t.setAttribute("y", String(Math.round(cursor + bh / 2 + 3.5)));
          t.removeAttribute("stroke"); t.removeAttribute("stroke-width"); t.removeAttribute("paint-order");
        } else {
          cursor -= 11;
        }
      });
    }
    var hidden = Math.max(0, used + vals[0] + vals[1] - cap - MAXOVER);
    LAYERS.forEach(function (L, k) {
      var v = vals[k];
      if (!(v > 0)) return;
      var h = PLOT * v / cap, y = cursor - h, clipped = false;
      if (y < LIMIT) { y = LIMIT; h = Math.max(0, cursor - y); clipped = true; }
      if (h >= 1) {
        var rc = document.createElementNS(NS, "rect");
        rc.setAttribute("x", String(cx - THIN / 2));
        rc.setAttribute("y", y.toFixed(1));
        rc.setAttribute("width", String(THIN));
        rc.setAttribute("height", h.toFixed(1));
        rc.setAttribute("rx", "1");
        rc.setAttribute("fill", L[1]);
        rc.setAttribute("stroke", L[2]);
        rc.setAttribute("stroke-width", "1");
        g.appendChild(rc);
        minY = Math.min(minY, y);
      }
      if (h >= 11) { txt(cx, y + h / 2 + 3.5, String(v), true); cursor = y; }
      else { txt(cx, y - 2, String(v), false); cursor = y - LBL; }
      if (clipped && hidden > 0) { txt(cx, Math.min(y, cursor) - 2, "+" + hidden, false, "#fca5a5"); }
    });
  });
  var cl = svg.querySelector('line[stroke-dasharray]');
  if (cl) { var c2 = cl.cloneNode(false); c2.setAttribute("stroke-opacity", "0.9"); g.appendChild(c2); }
  svg.appendChild(g);
  var HEAD = Math.max(12, Math.ceil(TOP - minY) + 4);
  svg.setAttribute("viewBox", vb[0] + " " + (vb[1] - HEAD) + " " + vb[2] + " " + (vb[3] + HEAD));
  svg.setAttribute("height", String((+svg.getAttribute("height") || vb[3]) + HEAD));
  var hi = svg.querySelector("rect.hi");
  if (hi) { hi.setAttribute("y", String(vb[1] - HEAD)); hi.setAttribute("height", String(vb[3] + HEAD)); }
  var note = document.getElementById("am-note");
  if (note && anyAm) note.hidden = true;
  var src = document.getElementById("am-src");
  if (src && !anyAm) src.hidden = true;
})();
</script>""".replace("%BF%", BOO_SALE_FILL).replace("%BS%", BOO_SALE_STROKE).replace("%AF%", AIRBNB_SALE_FILL).replace("%AS%", AIRBNB_SALE_STROKE)


# Month labels + separators under both charts, drawn client-side (added 2026-10-07 with the Feb 2027 extension).
# Kept out of chart_svg so patch scripts still regenerate the SVGs byte-for-byte.
MONTH_JS = '<script id="month-js">\n(function () {\n  var el = document.getElementById("chart-data");\n  if (!el) return;\n  var rows = JSON.parse(el.textContent);\n  var NS = "http://www.w3.org/2000/svg";\n  var MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];\n  var EXTRA = 13, BOTTOM = 128;\n  var today = "";\n  try { today = new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date()); } catch (e) {}\n  var todayIndex = -1;\n  rows.forEach(function (r, i) { if (r.d === today) todayIndex = i; });\n  Array.prototype.forEach.call(document.querySelectorAll(".chart svg"), function (svg) {\n    if (svg.getAttribute("data-months")) return;\n    var vb = (svg.getAttribute("viewBox") || "").split(/\\s+/).map(Number);\n    if (vb.length !== 4) return;\n    svg.setAttribute("data-months", "1");\n    var left = +svg.getAttribute("data-left") || 22, slot = +svg.getAttribute("data-slot") || 20;\n    var g = document.createElementNS(NS, "g");\n    g.setAttribute("class", "months");\n    g.setAttribute("pointer-events", "none");\n    rows.forEach(function (r, i) {\n      var p = String(r.d || "").split("-");\n      if (p.length !== 3) return;\n      var yr = +p[0], mo = +p[1], dy = +p[2];\n      if (i !== 0 && dy !== 1) return;\n      var x = left + i * slot;\n      if (i !== 0) {\n        var ln = document.createElementNS(NS, "line");\n        ln.setAttribute("x1", String(x)); ln.setAttribute("x2", String(x));\n        ln.setAttribute("y1", String(vb[1])); ln.setAttribute("y2", String(BOTTOM + EXTRA));\n        ln.setAttribute("stroke", "#52525b"); ln.setAttribute("stroke-dasharray", "2 3");\n        g.appendChild(ln);\n      }\n      var t = document.createElementNS(NS, "text");\n      t.setAttribute("x", String(x + 3));\n      t.setAttribute("y", String(BOTTOM + 9));\n      t.setAttribute("fill", "#d4d4d8");\n      t.setAttribute("font-size", "10");\n      t.setAttribute("font-weight", "700");\n      t.textContent = MON[mo - 1] + ((i === 0 || mo === 1) ? " " + yr : "");\n      g.appendChild(t);\n    });\n    svg.appendChild(g);\n    svg.setAttribute("viewBox", vb[0] + " " + vb[1] + " " + vb[2] + " " + (vb[3] + EXTRA));\n    svg.setAttribute("height", String((+svg.getAttribute("height") || vb[3]) + EXTRA));\n    var hi = svg.querySelector("rect.hi");\n    if (hi) hi.setAttribute("height", String((+hi.getAttribute("height") || vb[3]) + EXTRA));\n    var box = svg.parentNode;\n    if (todayIndex > 3 && box && box.scrollWidth > box.clientWidth) box.scrollLeft = Math.max(0, left + (todayIndex - 2) * slot);\n  });\n})();\n</script>'


def legend_html(booked_color):
    return (
        '<p class="legend">'
        f'<span><i style="background:{booked_color}"></i>Booked</span>'
        f'<span><i style="background:{AMBER}"></i>Airbnb open</span>'
        f'<span><i style="background:{GREEN}"></i>Booking open</span>'
        "</p>"
    )


PAGE_CSS = """
:root{color-scheme:dark}
body{margin:0;background:#0c0e12;color:#f4f4f5;font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:18px 16px 72px}
h1{font-size:1.15rem;font-weight:650;margin:0 0 6px;letter-spacing:-.02em}
.asof{margin:0 0 4px;color:#f4f4f5;font-size:15px}
.meta{margin:0 0 16px;color:#9ca3af;font-size:13px}
.tonight{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.card{background:#161a22;border:1px solid #262b36;border-radius:16px;padding:14px 14px 12px}
.card.male{box-shadow:inset 3px 0 0 #3b82f6}
.card.female{box-shadow:inset 3px 0 0 #f97316}
.k{margin:0;color:#a1a1aa;font-size:13px;font-weight:650}
.big{margin:8px 0 2px;font-size:clamp(32px,10vw,46px);font-weight:750;letter-spacing:-.045em;line-height:.95;font-variant-numeric:tabular-nums}
.big .of{font-size:.46em;font-weight:560;color:#a1a1aa;letter-spacing:-.03em}
.open{margin:6px 0 0;font-weight:700;color:#4ade80;font-size:15px}
h2{font-size:1.02rem;margin:26px 0 8px;font-weight:680;letter-spacing:-.01em}
.chart{background:#161a22;border:1px solid #262b36;border-radius:16px;padding:8px 6px 4px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.chart svg{display:block;height:auto;cursor:pointer}
.chart{touch-action:pan-x}
.chart rect.on{stroke:#f4f4f5;stroke-width:2}
.legend{display:flex;flex-wrap:wrap;gap:8px 14px;margin:8px 2px 0;color:#e4e4e7;font-size:12px;align-items:center}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.detail{margin:14px 2px 0;background:#161a22;border:1px solid #262b36;border-radius:16px;padding:12px 14px;font-size:15px}
.detail strong{display:block;margin:0 0 4px;font-size:1.05rem}
.detail .who{margin:8px 0 0}
.detail .who-h{margin:8px 0 2px;color:#a1a1aa;font-size:12px;font-weight:750;letter-spacing:.04em;text-transform:uppercase}
button.breakdown{margin:10px 0 0;padding:6px 12px;border:1px solid #3f4654;border-radius:999px;background:#222733;color:#f4f4f5;font:inherit;font-size:14px;font-weight:700;cursor:pointer;touch-action:manipulation}
.capnote{margin:6px 2px 0;color:#9ca3af;font-size:12px}
h3{margin:18px 0 6px;padding:6px 10px;font-size:1rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;background:#1c212b;border-left:4px solid #e6a23c;border-radius:4px}
table{border-collapse:collapse;width:100%;background:#161a22;border:1px solid #262b36;border-radius:12px}
th,td{border-bottom:1px solid #262b36;padding:7px 8px;text-align:left;vertical-align:top}
th{color:#a1a1aa;font-weight:600;font-size:12px}
tr:last-child td{border-bottom:none}
"""



def asof_phrase(as_of: str) -> str:
    """as_of is YYYY-MM-DD HH:MM in Asia/Shanghai. Paris leads, then Shanghai."""
    sh = datetime.strptime(as_of, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    paris = sh.astimezone(ZoneInfo("Europe/Paris"))
    if paris.date() == sh.date():
        return f"{paris.strftime('%H:%M')} Paris, {sh.strftime('%H:%M')} Shanghai ({sh.strftime('%Y-%m-%d')})"
    return (
        f"{paris.strftime('%Y-%m-%d')} {paris.strftime('%H:%M')} Paris, "
        f"{sh.strftime('%Y-%m-%d')} {sh.strftime('%H:%M')} Shanghai"
    )


def render_page(as_of, status_line, points, male_tables, female_tables):
    """Dark chart page. The first night row is tonight. Occupancy is not recomputed here."""
    if not points:
        raise ValueError("no night rows")
    t = points[0]
    def series(side):
        if side == "male":
            return [{
                "label": p["label"], "iso": p["iso"], "booked": p["male_booked"], "real": p["male"],
                "airbnb": p["male_airbnb"], "booking": p["male_booking"], "trim": p.get("male_trim"),
            } for p in points]
        return [{
            "label": p["label"], "iso": p["iso"], "booked": p["female_booked"], "real": p["female"],
            "airbnb": p["female_airbnb"], "booking": p["female_booking"], "trim": p.get("female_trim"),
        } for p in points]
    male_svg = chart_svg(
        series("male"),
        MALE_CAP,
        BOOKED_MALE,
        f"Male beds per night, {points[0]['label']} through {points[-1]['label']}, cap {MALE_CAP}",
    )
    female_svg = chart_svg(
        series("female"),
        FEMALE_CAP,
        BOOKED_FEMALE,
        f"Female beds per night, {points[0]['label']} through {points[-1]['label']}, cap {FEMALE_CAP}",
    )
    chart_rows = inject_onsale([{
        "l": p["label"],
        "d": p["iso"],
        "m": [p["male"], p["male_airbnb"], p["male_booking"], MALE_CAP, 1 if p.get("male_trim") else 0],
        "f": [p["female"], p["female_airbnb"], p["female_booking"], FEMALE_CAP, 1 if p.get("female_trim") else 0],
        "w": [p.get("mw") or [], p.get("fw") or []],
    } for p in points])
    chart_json = json.dumps(chart_rows, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Who is in</title>
<style>{PAGE_CSS}</style></head><body><div class="wrap">
<h1>Who is in</h1>
<p class="asof"><strong>As of {escape(asof_phrase(as_of))}.</strong></p>
<p class="meta">Refreshes every 30 min. Last refreshed {escape(asof_phrase(as_of))}.</p>
<p class="meta">{escape(status_line)}</p>
<div class="tonight">
<section class="card male"><p class="k">Male tonight</p><p class="big"><span id="male-tonight">{t["male"]}</span> <span class="of">/ {MALE_CAP}</span></p><p class="open"><span id="male-open">{t["open_male"]}</span> open</p></section>
<section class="card female"><p class="k">Female tonight</p><p class="big"><span id="female-tonight">{t["female"]}</span> <span class="of">/ {FEMALE_CAP}</span></p><p class="open"><span id="female-open">{t["open_female"]}</span> open</p></section>
</div>
<h2>Male, beds used per night</h2>
<div class="chart">{male_svg}</div>
{ONSALE_LEGEND_MALE}
{airbnb_onsale_source_line()}
{ONSALE_CAPNOTE_MALE}
<h2>Female, beds used per night</h2>
<div class="chart">{female_svg}</div>
{legend_html(BOOKED_FEMALE)}
<p class="capnote">Dashed line is the cap, {FEMALE_CAP}. Empty space up to the line is not listed on either site.</p>
<div id="night-detail" class="detail" role="status" aria-live="polite">Tap a bar for that night.</div>
<section><h2>Male</h2>{male_tables}</section>
<section><h2>Female</h2>{female_tables}</section>
</div>
<script type="application/json" id="chart-data">{chart_json}</script>
<script>
(function () {{
  var panel = document.getElementById("night-detail");
  var rows = JSON.parse(document.getElementById("chart-data").textContent);
  var svgs = document.querySelectorAll(".chart svg");
  function pack(side, i) {{
    var r = rows[i];
    var p = side ? r.f : r.m;
    return {{label: r.l, used: p[0], airbnb: p[1], booking: p[2], cap: p[3], trim: p[4] === 1, bm: side ? r.bf : r.bm, am: side ? r.af : r.am}};
  }}
  function show(i) {{
    if (!rows[i]) return;
    var male = pack(0, i), female = pack(1, i);
    panel.replaceChildren();
    var heading = document.createElement("strong");
    heading.textContent = male.label;
    function line(o, side) {{
      var occupiedLine = document.createElement("div");
      var openBeds = o.cap - o.used;
      occupiedLine.textContent = side + " occupied " + o.used + ", open " + openBeds;
      var channelLine = document.createElement("div");
      channelLine.textContent = side === "Male"
        ? "Boo on sale " + (typeof o.bm === "number" ? o.bm : "unknown") + " \\u00b7 Airbnb on sale " + (typeof o.am === "number" ? o.am : "not tracked yet")
        : "Airbnb open " + o.airbnb + ", Booking open " + o.booking + (o.trim ? " (trimmed to cap)" : "");
      return [occupiedLine, channelLine];
    }}
    var maleLines = line(male, "Male"), femaleLines = line(female, "Female");
    var srcName = {{C:"Cash", A:"Airbnb", P:"Booking pianist9", R:"Booking royceb", G:"Agoda"}};
    function people(groups) {{
      var lines = [];
      (groups || []).forEach(function (g) {{
        if (!g || !g[1] || !g[1].length) return;
        var src = srcName[g[0]] || g[0];
        g[1].forEach(function (name) {{
          if (!name) return;
          lines.push(name + " - " + src);
        }});
      }});
      return lines;
    }}
    var who = (rows[i].w || [[], []]);
    var malePeople = people(who[0]);
    var femalePeople = people(who[1]);
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "breakdown";
    btn.textContent = "Breakdown";
    var box = document.createElement("div");
    box.className = "who";
    box.hidden = true;
    function paintNames() {{
      box.replaceChildren();
      var both = malePeople.length && femalePeople.length;
      function group(title, lines) {{
        if (!lines.length) return;
        if (both) {{
          var h = document.createElement("div");
          h.className = "who-h";
          h.textContent = title;
          box.appendChild(h);
        }}
        lines.forEach(function (text) {{
          var row = document.createElement("div");
          row.textContent = text;
          box.appendChild(row);
        }});
      }}
      group("Male", malePeople);
      group("Female", femalePeople);
    }}
    function showNames() {{
      paintNames();
      box.hidden = false;
      btn.setAttribute("aria-pressed", "true");
    }}
    function hideNames() {{
      box.hidden = true;
      box.replaceChildren();
      btn.setAttribute("aria-pressed", "false");
    }}
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", function () {{
      if (box.hidden) showNames();
      else hideNames();
    }});
    panel.append(heading, maleLines[0], maleLines[1], femaleLines[0], femaleLines[1], btn, box);
    Array.prototype.forEach.call(svgs, function (svg) {{
      var hi = svg.querySelector("rect.hi");
      if (!hi) return;
      var left = +svg.getAttribute("data-left") || 0;
      var slot = +svg.getAttribute("data-slot") || 20;
      hi.setAttribute("x", String(left + i * slot));
      hi.setAttribute("visibility", "visible");
    }});
  }}
  function indexFromEvent(svg, ev) {{
    if (!svg.createSVGPoint || !svg.getScreenCTM()) return -1;
    var pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    var p = pt.matrixTransform(svg.getScreenCTM().inverse());
    var left = +svg.getAttribute("data-left") || 0;
    var slot = +svg.getAttribute("data-slot") || 20;
    var n = +svg.getAttribute("data-n") || rows.length;
    var i = Math.floor((p.x - left) / slot);
    if (i < 0 || i >= n) return -1;
    return i;
  }}
  Array.prototype.forEach.call(svgs, function (svg) {{
    var down = null;
    svg.addEventListener("pointerdown", function (ev) {{ down = {{x: ev.clientX, y: ev.clientY, id: ev.pointerId}}; }});
    svg.addEventListener("pointerup", function (ev) {{
      if (!down || down.id !== ev.pointerId) return;
      var dx = Math.abs(ev.clientX - down.x), dy = Math.abs(ev.clientY - down.y);
      down = null;
      if (dx > 10 || dy > 10) return;
      var i = indexFromEvent(svg, ev);
      if (i >= 0) show(i);
    }});
  }});
  function parisToday() {{
    try {{ return new Intl.DateTimeFormat("en-CA", {{timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit"}}).format(new Date()); }}
    catch (e) {{ return ""; }}
  }}
  var today = parisToday(), todayIndex = -1;
  rows.forEach(function (r, i) {{ if (r.d === today) todayIndex = i; }});
  function setText(id, value) {{ var el = document.getElementById(id); if (el) el.textContent = String(value); }}
  if (todayIndex >= 0) {{
    show(todayIndex);
    var m = pack(0, todayIndex), f = pack(1, todayIndex);
    setText("male-tonight", m.used);
    setText("male-open", m.cap - m.used);
    setText("female-tonight", f.used);
    setText("female-open", f.cap - f.used);
  }}
}})();
</script>
{ONSALE_JS}{MONTH_JS}</body></html>"""


def write(male, female, meta, days):
    labels = {"cash": "Cash", "airbnb": "Airbnb in now", "airbnb_soon": "Airbnb still to come", "pianist9": "Booking pianist9", "royceb": "Booking royceb", "agoda": "Agoda"}
    order = ["cash", "airbnb", "airbnb_soon", "pianist9", "royceb", "agoda"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gender", "name", "source", "in", "out", "note"])
        for gender, rows in (("Male", male), ("Female", female)):
            for r in rows:
                w.writerow([gender, r["guest"], labels.get(r["source"], r["source"]), r["check_in"], "no exit" if r["check_out"] == "open" else r["check_out"], r["note"]])
        w.writerow([])
        w.writerow(["night", "male", "male_open", "female", "female_open", "male_airbnb_open", "male_booking_open", "female_airbnb_open", "female_booking_open"])
        for d in days:
            w.writerow([
                d["date"].isoformat(), d["male"], d["open_male"], d["female"], d["open_female"],
                d["male_airbnb"], d["male_booking"], d["female_airbnb"], d["female_booking"],
            ])

    def table(rows):
        blocks = []
        for src in order:
            group = [r for r in rows if r["source"] == src]
            if not group:
                continue
            def by_check_in(r):
                co = "9999" if r["check_out"] == "open" else r["check_out"]
                if src == "cash":
                    return (co, r["guest"].lower())
                if r["check_in"] == "already here":
                    return (1, co, r["guest"].lower())
                return (0, r["check_in"], co, r["guest"].lower())
            group.sort(key=by_check_in)
            body = []
            accent = {"cash": "#d4d4d8", "airbnb": "#e6a23c", "airbnb_soon": "#f97316", "pianist9": "#3d9a5b", "royceb": "#3d9a5b", "agoda": "#38bdf8"}[src]
            for r in group:
                inn = "already here" if r["check_in"] == "already here" else fmt(r["check_in"])
                # Names and dates only. Bed counts stay on the night charts, never on a guest row.
                note = r["note"] or ""
                if "175" in note and ("€" in note or "euro" in note.lower()):
                    note = ""
                body.append(f"<tr><td>{escape(r['guest'])}</td><td>{escape(inn)}</td><td>{escape(fmt(r['check_out']))}</td><td>{escape(note)}</td></tr>")
            blocks.append(f'<h3 style="border-left-color:{accent}">{labels[src]}</h3><table><thead><tr><th>Who</th><th>In</th><th>Out</th><th></th></tr></thead><tbody>{"".join(body)}</tbody></table>')
        return "".join(blocks)

    if not days or "male_booked" not in days[0]:
        days = attach_open(days)
    points = [{
        "label": d["label"],
        "iso": d["date"].isoformat(),
        "male": d["male"],
        "open_male": d["open_male"],
        "female": d["female"],
        "open_female": d["open_female"],
        "male_booked": d["male_booked"],
        "male_airbnb": d["male_airbnb"],
        "male_booking": d["male_booking"],
        "male_trim": d["male_trim"],
        "female_booked": d["female_booked"],
        "female_airbnb": d["female_airbnb"],
        "female_booking": d["female_booking"],
        "female_trim": d["female_trim"],
        "mw": who_on(male, d["date"]),
        "fw": who_on(female, d["date"]),
    } for d in days]
    status = "Cash + Airbnb + 2 booking.com"
    if any(r["source"] == "agoda" for r in male + female):
        status += " + Agoda"
    html = render_page(meta["as_of"], status, points, table(male), table(female))
    # Charts are the normal page. Never substitute the open-bed placeholder.
    if "Open-bed bars in next refresh" in html or html.count("<svg") < 2 or html.count("<path") < 2:
        raise RuntimeError("refusing to write a page without male and female bar charts")
    if not html.startswith("<!DOCTYPE html>"):
        raise RuntimeError("page is not HTML")
    OUT_HTML.write_text(html)



def chart_start() -> date:
    """First column is the Paris night still in progress.

    Shanghai can already be the next calendar day while it is evening in Paris.
    As-of text still leads with Paris, then Shanghai. Occupancy is not hardcoded.
    """
    return datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Paris")).date()


def main():
    start = chart_start()
    end = start + timedelta(days=31)
    male, female, air_ok, p9_ok, rb_ok, p9_block, rb_block = rows_for(start, end)
    meta = {
        "as_of": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "airbnb": "fresh" if air_ok else "not fresh",
        "pianist9": "fresh" if p9_ok else "last known stays",
        "royceb": "fresh" if rb_ok else "last known stays",
    }
    days = attach_open(daily(male, female, start))
    write(male, female, meta, days)
    trimmed = []
    missing_airbnb = []
    missing_booking = []
    for d in days:
        iso = d["date"].isoformat()
        if not d["male_airbnb_known"]:
            missing_airbnb.append(iso)
        if not d["male_booking_known"]:
            missing_booking.append(iso)
        for side in ("male", "female"):
            if d.get(f"{side}_trim"):
                trimmed.append({
                    "date": iso,
                    "side": side,
                    "reason": d[f"{side}_trim"],
                    "occupied": d[side],
                    "airbnb_drawn": d[f"{side}_airbnb"],
                    "booking_drawn": d[f"{side}_booking"],
                })
    print(json.dumps({
        "male": len(male), "female": len(female),
        "tonight_male": tonight(male), "tonight_female": tonight(female),
        "start": start.isoformat(),
        "trimmed": trimmed,
        "male_airbnb_open_missing": missing_airbnb,
        "male_booking_open_missing": missing_booking,
        **meta,
    }, indent=2))

if __name__ == "__main__":
    main()


import re, json  # capfix helpers
# ---- capfix 2026-10-19: booked + on beds (not in bookings) + on sale, same rule as the page's count() ----
def _cap_toks(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


def _cap_lev1(a, b):
    if abs(len(a) - len(b)) > 1:
        return False
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1; continue
        d += 1
        if d > 1:
            return False
        if len(a) > len(b): i += 1
        elif len(b) > len(a): j += 1
        else: i += 1; j += 1
    return d + (len(a) - i) + (len(b) - j) <= 1


def _cap_same(a, b):
    x, y = _cap_toks(a), _cap_toks(b)
    if not x or not y:
        return False
    def hit(t, q):
        return any(u == t or (len(t) >= 4 and len(u) >= 4 and (u.startswith(t) or t.startswith(u)))
                   or (len(t) >= 5 and len(u) >= 5 and _cap_lev1(t, u)) for u in q)
    sub = lambda p, q: all(hit(t, q) for t in p)
    return sub(x, y) or sub(y, x)


def page_seed_beds(html):
    """Built-in bed map entries from the page SEED: [{"bed","side","s","n","ci","co","lb","x"}]."""
    i = html.index("var SEED = {"); j = html.index("function mergeSeed", i)
    out = []
    for key, body in re.findall(r'"([FM]-\d+)":\s*\{([^}]*)\}', html[i:j]):
        e = {"bed": key, "side": 1 if key.startswith("F-") else 0}
        for k, v in re.findall(r'(\w+):\s*("(?:[^"\\]|\\.)*"|\d+)', body):
            e[k] = json.loads(v) if v.startswith('"') else int(v)
        out.append(e)
    return out


def cap_totals(html, side=0, dates=None):
    """{night: {"booked","only":[names],"onsale","total"}} where total = booked + on beds not in bookings
    (display-only labels lb:1, out-of-service x:1 and free beds excluded) + Boo/Airbnb on sale.
    Use this (not m[0] + bm + am) for every booked + on-sale vs cap check."""
    rows = json.loads(re.search(r'id="chart-data">(.*?)</script>', html, re.S).group(1))
    beds = [b for b in page_seed_beds(html) if b["side"] == side and b.get("n") and not b.get("x") and not b.get("lb") and b.get("s") != "free"]
    res = {}
    for r in rows:
        d = r["d"]
        if dates and d not in dates:
            continue
        names = [n for g in (r["w"][side] or []) for n in (g[1] or []) if n]
        only = [b["n"] for b in beds if (not b.get("ci") or b["ci"] <= d) and (not b.get("co") or b["co"] > d)
                and not any(_cap_same(g, b["n"]) for g in names)]
        booked = (r["f"] if side else r["m"])[0]
        onsale = sum(max(0, r.get(k) or 0) for k in (("wbm", "wam") if side else ("bm", "am")))
        res[d] = {"booked": booked, "only": only, "onsale": onsale, "total": booked + len(only) + onsale}
    return res
