# Men's "on sale" layers (added 2026-10-06, 17:30 Shanghai; Airbnb filled 2026-10-06 17:45 Shanghai / 11:45 Paris)

The men's bar chart shows, on top of each blue booked bar (blue = booked, all sources),
thin bars for beds **still on sale** that night:

| layer | chart-data field | colour | data source |
|---|---|---|---|
| Boo on sale (Booking.com, property 16844588, room "Bed in Male Dormitory Room") | `"bm"` (int) | navy `#003580`, light-blue outline | `boo_onsale.json` → `men` |
| Airbnb on sale (men's Airbnb listings open and unbooked, 1 listing = 1 bed) | `"am"` (int) | coral `#ff5a5f`, pink outline | `airbnb_onsale.json` → `men` (read from the Airbnb host calendar 11:43 Paris Oct 6, 17 listed men's listings) |

* A night with no field means unknown, so nothing is drawn. `0` also draws nothing; the tap panel says "Boo on sale 0".
* The number is drawn inside the thin bar when it fits (3 beds or more), otherwise just above it.
* Stack order per night: blue booked → navy Boo (`bm`) → coral Airbnb (`am`), all on the booked bars' scale (100px = cap 23).
* **Stacks may cross the dashed cap line on purpose**: booked + Boo on sale + Airbnb on sale > 22 = overbooking risk.
  The SVG grows upward to fit (up to 15 beds over the cap; anything taller would be clipped with a small pink "+N"),
  and the dashed cap line is redrawn on top of the bars so the crossing stays visible.
* The legend note `<p class="capnote" id="am-note" hidden>Airbnb on sale: not tracked yet.</p>` is hidden (static
  `hidden` + JS hides it whenever any row has a numeric `"am"`).
* Under the legend: `<p class="capnote" id="am-src">Airbnb on sale read from the Airbnb host calendar at 11:43 Paris, Oct 6</p>`
  (`who_list.airbnb_onsale_source_line()`, from `airbnb_onsale.json → read_at_label`). Only change it when the Airbnb
  host calendar is re-read, not when the routine adjusts `am` for a booking. JS hides it if no row has `"am"`.
* Women's chart is unchanged. Women's Booking is closed, so `boo_onsale.json → women` is all 0 and is not injected.

## Where the code lives (in the page)
1. `<script type="application/json" id="chart-data">`: each row may carry `"bm"` and `"am"` (after `"w"`).
   Patches that do `json.loads` → edit → `json.dumps(separators=(",",":"), ensure_ascii=False).replace("<","\\u003c")`
   keep both automatically. **Never drop unknown keys from rows (`bm`, `am`).** Patch scripts' marker checks should include `'"am":'`.
2. `<script id="onsale-js">` (last script, before `</body>`): draws the thin bars in the browser from `bm`/`am`,
   stacked, growing the SVG upward over the cap. Incremental patches never need to touch it
   (source: `who_list.ONSALE_JS`; replaced once by `push-airbnbonsale/patch.py`).
3. Main script: `pack()` returns `bm`/`am`. The male channel line in the tap panel reads
   "Boo on sale N · Airbnb on sale N" (falls back to "unknown" / "not tracked yet" when a field is missing). The female line is unchanged.
4. Men's legend: "Blue = booked (all sources) · Boo on sale · Airbnb on sale", plus the (hidden) am-note, the am-src line,
   and a capnote "Dashed line is the cap, 23; we sell at most 22. … Bars crossing the dashed line = … overbooking risk."

## Server-side SVG (who_list.chart_svg)
`who_list.chart_svg(..., booked_fill=BOOKED_MALE, ...)` **no longer draws the old full-width amber "Airbnb open" /
green "Booking open" stack (m[1], m[2])** on the men's chart. The on-sale bars replace it, and they are drawn
client-side, so the men's SVG depends only on the booked counts. Existing patch scripts
(`male_series` → `W.chart_svg(male_series(rows), 23, W.BOOKED_MALE, aria)` → `assert old_svg in h`) keep
working unchanged. `m[1]`/`m[2]` are still in the JSON and archives; keep maintaining them as before.
The women's chart still draws amber/green (all 0).

The pre-change module is saved at `push-onsale/who_list_pre_onsale.py`, and the one-off patch at `push-onsale/patch.py`.

## Updating the Boo numbers
1. Edit `boo_onsale.json` → `men` (`"YYYY-MM-DD": n`, night = check-in date).
2. Patch LAST_GOOD.html incrementally: parse chart-data, call `who_list.inject_onsale(rows)` (sets/removes `bm`
   from the file), dump with the same separators, and replace only the JSON. No SVG change is needed.
3. Booking.com lowers rooms-to-sell by itself when a Booking (pianist9) guest books. When the routine adds a
   pianist9 men's stay, lower `bm` (and the file) by 1 for each night of the stay, minimum 0. Raise it back on a
   cancellation. Airbnb/cash/Agoda bookings do not change Booking's numbers (no channel manager), so leave `bm` alone.
4. `who_list.render_page` (full rebuild, not used for publishing) also injects `bm` and includes ONSALE_JS.

## Updating the Airbnb numbers (`am`)
1. Re-read from the Airbnb host calendar: rewrite `airbnb_onsale.json → men` (`"YYYY-MM-DD": n` = men's listings open
   and unbooked that night, night = check-in date), set `read_at` / `read_at_label` (e.g. "11:43 Paris, Oct 6"), then patch
   the page: `who_list.inject_onsale(rows)` (sets/removes both `bm` and `am`) and replace the `id="am-src"` line with
   `who_list.airbnb_onsale_source_line()`.
2. **Routine rule (15-minute run), men's Airbnb bookings only:**
   * **New men's Airbnb booking arrives → lower `am` by 1 for each night of the stay** (check-in night up to the night
     before check-out), minimum 0.
   * **Men's Airbnb booking cancels → raise `am` by 1 for each night of the stay.**
   * Date change = cancel the old nights (+1) and book the new nights (−1).
   * Do it in the file AND the page in one step: `W.adjust_onsale("am", check_in, check_out, -1, why="HMxxxx Name", rows=rows)`
     (or `+1` for a cancellation) inside the patch, before `dump(rows)`. It edits `airbnb_onsale.json`, logs to its
     `adjustments` list, and re-injects `bm`/`am` into `rows`. Nights not in the file stay unknown.
   * Women's Airbnb, cash, Booking (pianist9/other) and Agoda bookings do not change `am`. (pianist9 men's stays change
     `bm` instead: `W.adjust_onsale("bm", ..., -1, rows=rows)`.) Pending requests/inquiries do not count until confirmed.
   * Mention the `am` change in the runs.log CHANGE line (e.g. "am Oct8-21 −1").
3. The am-src timestamp stays at the last host-calendar read; the routine does not change it.

## History
* 2026-10-06 11:34 Paris: `bm` added, Airbnb slot empty ("not tracked yet").
* 2026-10-06 11:45 Paris: `am` filled from the Airbnb host calendar (read 11:43 Paris, 17 listed men's listings);
  pre-change page `versions/20261006-114508-pre-airbnbonsale.html`, patch `push-airbnbonsale/patch.py`.
  The older note that `am` needed a multi-calendar read of listings 1–26 except (5) is superseded by this read.

## Cap checks include people on beds only (capfix 2026-10-19, Royce)
* Every "booked + on sale vs cap" check (routine, patches, Airbnb/Booking trims) must use
  `who_list.cap_totals(html, side)` → `total = booked + on beds not in bookings + Boo/Airbnb on sale`,
  not `m[0] + bm + am`. Bed-map labels (`lb:1`), out-of-service beds (`x:1`) and free beds are excluded; a bed whose
  name matches a booked guest that night is not counted twice (same name match as the page's `count()`).
* Cash guests seen on the bed map must also have a cash row in the bookings (chart-data `C` group + Cash table) with a
  check-out date; extend the cash row when the bed map shows them staying longer (Kamel to Nov 17, Nader to Oct 31 done).
* The blue/orange booked bars and their numbers are drawn in the browser from chart-data (`<script id="bars-js">`),
  so patches only need to edit chart-data; the server-side SVG path/labels are replaced at load.
* The page's tap panel shows "booked + on beds + on sale N/cap" per night (red when over).
* Bed-map phone storage keeps every field (incl. `lb`); SEED_T bumped 2026-10-19 12:52Z (built-in beats older phone edits).

## Women's cap (2026-10-19 17:20 Paris, Royce) — supersedes the old "limit 10 / 8 Booking beds" assumption
* Women's cap is **8**: booked + Booking Femme Girls on sale (`wbm`, boo_onsale.json → women) + women's Airbnb on sale (`wam`) must be <= 8.
* `wbm` = real rooms to sell read in the Femme Girls 16840329 extranet (read 17:20 Paris Oct 19 for Oct 19-31 and Nov 16-Dec 31;
  Nov 1-15 still older values). Booking is no longer assumed to have 8 beds open; do NOT report "women over 10".
* The old open item "women over 10 on Nov 25/29/30, trim Booking Femme Girls by 1 each" is CLOSED (Nov 25 = 1+2+2 = 5, Nov 29/30 = 1+2+2 = 5).
* Use `who_list.cap_totals(html, 1)` for the women's check (it already sums wbm + wam).
