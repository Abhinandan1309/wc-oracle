import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import poisson
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from feature_engineering import (
    FEATURE_COLS, ELO_BASE, build_elo_series, normalise,
    HOST_NATIONS_2026, FIFA_RANKINGS_2026, DEFAULT_RANKING,
)

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Model A — XGBoost Classifier
# --------------------------------------------------------------------------- #
class XGBoostWCModel:
    def __init__(self):
        self.model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
        )
        self.label_encoder = LabelEncoder()
        self.val_accuracy = None
        self.val_logloss = None

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame):
        X_train = train_df[FEATURE_COLS].fillna(0)
        y_train = self.label_encoder.fit_transform(train_df["result"].astype(int))

        X_val = val_df[FEATURE_COLS].fillna(0)
        y_val = self.label_encoder.transform(val_df["result"].astype(int))

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        y_pred = self.model.predict(X_val)
        y_proba = self.model.predict_proba(X_val)
        self.val_accuracy = accuracy_score(y_val, y_pred)
        self.val_logloss = log_loss(y_val, y_proba)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Returns (n, 3) array: columns = [p_away_win, p_draw, p_home_win]."""
        X_clean = X[FEATURE_COLS].fillna(0)
        raw = self.model.predict_proba(X_clean)
        # XGBoost returns columns in label_encoder order (0,1,2 = away,draw,home)
        return raw  # shape (n, 3), indices match result labels 0,1,2

    def predict_single(self, features: dict) -> np.ndarray:
        df = pd.DataFrame([features])
        return self.predict_proba(df)[0]

    def save(self):
        joblib.dump(self.model, MODELS_DIR / "xgboost_model.joblib")

    def load(self):
        self.model = joblib.load(MODELS_DIR / "xgboost_model.joblib")
        return self

    def feature_importance(self, top_n: int = 10) -> pd.Series:
        scores = self.model.feature_importances_
        return pd.Series(scores, index=FEATURE_COLS).sort_values(ascending=False).head(top_n)


# --------------------------------------------------------------------------- #
# Model B — Poisson Goal Model
# --------------------------------------------------------------------------- #
class PoissonGoalModel:
    """
    Dixon-Coles style: estimate attack/defence strengths per team,
    simulate scorelines via Poisson, derive W/D/L probabilities.
    """
    MAX_GOALS = 8
    HOME_ADVANTAGE = 1.15

    def __init__(self):
        self.attack: dict[str, float] = {}
        self.defence: dict[str, float] = {}
        self.avg_goals: float = 1.2
        self.val_accuracy: float | None = None

    def fit(self, df: pd.DataFrame):
        """Fit on completed WC matches."""
        df = df[df["home_score"].notna()].copy()
        df["home_team"] = df["home_team"].map(normalise)
        df["away_team"] = df["away_team"].map(normalise)

        total_goals = df["home_score"].sum() + df["away_score"].sum()
        total_matches = len(df)
        self.avg_goals = total_goals / (2 * total_matches)

        # Per-team stats
        stats: dict[str, dict] = {}
        for _, row in df.iterrows():
            for team, scored, conceded in [
                (row["home_team"], row["home_score"], row["away_score"]),
                (row["away_team"], row["away_score"], row["home_score"]),
            ]:
                s = stats.setdefault(team, {"scored": 0, "conceded": 0, "n": 0})
                s["scored"] += scored
                s["conceded"] += conceded
                s["n"] += 1

        for team, s in stats.items():
            n = max(s["n"], 1)
            self.attack[team] = (s["scored"] / n) / self.avg_goals
            self.defence[team] = (s["conceded"] / n) / self.avg_goals

        return self

    def _lambda(self, team: str, is_attack: bool) -> float:
        d = self.attack if is_attack else self.defence
        return d.get(team, 1.0)

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        lh = self._lambda(home, True) * self._lambda(away, False) * self.avg_goals * self.HOME_ADVANTAGE
        la = self._lambda(away, True) * self._lambda(home, False) * self.avg_goals
        return round(lh, 3), round(la, 3)

    def scoreline_matrix(self, home: str, away: str) -> np.ndarray:
        lh, la = self.expected_goals(home, away)
        g = self.MAX_GOALS + 1
        mat = np.outer(
            poisson.pmf(range(g), lh),
            poisson.pmf(range(g), la),
        )
        return mat

    def predict_proba(self, home: str, away: str) -> np.ndarray:
        """Returns [p_away_win, p_draw, p_home_win]."""
        home = normalise(home)
        away = normalise(away)
        mat = self.scoreline_matrix(home, away)
        p_home = float(np.tril(mat, -1).sum())
        p_draw = float(np.trace(mat))
        p_away = float(np.triu(mat, 1).sum())
        total = p_home + p_draw + p_away
        return np.array([p_away / total, p_draw / total, p_home / total])

    def validate(self, val_df: pd.DataFrame) -> float:
        correct = 0
        for _, row in val_df.iterrows():
            probs = self.predict_proba(row["home_team"], row["away_team"])
            pred = int(np.argmax(probs))
            if pred == int(row["result"]):
                correct += 1
        self.val_accuracy = correct / len(val_df)
        return self.val_accuracy

    def save(self):
        data = {
            "attack": self.attack,
            "defence": self.defence,
            "avg_goals": self.avg_goals,
        }
        with open(MODELS_DIR / "poisson_model.json", "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        with open(MODELS_DIR / "poisson_model.json") as f:
            data = json.load(f)
        self.attack = data["attack"]
        self.defence = data["defence"]
        self.avg_goals = data["avg_goals"]
        return self


# --------------------------------------------------------------------------- #
# Model C — Elo Rating System
# --------------------------------------------------------------------------- #
class EloWCModel:
    """
    Pure Elo-based predictor. Converts Elo difference to 3-way probabilities
    using a logistic + draw calibration fitted to historical WC outcomes.
    """
    # Fitted empirically: draw probability peaks at ~0.28 when elo_diff=0
    DRAW_BASE = 0.285
    DRAW_DECAY = 0.0003  # per Elo point squared

    def __init__(self):
        self.elo: dict[str, float] = {}
        self.val_accuracy: float | None = None

    def fit(self, df: pd.DataFrame):
        df = df[df["home_score"].notna()].copy()
        df["home_team"] = df["home_team"].map(normalise)
        df["away_team"] = df["away_team"].map(normalise)
        df = df.sort_values(["year", "stage"]).reset_index(drop=True)
        _, _, self.elo = build_elo_series(df)
        return self

    def _elo_proba(self, elo_diff: float) -> np.ndarray:
        """Convert Elo diff to [p_away_win, p_draw, p_home_win]."""
        p_home_2way = 1 / (1 + 10 ** (-elo_diff / 400))
        p_draw = max(0.05, self.DRAW_BASE - self.DRAW_DECAY * elo_diff ** 2)
        p_home = p_home_2way * (1 - p_draw)
        p_away = (1 - p_home_2way) * (1 - p_draw)
        total = p_home + p_draw + p_away
        return np.array([p_away / total, p_draw / total, p_home / total])

    def predict_proba(self, home: str, away: str) -> np.ndarray:
        """Returns [p_away_win, p_draw, p_home_win]."""
        home = normalise(home)
        away = normalise(away)
        ra = self.elo.get(home, ELO_BASE)
        rb = self.elo.get(away, ELO_BASE)
        return self._elo_proba(ra - rb)

    def predict_proba_from_diff(self, elo_diff: float) -> np.ndarray:
        return self._elo_proba(elo_diff)

    def update(self, home: str, away: str, result: int, k: float = 40.0):
        """Update Elo after a real match (result: 2=home win, 1=draw, 0=away win)."""
        home = normalise(home)
        away = normalise(away)
        ra = self.elo.get(home, ELO_BASE)
        rb = self.elo.get(away, ELO_BASE)
        score = {2: 1.0, 1: 0.5, 0: 0.0}[result]
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        self.elo[home] = ra + k * (score - ea)
        self.elo[away] = rb + k * ((1 - score) - (1 - ea))

    def validate(self, val_df: pd.DataFrame) -> float:
        correct = 0
        for _, row in val_df.iterrows():
            probs = self.predict_proba(row["home_team"], row["away_team"])
            pred = int(np.argmax(probs))
            if pred == int(row["result"]):
                correct += 1
        self.val_accuracy = correct / len(val_df)
        return self.val_accuracy

    def rankings(self, teams: list[str] | None = None) -> pd.DataFrame:
        elo_dict = self.elo if teams is None else {t: self.elo.get(normalise(t), ELO_BASE) for t in teams}
        df = pd.DataFrame(list(elo_dict.items()), columns=["team", "elo"])
        return df.sort_values("elo", ascending=False).reset_index(drop=True)

    def save(self):
        with open(MODELS_DIR / "elo_ratings.json", "w") as f:
            json.dump(self.elo, f, indent=2)

    def load(self):
        with open(MODELS_DIR / "elo_ratings.json") as f:
            self.elo = json.load(f)
        return self


# --------------------------------------------------------------------------- #
# Train & evaluate all models
# --------------------------------------------------------------------------- #
def train_all(features_path: Path | None = None) -> tuple:
    path = features_path or (PROCESSED_DIR / "features_train.csv")
    df = pd.read_csv(path)
    df["home_team"] = df["home_team"].map(normalise)
    df["away_team"] = df["away_team"].map(normalise)
    df = df[df["result"].notna()].copy()
    df["result"] = df["result"].astype(int)

    # Train/validation split: 1990-2018 train, 2022 validate
    train_df = df[df["year"] <= 2018].copy()
    val_df = df[df["year"] == 2022].copy()

    print(f"Training set : {len(train_df)} matches (1930-2018)")
    print(f"Validation   : {len(val_df)} matches (2022)\n")

    # --- Model A: XGBoost ---
    print("Training Model A — XGBoost...")
    xgb = XGBoostWCModel()
    xgb.fit(train_df, val_df)
    xgb.save()
    print(f"  Accuracy : {xgb.val_accuracy:.4f}")
    print(f"  Log-loss : {xgb.val_logloss:.4f}")
    print(f"  Top features:")
    for feat, imp in xgb.feature_importance().items():
        print(f"    {feat:<25} {imp:.4f}")

    # --- Model B: Poisson ---
    print("\nTraining Model B — Poisson Goal Model...")
    poisson_model = PoissonGoalModel()
    poisson_model.fit(train_df)
    poisson_model.validate(val_df)
    poisson_model.save()
    print(f"  Accuracy : {poisson_model.val_accuracy:.4f}")
    # Show a sample prediction
    lh, la = poisson_model.expected_goals("France", "Argentina")
    print(f"  Sample France vs Argentina: xG home={lh}, xG away={la}")
    p = poisson_model.predict_proba("France", "Argentina")
    print(f"  Probs [away_win, draw, home_win]: {p.round(3)}")

    # --- Model C: Elo ---
    print("\nTraining Model C — Elo Rating System...")
    elo_model = EloWCModel()
    elo_model.fit(train_df)
    elo_model.validate(val_df)
    elo_model.save()
    print(f"  Accuracy : {elo_model.val_accuracy:.4f}")
    p = elo_model.predict_proba("France", "Argentina")
    print(f"  Sample France vs Argentina [away_win, draw, home_win]: {p.round(3)}")

    print(f"\n  Top 10 Elo rankings after training:")
    rankings = elo_model.rankings().head(10)
    for _, row in rankings.iterrows():
        print(f"    {row['team']:<25} {row['elo']:.1f}")

    return xgb, poisson_model, elo_model, train_df, val_df


if __name__ == "__main__":
    print("=" * 55)
    print("  FIFA WC 2026 Predictor — Step 3: Models")
    print("=" * 55 + "\n")
    train_all()
