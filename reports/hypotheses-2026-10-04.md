# M3 hypothesis report

Generated from the database. Match run `3425556d-c5eb-4120-b957-6b5c7843f8b5`, dataset `dd0bcb816434`. Decision policy: score ≥ -0.25; judge in [-2, 3) at confidence ≥ 0.8 suggests and vetoes.
Matcher precision 100.0% (95% CI 95.9%–100.0%), recall 65.0% (95% CI 41.5%–83.0%) (the policy end to end on the gold set, labels not applied).

## H1 — overlap between platforms

Predicted cross-platform matches: **302** (at most one partner per listing).

| Platform | Listings | With a predicted match | Share |
|---|---|---|---|
| jabama | 2987 | 302 | 10.1% |
| shab | 601 | 302 | 50.2% |

Corrected for the matcher (real ≈ predicted × precision / recall): about **464** real pairs (range 349–601, from the ends of the two Wilson intervals and capped by the smaller platform; not itself a 95% interval). Listings with a partner: jabama 15.5% (11.7%–20.1%), shab 77.3% (58.1%–100.0%). Distinct villas on both platforms: **14.9%** of all villas in the catalog (range 10.8%–20.1%).

Caveats: predicted matches include false positives (see precision) and miss pairs the matcher or the blocking did not find (see recall), so the shares are estimates, not counts of real villas. The crawl covers the Ramsar–Tonekabon region of two platforms; villas listed only on other platforms are not counted.

## H2 — listed totals for the same villa and stay

Totals are listed prices (nights + extra guests). Neither platform publishes its fees, so both sides are lower bounds ("≥ X") and the comparison excludes fees.

| Scenario | Guests | Pairs bookable on both | Median higher/lower | p90 | Cheaper on |
|---|---|---|---|---|---|
| weekend | 4 | 208 | 1.10× | 1.50× | jabama: 95, shab: 89 |
| weekend | 8 | 70 | 1.10× | 1.53× | jabama: 32, shab: 31 |
| midweek | 4 | 225 | 1.09× | 1.51× | jabama: 92, shab: 83 |
| midweek | 8 | 79 | 1.10× | 1.47× | jabama: 37, shab: 28 |
| holiday | 4 | 183 | 1.25× | 2.04× | jabama: 52, shab: 117 |
| holiday | 8 | 58 | 1.20× | 1.70× | jabama: 22, shab: 34 |

The cheaper platform changes between scenarios for **63** of 248 pairs compared in more than one scenario.

## H3 — hidden nights

Nights from 2026-10-02 to 2026-12-16 observed on both platforms less than 6 h apart: **22348**. Free on one platform and taken on the other: **4617** (20.7%), in 166 of 302 pairs.

Some platforms do not say whether a taken night is booked or closed by the host (stored as unavailable), so a hidden night means *shown free elsewhere*, not *bookable*.
