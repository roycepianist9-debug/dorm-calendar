#!/usr/bin/env python3
"""After airbnb-ui-reservations.json is fresh: rebuild, signature, compare to published."""
from __future__ import annotations
import json, re, hashlib, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path("/workspace/multi-ota")
SH = timezone(timedelta(hours=8))

def normalize(html: str) -> str:
    return re.sub(r'<p class="asof">.*?</p>', '', html, flags=re.S)

def sha(html: str) -> str:
    return hashlib.sha256(normalize(html).encode()).hexdigest()

def build_sig_from_csv():
    # Use who_list nightly rows + guest lists for occupancy signature matching last format
    import who_list as wl
    start = wl.chart_start()
    end = start + __import__('datetime').timedelta(days=31)
    male, female, air_ok, p9_ok, rb_ok, p9_block, rb_block = wl.rows_for(start, end)
    days = wl.daily(male, female, start)
    lines = []
    for drow in days:
        d = drow["date"].isoformat()
        # aggregate airbnb counts; name cash/booking guests
        for side, rows in (("male", male), ("female", female)):
            air_n = 0
            for r in rows:
                if not wl.on_night(r, drow["date"]):
                    continue
                beds = int(r["beds"])
                src = r["source"]
                if src in ("airbnb", "airbnb_soon"):
                    air_n += beds
                elif src == "cash":
                    lines.append(f"{d}|{side}|cash|{r['guest']}|{beds}")
                else:
                    # pianist9 / royceb
                    lines.append(f"{d}|{side}|{src}|{r['guest']}|{beds}")
            if air_n:
                lines.append(f"{d}|{side}|airbnb|Airbnb {side}|{air_n}")
    sig = "\n".join(sorted(lines)) + ("\n" if lines else "")
    (ROOT / "occupancy-signature.txt").write_text(sig)
    return {
        "tonight_male": wl.tonight(male),
        "tonight_female": wl.tonight(female),
        "air_ok": air_ok,
        "p9_ok": p9_ok,
        "rb_ok": rb_ok,
        "p9_block": p9_block,
        "rb_block": rb_block,
        "male_rows": len(male),
        "female_rows": len(female),
        "days": [{"date": x["date"].isoformat(), "male": x["male"], "female": x["female"]} for x in days],
    }

def main():
    subprocess.check_call([sys.executable, str(ROOT / "ui_to_airbnb_raw.py")])
    subprocess.check_call([sys.executable, str(ROOT / "who_list.py")])
    stats = build_sig_from_csv()
    new_html = Path("/workspace/multi-ota-calendar.html").read_text(encoding="utf-8")
    pub = ROOT / "published-index.html"
    pub_html = pub.read_text(encoding="utf-8") if pub.exists() else ""
    same_pub = sha(new_html) == sha(pub_html) if pub_html else False
    prev_sig = (ROOT / "last-occupancy-signature.txt").read_text() if (ROOT / "last-occupancy-signature.txt").exists() else ""
    new_sig = (ROOT / "occupancy-signature.txt").read_text()
    same_sig = prev_sig.strip() == new_sig.strip()
    open_set = json.loads((ROOT / "last-open-bed-set.json").read_text()) if (ROOT / "last-open-bed-set.json").exists() else {}
    out = {
        "run_at": datetime.now(SH).isoformat(timespec="seconds"),
        **stats,
        "same_signature": same_sig,
        "same_as_published_html": same_pub,
        "open_listings": open_set.get("listings_opened_for_sale", [12, 7, 11]),
        "new_html_sha": sha(new_html),
        "pub_html_sha": sha(pub_html) if pub_html else None,
    }
    (ROOT / "compare-result.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
