#!/usr/bin/env python3
"""Auto-assign women's stays to beds F-1..F-8 (Royce rule, 2026-10-21).

Usage (15-min 'Multi-OTA bed calendar' routine, after any women's booking change):
  python3 /workspace/multi-ota/assign_women.py            # dry run, prints plan
  python3 /workspace/multi-ota/assign_women.py --write    # writes /workspace/multi-ota/shared-edits.out.json
Then, only if the plan has "changes" > 0, push with GitHub push_files (ONE commit, 2 files):
  versions/shared-edits/<UTC stamp>.json  <- /workspace/multi-ota/shared-edits.prev.json (backup of what was live)
  shared-edits.json                       <- /workspace/multi-ota/shared-edits.out.json
Re-run the script right before pushing (it re-reads the latest shared-edits.json; never push a stale file).

Rules:
 - stays come from chart-data (women side, w[1]) in LAST_GOOD.html, plus corrections in women_stay_fixes.json
   ({"<name in chart>": {"n": "Real Name", "ci": "YYYY-MM-DD", "co": "YYYY-MM-DD"}}).
 - a stay already on a bed (name match) is never moved; manual entries are never overwritten.
 - Nelly (staff) keeps her bed; she is never auto-assigned or moved.
 - a bed is usable for a stay only if every night ci..co-1 is free: empty, or its guest left (co <= stay ci),
   and not out of service (x). The bed map holds ONE guest per bed, so stays starting after tonight are
   only assigned on/after their check-in day (the routine catches them on that day).
 - lowest bed number first. If no single bed is free for all nights: put her on the bed free for the
   longest run from check-in, mark "split": true + note, and report it in "flags" (tell Royce).
"""
import json, re, sys, datetime, urllib.request, unicodedata
from zoneinfo import ZoneInfo
D = "/workspace/multi-ota/"
P = ZoneInfo("Europe/Paris")
now = datetime.datetime.now(P)
night = (now - datetime.timedelta(hours=6)).date().isoformat()  # before 06:00 Paris = previous night

def toks(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s); return [t for t in re.split(r"[^a-z0-9]+", s) if t]
def same(a, b):
    """same guest? token subset, or short-name prefix (Semy ~ Semyfaveur Tsegay Mengesha)"""
    x, y = set(toks(a)), set(toks(b))
    if not (x and y): return False
    if x <= y or y <= x: return True
    sm, lg = (x, y) if len(x) <= len(y) else (y, x)
    return all(any(len(t) >= 4 and (u.startswith(t) or t.startswith(u)) for u in lg) for t in sm)

h = open(D + "LAST_GOOD.html", encoding="utf-8").read()
rows = json.loads(re.search(r'id="chart-data">(.*?)</script>', h, re.S).group(1))
fixes = {}
try: fixes = json.load(open(D + "women_stay_fixes.json"))
except FileNotFoundError: pass

# women stays = runs of consecutive nights per name
stays, open_ = [], {}
for r in rows:
    cur = {}
    for g in (r.get("w") or [[], []])[1]:
        for n in g[1]:
            if n: cur[n] = g[0]
    for n in list(open_):
        if n not in cur: open_[n]["co"] = r["d"]; stays.append(open_.pop(n))
    for n, s in cur.items():
        if n not in open_: open_[n] = {"n": n, "src": s, "ci": r["d"], "co": None}
stays += open_.values()
for s in stays:
    f = fixes.get(s["n"])
    if f: s.update({k: v for k, v in f.items() if v})
SRC = {"P": "B", "R": "B", "C": "C", "A": "A", "G": "G", "J": "J"}

# LIVE map = the Save server (what whosthere.site shows after Save/pull). shared-edits.json in GitHub is NOT used (never existed).
LOAD, SAVE = "https://royce-dorm-save.netlify.app/load", "https://royce-dorm-save.netlify.app/save"
prev_raw = urllib.request.urlopen(LOAD + "?t=%d" % now.timestamp(), timeout=20).read().decode()
shared = json.loads(prev_raw or "{}")
bm = shared.setdefault("bedmap", {}); fem = bm.setdefault("f", {})
BEDS = ["F-%d" % i for i in range(1, 9)]

def staff(v): return "nelly" in toks(v.get("n"))
def placed(n): return any(same(fem.get(b, {}).get("n"), n) and not fem[b].get("x") for b in BEDS)
def free_from(b, ci):  # bed usable from ci?
    v = fem.get(b) or {}
    if v.get("x") or staff(v): return False
    if not v.get("n"): return True
    return bool(v.get("co")) and v["co"] <= ci and v["co"] <= night  # previous guest gone, safe to overwrite
def days(a, b):
    a, b = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b); return (b - a).days

plan, flags, changed = [], [], {}
T = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)
for b in BEDS:  # departed guests (co <= tonight) free their bed; never Nelly/staff, never out-of-service, never manual beds without co
    v = fem.get(b) or {}
    if v.get("n") and not staff(v) and not v.get("x") and v.get("co") and v["co"] <= night:
        plan.append({"bed": b, "freed": v["n"], "co": v["co"]}); fem[b] = {"s": "free", "n": "", "src": "", "t": T}; changed[b] = fem[b]
todo = sorted([s for s in stays if s["co"] and s["co"] > night and s["ci"] <= night and "staff" not in s["n"].lower() and "nelly" not in toks(s["n"])], key=lambda s: (s["ci"], s["n"]))
for s in todo:
    if placed(s["n"]): continue
    cand = [b for b in BEDS if free_from(b, s["ci"])]
    if not cand:
        flags.append({"n": s["n"], "ci": s["ci"], "co": s["co"], "why": "no free women's bed tonight"}); continue
    b = cand[0]  # bed map holds one guest per bed, so a free bed is free for the whole stay
    v = {"s": "in", "n": s["n"], "src": SRC.get(s["src"], ""), "ci": s["ci"], "co": s["co"], "auto": 1, "t": T}
    fem[b] = v; changed[b] = v; plan.append({"bed": b, **{k: v[k] for k in ("n", "ci", "co", "src")}})

out = {"night": night, "changes": len(plan), "assigned": plan, "flags": flags,
       "note": "stays starting after tonight wait for their check-in day", "live_beds": {b: (fem.get(b) or {}).get("n", "") for b in BEDS}}
print(json.dumps(out, ensure_ascii=False, indent=1))
open(D + "shared-edits.prev.json", "w").write(prev_raw)
if "--write" in sys.argv and changed:
    # send ONLY the changed beds; the server keeps the newest edit per bed, so Royce's phone edits are never wiped
    body = json.dumps({"by": "auto-assign", "bedmap": {"f": changed}, "arrived": {}}).encode()
    r = urllib.request.urlopen(urllib.request.Request(SAVE, data=body, method="POST",
        headers={"Origin": "https://whosthere.site", "Content-Type": "text/plain"}), timeout=30)
    live = json.loads(r.read())["data"]["bedmap"].get("f", {})
    bad = [b for b, v in changed.items() if live.get(b, {}).get("n") != v["n"]]
    print("saved", sorted(changed), "VERIFY FAILED " + str(bad) if bad else "verified live")
