"""Behaviour checks for the two additional standalone notebook classifiers."""
import ast
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import QuantileTransformer, StandardScaler
from sklearn.utils.validation import check_is_fitted


AVAILABLE = all(importlib.util.find_spec(name) for name in ("torch", "tabm", "lightgbm"))
if AVAILABLE:
    import torch
    from tabm import TabM
    from lightgbm import LGBMClassifier

ROOT = Path(__file__).resolve().parents[1]


def notebook_types():
    notebook = json.loads((ROOT / "notebooks/00_netguard_complete.ipynb").read_text(encoding="utf-8"))
    source = "".join(next(c for c in notebook["cells"] if c["id"] == "upgraded-model-implementation")["source"])
    names = {"NativeBoostingClassifier", "IdentityFeatureScaler", "QuantileStandardScaler",
             "GroupedNeuralClassifier", "GroupedTabMClassifier"}
    namespace = dict(globals(), __name__="notebook_tabm_test")
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<notebook-tabm>", "exec"), namespace)
    return namespace["GroupedTabMClassifier"], namespace["NativeBoostingClassifier"]


@unittest.skipUnless(AVAILABLE, "Install the locked notebook environment for LightGBM/TabM checks")
class AdditionalNotebookModelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tabm_type, cls.boosting_type = notebook_types()
        rng = np.random.default_rng(27)
        values = rng.uniform(0, 100, (300, 4))
        values[:, 3] = rng.uniform(-1, 1, len(values))
        labels = (values[:, 0] + values[:, 1] > 100).astype(int)
        cls.X = pd.DataFrame(np.vstack([values, values[:30]]), columns=list("abcd"))
        cls.y = np.r_[labels, 1 - labels[:30]]
        cls.calls = []
        original = cls.tabm_type.train_epoch

        def record_epoch(model, network, optimizer, features, targets, generator):
            cls.calls.append(len(features))
            return original(model, network, optimizer, features, targets, generator)

        cls.tabm_type.train_epoch = record_epoch
        try:
            cls.model = cls.tabm_type(k=4, width=16, n_blocks=2, max_epochs=3,
                patience=2, batch_size=64, threads=2, seed=17).fit(cls.X, cls.y)
        finally:
            cls.tabm_type.train_epoch = original

    def test_inner_groups_are_disjoint_and_monitor_preprocessing_uses_only_inner_fit(self):
        groups = pd.util.hash_pandas_object(self.X, index=False).to_numpy()
        fitting, monitoring = self.model.inner_fit_indices_, self.model.inner_monitor_indices_
        self.assertEqual(np.intersect1d(groups[fitting], groups[monitoring]).size, 0)
        compressed = np.sign(self.X.to_numpy()) * np.log1p(np.abs(self.X.to_numpy()))
        expected = QuantileTransformer(n_quantiles=min(1000, len(fitting)),
            output_distribution="normal", subsample=None, random_state=17).fit(compressed[fitting])
        np.testing.assert_allclose(self.model.monitor_scaler_.quantile_.quantiles_, expected.quantiles_)
        self.assertFalse(self.model.inner_split_["monitor_uses_outer_validation"])

    def test_final_refit_trains_all_rows_for_the_selected_duration(self):
        self.assertEqual(self.calls.count(len(self.X)), self.model.selected_epochs_)
        self.assertEqual(self.calls.count(len(self.model.inner_fit_indices_)), len(self.model.history_))
        compressed = np.sign(self.X.to_numpy()) * np.log1p(np.abs(self.X.to_numpy()))
        expected = QuantileTransformer(n_quantiles=len(compressed), output_distribution="normal",
            subsample=None, random_state=17).fit(compressed)
        np.testing.assert_allclose(self.model.scaler_.quantile_.quantiles_, expected.quantiles_)
        self.assertFalse(self.model.network_.training)
        self.assertEqual(next(self.model.network_.parameters()).dtype, torch.float64)

    def test_each_member_receives_its_own_training_gradient(self):
        logits = torch.tensor([[[3.0], [-3.0]]], dtype=torch.float64, requires_grad=True)
        labels = torch.tensor([1.0], dtype=torch.float64)
        loss = self.model.member_loss(logits, labels)
        loss.backward()
        # Both members must learn: averaging predictions before loss would hide
        # the confident wrong member behind the confident correct member.
        self.assertLess(logits.grad[0, 1, 0].item(), logits.grad[0, 0, 0].item())
        averaged_prediction_loss = -torch.log(torch.sigmoid(logits.detach()).mean()).item()
        self.assertGreater(loss.item(), averaged_prediction_loss)

    def test_probabilities_average_member_sigmoids_and_are_batch_independent(self):
        batch = self.model.predict_proba(self.X.iloc[:12])
        singles = np.vstack([self.model.predict_proba(self.X.iloc[[i]]) for i in range(12)])
        np.testing.assert_allclose(batch, singles, rtol=0, atol=1e-12)
        raw = self.X.iloc[:12].to_numpy()
        features = self.model.scaler_.transform(np.sign(raw) * np.log1p(np.abs(raw)))
        with torch.inference_mode():
            expected = torch.sigmoid(self.model.network_(torch.as_tensor(features))).mean(dim=1).squeeze(-1).numpy()
        np.testing.assert_allclose(batch[:, 1], expected, rtol=0, atol=1e-12)
        np.testing.assert_allclose(batch.sum(axis=1), 1, rtol=0, atol=1e-12)
        self.assertFalse(hasattr(clone(self.model), "network_"))

    def test_lightgbm_wrapper_fits_and_clones_without_carrying_training_state(self):
        model = self.boosting_type("lightgbm", {"n_estimators": 10, "num_leaves": 7,
            "min_child_samples": 10, "random_state": 17, "n_jobs": 2,
            "deterministic": True, "force_col_wise": True, "verbosity": -1})
        model.fit(self.X, self.y)
        scores = model.predict_proba(self.X)
        self.assertEqual(scores.shape, (len(self.X), 2))
        np.testing.assert_allclose(scores.sum(axis=1), 1, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(model.classes_, [0, 1])
        self.assertFalse(hasattr(clone(model), "model_"))


if __name__ == "__main__":
    unittest.main()
