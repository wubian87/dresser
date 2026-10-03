# Rotation simulation (example data, rules only)

**This is a simulation, not a user study.** The wardrobe is the autumn room (19 of the 21 synthetic illustrations in `sample_wardrobe/`; the weather below is autumn-like, and the app only styles from the current room); the "habit user" is a made-up picker; the app arms always accept the app's top pick. Reproduce: `python tools/simulate_rotation.py`. No language model and no network are used, so the numbers are exactly repeatable.

Setup per run: 14 days of habit history, then 14 new days of weather (random, autumn-like 5-26 °C, ~30% rainy days, weekdays commute / weekends casual) under three policies that start from the same history. 50 runs (seeds 0-49) for each habit strength. Cells are the mean over runs, with [min - max] in brackets.

Rotation policy used: worn today/yesterday -2.5, worn 2-3 days ago -1.0, long-unworn bonus up to +0.5 per piece (full at 21 days). For scale, rule scores of the best candidates are typically within 1-3 points of each other.

How to read it: `no_rotation` takes the same best-scoring outfit whenever the weather repeats, which is why it repeats a lot; that is the baseline the rotation changes, not a claim about how anyone dresses. The made-up habit user did **not** reproduce a "half the closet is never worn" pattern (it wears ~70-80% of the pieces in a fortnight, because weather and the rules already force some variety), so these numbers say nothing about how much of a real closet sits unused.

## mild habit (favourite piece ~4x as likely)

Seed period (the 14 days of habit history before the comparison): 14.8 of 19 pieces worn on average [11 - 18].

| Measure (14 days) | made-up habit user keeps choosing as before | app top pick, no rotation | app top pick, with rotation |
|---|---|---|---|
| Pieces worn at least once in 14 days | 14.3 [10.0 - 18.0] | 13.0 [11.0 - 17.0] | 16.7 [14.0 - 18.0] |
| ... of the pieces the rules allow in that weather | 79% [56% - 100%] | 72% [61% - 94%] | 93% [78% - 100%] |
| Most times one piece was worn in 14 days | 7.7 [5.0 - 11.0] | 7.8 [6.0 - 11.0] | 4.3 [4.0 - 5.0] |
| Piece-days repeated from the previous day | 14.0 [4.0 - 21.0] | 17.0 [7.0 - 27.0] | 0.2 [0.0 - 2.0] |
| Days wearing an outfit already worn in the window | 3.7 [0.0 - 8.0] | 6.5 [4.0 - 10.0] | 1.6 [0.0 - 5.0] |
| Mean rule score of the outfit worn (higher = better by the rules) | 10.3 [9.5 - 10.6] | 10.7 [10.1 - 11.0] | 10.0 [9.7 - 10.5] |

Pieces the rules allow at all in these 14-day weather windows: 18.0 of 19 on average [18 - 18]. Never usable in any run: black-flats (the vision model labelled it an accessory, so the outfit builder does not use it; this is a known misreading, see README).

## strong habit (~12x)

Seed period (the 14 days of habit history before the comparison): 13.8 of 19 pieces worn on average [9 - 17].

| Measure (14 days) | made-up habit user keeps choosing as before | app top pick, no rotation | app top pick, with rotation |
|---|---|---|---|
| Pieces worn at least once in 14 days | 13.3 [9.0 - 17.0] | 13.0 [11.0 - 17.0] | 16.8 [14.0 - 18.0] |
| ... of the pieces the rules allow in that weather | 74% [50% - 94%] | 72% [61% - 94%] | 94% [78% - 100%] |
| Most times one piece was worn in 14 days | 9.0 [6.0 - 13.0] | 7.8 [6.0 - 11.0] | 4.3 [4.0 - 5.0] |
| Piece-days repeated from the previous day | 16.9 [8.0 - 25.0] | 17.0 [7.0 - 27.0] | 0.2 [0.0 - 2.0] |
| Days wearing an outfit already worn in the window | 5.0 [1.0 - 9.0] | 6.5 [4.0 - 10.0] | 1.5 [0.0 - 3.0] |
| Mean rule score of the outfit worn (higher = better by the rules) | 10.3 [9.4 - 10.7] | 10.7 [10.1 - 11.0] | 10.0 [9.6 - 10.3] |

Pieces the rules allow at all in these 14-day weather windows: 18.0 of 19 on average [18 - 18]. Never usable in any run: black-flats (the vision model labelled it an accessory, so the outfit builder does not use it; this is a known misreading, see README).

