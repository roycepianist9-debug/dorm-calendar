# Dorm calendar handover (whosthere.site)

Snapshot of the source data and scripts behind the live calendar, copied from the
bot's working folder (`/workspace/multi-ota`) on 2026-10-24 (Paris time).
The live page itself (`index.html` + assemble workflow) is **not** in this folder and was not changed.

Caps: **23 men**, **8 women** per night. Rule per night: booked + Booking on sale + Airbnb on sale <= cap.
All times are Paris time.

## Data (`handover/data/`)
| File | What it is | Updated by |
|---|---|---|
| `boo_onsale.json` | Booking.com beds on sale per night: `men` (property 16844588) and `women` (Femme Girls 16840329, "rooms to sell"). Has a `log` and `adjustments` history. | Booking email routine / extranet reads; drawn on the page as `bm` / `wbm` |
| `airbnb_onsale.json` | Men's Airbnb beds on sale per night (+ history) | Airbnb calendar routine; drawn as `am` |
| `airbnb_onsale_women.json` | Women's Airbnb beds on sale per night (max 2, re-capped to 8) | Airbnb routine; drawn as `wam` |
| `booking-rooms-to-sell.json` | Last raw read of Booking rooms to sell | Booking routine |
| `agoda-stays.json` | Agoda stays added to the men's count | Agoda email routine |
| `fallback-named-stays.json` | Named stays (cash / manual) used when a scrape is incomplete | manual / routines |
| `women_stay_fixes.json` | Manual check-in/checkout fixes for women | manual |
| `bedmap-snapshot.json` | Snapshot of the shared bed map (F-1..F-8, M-x) + "arrived" ticks, as saved by the page's save service | page edits + `assign_women.py` |
| `STABLE_META.json` | sha256/meta of the last known-good published page | publish step |

## Scripts (`handover/scripts/`)
| File | Purpose |
|---|---|
| `build_calendar_v2.py` / `build_calendar.py` | Build per-night counts (men/women, by source) from reservation exports |
| `run_after_scrape.py` | Runs the build after an Airbnb scrape |
| `write_airbnb.py`, `plan_airbnb_open_beds.py` | Airbnb on-sale planning / writes |
| `who_list.py` | "Who's there" guest lists per night grouped by source (C cash, A Airbnb, B/R Booking, G Agoda, P other) |
| `assign_women.py` | `--write` places new women guests on a free bed **on their check-in day only**, via the bed-map load/save service |
| `check_calendar_js.py` | Must pass (`python3 check_calendar_js.py patched.html`) before any push of the page HTML |

## Docs (`handover/docs/`)
`ONSALE_README.md` (on-sale layers), `ROLLBACK_GUARD.md` (how to restore the last good page), `HEARTBEAT_README.md`.

## How the routines update things
1. Booking/Airbnb/Agoda emails or calendar reads -> update the on-sale JSON (lower on a new booking, raise on cancel, never above cap).
2. Builders recompute per-night counts -> page `chart-data` rows (`m`, `f`, `bm`, `am`, `wbm`, `wam`, guest lists).
3. `assign_women.py --write` updates the bed map.
4. Page HTML patched, `check_calendar_js.py` run, pushed to this repo; Netlify serves whosthere.site.

## Deliberately excluded
Raw reservation exports (`reservations-fresh.csv`, `airbnb-ui-reservations*.json`, `airbnb-raw*.json`, snapshots CSVs) because they contain guest phone numbers;
`booking_properties.md` (account emails / phone); push-argument blobs, logs and session files. No passwords, tokens or door codes are included.
