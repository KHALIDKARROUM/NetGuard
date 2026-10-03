# Supervised comparison and ensemble decision

The current sections in `00_netguard_complete.ipynb` train and evaluate all five
candidates. All original notebook cells remain preserved as historical reference.
The tables below are from the current reproducible run, not the historical
test-informed anomaly ensemble.

## Same data and preprocessing

Each candidate uses 144,587 fitting rows and 30,754 grouped validation rows from
the development CSV. Exact signatures across the ten measured inputs remain in
one partition; labels and attack categories are excluded from predictors.
Every candidate shares the same 29 raw physical features and **the same fitted
StandardScaler**. Features, scaling and scoring are packaged with its threshold.

StandardScaler replaces the earlier robust scaling for this comparison: the
linear model reached its 2,000-iteration limit with robust scaling but converged
in 194 iterations with standardization. This was an optimization check on fitting
data, not a choice based on benchmark metrics. All final candidates converged.
Shared feature computation and output scores use float64. Random forest's internal
precision follows scikit-learn consistently in training/inference; its trees are
fitted with two workers, then scored with one worker for deterministic summation.

Settings are fixed in `WorkflowConfig`: seed 42; logistic regression C=1, L2,
lbfgs, tolerance `1e-5`, up to 2,000 iterations; random forest 200 trees, depth
20, minimum leaf size 2, square-root feature sampling; histogram gradient boosting
150 iterations, 31 leaves, L2=1, early stopping disabled. No benchmark optimization
or validation refit occurs. Full estimator parameters are saved in the report.

Every candidate receives its own fixed threshold, selected for maximum attack
recall under **at most 1% empirical validation false-positive rate**. Equal
recall prefers fewer false positives, then the higher threshold. All score ties
move together. The dummy predicts its fitting prior; its budget-feasible decision
rejects all alerts, making the no-skill reference explicit.

## Validation comparison

Percentages below are classification metrics; times are milliseconds.

| Candidate | Accuracy | Balanced accuracy | Precision | Recall | F1 | ROC-AUC | AP | False positives | FPR | Single median / p95 | 256-row batch median / p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy prior | 43.08% | 50.00% | 0.00% | 0.00% | 0.00% | 0.5000 | 0.5692 | 0 | 0.000% | 28.79 / 63.66 | 30.10 / 61.82 |
| Logistic regression | 45.76% | 52.25% | 88.87% | 5.38% | 10.15% | 0.9344 | 0.9314 | 118 | 0.891% | 28.94 / 33.23 | 30.11 / 33.32 |
| Random forest | 82.81% | 84.78% | 98.94% | 70.55% | 82.37% | 0.9819 | 0.9851 | 132 | 0.996% | 87.34 / 136.87 | 101.06 / 130.98 |
| Gradient boosting | 84.71% | 86.53% | 99.67% | 73.38% | 84.53% | 0.9354 | 0.9531 | 42 | 0.317% | 61.05 / 75.77 | 67.89 / 76.35 |
| **Supervised soft vote** | 87.61% | 89.00% | 99.05% | 79.00% | 87.90% | 0.9714 | 0.9802 | 132 | 0.996% | 78.85 / 87.27 | 90.55 / 107.73 |

The authoritative unrounded results, thresholds, counts, timings, convergence,
training time and model sizes are in
[`supervised_validation_comparison.csv`](../data/reports/supervised_validation_comparison.csv)
and [`supervised_comparison.json`](../data/reports/supervised_comparison.json).
The API comparison response and dashboard validation tab expose the same saved
table. Candidate pipelines are generated under `artifacts/notebook_workflow/candidates/`.

## Full prediction latency

All timings call the actual `predict_raw` serving path on raw measurements.
They include feature creation, fitted scaling, score calculation, the threshold,
contract/thread checks and result construction. Input frames and models are
already loaded. Artifact loading, HTTP validation/transport and network time
are excluded. One single/batch warmup precedes 11 alternating repetitions.
Batch measurements use the same 256 deterministic validation rows for every
candidate. The report saves the machine/runtime, median, descriptive p95,
batch size and time per row. These are hardware-dependent sample measurements,
not service-level latency guarantees. Candidate artifact sizes include its
pipeline and core contract; the deployed artifact also contains report metadata.

## Why the supervised ensemble was retained

Compare one declared equal-weight average of the three supervised classifiers.
Its members reuse the already fitted models and shared preprocessing; weights
are not learned or searched. The earlier Isolation Forest/LOF/autoencoder ensemble
is historical and is not served or claimed comparable to this experiment.

Before benchmark evaluation, require both: at least **0.02 absolute validation
recall gain** over the best eligible individual, and median 256-row prediction
latency no more than **2x** that individual. Fits must converge and satisfy the
validation false-positive budget. These policy constants are adjustable before
a new development run, not retrospectively to fit benchmark results.

The soft vote gained **0.05615 recall (5.62 percentage points)** over gradient
boosting and took **1.3338x batch latency**, so it passed both rules. It becomes
the shared API artifact with fixed threshold **0.8631127466983196**. Storage
and memory are a substantial additional cost: about **63.6 MB** versus **0.6 MB**
for gradient boosting. The decision is based on this one validation split and
does not establish independent statistical significance or production readiness.

## Frozen benchmark results

All models and thresholds are frozen before reading benchmark performance.
The benchmark was previously inspected and is not an untouched final holdout.

| Candidate | Accuracy | Precision | Recall | F1 | False positives | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dummy prior | 44.94% | 0.00% | 0.00% | 0.00% | 0 | 0.000% |
| Logistic regression | 49.04% | 74.30% | 11.40% | 19.76% | 1,787 | 4.830% |
| Random forest | 90.31% | 97.36% | 84.69% | 90.59% | 1,039 | 2.808% |
| Gradient boosting | 90.56% | 99.35% | 83.41% | 90.68% | 248 | 0.670% |
| Supervised soft vote | 91.24% | 97.28% | 86.51% | 91.58% | 1,095 | 2.959% |

See [`supervised_benchmark_comparison.csv`](../data/reports/supervised_benchmark_comparison.csv)
for all metrics and counts. The selected model exceeds the 1% budget here;
this is reported without benchmark-informed retuning. The discrepancy requires
new representative traffic and prospective assessment before operational use.

## Anomaly detectors for unfamiliar attacks

Keep Isolation Forest and novelty LOF as separate normal-only experiments.
`run_unfamiliar_attack_experiment.py` removes a declared attack family **and
every matching raw-input signature** from model fitting and normal threshold
calibration. It uses only the development CSV, the same grouped split and raw
feature contract. Both detectors share a scaler fitted on a fixed sample of up
to 5,000 normal fitting rows. This cap keeps the LOF reference cost explicit.
Set `novelty=True` and score only groups absent from LOF fitting data.

Choose a fixed threshold using normal validation scores alone, admitting no more
than 1% false positives; use higher native anomaly scores for alerts. Held-out
attack labels are used only for reporting recall, not threshold choice. Save
native-score settings and separate experimental artifacts; these are not serving
bundles and cannot replace the deployed model through `PredictionService`.

```powershell
.venv-workflow/Scripts/python.exe scripts/run_unfamiliar_attack_experiment.py --family Backdoor
```

The Backdoor example withholds 1,746 attack rows. Both detectors achieve about
0.994% normal-validation false positives, while held-out recall is only **3.44%**
for Isolation Forest and **8.08%** for novelty LOF. Evidence and sample counts are
in [`unfamiliar_attack_backdoor.json`](../data/reports/unfamiliar_attack_backdoor.json).
These poor results do not support treating an anomaly detector as a reliable
unknown-attack detector. Repeat prespecified families, quantify uncertainty,
and obtain capture/host provenance before broader claims. All historical
detector notebooks and artifacts remain reference material.

This workflow follows scikit-learn's documentation for
[supervised ensembles](https://scikit-learn.org/stable/modules/ensemble.html),
[computation and latency](https://scikit-learn.org/stable/computing/computational_performance.html),
and [novelty LOF on unseen observations](https://scikit-learn.org/stable/modules/outlier_detection.html).
