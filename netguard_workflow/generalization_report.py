"""Render evidence and limits without inventing physical traffic provenance."""
from __future__ import annotations

from .evaluation import METRICS


def _percent(value):
    return "undefined" if value is None else f"{100*value:.2f}%"


def _estimate(row, name):
    point = _percent(row[name])
    low, high = row[f"{name}_ci_low"], row[f"{name}_ci_high"]
    return point+f" [{100*low:.2f}, {100*high:.2f}]" if low is not None else point+" [not estimable]"


def _table(rows, label="scope"):
    header = f"| {label.replace('_', ' ').title()} | Rows | Normal / attack | Signatures | Precision | Recall | F1 | PR-AUC | AP | FPR |"
    lines = [header, "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        cells = [str(row[label]), f"{row['rows']:,}", f"{row['normal_rows']:,} / {row['attack_rows']:,}",
                 f"{row['unique_signatures']:,}", *[_estimate(row, name) for name in METRICS]]
        lines.append("| "+" | ".join(cells)+" |")
    return "\n".join(lines)


def render_report(report):
    benchmark = [row for row in report["evaluation"] if row["scope"].startswith("benchmark_")]
    grouped = [row for row in report["evaluation"] if row["scope"].startswith("three_way_")]
    families = [row for row in report["evaluation"] if row["scope"].startswith("withheld_family_")]
    categories = [row for row in report["attack_categories"] if row["scope"] == "benchmark_all"]
    seen = next(row for row in benchmark if row["scope"] == "benchmark_seen_in_fit")
    unseen = next(row for row in benchmark if row["scope"] == "benchmark_unseen_in_fit")
    strict = next(row for row in benchmark if row["scope"] == "benchmark_unseen_in_any_development")
    overall = next(row for row in benchmark if row["scope"] == "benchmark_all")
    best = sorted(categories, key=lambda row: row["recall"], reverse=True)[:2]
    worst = sorted(categories, key=lambda row: row["recall"])[:3]
    hardest_withheld = sorted(families, key=lambda row: row["recall"])[:3]
    overlap = report["overlap"]
    count_table = ["| Experiment | Fit rows | Calibration rows | Evaluation rows | Development rows matching held-family signatures |",
                   "| --- | ---: | ---: | ---: | ---: |"]
    count_table.extend(f"| {run['scope']} | {run['fit_rows']:,} | {run['calibration_rows']:,} | {run['evaluation_rows']:,} | {run['excluded_family_signature_rows']:,} |"
                       for run in report["experiments"])
    lines = ["# Performance on unfamiliar traffic", "",
        "This report evaluates the unchanged original benchmark with the frozen serving model, then refits the same fixed design for additional internal robustness experiments. Every original notebook cell remains preserved. It reports measured-input novelty, not verified physical connection identity.", "",
        f"Serving model: **{report['serving_model']}**; fixed threshold **{report['serving_threshold']}**. Artifact SHA-256: `{report['serving_artifact_sha256']}`. The benchmark and development file hashes are recorded in the evidence. No model, ensemble weight, hyperparameter, or threshold was selected using these evaluation outcomes.", "",
        "## What the overlap means", "",
        f"The audit's **{100*overlap['historical_selected_feature_overlap_fraction']:.2f}%** overlap ({overlap['historical_selected_feature_overlap_rows']:,}/{overlap['benchmark_rows']:,}) describes matches in the earlier selected/engineered predictor representation. It does **not** establish identical physical connections. The current model uses ten raw measurements and 29 deterministic predictors, so its signature definition and overlap differ.", "",
        f"The current ten-measurement signature appears in actual model-fitting data for **{overlap['seen_in_actual_fit_rows']:,}** benchmark rows, and anywhere in development (fit plus threshold-selection validation) for **{overlap['seen_in_any_development_rows']:,}**. Exact float64 equality joins verify hash membership. `{unseen['scope']}` is unseen by model fitting; `{strict['scope']}` additionally excludes signatures encountered during threshold selection. The latter is a benchmark subset with changed composition, not a replacement for the original benchmark.", "",
        "## Frozen benchmark results", "",
        "Every estimate below is a percentage followed by a 95% signature-cluster percentile bootstrap interval in brackets. AP is non-interpolated average precision; PR-AUC is the trapezoidal area and is reported separately. Tables include all rows, including repeats, at their original prevalence.", "", _table(benchmark), "",
        "## Attack-category detection on the full original benchmark", "",
        "Each row compares that attack category with **all normal benchmark rows**, excluding other attacks. Recall is the fraction of that category detected. Precision, F1 and ranking metrics depend on this constructed category-versus-normal prevalence, and are not multiclass category-identification metrics. FPR uses the same normal rows in each row. All counts and category tables for seen/unseen slices and additional experiments are in the CSV/JSON evidence.", "",
        _table(categories, "attack_category"), "",
        "## Additional signature-disjoint three-way evaluation", "",
        "The previously selected architecture, parameters, equal ensemble weights and feature contract are frozen before these runs. Five stratified signature folds partition **development only**: fold 0 evaluates, fold 1 selects the 1% empirical false-positive-budget threshold, and folds 2–4 fit features/scaling/model. Seeds 42, 43 and 44 were declared before running; all results are retained. All three partitions are pairwise signature-disjoint. Fitting and threshold selection never use the evaluation partition. This removes threshold reuse within each run; the previously inspected dataset and design history still prevent an untouched-final-test claim. Repeated evaluations overlap across seeds, so their intervals must not be pooled as independent runs.", "", _table(grouped), "",
        "## Withheld attack families", "",
        "Run every one of the nine attack families separately. Using seed 42's three-way folds, remove **every signature matching any held-family row** from both fitting and threshold calibration. Evaluate all held-family rows against fold-0 normal traffic. Model design remains fixed, and calibration includes only normal traffic and the remaining known attack families. No held-family labels/scores are used in model fitting or threshold choice. This tests withheld-category detection within the same source dataset; it does not establish detection of arbitrary novel attacks in a new environment.", "", _table(families), "",
        "Separate normal-only Isolation Forest and novelty LOF experiments remain available in `SUPERVISED_COMPARISON.md`. Their Backdoor recall was only 3.44% and 8.08%, respectively; they do not provide strong generalization evidence.", "",
        "## Where the model works and fails", "",
        f"- Among fitting-seen signatures, attack recall is {_estimate(seen, 'recall')}; among fitting-unseen signatures it is {_estimate(unseen, 'recall')}. On the stricter development-unseen subset it is {_estimate(strict, 'recall')}. Signature novelty therefore has measurable performance consequences; different slice prevalences also affect precision and PR-AUC.",
        "- The strongest full-benchmark category recalls are "+", ".join(f"**{row['attack_category']}** {_estimate(row, 'recall')} (n={row['attack_rows']:,})" for row in best)+".",
        "- The weakest full-benchmark category recalls are "+", ".join(f"**{row['attack_category']}** {_estimate(row, 'recall')} (n={row['attack_rows']:,})" for row in worst)+". High aggregate performance can hide these missed attacks.",
        "- The weakest withheld-family recalls are "+", ".join(f"**{row['scope'].removeprefix('withheld_family_')}** {_estimate(row, 'recall')} (n={row['attack_rows']:,})" for row in hardest_withheld)+". Excluding an attack family reveals failures that familiar-category benchmark recall alone does not describe.",
        f"- Across the three declared grouped splits, recall ranges from {_percent(min(row['recall'] for row in grouped))} to {_percent(max(row['recall'] for row in grouped))}, while evaluation FPR ranges from {_percent(min(row['false_positive_rate'] for row in grouped))} to {_percent(max(row['false_positive_rate'] for row in grouped))}. This split sensitivity and the broad cluster intervals limit claims based on one partition.",
        f"- The frozen benchmark false-positive rate is {_estimate(overall, 'false_positive_rate')}, versus the 1% threshold-selection target. It is reported without benchmark-informed retuning; the validation operating point does not transfer reliably to this benchmark.",
        "- Evidence for generalization consists of the disjoint signature subsets, three-way grouped repetitions, and all declared family-withholding outcomes above. This is internal robustness evidence, including its failures, rather than proof of prospective deployment performance.", "",
        "## Experimental sample counts and signature-purge effects", "", "\n".join(count_table), "",
        "The last column counts all development rows matching a held family's measured signature, including its evaluation rows; it is not a count of identical physical connections or solely discarded rows. Signature exclusion can also remove normal and other attack rows from fitting/calibration when measurements coincide. This changes training size/composition substantially in some runs, so a withheld-family recall difference is not a pure causal effect of family novelty. Membership CSVs identify rows actually fitted, calibrated, evaluated or excluded.", "",
        "## Uncertainty and remaining evidence", "",
        f"Intervals use **{report['uncertainty']['repetitions']}** seeded draws, resampling entire ten-measurement signatures with replacement, keeping all duplicate and mixed-label rows together. Point estimates are row weighted. The fitted model and threshold remain fixed during resampling. Valid bootstrap counts and flags for sparse signature groups and boundary estimates are saved for every metric. Undefined metrics/intervals remain null; a degenerate zero-width bootstrap interval does not establish a population rate of exactly zero or one.", "",
        "These intervals account for observed signature clustering, but not unobserved host/capture dependence, model/threshold selection, or full training uncertainty. Rare categories have limited distinct signatures and support. Three seed results show split sensitivity but do not estimate a new domain's performance. Family withholding is retrospective within a familiar dataset. The benchmark was previously inspected.", "",
        "The supplied 45-column CSVs contain no capture timestamps, source/destination host identities, capture IDs, or verified connection identifiers. CSV-local `id` and row order are not adequate substitutes. Time, host and independent-capture splits are therefore unsupported here. [UNSW's dataset documentation](https://research.unsw.edu.au/projects/unsw-nb15-dataset) identifies original PCAP/Argus/Bro files, full CSVs, ground truth and event records. Verified mappings to that provenance are required before claiming these stronger evaluations. A representative prospective dataset, a fixed operational alarm budget, and independent capture/domain testing remain necessary.", "",
        "## Reproduce and inspect", "",
        "```powershell", ".venv-workflow/Scripts/python.exe scripts/run_generalization_report.py", "```", "",
        "The command executes the new evaluation cell in a fresh kernel and saves its output into `00_netguard_complete.ipynb`; previous baseline and historical cells remain preserved. The full notebook runner also executes this section after training. Row-level predictions, exact partition memberships and an output-hash manifest are generated under `artifacts/generalization/`. Excluded family signatures are distinguished from known attack rows not used in a family run's evaluation. Run `python scripts/verify_generalization_report.py` to independently reproduce all reported point metrics from saved predictions and verify every membership/hash.", "",
        "Committed evidence: [generalization.json](../data/reports/generalization.json), [all evaluation metrics and intervals](../data/reports/generalization_metrics.csv), [all category metrics and intervals](../data/reports/generalization_attack_categories.csv), [notebook execution checks](../data/reports/generalization_notebook_execution.json), and [independent verification](../data/reports/generalization_verification.json). The data and serving artifact hashes before/after must agree; full-benchmark confusion counts and original classification metrics must reproduce the prior run.", "",
        "Metric and grouping definitions follow [scikit-learn 1.6 average precision](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.average_precision_score.html) and [grouped cross-validation](https://scikit-learn.org/1.6/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).", ""]
    nonconverged = [run["scope"] for run in report["experiments"] if not run["converged"]]
    if nonconverged:
        lines.extend(["**Optimization limitation:** these frozen-design fits did not converge: "+", ".join(nonconverged)+". Their outcomes are retained and flagged; no evaluation-informed rescue/tuning was performed.", ""])
    return "\n".join(lines)
