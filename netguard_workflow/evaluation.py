"""Frozen binary evaluation with measured-signature cluster uncertainty.

Signatures describe predictor equality, not connection, host or capture identity.
No model fitting or threshold choice occurs in this module.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import RAW_INPUTS
from .workflow import input_signatures

METRICS = ("precision", "recall", "f1", "pr_auc", "average_precision", "false_positive_rate")


def seen_signatures(frame, reference):
    """Verify hash membership with exact numeric equality across ten inputs."""
    hashed = np.isin(input_signatures(frame), input_signatures(reference))
    keys = pd.MultiIndex.from_frame(frame.loc[:, list(RAW_INPUTS)].astype(np.float64))
    reference_keys = pd.MultiIndex.from_frame(reference.loc[:, list(RAW_INPUTS)].astype(np.float64))
    exact = keys.isin(reference_keys)
    if not np.array_equal(hashed, exact):
        raise ValueError("Signature hash membership differs from exact predictor equality.")
    return exact


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def _weighted_metrics(labels, scores, threshold, weights, order, ends):
    alerts = scores >= threshold
    tp = float(weights[(labels == 1) & alerts].sum())
    fp = float(weights[(labels == 0) & alerts].sum())
    fn = float(weights[(labels == 1) & ~alerts].sum())
    tn = float(weights[(labels == 0) & ~alerts].sum())
    results = {"precision": _ratio(tp, tp+fp), "recall": _ratio(tp, tp+fn),
               "f1": _ratio(2*tp, 2*tp+fp+fn), "false_positive_rate": _ratio(fp, fp+tn),
               "pr_auc": None, "average_precision": None}
    # Undefined when either class is absent: an attack-only category is not a
    # ranking evaluation, so categories are evaluated against normal traffic.
    if tp+fn and fp+tn:
        w, y = weights[order], labels[order]
        cumulative_tp = np.cumsum(w * (y == 1))[ends]
        cumulative_all = np.cumsum(w)[ends]
        nonempty = cumulative_all > 0
        p = cumulative_tp[nonempty] / cumulative_all[nonempty]
        r = cumulative_tp[nonempty] / (tp+fn)
        increments = np.diff(np.r_[0., r])
        results["average_precision"] = float(np.sum(increments*p))
        results["pr_auc"] = float(np.sum(increments*(np.r_[1., p[:-1]]+p)/2))
    return results, {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def metrics_with_uncertainty(labels, scores, threshold, signatures, *, repeats=400, seed=42):
    """Row-weighted estimates and 95% percentile signature-cluster bootstrap.

    Resample whole observed signatures, including all repeated and mixed-label
    rows, with replacement. Fits and thresholds remain fixed. Intervals describe
    resampling these data, not new hosts, captures, or model-selection uncertainty.
    Undefined bootstrap statistics are omitted and their valid count reported.
    """
    y, s, g = np.asarray(labels), np.asarray(scores, dtype=np.float64), np.asarray(signatures)
    if y.ndim != 1 or s.ndim != 1 or g.ndim != 1 or not (len(y) == len(s) == len(g)):
        raise ValueError("Supply equal-length one-dimensional labels, scores and signatures.")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(s).all() or not np.isfinite(threshold):
        raise ValueError("Require binary labels and finite scores/threshold.")
    if repeats < 20:
        raise ValueError("Use at least 20 cluster bootstrap repetitions.")
    groups, inverse = np.unique(g, return_inverse=True)
    order = np.argsort(-s, kind="stable")
    ordered = s[order]
    ends = np.flatnonzero(np.r_[ordered[:-1] != ordered[1:], True]) if len(s) else np.array([], dtype=int)
    point, counts = _weighted_metrics(y, s, threshold, np.ones(len(y)), order, ends)
    result = {"rows": len(y), "normal_rows": int((y == 0).sum()), "attack_rows": int((y == 1).sum()),
              "unique_signatures": len(groups), "normal_signatures": len(np.unique(g[y == 0])),
              "attack_signatures": len(np.unique(g[y == 1])), "threshold": float(threshold),
              **counts, **point}
    draws = {name: [] for name in METRICS}
    if len(groups) > 1:
        rng = np.random.default_rng(seed)
        probabilities = np.full(len(groups), 1/len(groups))
        for _ in range(repeats):
            weights = rng.multinomial(len(groups), probabilities)[inverse]
            values, _ = _weighted_metrics(y, s, threshold, weights, order, ends)
            for name, value in values.items():
                if value is not None:
                    draws[name].append(value)
    for name in METRICS:
        values = draws[name]
        usable = len(values) >= max(20, int(.8*repeats)) and point[name] is not None
        low, high = np.percentile(values, [2.5, 97.5]) if usable else (None, None)
        result.update({f"{name}_ci_low": float(low) if low is not None else None,
                       f"{name}_ci_high": float(high) if high is not None else None,
                       f"{name}_bootstrap_valid": len(values)})
    flags = []
    if result["attack_signatures"] < 20:
        flags.append("fewer than 20 attack signatures")
    if result["normal_signatures"] < 20:
        flags.append("fewer than 20 normal signatures")
    if any(point[name] in (0., 1.) for name in METRICS):
        flags.append("boundary estimates: bootstrap may be degenerate and cannot bound unobserved outcomes")
    if len(groups) < 2:
        flags.append("fewer than two signatures: uncertainty not estimable")
    result["uncertainty_flags"] = "; ".join(flags)
    return result


def evaluate_frame(frame, scores, threshold, *, scope, repeats=400, seed=42, categories=True):
    """Every attack category versus the normal rows in the SAME evaluation scope.

    Other attacks are excluded, not mislabeled as false positives. Thus category
    precision/PR-AUC are prevalence dependent; category FPR shares normal traffic.
    """
    scores = np.asarray(scores, dtype=np.float64)
    if len(scores) != len(frame):
        raise ValueError("Scores must align positionally with evaluation rows.")
    signatures = input_signatures(frame)
    overall = {"scope": scope, **metrics_with_uncertainty(frame.label, scores, threshold, signatures,
                                                         repeats=repeats, seed=seed)}
    rows = []
    if categories:
        for index, family in enumerate(sorted(frame.loc[frame.label == 1, "attack_cat"].unique())):
            mask = ((frame.label == 0) | ((frame.label == 1) & (frame.attack_cat == family))).to_numpy()
            rows.append({"scope": scope, "attack_category": str(family),
                         "comparison": "this attack category versus normal rows in this scope; other attacks excluded",
                         **metrics_with_uncertainty(frame.label.to_numpy()[mask], scores[mask], threshold,
                                                    signatures[mask], repeats=repeats, seed=seed+index+1)})
    return overall, rows


def three_way_partition(development, *, seed=42, folds=5, held_family=None):
    """Fold 0 evaluates, fold 1 calibrates threshold, remaining folds fit.

    Held-family runs remove ALL matching signatures from fit/calibration before
    fitting, and evaluate all that family's rows against fold-0 normal traffic.
    IDs/order are never treated as timestamps or capture provenance.
    """
    from sklearn.model_selection import StratifiedGroupKFold
    if folds < 3:
        raise ValueError("Require at least three signature folds.")
    signatures = input_signatures(development)
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    assignment = np.full(len(development), -1, dtype=int)
    for fold, (_, evaluation) in enumerate(splitter.split(development, development.label, signatures)):
        assignment[evaluation] = fold
    fit = np.flatnonzero(assignment >= 2)
    calibration = np.flatnonzero(assignment == 1)
    evaluation = np.flatnonzero(assignment == 0)
    excluded = 0
    if held_family is not None:
        held = ((development.attack_cat == held_family) & (development.label == 1)).to_numpy()
        if not held.any():
            raise ValueError("The held-out attack family is absent.")
        allowed = ~np.isin(signatures, signatures[held])
        excluded = int((~allowed).sum())
        fit, calibration = fit[allowed[fit]], calibration[allowed[calibration]]
        evaluation = np.union1d(np.flatnonzero(held), evaluation[development.iloc[evaluation].label.eq(0)])
    for left, right in ((fit, calibration), (fit, evaluation), (calibration, evaluation)):
        if np.intersect1d(signatures[left], signatures[right]).size:
            raise AssertionError("Signature overlap across fitting, calibration and evaluation.")
    for indices in (fit, calibration, evaluation):
        if development.iloc[indices].label.nunique() != 2:
            raise ValueError("Every three-way partition needs both classes.")
    return fit, calibration, evaluation, {"seed": seed, "folds": folds, "held_out_family": held_family,
        "fit_rows": len(fit), "calibration_rows": len(calibration), "evaluation_rows": len(evaluation),
        "fit_signatures": len(np.unique(signatures[fit])),
        "calibration_signatures": len(np.unique(signatures[calibration])),
        "evaluation_signatures": len(np.unique(signatures[evaluation])),
        "excluded_family_signature_rows": excluded, "pairwise_signature_disjoint": True}


def partition_membership(development, fit, calibration, evaluation, *, held_family=None):
    """Distinguish family exclusions from unused known attacks in fold 0."""
    phases = np.full(len(development), "excluded_known_attack", dtype=object)
    if held_family is not None:
        signatures = input_signatures(development)
        family = ((development.label == 1) & (development.attack_cat == held_family)).to_numpy()
        phases[np.isin(signatures, signatures[family])] = "excluded_family_signature"
    phases[fit] = "fit"
    phases[calibration] = "calibration"
    phases[evaluation] = "evaluation"
    return pd.DataFrame({"row_id": development.id.to_numpy(), "partition": phases})
