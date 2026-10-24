# Dorm calendar anti-rollback rule (2026-10-12)
Cause: at 13:06 Paris (11:06Z) commit 25c0a50f "Calendar: restore LAST_GOOD (undo Ahmed Dkar Nov Booking sync)"
pushed fragments of an old LAST_GOOD (0fc1da2f) because the publisher found no confirm mail after ITS OWN
watermark (2026-10-11T20:04:09Z). The Ahmed stays came from the Booking extranet export (Royce-requested),
not mail. Same pattern removed Vin at 08:54Z (that one Royce wanted).
Rules for every publisher (incl. "Dorm calendar stay up" and the hourly bed-calendar run):
1. Never republish a stored LAST_GOOD over live. Always patch on top of the CURRENT live page.
2. "No mail after my watermark" is NOT a reason to remove data; Booking/Airbnb extranet reads and Royce manual changes are valid sources. Flag, don't revert.
3. Stay-up only restores when live is BROKEN (not 200, no DOCTYPE/chart-data/Breakdown, $file:/PLACEHOLDER). Then restore the newest copy in STABLE_META.json (check its sha/calendar_version), never an older one.
4. Every page carries <meta name="calendar-version" content="UTC ISO">; bump it on each publish.
   The repo assemble workflow refuses an index with a missing or older version than live unless the
   triggering commit message contains [allow-rollback] (only with Royce OK).

## No money on female dorm (Royce 2026-10-20)
Never add € amounts to the Female section or Female tonight card. Keep script id=nofem-eur and the male-only n10 draw().

## Lock bedmap-js / i18n-js (Royce 2026-10-23)
Cause: Bryan M-15 publish replaced a SEED line and left `}, /* comment */,` (extra comma after the comment). That SyntaxError aborted the whole bedmap IIFE → Female/Male toggle dead and Bed map blank. It did not "decay on its own"; a publish patch broke it.
Rules:
1. Before every fragment push, run `python3 /workspace/multi-ota/check_calendar_js.py patched.html` (exit 1 = do not push).
2. GitHub Actions assemble-index.yml also runs `node --check` on bedmap-js and i18n-js after gunzip; a SyntaxError refuses the assemble commit so broken JS never becomes live.
3. When editing SEED bed lines, keep exactly one comma between object entries — never a comma after a trailing `/* … */` comment that already follows a `,`.
