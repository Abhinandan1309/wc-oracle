"""
Update Elo ratings with actual WC 2026 results (K=40 for World Cup).
Run after every scrape cycle so the simulation uses current team strengths.
"""
import json
import pandas as pd
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
LIVE_DIR   = BASE_DIR / "data" / "live"
MODELS_DIR = BASE_DIR / "models"

ELO_LIVE_JSON = LIVE_DIR / "elo_live.json"
SCHEDULE_CSV  = LIVE_DIR / "schedule_2026.csv"
K_WC = 40.0   # FIFA World Cup K-factor (high-stakes tournament)


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


def update_elo() -> dict:
    """
    Load base Elo from models/, apply every WC 2026 played result in
    chronological order, save result to data/live/elo_live.json.
    """
    with open(MODELS_DIR / "elo_ratings.json") as f:
        ratings: dict[str, float] = json.load(f)

    if not SCHEDULE_CSV.exists():
        print("  schedule_2026.csv not found — keeping base Elo.")
        return ratings

    df = pd.read_csv(SCHEDULE_CSV)
    played = df[df["played"] == True].copy()

    if "date" in played.columns:
        played = played.sort_values("date", na_position="last")

    n = 0
    for _, row in played.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        try:
            hs  = int(row["home_score"])
            as_ = int(row["away_score"])
        except (ValueError, TypeError):
            continue

        ra  = ratings.get(home, 1500.0)
        rb  = ratings.get(away, 1500.0)
        exp = _expected(ra, rb)

        sa = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)

        ratings[home] = ra + K_WC * (sa       - exp)
        ratings[away] = rb + K_WC * ((1 - sa) - (1 - exp))
        n += 1

    with open(ELO_LIVE_JSON, "w") as f:
        json.dump(ratings, f, indent=2)

    print(f"  Elo updated: {n} WC 2026 results applied -> {ELO_LIVE_JSON.name}")
    return ratings


if __name__ == "__main__":
    update_elo()
