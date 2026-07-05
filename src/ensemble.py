import json
import numpy as np
import pandas as pd
from itertools import product
from pathlib import Path
from scipy.optimize import minimize
from sklearn.metrics import accuracy_score, log_loss

from feature_engineering import FEATURE_COLS, normalise, FIFA_RANKINGS_2026, DEFAULT_RANKING
from models import XGBoostWCModel, PoissonGoalModel, EloWCModel, MODELS_DIR, PROCESSED_DIR

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Ensemble model
# --------------------------------------------------------------------------- #
class EnsembleModel:
    """
    Weighted average of XGBoost (A), Poisson (B), Elo (C).
    Default weights: 40% / 35% / 25%.
    Weights are tuned on the 2022 WC holdout set.
    """
    DEFAULT_WEIGHTS = (0.40, 0.35, 0.25)

    def __init__(self):
        self.xgb = XGBoostWCModel()
        self.poisson = PoissonGoalModel()
        self.elo = EloWCModel()
        self.weights = list(self.DEFAULT_WEIGHTS)
        self.val_accuracy: float | None = None
        self.val_logloss: float | None = None

    # ----- load sub-models from disk -----
    def load_models(self):
        self.xgb.load()
        self.poisson.load()
        self.elo.load()
        return self

    # ----- core prediction -----
    def _predict_row(self, home: str, away: str, features: dict | None = None) -> np.ndarray:
        """
        Returns [p_away_win, p_draw, p_home_win] as weighted ensemble.
        features: dict of FEATURE_COLS values (required for XGBoost).
        """
        home = normalise(home)
        away = normalise(away)

        wa, wb, wc = self.weights

        # Model A — XGBoost
        if features is not None:
            p_xgb = self.xgb.predict_single(features)
        else:
            # Fallback: equal priors if no features provided
            p_xgb = np.array([1/3, 1/3, 1/3])

        # Model B — Poisson
        p_poi = self.poisson.predict_proba(home, away)

        # Model C — Elo
        p_elo = self.elo.predict_proba(home, away)

        combined = wa * p_xgb + wb * p_poi + wc * p_elo
        return combined / combined.sum()

    def predict_proba(self, home: str, away: str, features: dict | None = None) -> dict:
        """
        Returns a dict with keys: home_win, draw, away_win, home_team, away_team.
        """
        probs = self._predict_row(home, away, features)
        return {
            "home_team":  normalise(home),
            "away_team":  normalise(away),
            "away_win":   round(float(probs[0]), 4),
            "draw":       round(float(probs[1]), 4),
            "home_win":   round(float(probs[2]), 4),
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        df must have home_team, away_team + FEATURE_COLS columns.
        Returns df with added probability columns.
        """
        rows = []
        for _, row in df.iterrows():
            feat = {c: row.get(c, 0) for c in FEATURE_COLS}
            p = self._predict_row(row["home_team"], row["away_team"], feat)
            rows.append({
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "p_away_win": round(float(p[0]), 4),
                "p_draw":     round(float(p[1]), 4),
                "p_home_win": round(float(p[2]), 4),
                "predicted_result": int(np.argmax(p)),
            })
        return pd.DataFrame(rows)

    # ----- weight tuning -----
    def tune_weights(self, val_df: pd.DataFrame) -> list[float]:
        """
        Grid-search / Nelder-Mead optimisation of weights on the 2022 holdout.
        Minimises log-loss of ensemble predictions.
        """
        print("Tuning ensemble weights on 2022 holdout...")

        # Pre-compute sub-model probabilities for validation set
        p_xgb_all = self.xgb.predict_proba(val_df[FEATURE_COLS].fillna(0))
        p_poi_all = np.array([self.poisson.predict_proba(r["home_team"], r["away_team"])
                               for _, r in val_df.iterrows()])
        p_elo_all = np.array([self.elo.predict_proba(r["home_team"], r["away_team"])
                               for _, r in val_df.iterrows()])
        y_true = val_df["result"].astype(int).values

        def neg_logloss(w):
            w = np.abs(w)
            w = w / w.sum()
            combined = w[0] * p_xgb_all + w[1] * p_poi_all + w[2] * p_elo_all
            combined = combined / combined.sum(axis=1, keepdims=True)
            return log_loss(y_true, combined)

        result = minimize(
            neg_logloss,
            x0=self.DEFAULT_WEIGHTS,
            method="Nelder-Mead",
            options={"maxiter": 1000, "xatol": 1e-5, "fatol": 1e-5},
        )
        w_opt = np.abs(result.x)
        w_opt /= w_opt.sum()
        self.weights = list(w_opt.round(4))

        # Evaluate tuned ensemble on 2022
        combined = (w_opt[0] * p_xgb_all + w_opt[1] * p_poi_all + w_opt[2] * p_elo_all)
        combined /= combined.sum(axis=1, keepdims=True)
        preds = combined.argmax(axis=1)
        self.val_accuracy = accuracy_score(y_true, preds)
        self.val_logloss = log_loss(y_true, combined)

        print(f"  Tuned weights  : XGB={self.weights[0]:.3f}  Poisson={self.weights[1]:.3f}  Elo={self.weights[2]:.3f}")
        print(f"  Val accuracy   : {self.val_accuracy:.4f}")
        print(f"  Val log-loss   : {self.val_logloss:.4f}")
        return self.weights

    def save(self):
        cfg = {
            "weights": self.weights,
            "val_accuracy": self.val_accuracy,
            "val_logloss": self.val_logloss,
        }
        with open(MODELS_DIR / "ensemble_config.json", "w") as f:
            json.dump(cfg, f, indent=2)

    def load(self):
        cfg_path = MODELS_DIR / "ensemble_config.json"
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = json.load(f)
            self.weights = cfg.get("weights", list(self.DEFAULT_WEIGHTS))
            self.val_accuracy = cfg.get("val_accuracy")
            self.val_logloss = cfg.get("val_logloss")
        self.load_models()
        return self


# --------------------------------------------------------------------------- #
# Run: train all models → tune ensemble → evaluate
# --------------------------------------------------------------------------- #
def run():
    print("=" * 55)
    print("  FIFA WC 2026 Predictor — Step 3+4: Ensemble")
    print("=" * 55 + "\n")

    from models import train_all
    xgb, poisson_model, elo_model, train_df, val_df = train_all()

    ensemble = EnsembleModel()
    ensemble.xgb = xgb
    ensemble.poisson = poisson_model
    ensemble.elo = elo_model

    # --- Tune weights on 2022 holdout ---
    ensemble.tune_weights(val_df)
    ensemble.save()

    # --- Per-model comparison on 2022 ---
    print("\n--- Per-model accuracy on 2022 WC holdout ---")
    models_acc = {
        "XGBoost":  xgb.val_accuracy,
        "Poisson":  poisson_model.val_accuracy,
        "Elo":      elo_model.val_accuracy,
        "Ensemble": ensemble.val_accuracy,
    }
    for name, acc in models_acc.items():
        bar = "#" * int((acc or 0) * 40)
        print(f"  {name:<10} {acc:.4f}  {bar}")

    # --- Sample predictions ---
    print("\n--- Sample 2026 match predictions ---")
    sample_matches = [
        ("France",    "Argentina"),
        ("Brazil",    "Germany"),
        ("England",   "Spain"),
        ("Mexico",    "USA"),
        ("Portugal",  "Netherlands"),
    ]
    print(f"  {'Match':<30} {'Home Win':>9} {'Draw':>7} {'Away Win':>9}")
    print("  " + "-" * 55)
    for home, away in sample_matches:
        p = ensemble.predict_proba(home, away)
        print(f"  {home:<15} vs {away:<12}  {p['home_win']:>8.1%}  {p['draw']:>6.1%}  {p['away_win']:>8.1%}")

    # --- Predict all upcoming 2026 matches ---
    future_path = PROCESSED_DIR / "features_2026.csv"
    if future_path.exists():
        future_df = pd.read_csv(future_path)
        future_df["home_team"] = future_df["home_team"].map(normalise)
        future_df["away_team"] = future_df["away_team"].map(normalise)
        preds = ensemble.predict_batch(future_df)
        out = future_df[["stage", "group", "home_team", "away_team"]].join(
            preds[["p_home_win", "p_draw", "p_away_win", "predicted_result"]]
        )
        out_path = PROCESSED_DIR / "predictions_2026.csv"
        out.to_csv(out_path, index=False)
        print(f"\n  Saved predictions for {len(out)} upcoming matches -> {out_path.name}")

    return ensemble


if __name__ == "__main__":
    run()
