# Rotation simulation (example data, rules only)

**This is a simulation, not a user study.** The wardrobe is the 21 synthetic illustrations in `sample_wardrobe/`; the "habit user" is a made-up picker; the app arms always accept the app's top pick. Reproduce: `python tools/simulate_rotation.py`. No language model and no network are used, so the numbers are exactly repeatable.

Setup per run: 14 days of habit history, then 14 new days of weather (random, autumn-like 5-26 °C, ~30% rainy days, weekdays commute / weekends casual) under three policies that start from the same history. 50 runs (seeds 0-49) for each habit strength. Cells are the mean over runs, with [min - max] in brackets.

Rotation policy used: worn today/yesterday -2.5, worn 2-3 days ago -1.0, long-unworn bonus up to +0.5 per piece (full at 21 days). For scale, rule scores of the best candidates are typically within 1-3 points of each other.

How to read it: `no_rotation` takes the same best-scoring outfit whenever the weather repeats, which is why it repeats a lot; that is the baseline the rotation changes, not a claim about how anyone dresses. The made-up habit user did **not** reproduce a "half the closet is never worn" pattern (it wears ~70-80% of the pieces in a fortnight, because weather and the rules already force some variety), so these numbers say nothing about how much of a real closet sits unused.

## mild habit (favourite piece ~4x as likely)

Seed period (the 14 days of habit history before the comparison): 16.3 of 21 pieces worn on average [13 - 20].

| Measure (14 days) | made-up habit user keeps choosing as before | app top pick, no rotation | app top pick, with rotation |
|---|---|---|---|
| Pieces worn at least once in 14 days (of 21) | 15.9 [11.0 - 19.0] | 15.0 [12.0 - 17.0] | 18.8 [14.0 - 20.0] |
| ... of the pieces the rules allow in that weather | 80% [55% - 95%] | 75% [60% - 85%] | 94% [70% - 100%] |
| Most times one piece was worn in 14 days | 6.8 [5.0 - 11.0] | 6.9 [5.0 - 10.0] | 4.1 [3.0 - 5.0] |
| Piece-days repeated from the previous day | 11.7 [4.0 - 19.0] | 12.7 [6.0 - 24.0] | 0.1 [0.0 - 1.0] |
| Days wearing an outfit already worn in the window | 2.9 [0.0 - 7.0] | 5.6 [2.0 - 8.0] | 0.9 [0.0 - 3.0] |
| Mean rule score of the outfit worn (higher = better by the rules) | 9.8 [9.3 - 10.1] | 10.2 [9.8 - 10.4] | 9.6 [9.2 - 10.0] |

Pieces the rules allow at all in these 14-day weather windows: 20.0 of 21 on average [20 - 20]. Never usable in any run: black-flats (the vision model labelled it an accessory, so the outfit builder does not use it; this is a known misreading, see README).

## strong habit (~12x)

Seed period (the 14 days of habit history before the comparison): 15.1 of 21 pieces worn on average [11 - 19].

| Measure (14 days) | made-up habit user keeps choosing as before | app top pick, no rotation | app top pick, with rotation |
|---|---|---|---|
| Pieces worn at least once in 14 days (of 21) | 14.7 [10.0 - 19.0] | 15.0 [12.0 - 17.0] | 18.8 [12.0 - 20.0] |
| ... of the pieces the rules allow in that weather | 74% [50% - 95%] | 75% [60% - 85%] | 94% [60% - 100%] |
| Most times one piece was worn in 14 days | 7.8 [5.0 - 11.0] | 6.9 [5.0 - 10.0] | 4.1 [3.0 - 5.0] |
| Piece-days repeated from the previous day | 14.5 [6.0 - 25.0] | 12.7 [6.0 - 24.0] | 0.1 [0.0 - 2.0] |
| Days wearing an outfit already worn in the window | 3.9 [0.0 - 8.0] | 5.6 [2.0 - 8.0] | 1.0 [0.0 - 4.0] |
| Mean rule score of the outfit worn (higher = better by the rules) | 9.8 [9.3 - 10.1] | 10.2 [9.8 - 10.4] | 9.6 [9.2 - 10.0] |

Pieces the rules allow at all in these 14-day weather windows: 20.0 of 21 on average [20 - 20]. Never usable in any run: black-flats (the vision model labelled it an accessory, so the outfit builder does not use it; this is a known misreading, see README).

