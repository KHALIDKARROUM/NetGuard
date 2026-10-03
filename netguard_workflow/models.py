"""A fixed soft-voting experiment using the same fitted supervised baselines."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.utils.validation import check_is_fitted


class MeanProbabilityClassifier(ClassifierMixin, BaseEstimator):
    """Average member attack scores with fixed equal weights, without tuning.

    Shared feature creation and scaling stay outside this classifier. The
    from_fitted constructor reuses the already fitted comparison models, so
    ensemble evaluation cannot refit on validation or benchmark measurements.
    """
    def __init__(self, estimators):
        self.estimators = estimators

    @classmethod
    def from_fitted(cls, estimators):
        instance = cls(estimators)
        instance._set_fitted_members([estimator for _, estimator in estimators])
        return instance

    def fit(self, X, y):
        self._set_fitted_members([clone(estimator).fit(X, y) for _, estimator in self.estimators])
        return self

    def _set_fitted_members(self, members):
        if not members or len(members) != len(self.estimators):
            raise ValueError("Supply at least one named fitted classifier.")
        for member in members:
            check_is_fitted(member)
            if not np.array_equal(member.classes_, [0, 1]):
                raise ValueError("Every member must use 0=normal, 1=attack in that order.")
        dimensions = {member.n_features_in_ for member in members}
        if len(dimensions) != 1:
            raise ValueError("Every member must use the same fitted predictor dimensions.")
        self.estimators_ = members
        self.member_names_ = [name for name, _ in self.estimators]
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = dimensions.pop()

    def predict_proba(self, X):
        check_is_fitted(self)
        return np.mean([member.predict_proba(X) for member in self.estimators_], axis=0, dtype=np.float64)

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(np.int8)
