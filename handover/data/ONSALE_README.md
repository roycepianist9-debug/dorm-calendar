# On-sale layers (men's chart) — rules

Set by Royce, 10 Oct 2026 07:16 Paris. Apply on EVERY run, after every booking change (new / change / cancel / cash / manual).

- `am` (Airbnb on sale, coral bars) = **max(0, 22 − men booked)** for every night from today onward, where men booked = `m[0]` in chart-data (all sources: cash, Airbnb, Booking, Agoda).
  - It is a derived value, not a host-calendar read. Do not use the old Oct 6 host-calendar numbers or the old "new Airbnb booking am −1 / cancel +1" rule; just recompute from booked.
- `bm` (Booking.com on sale, navy bars) = **0** on every night (Booking.com men's property 16844588 closed, Royce 9 Oct 2026).
- Never change booked counts when recomputing the layers.
- Note under the male chart (`#am-src`): "Airbnb on sale = beds left up to 22".
- Past nights (before today) are left as they were.
