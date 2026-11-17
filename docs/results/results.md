# Simulation results: first-come-first-served vs priority-aware

**These are simulation results**, produced by `python3 -m carcomms experiment`. Model: one intersection, two cars, 1.5 s inside the intersection, 50 ms one-way message delay, 20 Hz state broadcasts, seed 1. No hardware was involved. Waiting time = from reaching the stop line to entering the intersection.

## Named scenarios (same arrivals for both policies)

The simulator advances in 50 ms steps, so 50 ms is the smallest delay it can represent.

| Scenario | Policy | Priority car wait (s) | Other car wait (s) | Total wait (s) | Went first |
|---|---|---:|---:|---:|---|
| S1a simultaneous, car_a has priority | FCFS | 0.10 | 1.65 | 1.75 | car_a |
| S1a simultaneous, car_a has priority | Priority | 0.10 | 1.65 | 1.75 | car_a |
| S1b simultaneous, car_b has priority | FCFS | 1.65 | 0.10 | 1.75 | car_a |
| S1b simultaneous, car_b has priority | Priority | 0.10 | 1.65 | 1.75 | car_b |
| S2 equal priority, simultaneous | FCFS | 1.65 | 0.10 | 1.75 | car_a |
| S2 equal priority, simultaneous | Priority | 1.65 | 0.10 | 1.75 | car_a |
| S3 priority arrives 0.05 s after other, slow link | FCFS | 1.90 | 0.30 | 2.20 | car_a |
| S3 priority arrives 0.05 s after other, slow link | Priority | 0.30 | 2.00 | 2.30 | car_b |
| S4 priority arrives 0.50 s after other | FCFS | 1.15 | 0.10 | 1.25 | car_a |
| S4 priority arrives 0.50 s after other | Priority | 1.15 | 0.10 | 1.25 | car_a |
| S5 priority car repeats 3 trips | FCFS | 1.80 | 1.15 | 2.95 | car_b |
| S5 priority car repeats 3 trips | Priority | 1.80 | 1.15 | 2.95 | car_b |

## Random arrivals (2000 trials, both cars arrive uniformly within 4 s)

| Policy | Priority car mean wait (s) | Other car mean wait (s) | Total mean wait (s) | Priority car went first |
|---|---:|---:|---:|---:|
| FCFS | 0.365 | 0.370 | 0.735 | 51.3% |
| Priority | 0.357 | 0.378 | 0.735 | 51.9% |

The two policies chose a different crossing order in 0.5% of trials; 5.1% of trials had arrivals within 100 ms of each other. Overlaps in the intersection: 0. Trials that did not finish: 0.

## Same, with 10% of messages lost (1000 trials)

| Policy | Priority car mean wait (s) | Other car mean wait (s) | Total mean wait (s) |
|---|---:|---:|---:|
| FCFS | 0.368 | 0.393 | 0.761 |
| Priority | 0.357 | 0.404 | 0.760 |

Overlaps: 0. Trials that did not finish: 0.

## Sensitivity to message delay

| One-way delay | Order differs | Priority car mean wait, FCFS (s) | Priority car mean wait, Priority (s) | Other car mean wait, FCFS (s) | Other car mean wait, Priority (s) |
|---:|---:|---:|---:|---:|---:|
| 50 ms | 0.6% | 0.348 | 0.339 | 0.374 | 0.383 |
| 100 ms | 2.0% | 0.471 | 0.439 | 0.484 | 0.516 |
| 200 ms | 4.1% | 0.709 | 0.639 | 0.717 | 0.787 |
| 400 ms | 10.1% | 1.199 | 1.009 | 1.200 | 1.394 |

