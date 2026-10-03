# M3 hypothesis report

Generated from the database. Match run `3425556d-c5eb-4120-b957-6b5c7843f8b5`, dataset `dd0bcb816434`, score threshold -0.25.
Matcher precision 98.1% (95% CI 93.0%–99.5%), recall 67.1% (95% CI 44.6%–83.8%) (from the gold set).

## H1 — overlap between platforms

Predicted cross-platform matches: **320** (at most one partner per listing).

| Platform | Listings | With a predicted match | Share |
|---|---|---|---|
| jabama | 2987 | 320 | 10.7% |
| shab | 601 | 320 | 53.2% |

Corrected for the matcher (real ≈ predicted × precision / recall): about **468** real pairs (range 355–601, from the ends of the two Wilson intervals and capped by the smaller platform; not itself a 95% interval). Listings with a partner: jabama 15.7% (11.9%–20.1%), shab 77.9% (59.1%–100.0%). Distinct villas on both platforms: **15.0%** of all villas in the catalog (range 11.0%–20.1%).

Caveats: predicted matches include false positives (see precision) and miss pairs the matcher or the blocking did not find (see recall), so the shares are estimates, not counts of real villas. The crawl covers the Ramsar–Tonekabon region of two platforms; villas listed only on other platforms are not counted.

## H2 — listed totals for the same villa and stay

Totals are listed prices (nights + extra guests). Neither platform publishes its fees, so both sides are lower bounds ("≥ X") and the comparison excludes fees.

| Scenario | Guests | Pairs bookable on both | Median higher/lower | p90 | Cheaper on |
|---|---|---|---|---|---|
| weekend | 4 | 221 | 1.10× | 1.56× | jabama: 100, shab: 96 |
| weekend | 8 | 71 | 1.10× | 1.41× | jabama: 33, shab: 31 |
| midweek | 4 | 240 | 1.11× | 1.65× | jabama: 98, shab: 91 |
| midweek | 8 | 80 | 1.11× | 1.52× | jabama: 39, shab: 28 |
| holiday | 4 | 194 | 1.26× | 2.07× | jabama: 59, shab: 121 |
| holiday | 8 | 59 | 1.24× | 1.73× | jabama: 24, shab: 33 |

The cheaper platform changes between scenarios for **63** of 265 pairs compared in more than one scenario.

## H3 — hidden nights

Nights from 2026-10-02 to 2026-12-16 observed on both platforms less than 6 h apart: **23680**. Free on one platform and taken on the other: **4995** (21.1%), in 180 of 320 pairs.

Some platforms do not say whether a taken night is booked or closed by the host (stored as unavailable), so a hidden night means *shown free elsewhere*, not *bookable*.
