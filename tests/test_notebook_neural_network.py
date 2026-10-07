"""Behaviour checks for the notebook's supervised neural classifier."""
import ast
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, QuantileTransformer
from sklearn.utils.validation import check_is_fitted


ROOT = Path(__file__).resolve().parents[1]


def notebook_neural_types():
    notebook = json.loads((ROOT / "notebooks/00_netguard_complete.ipynb").read_text(encoding="utf-8"))
    cell = next(c for c in notebook["cells"] if c["id"] == "upgraded-model-implementation")
    source = "".join(cell["source"])
    tree = ast.parse(source)
    namespace = dict(globals(), __name__="notebook_neural_test")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"IdentityFeatureScaler", "QuantileStandardScaler", "GroupedNeuralClassifier"}:
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<notebook-neural>", "exec"), namespace)
    return namespace["IdentityFeatureScaler"], namespace["GroupedNeuralClassifier"]


class NotebookNeuralChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scaler_type, cls.model_type = notebook_neural_types()
        rng = np.random.default_rng(9)
        X = rng.uniform(0, 100, size=(500, 4))
        X[:, 3] = rng.uniform(-1, 1, 500)
        y = (X[:, 0] + X[:, 1] > 100).astype(int)
        # Repeated measurements, including conflicting labels, must stay together.
        cls.X = pd.DataFrame(np.vstack([X, X[:40]]), columns=["a", "b", "c", "balance"])
        cls.y = np.r_[y, 1 - y[:40]]
        cls.model = cls.model_type(hidden_layer_sizes=(16, 8), max_epochs=4,
                                   patience=2, batch_size=64, seed=17).fit(cls.X, cls.y)

    def test_inner_monitor_is_grouped_and_scaling_uses_inner_fit_only(self):
        groups = pd.util.hash_pandas_object(self.X, index=False).to_numpy()
        fitting, monitoring = self.model.inner_fit_indices_, self.model.inner_monitor_indices_
        self.assertEqual(np.intersect1d(groups[fitting], groups[monitoring]).size, 0)
        compressed = self.model.log_features(self.X)
        expected = QuantileTransformer(n_quantiles=min(1000, len(fitting)),
            output_distribution="normal", subsample=None, random_state=17).fit(compressed[fitting])
        np.testing.assert_allclose(self.model.monitor_scaler_.quantile_.quantiles_, expected.quantiles_)
        np.testing.assert_allclose(self.model.monitor_scaler_mean_, expected.transform(compressed[fitting]).mean(axis=0))
        self.assertFalse(self.model.inner_split_["monitor_uses_outer_validation"])

    def test_final_network_refits_all_outer_fit_rows_for_selected_epochs(self):
        compressed = self.model.log_features(self.X)
        expected = QuantileTransformer(n_quantiles=min(1000, len(compressed)),
            output_distribution="normal", subsample=None, random_state=17).fit(compressed)
        np.testing.assert_allclose(self.model.scaler_.quantile_.quantiles_, expected.quantiles_)
        np.testing.assert_allclose(self.model.scaler_.mean_, expected.transform(compressed).mean(axis=0))
        self.assertEqual(self.model.network_.t_, len(self.X) * self.model.selected_epochs_)
        self.assertLessEqual(self.model.selected_epochs_, self.model.max_epochs)
        self.assertGreaterEqual(self.model.selected_epochs_, 1)

    def test_neural_predictions_are_independent_of_batch_composition(self):
        batch = self.model.predict_proba(self.X.iloc[:12])
        singles = np.vstack([self.model.predict_proba(self.X.iloc[[i]]) for i in range(12)])
        np.testing.assert_allclose(batch, singles, rtol=0, atol=1e-12)
        np.testing.assert_allclose(batch.sum(axis=1), 1, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(self.model.classes_, [0, 1])
        self.assertTrue(np.isfinite(batch).all())

    def test_clone_discards_fitted_state_and_pipeline_keeps_its_preprocessing(self):
        fresh = clone(self.model)
        self.assertFalse(hasattr(fresh, "network_"))
        self.assertEqual(fresh.hidden_layer_sizes, (16, 8))
        scaler = self.scaler_type().fit(self.X)
        pipeline = Pipeline([("scaler", scaler), ("model", self.model)])
        np.testing.assert_allclose(pipeline.predict_proba(self.X.iloc[:8]),
                                   self.model.predict_proba(self.X.iloc[:8]), rtol=0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
