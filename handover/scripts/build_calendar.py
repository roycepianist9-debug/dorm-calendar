#!/usr/bin/env python3
from __future__ import annotations
import json, csv, html
from datetime import date, timedelta
from pathlib import Path

ROOT = Path("/workspace/multi-ota")
OUT_CSV = Path("/workspace/multi-ota-calendar.csv")
OUT_HTML = Path("/workspace/multi-ota-calendar.html")
SNAP = ROOT / "last-sent-snapshot.csv"
MALE_CAP, FEMALE_CAP = 23, 7
TODAY = date(2026, 10, 3)
N_NIGHTS = 30  # today through next 30 nights

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def dparse(s: str) -> date:
    return date.fromisoformat(s[:10])

def nights_between(ci: date, co: date):
    d = ci
    while d < co:
        yield d
        d += timedelta(days=1)

def load_stays(path: Path, channel: str, side: str, hotel_id: str):
    if not path.exists():
        return [], False, "missing"
    data = json.loads(path.read_text())
    ok = bool(data.get("login_ok"))
    stays = []
    for s in data.get("stays") or []:
        if (s.get("status") or "ok").lower() in {"cancelled", "canceled", "no-show", "noshow"}:
            continue
        stays.append({
            "channel": channel, "guest": s["guest"], "side": side, "hotel_id": hotel_id,
            "check_in": s["check_in"][:10], "check_out": s["check_out"][:10],
            "beds": int(s.get("beds") or 1),
        })
    return stays, ok, data.get("blocker") or data.get("url") or ""

def load_airbnb(path: Path):
    if not path.exists():
        return {}, False, "missing"
    data = json.loads(path.read_text())
    ok = bool(data.get("login_ok"))
    nights = {}
    for n in data.get("nights") or []:
        nights[n["date"][:10]] = {"male": int(n.get("male") or 0), "female": int(n.get("female") or 0), "known": True}
    return nights, ok, data.get("blocker") or ""

def load_prev_csv(path: Path):
    stays, ab = [], {}
    if not path.exists():
        return stays, ab
    with path.open() as f:
        for row in csv.reader(f):
            if not row:
                continue
            if row[0] == "stay":
                stays.append({"channel": row[1], "guest": row[2], "side": row[3], "hotel_id": row[4],
                              "check_in": row[5], "check_out": row[6], "beds": int(row[7])})
            elif row[0] == "airbnb_night":
                ab[row[1]] = {"male": int(row[2] or 0), "female": int(row[3] or 0), "known": True}
    return stays, ab

def occupancy_signature(derived):
    return "\n".join(f"{r['date']}|{r['side']}|{r['combined']}|{r['status']}" for r in derived)

def fmt_range(ci: str, co: str) -> str:
    a, b = dparse(ci), dparse(co)
    return f"{a.day} {MON[a.month]} – {b.day} {MON[b.month]}"

def build_html(dates, stays, airbnb, derived, overs, meta_notes):
    by_side = {"male": [s for s in stays if s["side"] == "male"],
               "female": [s for s in stays if s["side"] == "female"]}
    derived_map = {(r["date"], r["side"]): r for r in derived}

    def night_class(d: date, side: str) -> str:
        r = derived_map[(d.isoformat(), side)]
        cls = ["night"]
        if d.weekday() >= 5:
            cls.append("weekend")
        if d.day == 1:
            cls.append("month-start")
        if r["status"] == "over":
            cls.append("over")
        elif r["status"] == "at_cap":
            cls.append("at")
        return " ".join(cls)

    def cell_class(d: date, side: str, extra="") -> str:
        r = derived_map[(d.isoformat(), side)]
        cls = ["cell"]
        if d.weekday() >= 5:
            cls.append("weekend")
        if r["status"] == "over":
            cls.append("over")
        elif r["status"] == "at_cap":
            cls.append("at")
        if extra:
            cls.append(extra)
        return " ".join(cls)

    def month_groups(dates):
        groups = []
        cur = None
        for d in dates:
            key = (d.year, d.month)
            if not groups or groups[-1][0] != key:
                groups.append([key, 1])
            else:
                groups[-1][1] += 1
        return groups

    def section(side: str, cap: int):
        title = "Male" if side == "male" else "Female"
        overs_side = [o for o in overs if o["side"] == side]
        under_note = ""
        known = [derived_map[(d.isoformat(), side)] for d in dates if derived_map[(d.isoformat(), side)]["airbnb_known"] == "yes"]
        if overs_side:
            under_note = f"{len(overs_side)} night(s) over cap on the numbers we have."
        elif known:
            mx = max(r["combined"] for r in known)
            under_note = f"No night in this window is over cap on the numbers we have. Highest combined on nights with an Airbnb count: {mx} of {cap}."
        else:
            under_note = "Airbnb counts missing for this window; named Booking stays only."

        mg = month_groups(dates)
        month_row = "".join(
            f'<th class="month" colspan="{n}" scope="colgroup">{MON[m]} {y}</th>'
            for (y, m), n in mg
        )
        head_nights = []
        for d in dates:
            head_nights.append(
                f'<th class="{night_class(d, side)}" scope="col" title="{DOW[d.weekday()]} {d.isoformat()} · night of this date" id="{side}-{d.isoformat()}">'
                f'<span class="num">{d.day}</span><span class="dow">{DOW[d.weekday()]}</span>'
                + (f'<span class="tag">OVER</span>' if derived_map[(d.isoformat(), side)]["status"] == "over" else "")
                + "</th>"
            )

        # Airbnb row
        ab_cells = []
        for d in dates:
            r = derived_map[(d.isoformat(), side)]
            if r["airbnb_known"] == "yes":
                ab_cells.append(f'<td class="{cell_class(d, side)}">{r["airbnb_beds"]}</td>')
            else:
                ab_cells.append(f'<td class="{cell_class(d, side, "na")}">·</td>')

        # stay rows
        stay_rows = []
        for s in sorted(by_side[side], key=lambda x: (x["check_in"], x["guest"])):
            ch_cls = "p9" if s["channel"] == "pianist9" else ("royceb" if s["channel"] == "royceb" else "ab")
            ch_label = s["channel"]
            when = f'{fmt_range(s["check_in"], s["check_out"])} · {s["beds"]} bed{"s" if s["beds"]!=1 else ""} · checks out {dparse(s["check_out"]).day} {MON[dparse(s["check_out"]).month]}'
            cells = []
            ci, co = dparse(s["check_in"]), dparse(s["check_out"])
            occupied = [d for d in dates if ci <= d < co]
            for d in dates:
                if not (ci <= d < co):
                    cells.append(f'<td class="{cell_class(d, side)}"></td>')
                    continue
                extras = ["bar"]
                if d == occupied[0]:
                    extras.append("start")
                if d == occupied[-1]:
                    extras.append("end")
                if d not in (occupied[0], occupied[-1]):
                    extras.append("mid")
                if derived_map[(d.isoformat(), side)]["status"] == "over":
                    extras.append("over")
                pip = s["beds"] if s["beds"] > 1 else ""
                title = html.escape(f'{s["guest"]} · {s["beds"]} bed · night of {d.isoformat()} · {s["channel"]}')
                cells.append(
                    f'<td class="{cell_class(d, side, " ".join(extras))}" title="{title}"><span class="pip">{pip}</span></td>'
                )
            stay_rows.append(
                f'<tr class="stay ch-{ch_cls}">'
                f'<th class="namecol" scope="row"><span class="guest"><span class="ch {ch_cls}">{html.escape(ch_label)}</span>{html.escape(s["guest"])}</span>'
                f'<span class="when">{html.escape(when)}</span></th>'
                + "".join(cells) + "</tr>"
            )

        # summary combined
        sum_cells = []
        for d in dates:
            r = derived_map[(d.isoformat(), side)]
            if r["airbnb_known"] == "yes":
                txt = str(r["combined"])
            else:
                txt = f'{r["named_beds"]}+?'
            sum_cells.append(f'<td class="{cell_class(d, side)}">{txt}</td>')

        return f'''
  <section id="{side}">
<h2>{title} · cap {cap} beds</h2>
<p class="subh">{html.escape(under_note)}</p>
<p class="hint">Scroll sideways. Each column is one night. The name stays put.</p>
<div class="scroll"><table>
<thead>
<tr>
<th class="namecol" scope="col">Night of</th>
{month_row}
</tr>
<tr>
<th class="namecol"></th>
{"".join(head_nights)}
</tr>
</thead>
<tbody>
<tr class="airbnb">
<th class="namecol" scope="row"><span class="guest"><span class="ch ab">Airbnb</span>occupied beds</span><span class="when">counts only · same physical beds</span></th>
{"".join(ab_cells)}
</tr>
{"".join(stay_rows)}
<tr class="summary">
<th class="namecol" scope="row"><span class="guest">Combined</span><span class="when">Booking named + Airbnb counts · cap {cap}</span></th>
{"".join(sum_cells)}
</tr>
</tbody>
</table></div>
</section>'''

    callouts = []
    for o in overs:
        d = dparse(o["date"])
        r = derived_map[(o["date"], o["side"])]
        named = r["named_beds"]
        ab = r["airbnb_beds"]
        who = [s for s in stays if s["side"] == o["side"] and dparse(s["check_in"]) <= d < dparse(s["check_out"])]
        who_txt = ", ".join(f'{s["guest"]} ({s["channel"]}, {s["beds"]} bed)' for s in who) or "no named Booking stays"
        callouts.append(f'''
<aside class="callout" aria-label="Overbooked night">
  <h2>{MON[d.month]} {d.day} · {o["side"]} · over cap</h2>
  <p class="math"><strong>Airbnb {ab} + Booking named {named} = {o["combined"]}</strong> occupied, cap is {o["cap"]}. {o["combined"] - o["cap"]} bed(s) over.</p>
  <p>Booking that night: {html.escape(who_txt)}.</p>
</aside>''')

    start, end = dates[0], dates[-1]
    title_range = f"{start.day} {MON[start.month]} – {end.day} {MON[end.month]} {end.year}"
    notes_ul = "".join(f"<li>{html.escape(n)}</li>" for n in meta_notes)

    css = Path("/workspace/multi-ota-calendar.html").read_text().split("</style>")[0].split("<style>")[-1] if Path("/workspace/multi-ota-calendar.html").exists() else ""
    if not css.strip():
        css = """
:root { --ink:#1c1917; --muted:#57534e; --faint:#a8a29e; --line:#e7e5e4; --paper:#fafaf9; --card:#fff;
  --airbnb:#c2412d; --airbnb-ink:#9a3412; --p9:#1e3a5f; --rb:#0f766e; --over:#b91c1c; --over-bg:#fde8e8; --at:#92400e; --at-bg:#fef3c7; --weekend:#f5f5f4; }
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.45 "Segoe UI", system-ui, sans-serif; }
.wrap { padding:32px 24px 64px; } .lede { max-width:44rem; }
h1 { font-size:1.7rem; font-weight:650; letter-spacing:-0.02em; margin:0 0 6px; }
.kicker { margin:0 0 4px; color:var(--muted); font-size:0.78rem; letter-spacing:0.08em; text-transform:uppercase; }
.meta { margin:0 0 8px; color:var(--muted); } .meta strong { color:var(--ink); font-weight:650; }
.legend { list-style:none; padding:0; margin:14px 0 0; display:flex; flex-wrap:wrap; gap:8px 16px; }
.legend li { display:flex; align-items:center; gap:6px; font-size:0.86rem; color:var(--muted); }
.sw { width:14px; height:14px; border-radius:3px; display:inline-block; }
.sw.airbnb { background:var(--airbnb); } .sw.p9 { background:var(--p9); } .sw.rb { background:var(--rb); }
.sw.over { background:var(--over-bg); box-shadow:inset 0 0 0 2px var(--over); }
.sw.at { background:var(--at-bg); box-shadow:inset 0 0 0 2px var(--at); }
.callout { max-width:44rem; margin:22px 0 8px; padding:12px 16px; background:var(--card); border-left:4px solid var(--over); }
.callout h2 { font-size:1rem; margin:0 0 6px; color:var(--over); font-weight:650; }
.callout p { margin:0 0 6px; } .callout p:last-child { margin:0; }
.callout .math { font-variant-numeric:tabular-nums; }
section { margin-top:28px; } section h2 { font-size:1.15rem; margin:0 0 4px; font-weight:650; }
section .subh { margin:0 0 10px; color:var(--muted); font-size:0.9rem; }
.hint { margin:0 0 8px; color:var(--faint); font-size:0.8rem; }
.scroll { overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:8px; }
table { border-collapse:separate; border-spacing:0; }
th, td { font-weight:500; font-size:12px; text-align:center; vertical-align:middle; border-bottom:1px solid var(--line); border-right:1px solid #f5f5f4; padding:0; }
.namecol { position:sticky; left:0; z-index:3; text-align:left; background:var(--card); min-width:248px; max-width:280px; padding:6px 10px; border-right:1px solid var(--line); box-shadow:1px 0 0 var(--line); }
thead .namecol { z-index:5; background:#f5f5f4; }
.month { background:#f5f5f4; color:var(--muted); font-size:11px; letter-spacing:0.06em; text-transform:uppercase; padding:6px 0 4px; border-bottom:1px solid var(--line); }
.night { width:36px; min-width:36px; background:var(--card); padding:4px 0 5px; font-variant-numeric:tabular-nums; }
.night .num { display:block; font-weight:650; font-size:13px; }
.night .dow { display:block; color:var(--faint); font-size:10px; font-weight:500; }
.night.weekend { background:var(--weekend); } .night.month-start { box-shadow:inset 2px 0 0 #d6d3d1; }
.night.over { background:var(--over-bg); } .night.over .num, .night.over .dow { color:var(--over); }
.night.at { background:var(--at-bg); } .night.at .num { color:var(--at); }
.tag { display:block; font-size:8px; font-weight:750; letter-spacing:0.04em; text-transform:uppercase; color:var(--over); margin-top:1px; }
td.cell { height:30px; background:var(--card); font-variant-numeric:tabular-nums; }
td.cell.weekend { background:var(--weekend); } td.cell.over { background:var(--over-bg); } td.cell.at { background:var(--at-bg); } td.cell.na { color:var(--faint); }
tr.summary td.cell, tr.summary th.namecol { font-weight:650; }
tr.summary td.over { color:var(--over); background:var(--over-bg); } tr.summary td.at { color:var(--at); background:var(--at-bg); }
tr.airbnb td.cell { color:var(--airbnb-ink); font-weight:650; }
tr.stay td.cell.bar { padding:4px 1px; }
tr.stay td.cell.bar .pip { display:block; height:18px; background:var(--p9); color:white; font-size:10px; line-height:18px; font-weight:650; }
tr.stay td.cell.bar.start .pip { border-radius:9px 0 0 9px; margin-left:3px; }
tr.stay td.cell.bar.end .pip { border-radius:0 9px 9px 0; margin-right:3px; }
tr.stay td.cell.bar.start.end .pip { border-radius:9px; margin-left:3px; margin-right:3px; }
tr.stay td.cell.bar.mid .pip { border-radius:0; }
tr.stay.ch-royceb td.cell.bar .pip { background:var(--rb); }
tr.stay td.cell.bar.over .pip { box-shadow:inset 0 -3px 0 var(--over); }
.guest { display:block; font-weight:650; font-size:13px; }
.guest .ch { font-weight:650; font-size:10px; letter-spacing:0.04em; text-transform:uppercase; margin-right:6px; }
.ch.p9 { color:var(--p9); } .ch.rb, .ch.royceb { color:var(--rb); } .ch.ab { color:var(--airbnb); }
.when { display:block; color:var(--muted); font-size:11px; font-weight:450; }
footer.notes { max-width:44rem; margin-top:28px; color:var(--muted); font-size:0.86rem; }
footer.notes h2 { font-size:0.95rem; color:var(--ink); margin:0 0 6px; }
footer.notes ul { margin:0; padding-left:1.1rem; } footer.notes li { margin:0 0 4px; }
"""

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Combined bed calendar · {title_range}</title>
<style>
{css}
</style>
</head>
<body>
<div class="wrap">
  <header class="lede">
    <p class="kicker">Combined bed calendar</p>
    <h1>{title_range}</h1>
    <p class="meta"><strong>Data as of {TODAY.isoformat()}.</strong> Same physical beds across channels. A night is overbooked when combined occupied beds exceed the cap (male {MALE_CAP}, female {FEMALE_CAP}).</p>
    <p class="meta">Airbnb shown as nightly occupied counts. Booking stays labeled by guest and channel (pianist9 / royceb).</p>
    <p class="meta">A bar is the nights stayed: check-in date through the morning of check-out. The check-out date itself is not a night.</p>
    <ul class="legend">
      <li><span class="sw airbnb"></span> Airbnb (counts)</li>
      <li><span class="sw p9"></span> pianist9 · Booking male · hotel 16844588</li>
      <li><span class="sw rb"></span> royceb · Booking female · hotel 16840329</li>
      <li><span class="sw over"></span> Over cap</li>
      <li><span class="sw at"></span> Exactly at cap</li>
    </ul>
  </header>
  {"".join(callouts)}
  {section("male", MALE_CAP)}
  {section("female", FEMALE_CAP)}
  <footer class="notes">
    <h2>Notes</h2>
    <ul>{notes_ul}</ul>
  </footer>
</div>
</body>
</html>
'''

def main():
    dates = [TODAY + timedelta(days=i) for i in range(N_NIGHTS)]
    p9, p9_ok, p9_block = load_stays(ROOT / "pianist9-raw.json", "pianist9", "male", "16844588")
    rb, rb_ok, rb_block = load_stays(ROOT / "royceb-raw.json", "royceb", "female", "16840329")
    ab, ab_ok, ab_block = load_airbnb(ROOT / "airbnb-raw.json")
    prev_stays, prev_ab = load_prev_csv(OUT_CSV if OUT_CSV.exists() else SNAP)

    stays = []
    if p9_ok:
        stays += p9
    else:
        stays += [s for s in prev_stays if s["channel"] == "pianist9"]
    if rb_ok:
        stays += rb
    else:
        stays += [s for s in prev_stays if s["channel"] == "royceb"]
    airbnb = ab if ab_ok else prev_ab

    male_named = {d.isoformat(): 0 for d in dates}
    female_named = {d.isoformat(): 0 for d in dates}
    for s in stays:
        bucket = male_named if s["side"] == "male" else female_named
        for n in nights_between(dparse(s["check_in"]), dparse(s["check_out"])):
            key = n.isoformat()
            if key in bucket:
                bucket[key] += s["beds"]

    derived = []
    overs = []
    for d in dates:
        key = d.isoformat()
        for side, cap, named in (("male", MALE_CAP, male_named), ("female", FEMALE_CAP, female_named)):
            abn = airbnb.get(key)
            if abn and abn.get("known"):
                ab_beds = abn["male" if side == "male" else "female"]
                combined = named[key] + ab_beds
                if combined > cap:
                    status = "over"
                    overs.append({"date": key, "side": side, "combined": combined, "cap": cap})
                elif combined == cap:
                    status = "at_cap"
                else:
                    status = "under"
                derived.append({"date": key, "side": side, "cap": cap, "named_beds": named[key],
                                "airbnb_beds": ab_beds, "airbnb_known": "yes", "combined": combined, "status": status})
            else:
                derived.append({"date": key, "side": side, "cap": cap, "named_beds": named[key],
                                "airbnb_beds": "", "airbnb_known": "no", "combined": named[key], "status": "airbnb_unknown"})

    lines = [
        ["type", "key", "value"],
        ["meta", "as_of", TODAY.isoformat()],
        ["meta", "window", f"{dates[0].isoformat()} to {dates[-1].isoformat()} inclusive columns; each column is the night of that date"],
        ["meta", "night_rule", "check-in inclusive, check-out exclusive (check-out morning is not a night)"],
        ["meta", "male_cap", str(MALE_CAP)],
        ["meta", "female_cap", str(FEMALE_CAP)],
        ["meta", "male_channel", "pianist9 Booking hotel 16844588"],
        ["meta", "female_channel", "royceb Booking hotel 16840329"],
        ["meta", "airbnb", "nightly occupied counts; guest names optional"],
        ["meta", "inventory", "same physical beds across channels; overbooked if combined occupied > cap"],
        ["meta", "scrape_pianist9", "ok" if p9_ok else f"fail:{p9_block}"],
        ["meta", "scrape_royceb", "ok" if rb_ok else f"fail:{rb_block}"],
        ["meta", "scrape_airbnb", "ok" if ab_ok else f"fail:{ab_block}"],
        [],
        ["type", "channel", "guest", "side", "hotel_id", "check_in", "check_out", "beds"],
    ]
    for s in sorted(stays, key=lambda x: (x["side"], x["check_in"], x["guest"])):
        lines.append(["stay", s["channel"], s["guest"], s["side"], s["hotel_id"], s["check_in"], s["check_out"], str(s["beds"])])
    lines += [[], ["type", "date", "airbnb_male_occupied", "airbnb_female_occupied"]]
    for key in sorted(airbnb):
        if dates[0].isoformat() <= key <= dates[-1].isoformat():
            n = airbnb[key]
            lines.append(["airbnb_night", key, str(n["male"]), str(n["female"])])
    lines += [[], ["type", "date", "side", "cap", "named_beds", "airbnb_beds", "airbnb_known", "combined", "status"]]
    for r in derived:
        lines.append(["derived_night", r["date"], r["side"], str(r["cap"]), str(r["named_beds"]),
                      str(r["airbnb_beds"]), r["airbnb_known"], str(r["combined"]), r["status"]])
    with OUT_CSV.open("w", newline="") as f:
        csv.writer(f).writerows(lines)

    notes = [
        "Sources: Airbnb + Booking pianist9 (male 16844588) + Booking royceb (female 16840329). Agoda excluded.",
        "Female dormitory4 suspended — not counted in Airbnb sellable beds.",
        f"pianist9 scrape: {'ok' if p9_ok else 'FAILED — used last known male Booking stays; needs sign-in on box'}.",
        f"royceb scrape: {'ok' if rb_ok else 'FAILED'}.",
        f"Airbnb scrape: {'ok' if ab_ok else 'FAILED'}.",
    ]
    OUT_HTML.write_text(build_html(dates, stays, airbnb, derived, overs, notes))

    sig = occupancy_signature(derived)
    (ROOT / "occupancy-signature.txt").write_text(sig)
    prev_path = ROOT / "last-occupancy-signature.txt"
    if not prev_path.exists() and SNAP.exists():
        prev_derived = []
        with SNAP.open() as f:
            for row in csv.reader(f):
                if row and row[0] == "derived_night":
                    prev_derived.append({"date": row[1], "side": row[2], "combined": row[7], "status": row[8]})
        prev_path.write_text(occupancy_signature(prev_derived))
    prev_sig = prev_path.read_text() if prev_path.exists() else ""
    # Compare only overlapping date|side keys that exist in both, plus flag new overs
    # Full signature inequality is the send trigger (window shift alone counts as change if combined/status differ)
    changed = sig != prev_sig

    result = {
        "changed": changed,
        "overbook_nights": overs,
        "at_cap": [r for r in derived if r["status"] == "at_cap"],
        "scrape": {"pianist9": p9_ok, "royceb": rb_ok, "airbnb": ab_ok},
        "blockers": {"pianist9": p9_block, "royceb": rb_block, "airbnb": ab_block},
        "csv": str(OUT_CSV),
        "html": str(OUT_HTML),
        "new_royceb_guests": [s["guest"] for s in rb] if rb_ok else [],
        "male_peak": max((r["combined"] for r in derived if r["side"]=="male" and r["airbnb_known"]=="yes"), default=None),
        "female_peak": max((r["combined"] for r in derived if r["side"]=="female" and r["airbnb_known"]=="yes"), default=None),
    }
    (ROOT / "compare-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
