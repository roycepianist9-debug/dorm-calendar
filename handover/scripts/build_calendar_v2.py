#!/usr/bin/env python3
"""Combined bed calendar: cash on bed numbers; Airbnb/Booking as separate channel demand.
Clash only when two assignees share a bed number, or cash beds assigned > 23.
Female cap 8 (informational). Exclude Imane Nazih. No Agoda.
"""
from __future__ import annotations
import csv, json, hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from html import escape

ROOT = Path("/workspace/multi-ota")
OUT_CSV = Path("/workspace/multi-ota-calendar.csv")
OUT_HTML = Path("/workspace/multi-ota-calendar.html")
MALE_BEDS = [1,2,3,4,5,6,7,11,12,13,14,15,16,17,18,21,22,23,24,25,26,27,28]
MALE_CAP, FEMALE_CAP = 23, 8
WINDOW_END_EXCLUSIVE_OFFSET = 31  # today + 30 nights => 31 columns? "today through the next 30 nights" = 31 nights
# interpret as today inclusive + next 30 nights = 31 nights total
N_NIGHTS = 31
EXCLUDE_GUESTS = {"imane nazih"}

CASH = [
    # name, bed, start inclusive or None = already in, end exclusive (checkout morning) or None = no exit
    # Royce 2026-10-03: the dates are checkouts, guests are already here. Vincent and Kliton may extend.
    ("Abdel", 6, None, date(2026,10,30)),
    ("Vincent", 4, None, date(2026,10,6)),
    ("Kliton", 11, None, date(2026,10,4)),
    ("Bruno", 17, None, date(2026,10,30)),
    ("Kamel", 23, None, date(2026,10,17)),
    ("Mouloud", 27, None, date(2026,10,3)),  # checkout morning Oct 3, not in tonight
    ("Nabile's friend", 16, None, None),
    ("Amin", 13, None, date(2026,10,16)),
]

DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]


def today_shanghai() -> date:
    # box may show CEST; force Asia/Shanghai calendar date from UTC+8
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()


def dparse(s: str) -> date:
    return date.fromisoformat(s[:10])


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_booking_stays(path: Path, channel: str, side: str, hotel_id: str):
    data = load_json(path)
    if not data:
        return [], False, "missing"
    stays = []
    for s in data.get("stays") or []:
        guest = (s.get("guest") or "").strip()
        if guest.lower() in EXCLUDE_GUESTS:
            continue
        status = (s.get("status") or "ok").lower()
        if status in {"cancelled", "canceled", "no-show", "noshow"}:
            continue
        stays.append({
            "channel": channel, "guest": guest, "side": side, "hotel_id": hotel_id,
            "check_in": s["check_in"][:10], "check_out": s["check_out"][:10],
            "beds": int(s.get("beds") or 1), "bed": s.get("bed"),
        })
    # Treat access-denied / empty scrape as not ok even if a session cookie exists
    blocker = data.get("blocker") or data.get("url") or ""
    ok = bool(data.get("login_ok")) and not any(x in blocker.lower() for x in ("denied", "protected", "locked", "timeout"))
    if ok and not stays and blocker:
        ok = False
    return stays, ok, blocker


def load_airbnb(path: Path):
    data = load_json(path)
    if not data:
        return {}, False, "missing", []
    ok = bool(data.get("login_ok"))
    nights = {}
    for n in data.get("nights") or []:
        nights[n["date"][:10]] = {
            "male": int(n.get("male") or 0),
            "female": int(n.get("female") or 0),
            "known": True,
        }
    return nights, ok, data.get("blocker") or "", data.get("reservations") or []


def fallback_named():
    data = load_json(ROOT / "fallback-named-stays.json") or []
    out = []
    for s in data:
        if (s.get("guest") or "").lower() in EXCLUDE_GUESTS:
            continue
        out.append(s)
    return out


def cash_rows(dates: list[date]):
    rows = []
    for name, bed, start, end in CASH:
        values = {}
        for d in dates:
            if start is None:
                on = True
            else:
                on = d >= start
            if end is not None and d >= end:
                on = False
            if on:
                values[d] = 1
        label_start = start.isoformat() if start else dates[0].isoformat()
        rows.append({
            "line": f"{name} · bed {bed}",
            "source": "cash",
            "side": "male",
            "bed": bed,
            "guest": name,
            "values": values,
            "check_in": label_start,
            "check_out": end.isoformat() if end else "open",
            "beds": 1,
        })
    return rows


def stay_values(stays, dates, side):
    rows = []
    for s in stays:
        if s["side"] != side:
            continue
        ci, co = dparse(s["check_in"]), dparse(s["check_out"])
        values = {d: s["beds"] for d in dates if ci <= d < co}
        if not values:
            continue
        bed = s.get("bed")
        line = s["guest"] + (f" · bed {bed}" if bed else "")
        rows.append({
            "line": line, "source": s["channel"], "side": side, "bed": bed,
            "guest": s["guest"], "values": values,
            "check_in": s["check_in"], "check_out": s["check_out"], "beds": s["beds"],
        })
    return rows


def airbnb_row(nights, dates, side):
    key = "male" if side == "male" else "female"
    values = {}
    known = False
    for d in dates:
        n = nights.get(d.isoformat())
        if n and n.get("known"):
            values[d] = n[key]
            known = True
    return {
        "line": f"Airbnb {side} (count)",
        "source": "airbnb",
        "side": side,
        "bed": None,
        "guest": f"Airbnb {side}",
        "values": values,
        "check_in": "",
        "check_out": "",
        "beds": 0,
        "known": known,
    }


def find_clashes(cash_lines, dates):
    """Flag nights where two cash assignees share a bed, or cash count > 23."""
    clashes = []
    for d in dates:
        by_bed = {}
        for r in cash_lines:
            if d not in r["values"]:
                continue
            b = r["bed"]
            by_bed.setdefault(b, []).append(r["guest"])
        for b, people in by_bed.items():
            if len(people) > 1:
                clashes.append({"date": d.isoformat(), "kind": "same_bed", "bed": b, "people": people})
        if len(by_bed) > MALE_CAP:
            clashes.append({"date": d.isoformat(), "kind": "cash_over_cap", "count": len(by_bed), "cap": MALE_CAP})
    return clashes


def occupancy_signature(male_rows, female_rows, clashes, dates):
    """Stable signature of channel occupancy + clashes (not cosmetic layout)."""
    lines = []
    for side, rows in (("male", male_rows), ("female", female_rows)):
        for r in rows:
            # normalize label: cash use guest; airbnb use side count; booking use guest
            if r["source"] == "cash":
                label = r.get("guest") or r["line"]
            elif r["source"] == "airbnb":
                label = f"Airbnb {side}"
            else:
                label = r.get("guest") or r["line"]
            for d in dates:
                v = r["values"].get(d)
                if v:
                    lines.append(f"{d.isoformat()}|{side}|{r['source']}|{label}|{v}")
    for c in clashes:
        lines.append(f"clash|{c['date']}|{c['kind']}|{c.get('bed','')}|{','.join(c.get('people',[]))}|{c.get('count','')}")
    return "\n".join(sorted(lines))


def write_csv(dates, male_rows, female_rows):
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gender", "line", "source", "bed"] + [f"{d.isoformat()} {DOW[d.weekday()]}" for d in dates])
        for gender, rows, cap in (("Male", male_rows, MALE_CAP), ("Female", female_rows, FEMALE_CAP)):
            for r in rows:
                w.writerow([gender, r["line"], r["source"], r.get("bed") or ""] + [r["values"].get(d, "") for d in dates])
            # channel demand totals (NOT summing airbnb onto cash for flag purposes — shown as demand)
            demand = {d: sum(int(r["values"].get(d) or 0) for r in rows) for d in dates}
            w.writerow([gender, "Channel demand sum (not physical merge)", "demand"] + [""] + [demand[d] for d in dates])
            cash_only = {d: sum(1 for r in rows if r["source"]=="cash" and d in r["values"]) for d in dates}
            if gender == "Male":
                w.writerow([gender, f"Cash beds occupied / {cap}", "cash_cap"] + [""] + [f"{cash_only[d]}/{cap}" for d in dates])
            else:
                named = {d: sum(int(r["values"].get(d) or 0) for r in rows if r["source"]!="airbnb") for d in dates}
                ab = {d: int((next((r for r in rows if r["source"]=="airbnb"), {}) or {}).get("values", {}).get(d) or 0) for d in dates}
                # show named + airbnb separately note; informational at-cap vs 8 using named+airbnb only as demand view
                w.writerow([gender, f"Named Booking beds / {cap}", "named_cap"] + [""] + [f"{named[d]}/{cap}" for d in dates])
                w.writerow([gender, f"Airbnb female count / {cap}", "airbnb_cap"] + [""] + [f"{ab[d]}/{cap}" for d in dates])


def write_html(dates, male_rows, female_rows, clashes, meta):
    def section(title, rows, cap, side):
        head = "".join(f'<th scope="col"><span>{d.day} {DOW[d.weekday()]}</span></th>' for d in dates)
        body = []
        for r in rows:
            cells = "".join(
                f'<td class="{"on" if d in r["values"] else ""}">{r["values"].get(d,"")}</td>' for d in dates
            )
            bed = f' · bed {r["bed"]}' if r.get("bed") else ""
            body.append(f'<tr class="src-{escape(r["source"])}"><th scope="row">{escape(r["line"])}<span class="src">{escape(r["source"])}{escape(bed)}</span></th>{cells}</tr>')
        clash_note = ""
        side_clashes = [c for c in clashes if side == "male" or c.get("kind") == "same_bed"]
        if side == "male" and clashes:
            clash_note = f'<p class="warn">{len(clashes)} bed-clash flag(s) in window.</p>'
        elif side == "male":
            clash_note = '<p class="ok">No cash bed-number clash and cash count ≤ 23.</p>'
        return f'''<section><h2>{escape(title)} · physical cap {cap}</h2>{clash_note}
<div class="scroll"><table><thead><tr><th>Line</th>{head}</tr></thead><tbody>
{''.join(body)}
</tbody></table></div></section>'''

    clash_html = ""
    if clashes:
        items = "".join(
            f"<li>{escape(c['date'])}: " + (
                f"bed {c['bed']} held by {escape(', '.join(c['people']))}" if c['kind']=='same_bed'
                else f"cash beds {c['count']} > {c['cap']}"
            ) + "</li>" for c in clashes
        )
        clash_html = f'<aside class="callout"><h2>Bed clashes</h2><ul>{items}</ul></aside>'

    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Combined bed calendar</title>
<style>
body{{margin:0;font:15px/1.45 system-ui,sans-serif;background:#fafaf9;color:#1c1917}}
.wrap{{padding:28px 20px 64px}} h1{{font-size:1.5rem;margin:0 0 6px}}
.meta{{color:#57534e;margin:0 0 8px}} .ok{{color:#166534}} .warn{{color:#b91c1c}}
.callout{{border-left:4px solid #b91c1c;background:#fff;padding:10px 14px;margin:16px 0}}
.scroll{{overflow-x:auto;background:#fff;border:1px solid #e7e5e4;border-radius:8px}}
table{{border-collapse:collapse;font-variant-numeric:tabular-nums}}
th,td{{border-bottom:1px solid #e7e5e4;padding:4px 6px;text-align:center;font-size:12px}}
th[scope=row]{{text-align:left;position:sticky;left:0;background:#fff;min-width:200px}}
td.on{{background:#ecfdf5;font-weight:650}}
.src{{display:block;color:#78716c;font-size:11px;font-weight:500}}
tr.src-cash td.on{{background:#fef3c7}} tr.src-pianist9 td.on{{background:#dbeafe}}
tr.src-royceb td.on{{background:#ccfbf1}} tr.src-airbnb td.on{{background:#fee2e2}}
section{{margin-top:28px}}
</style></head><body><div class="wrap">
<p class="kicker" style="text-transform:uppercase;letter-spacing:.08em;color:#78716c;font-size:.75rem;margin:0">Combined bed calendar</p>
<h1>{dates[0].isoformat()} → {dates[-1].isoformat()}</h1>
<p class="meta"><strong>As of {meta["as_of"]} Asia/Shanghai.</strong> Cash shown on bed numbers. Airbnb and Booking are separate channel demand (not merged onto cash beds). Flag only same-bed clash or cash beds &gt; 23. Female cap {FEMALE_CAP}. Imane Nazih excluded. Agoda excluded.</p>
<p class="meta">Scrapes: Airbnb {meta["airbnb"]}; pianist9 {meta["pianist9"]}; royceb {meta["royceb"]}.</p>
{clash_html}
{section("Male", male_rows, MALE_CAP, "male")}
{section("Female", female_rows, FEMALE_CAP, "female")}
<footer class="meta" style="margin-top:24px"><ul>
<li>Male physical beds: 1–7, 11–18, 21–28 (23).</li>
<li>Open cash stays run through end of window.</li>
<li>Read-only refresh; send only when occupancy or clash signature changes.</li>
</ul></footer>
</div></body></html>'''
    OUT_HTML.write_text(html)


def main():
    today = today_shanghai()
    dates = [today + timedelta(days=i) for i in range(N_NIGHTS)]

    p9, p9_ok, p9_block = load_booking_stays(ROOT / "pianist9-raw.json", "pianist9", "male", "16844588")
    rb, rb_ok, rb_block = load_booking_stays(ROOT / "royceb-raw.json", "royceb", "female", "16840329")
    ab, ab_ok, ab_block, _ab_res = load_airbnb(ROOT / "airbnb-raw.json")

    fallback = fallback_named()
    if not p9_ok:
        if not p9:
            p9 = [s for s in fallback if s.get("channel") == "pianist9"]
        for s in p9:
            s.setdefault("side", "male"); s.setdefault("hotel_id", "16844588"); s.setdefault("bed", None)
    if not rb_ok:
        if not rb:
            rb = [s for s in fallback if s.get("channel") == "royceb"]
        for s in rb:
            s.setdefault("side", "female"); s.setdefault("hotel_id", "16840329"); s.setdefault("bed", None)
    # always drop Imane
    rb = [s for s in rb if s["guest"].lower() not in EXCLUDE_GUESTS]

    # if airbnb failed, keep previous nights from last airbnb-raw if present with known; else empty
    if not ab_ok:
        prev = load_json(ROOT / "airbnb-raw.json")
        # already failed; try snapshot from last build via CSV airbnb lines? leave empty known
        ab = {}

    cash = cash_rows(dates)
    male_named = stay_values(p9, dates, "male")
    female_named = stay_values(rb, dates, "female")
    male_ab = airbnb_row(ab if ab_ok else {}, dates, "male")
    female_ab = airbnb_row(ab if ab_ok else {}, dates, "female")

    male_rows = cash + male_named + ([male_ab] if male_ab["values"] else [])
    female_rows = female_named + ([female_ab] if female_ab["values"] else [])

    clashes = find_clashes(cash, dates)
    write_csv(dates, male_rows, female_rows)
    meta = {
        "as_of": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "airbnb": "ok" if ab_ok else f"FAIL:{ab_block}",
        "pianist9": "ok" if p9_ok else f"FAIL_using_fallback:{p9_block[:80]}",
        "royceb": "ok" if rb_ok else f"FAIL_using_fallback:{rb_block[:80]}",
    }
    write_html(dates, male_rows, female_rows, clashes, meta)

    sig = occupancy_signature(male_rows, female_rows, clashes, dates)
    (ROOT / "occupancy-signature.txt").write_text(sig)
    prev_path = ROOT / "last-occupancy-signature.txt"
    prev = prev_path.read_text() if prev_path.exists() else ""
    # If previous signature looks like old combined-cap format, use baseline-published-sig
    if prev and prev.lstrip().startswith("2026-") and "|male|" in prev.split("\n",1)[0] and "cash" not in prev and "airbnb" not in prev.split("\n",1)[0]:
        # old format like date|side|combined|status
        base = ROOT / "baseline-published-sig.txt"
        if base.exists():
            # rebuild baseline with normalized labels
            prev = base.read_text()
    # Normalize prev lines for cash "Name · open" -> Name
    def norm_sig(s: str) -> str:
        out=[]
        for line in s.splitlines():
            parts=line.split("|")
            if len(parts)==5 and parts[2]=="cash":
                label=parts[3]
                label=label.replace(" · open","").split(" · bed")[0].strip()
                parts[3]=label
                out.append("|".join(parts))
            elif len(parts)==5 and parts[2]=="airbnb":
                side=parts[1]
                parts[3]=f"Airbnb {side}"
                out.append("|".join(parts))
            else:
                out.append(line)
        return "\n".join(sorted(out))
    changed = norm_sig(sig) != norm_sig(prev) if prev else True

    result = {
        "changed": changed,
        "clashes": clashes,
        "scrape": {"pianist9": p9_ok, "royceb": rb_ok, "airbnb": ab_ok},
        "blockers": {"pianist9": p9_block, "royceb": rb_block, "airbnb": ab_block},
        "window": [dates[0].isoformat(), dates[-1].isoformat()],
        "cash_beds": sorted({r["bed"] for r in cash}),
        "male_rows": len(male_rows),
        "female_rows": len(female_rows),
        "csv": str(OUT_CSV),
        "html": str(OUT_HTML),
        "sig_sha": hashlib.sha256(sig.encode()).hexdigest()[:16],
        "prev_sig_sha": hashlib.sha256(prev.encode()).hexdigest()[:16] if prev else None,
    }
    (ROOT / "compare-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
    # Royce: publish names and dates only, no bed numbers.
    import runpy
    runpy.run_path(str(ROOT / "who_list.py"), run_name="__main__")
