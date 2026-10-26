# Dorm bed calendar — current state (Mon 26 Oct 2026, ~09:55 Paris)

Live page: https://roycepianist9-debug.github.io/dorm-calendar/ (repo roycepianist9-debug/dorm-calendar, `index.html`, branch main)
- Live sha256: `c515f0e691258f33eceae258d6f7dff193821d490cf4e15d19f5a84893c9d129` (262522 bytes) = LAST_GOOD.html on box (`/workspace/multi-ota/LAST_GOOD.html`). Last run: patch_run59 (fragments 881b615 → assemble 49ffe84 → deploy-touch 1f57726, live verified).
- Gmail watermark: `2026-10-26T08:10:41Z` (= 09:10 Paris) per STABLE_META.json. Read mail newer than this in both inboxes.
- Bookings/stays and the bed map have no separate files: they live in the page's `chart-data` JSON and who-list tables inside LAST_GOOD.html / index.html. On-sale counts: `boo_onsale.json` + `ONSALE_README.md`.

## Caps and occupancy
- Caps: men 23, women 8.
- Men: full 23/23 on Oct 26–27. Garice Labeau, Airbnb HMMAMS55C3, Male (12), Oct 26–30, €60.07. Rosanthan HM2CQ4DRDX cancelled. Men's Airbnb beds blocked Oct 26–28.
- Women: Vanessa Ruiz HM2TAF82HA moved from Male (14) to "Female dormitory (Vanessa)", Oct 28–Nov 30, payout €299.58.
- Booking.com 6756773216, Ta Sangi, Nov 4–7, €46.07, commission €8.06, net ≈€38.01.
- Women 8/8 on Nov 3, 4, 5, 6. Women's Airbnb blocked Nov 3–6. **Nov 7 is 10/8, over cap. Waiting for Royce's decision.**
- Oct 28: all women's beds booked or blocked. Oct 29: Female dormitory3 and 6 open at €14.

## Pending
- Veronica inquiry: Female shared room 9, Oct 28–30. Those dates are unavailable; Royce said he would look for a bed.
- Basil inquiry: Female dormitory2, Dec 22–31. He was sent the Male (10) link and is asking for documentation.
- Fouad: €12 money request due Oct 26 21:00 Paris.
- Male (5) removal on Nov 7. Male (7) suspended.
- Airbnb account details due Dec 1.
- Booking.com men's property 16773673 is closed for regulatory status. Royce says he added the registration number. Booking says to contact support via extranet Inbox > Booking.com messages > Contact us.
- Older pending cancel/modify/change requests are listed in STABLE_META.json.

## Rules
- Never send guest messages without Royce's yes.
- Closure wording: "closed from 11:00 to 20:00".
- Dorms are strictly single-gender.
- Use Booking.com only in Firefox (firefox-esr) on the box, never in Chrome.
- Always read guest threads live.
- When a night hits cap, close the open beds on every channel.
- Airbnb payout floor is about €13–14/night.

## Publishing
- Flow: patch LAST_GOOD → push fragments → assemble commit → verify the live sha256 → log the run in runs.log → update STABLE_META.json.
- An assemble commit may not trigger a Pages deploy. Push a deploy-touch commit (`deploy-touch.txt`) to force one.
- Before pushing, check that the forbidden strings are absent. Copied scripts show them as `<FORBIDDEN_n>`; the real list is in the box originals only.

## Files in this folder
- data/STABLE_META.json, data/boo_onsale.json, data/ONSALE_README.md
- data/runs.log.excerpt.txt (last 120 lines of runs.log)
- scripts/patch_run57–59.py: the latest patch scripts, sanitized. Use run59 as the template.
- LAST_GOOD reference: sha above = live index.html in this repo.
