from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURE_COLUMNS = (
    "momentum_21",
    "volatility_21",
    "volume_trend",
    "drawdown_63",
    "relative_strength_63",
    "news_sentiment",
    "news_count",
    "news_shock",
)


@dataclass(frozen=True)
class RankingModel:
    estimator: RandomForestClassifier
    feature_names: tuple[str, ...]

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        missing = [name for name in self.feature_names if name not in features.columns]
        if missing:
            raise ValueError(f"missing features: {missing}")
        matrix = features.loc[:, list(self.feature_names)].astype(float)
        return self.estimator.predict_proba(matrix)[:, 1]

    def save(self, path: str | Path) -> None:
        joblib.dump(
            {
                "estimator": self.estimator,
                "feature_names": self.feature_names,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "RankingModel":
        payload = joblib.load(path)
        return cls(
            estimator=payload["estimator"],
            feature_names=tuple(payload["feature_names"]),
        )


def train_ranker(
    features: pd.DataFrame,
    labels: pd.Series,
    *,
    random_state: int = 42,
) -> RankingModel:
    missing = [name for name in FEATURE_COLUMNS if name not in features.columns]
    if missing:
        raise ValueError(f"missing features: {missing}")
    if len(features) != len(labels):
        raise ValueError("features and labels must align")
    if labels.nunique() < 2:
        raise ValueError("labels must contain both classes")
    estimator = RandomForestClassifier(
        n_estimators=200,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    estimator.fit(features.loc[:, list(FEATURE_COLUMNS)], labels.astype(int))
    return RankingModel(estimator=estimator, feature_names=FEATURE_COLUMNS)
