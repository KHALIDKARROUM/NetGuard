# Performance on unfamiliar traffic

This report evaluates the unchanged original benchmark with the frozen serving model, then refits the same fixed design for additional internal robustness experiments. Every original notebook cell remains preserved. It reports measured-input novelty, not verified physical connection identity.

Serving model: **supervised_soft_vote**; fixed threshold **0.8631127466983196**. Artifact SHA-256: `e05c143820f71d2347b2bc8c2ccaa57145878747ec9cf7a3598f14e45557d0eb`. The benchmark and development file hashes are recorded in the evidence. No model, ensemble weight, hyperparameter, or threshold was selected using these evaluation outcomes.

## What the overlap means

The audit's **40.62%** overlap (33,440/82,332) describes matches in the earlier selected/engineered predictor representation. It does **not** establish identical physical connections. The current model uses ten raw measurements and 29 deterministic predictors, so its signature definition and overlap differ.

The current ten-measurement signature appears in actual model-fitting data for **30,691** benchmark rows, and anywhere in development (fit plus threshold-selection validation) for **35,518**. Exact float64 equality joins verify hash membership. `benchmark_unseen_in_fit` is unseen by model fitting; `benchmark_unseen_in_any_development` additionally excludes signatures encountered during threshold selection. The latter is a benchmark subset with changed composition, not a replacement for the original benchmark.

## Frozen benchmark results

Every estimate below is a percentage followed by a 95% signature-cluster percentile bootstrap interval in brackets. AP is non-interpolated average precision; PR-AUC is the trapezoidal area and is reported separately. Tables include all rows, including repeats, at their original prevalence.

| Scope | Rows | Normal / attack | Signatures | Precision | Recall | F1 | PR-AUC | AP | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| benchmark_all | 82,332 | 37,000 / 45,332 | 43,336 | 97.28% [96.21, 97.99] | 86.51% [82.08, 89.85] | 91.58% [88.54, 93.71] | 98.26% [96.94, 99.02] | 98.26% [96.94, 99.01] | 2.96% [2.73, 3.22] |
| benchmark_seen_in_fit | 30,691 | 6,299 / 24,392 | 1,632 | 99.44% [98.94, 99.65] | 97.54% [95.37, 98.73] | 98.48% [97.17, 99.17] | 99.88% [99.63, 99.97] | 99.88% [99.61, 99.97] | 2.14% [1.55, 2.83] |
| benchmark_unseen_in_fit | 51,641 | 30,701 / 20,940 | 41,704 | 94.14% [93.26, 94.94] | 73.67% [70.95, 76.55] | 82.66% [80.69, 84.69] | 94.28% [93.05, 95.44] | 94.29% [93.05, 95.45] | 3.13% [2.87, 3.42] |
| benchmark_unseen_in_any_development | 46,814 | 28,217 / 18,597 | 41,306 | 93.44% [92.88, 93.97] | 71.55% [70.30, 72.88] | 81.05% [80.11, 82.04] | 93.62% [93.09, 94.15] | 93.62% [93.10, 94.16] | 3.31% [3.06, 3.53] |

## Attack-category detection on the full original benchmark

Each row compares that attack category with **all normal benchmark rows**, excluding other attacks. Recall is the fraction of that category detected. Precision, F1 and ranking metrics depend on this constructed category-versus-normal prevalence, and are not multiclass category-identification metrics. FPR uses the same normal rows in each row. All counts and category tables for seen/unseen slices and additional experiments are in the CSV/JSON evidence.

| Attack Category | Rows | Normal / attack | Signatures | Precision | Recall | F1 | PR-AUC | AP | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Analysis | 37,677 | 37,000 / 677 | 28,248 | 36.08% [24.59, 44.77] | 91.29% [86.33, 94.17] | 51.72% [38.51, 60.49] | 84.56% [70.84, 89.93] | 85.63% [74.68, 90.91] | 2.96% [2.70, 3.24] |
| Backdoor | 37,583 | 37,000 / 583 | 28,261 | 34.00% [25.41, 41.93] | 96.74% [94.51, 98.14] | 50.31% [40.12, 58.59] | 85.86% [74.34, 91.30] | 86.27% [75.24, 91.58] | 2.96% [2.68, 3.22] |
| DoS | 41,089 | 37,000 / 4,089 | 29,422 | 76.85% [66.40, 83.82] | 88.90% [81.91, 92.62] | 82.44% [73.36, 87.90] | 92.58% [84.85, 96.15] | 92.63% [84.87, 96.20] | 2.96% [2.71, 3.22] |
| Exploits | 48,132 | 37,000 / 11,132 | 35,299 | 89.86% [88.10, 91.49] | 87.20% [84.96, 89.12] | 88.51% [86.54, 90.25] | 95.17% [93.62, 96.40] | 95.18% [93.62, 96.43] | 2.96% [2.71, 3.21] |
| Fuzzers | 43,062 | 37,000 / 6,062 | 32,050 | 69.65% [64.70, 73.36] | 41.45% [35.84, 46.13] | 51.98% [46.38, 56.63] | 62.81% [55.97, 68.15] | 62.83% [56.00, 68.20] | 2.96% [2.72, 3.21] |
| Generic | 55,871 | 37,000 / 18,871 | 28,799 | 94.47% [88.95, 96.48] | 99.08% [97.96, 99.45] | 96.72% [93.15, 97.91] | 99.80% [99.24, 99.92] | 99.80% [99.24, 99.92] | 2.96% [2.71, 3.22] |
| Reconnaissance | 40,496 | 37,000 / 3,496 | 30,063 | 74.81% [69.51, 78.71] | 93.02% [91.02, 94.59] | 82.93% [78.97, 85.85] | 90.11% [84.99, 92.98] | 90.25% [85.30, 93.11] | 2.96% [2.76, 3.22] |
| Shellcode | 37,378 | 37,000 / 378 | 28,456 | 15.18% [13.23, 17.20] | 51.85% [46.80, 56.97] | 23.49% [20.74, 26.26] | 20.39% [16.00, 24.49] | 20.51% [16.21, 24.67] | 2.96% [2.66, 3.22] |
| Worms | 37,044 | 37,000 / 44 | 28,148 | 3.10% [2.05, 4.08] | 79.55% [66.65, 89.75] | 5.96% [4.00, 7.78] | 18.86% [9.14, 30.88] | 18.94% [9.29, 31.01] | 2.96% [2.72, 3.23] |

## Additional signature-disjoint three-way evaluation

The previously selected architecture, parameters, equal ensemble weights and feature contract are frozen before these runs. Five stratified signature folds partition **development only**: fold 0 evaluates, fold 1 selects the 1% empirical false-positive-budget threshold, and folds 2–4 fit features/scaling/model. Seeds 42, 43 and 44 were declared before running; all results are retained. All three partitions are pairwise signature-disjoint. Fitting and threshold selection never use the evaluation partition. This removes threshold reuse within each run; the previously inspected dataset and design history still prevent an untouched-final-test claim. Repeated evaluations overlap across seeds, so their intervals must not be pooled as independent runs.

| Scope | Rows | Normal / attack | Signatures | Precision | Recall | F1 | PR-AUC | AP | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| three_way_grouped_seed_42 | 30,754 | 13,248 / 17,506 | 16,459 | 99.29% [98.68, 99.58] | 75.92% [62.62, 83.56] | 86.04% [76.60, 90.83] | 98.01% [95.12, 99.36] | 98.03% [95.13, 99.39] | 0.72% [0.47, 1.04] |
| three_way_grouped_seed_43 | 27,012 | 10,563 / 16,449 | 16,509 | 98.26% [95.64, 99.46] | 68.44% [54.82, 77.60] | 80.68% [70.03, 87.05] | 97.93% [95.67, 99.08] | 97.93% [95.64, 99.12] | 1.88% [0.69, 4.00] |
| three_way_grouped_seed_44 | 28,348 | 13,141 / 15,207 | 16,504 | 99.04% [98.55, 99.36] | 70.84% [61.24, 78.59] | 82.60% [75.58, 87.76] | 97.07% [93.53, 98.90] | 97.10% [93.53, 98.96] | 0.79% [0.51, 1.12] |

## Withheld attack families

Run every one of the nine attack families separately. Using seed 42's three-way folds, remove **every signature matching any held-family row** from both fitting and threshold calibration. Evaluate all held-family rows against fold-0 normal traffic. Model design remains fixed, and calibration includes only normal traffic and the remaining known attack families. No held-family labels/scores are used in model fitting or threshold choice. This tests withheld-category detection within the same source dataset; it does not establish detection of arbitrary novel attacks in a new environment.

| Scope | Rows | Normal / attack | Signatures | Precision | Recall | F1 | PR-AUC | AP | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| withheld_family_Analysis | 15,248 | 13,248 / 2,000 | 8,854 | 92.66% [80.77, 96.33] | 60.00% [30.36, 75.95] | 72.84% [44.32, 84.52] | 79.70% [57.96, 88.44] | 80.63% [59.47, 90.34] | 0.72% [0.48, 1.03] |
| withheld_family_Backdoor | 14,994 | 13,248 / 1,746 | 8,880 | 92.94% [84.99, 96.32] | 71.59% [44.84, 86.47] | 80.88% [59.46, 90.94] | 86.48% [75.00, 92.12] | 87.21% [76.51, 93.33] | 0.72% [0.48, 1.06] |
| withheld_family_DoS | 25,512 | 13,248 / 12,264 | 11,078 | 99.04% [97.63, 99.48] | 73.12% [48.34, 86.26] | 84.13% [64.81, 92.28] | 97.89% [94.90, 98.88] | 97.98% [95.27, 99.03] | 0.66% [0.42, 0.97] |
| withheld_family_Exploits | 46,641 | 13,248 / 33,393 | 27,032 | 99.46% [99.13, 99.65] | 53.15% [41.79, 62.79] | 69.27% [58.79, 77.05] | 99.04% [98.53, 99.36] | 99.05% [98.54, 99.38] | 0.73% [0.48, 1.07] |
| withheld_family_Fuzzers | 31,432 | 13,248 / 18,184 | 21,118 | 94.48% [90.60, 96.98] | 16.56% [11.78, 21.56] | 28.19% [20.91, 35.16] | 91.46% [88.86, 93.35] | 91.64% [89.00, 93.89] | 1.33% [0.67, 2.46] |
| withheld_family_Generic | 53,248 | 13,248 / 40,000 | 9,024 | 99.73% [99.25, 99.86] | 99.17% [97.66, 99.59] | 99.45% [98.48, 99.71] | 99.71% [98.61, 99.83] | 99.79% [99.43, 99.91] | 0.82% [0.50, 1.13] |
| withheld_family_Reconnaissance | 23,739 | 13,248 / 10,491 | 13,695 | 95.78% [93.37, 97.39] | 25.29% [15.96, 35.43] | 40.01% [27.32, 51.92] | 93.23% [89.66, 95.13] | 93.37% [89.87, 95.41] | 0.88% [0.58, 1.26] |
| withheld_family_Shellcode | 14,381 | 13,248 / 1,133 | 9,286 | 78.48% [74.33, 82.75] | 30.89% [27.62, 34.14] | 44.33% [40.53, 48.09] | 67.71% [63.90, 71.32] | 67.76% [64.06, 71.38] | 0.72% [0.46, 1.02] |
| withheld_family_Worms | 13,378 | 13,248 / 130 | 8,462 | 35.42% [26.89, 43.72] | 39.23% [30.16, 47.93] | 37.23% [29.13, 44.53] | 40.82% [32.09, 48.88] | 40.99% [32.49, 49.16] | 0.70% [0.46, 1.03] |

Separate normal-only Isolation Forest and novelty LOF experiments remain available in `SUPERVISED_COMPARISON.md`. Their Backdoor recall was only 3.44% and 8.08%, respectively; they do not provide strong generalization evidence.

## Where the model works and fails

- Among fitting-seen signatures, attack recall is 97.54% [95.37, 98.73]; among fitting-unseen signatures it is 73.67% [70.95, 76.55]. On the stricter development-unseen subset it is 71.55% [70.30, 72.88]. Signature novelty therefore has measurable performance consequences; different slice prevalences also affect precision and PR-AUC.
- The strongest full-benchmark category recalls are **Generic** 99.08% [97.96, 99.45] (n=18,871), **Backdoor** 96.74% [94.51, 98.14] (n=583).
- The weakest full-benchmark category recalls are **Fuzzers** 41.45% [35.84, 46.13] (n=6,062), **Shellcode** 51.85% [46.80, 56.97] (n=378), **Worms** 79.55% [66.65, 89.75] (n=44). High aggregate performance can hide these missed attacks.
- The weakest withheld-family recalls are **Fuzzers** 16.56% [11.78, 21.56] (n=18,184), **Reconnaissance** 25.29% [15.96, 35.43] (n=10,491), **Shellcode** 30.89% [27.62, 34.14] (n=1,133). Excluding an attack family reveals failures that familiar-category benchmark recall alone does not describe.
- Across the three declared grouped splits, recall ranges from 68.44% to 75.92%, while evaluation FPR ranges from 0.72% to 1.88%. This split sensitivity and the broad cluster intervals limit claims based on one partition.
- The frozen benchmark false-positive rate is 2.96% [2.73, 3.22], versus the 1% threshold-selection target. It is reported without benchmark-informed retuning; the validation operating point does not transfer reliably to this benchmark.
- Evidence for generalization consists of the disjoint signature subsets, three-way grouped repetitions, and all declared family-withholding outcomes above. This is internal robustness evidence, including its failures, rather than proof of prospective deployment performance.

## Experimental sample counts and signature-purge effects

| Experiment | Fit rows | Calibration rows | Evaluation rows | Development rows matching held-family signatures |
| --- | ---: | ---: | ---: | ---: |
| three_way_grouped_seed_42 | 121,493 | 23,094 | 30,754 | 0 |
| three_way_grouped_seed_43 | 108,967 | 39,362 | 27,012 | 0 |
| three_way_grouped_seed_44 | 105,754 | 41,239 | 28,348 | 0 |
| withheld_family_Analysis | 100,172 | 22,005 | 15,248 | 28,235 |
| withheld_family_Backdoor | 97,981 | 21,340 | 14,994 | 31,393 |
| withheld_family_DoS | 89,439 | 20,673 | 25,512 | 42,689 |
| withheld_family_Exploits | 85,604 | 17,252 | 46,641 | 52,226 |
| withheld_family_Fuzzers | 86,513 | 17,993 | 31,432 | 49,629 |
| withheld_family_Generic | 63,259 | 21,074 | 53,248 | 65,975 |
| withheld_family_Reconnaissance | 93,686 | 20,231 | 23,739 | 40,008 |
| withheld_family_Shellcode | 82,380 | 22,384 | 14,381 | 40,126 |
| withheld_family_Worms | 121,405 | 23,065 | 13,378 | 147 |

The last column counts all development rows matching a held family's measured signature, including its evaluation rows; it is not a count of identical physical connections or solely discarded rows. Signature exclusion can also remove normal and other attack rows from fitting/calibration when measurements coincide. This changes training size/composition substantially in some runs, so a withheld-family recall difference is not a pure causal effect of family novelty. Membership CSVs identify rows actually fitted, calibrated, evaluated or excluded.

## Uncertainty and remaining evidence

Intervals use **400** seeded draws, resampling entire ten-measurement signatures with replacement, keeping all duplicate and mixed-label rows together. Point estimates are row weighted. The fitted model and threshold remain fixed during resampling. Valid bootstrap counts and flags for sparse signature groups and boundary estimates are saved for every metric. Undefined metrics/intervals remain null; a degenerate zero-width bootstrap interval does not establish a population rate of exactly zero or one.

These intervals account for observed signature clustering, but not unobserved host/capture dependence, model/threshold selection, or full training uncertainty. Rare categories have limited distinct signatures and support. Three seed results show split sensitivity but do not estimate a new domain's performance. Family withholding is retrospective within a familiar dataset. The benchmark was previously inspected.

The supplied 45-column CSVs contain no capture timestamps, source/destination host identities, capture IDs, or verified connection identifiers. CSV-local `id` and row order are not adequate substitutes. Time, host and independent-capture splits are therefore unsupported here. [UNSW's dataset documentation](https://research.unsw.edu.au/projects/unsw-nb15-dataset) identifies original PCAP/Argus/Bro files, full CSVs, ground truth and event records. Verified mappings to that provenance are required before claiming these stronger evaluations. A representative prospective dataset, a fixed operational alarm budget, and independent capture/domain testing remain necessary.

## Reproduce and inspect

```powershell
.venv-workflow/Scripts/python.exe scripts/run_generalization_report.py
```

The command executes the new evaluation cell in a fresh kernel and saves its output into `00_netguard_complete.ipynb`; previous baseline and historical cells remain preserved. The full notebook runner also executes this section after training. Row-level predictions, exact partition memberships and an output-hash manifest are generated under `artifacts/generalization/`. Excluded family signatures are distinguished from known attack rows not used in a family run's evaluation. Run `python scripts/verify_generalization_report.py` to independently reproduce all reported point metrics from saved predictions and verify every membership/hash.

Committed evidence: [generalization.json](../data/reports/generalization.json), [all evaluation metrics and intervals](../data/reports/generalization_metrics.csv), [all category metrics and intervals](../data/reports/generalization_attack_categories.csv), [notebook execution checks](../data/reports/generalization_notebook_execution.json), and [independent verification](../data/reports/generalization_verification.json). The data and serving artifact hashes before/after must agree; full-benchmark confusion counts and original classification metrics must reproduce the prior run.

Metric and grouping definitions follow [scikit-learn 1.6 average precision](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.average_precision_score.html) and [grouped cross-validation](https://scikit-learn.org/1.6/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).
