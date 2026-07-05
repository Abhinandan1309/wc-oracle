import math
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# --------------------------------------------------------------------------- #
# Team name normalisation (openfootball uses different names across years)
# --------------------------------------------------------------------------- #
NAME_MAP = {
    "Czech Republic":       "Czechia",
    "Czechoslovakia":       "Czechia",
    "Cape Verde":           "Cabo Verde",
    "Cote d'Ivoire":        "Ivory Coast",
    "Côte d'Ivoire":        "Ivory Coast",
    "IR Iran":              "Iran",
    "Korea Republic":       "South Korea",
    "Republic of Korea":    "South Korea",
    "Bosnia & Herzegovina": "Bosnia-Herzegovina",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "DR Congo":             "DR Congo",
    "Congo DR":             "DR Congo",
    "Democratic Republic of the Congo": "DR Congo",
    "United States":        "USA",
    "Curaçao":              "Curacao",
    "Curacao":              "Curacao",
    "West Germany":         "Germany",
    "Soviet Union":         "Russia",
    "Yugoslavia":           "Serbia",
    "Dutch East Indies":    "Indonesia",
    "Republic of Ireland":  "Ireland",
    "Trinidad and Tobago":  "Trinidad & Tobago",
}

# 2026 FIFA rankings (approximate, June 2026)
FIFA_RANKINGS_2026 = {
    "Argentina":        1,  "France":          2,  "England":         3,
    "Brazil":           4,  "Portugal":        5,  "Belgium":         6,
    "Netherlands":      7,  "Spain":           8,  "Germany":         9,
    "Italy":           10,  "Uruguay":        11,  "Colombia":       12,
    "USA":             13,  "Croatia":        14,  "Mexico":         15,
    "Morocco":         16,  "Switzerland":    17,  "Japan":          18,
    "Senegal":         19,  "South Korea":    20,  "Canada":         21,
    "Australia":       22,  "Turkey":         23,  "Austria":        24,
    "Ecuador":         25,  "Denmark":        26,  "Norway":         27,
    "Sweden":          28,  "Poland":         29,  "Ukraine":        30,
    "Algeria":         31,  "Tunisia":        32,  "Egypt":          33,
    "Scotland":        34,  "Qatar":          35,  "Iran":           36,
    "Ghana":           37,  "Czechia":        38,  "Saudi Arabia":   39,
    "Peru":            40,  "Panama":         41,  "Paraguay":       42,
    "Iraq":            43,  "Jordan":         44,  "Ivory Coast":    45,
    "Uzbekistan":      46,  "DR Congo":       47,  "New Zealand":    48,
    "South Africa":    49,  "Haiti":          50,  "Curacao":        51,
    "Cabo Verde":      52,  "Bosnia-Herzegovina": 53,
}
DEFAULT_RANKING = 60  # for teams not in the list

HOST_NATIONS_2026 = {"Mexico", "USA", "Canada"}

WC_APPEARANCES: dict[str, int] = {}


def normalise(name: str) -> str:
    return NAME_MAP.get(name, name)


def _build_wc_appearances(df: pd.DataFrame) -> dict[str, int]:
    """Count distinct WC years each team appeared in (historical only)."""
    appearances: dict[str, set] = {}
    for _, row in df[df["year"] < 2026].iterrows():
        for team in [row["home_team"], row["away_team"]]:
            appearances.setdefault(team, set()).add(row["year"])
    return {t: len(yrs) for t, yrs in appearances.items()}


# --------------------------------------------------------------------------- #
# Elo system
# --------------------------------------------------------------------------- #
ELO_BASE = 1500
K_WC = 40


def _elo_expected(ra: float, rb: float) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def _elo_update(ra: float, rb: float, result: int, k: float = K_WC):
    """result: 2=home win, 1=draw, 0=home loss (from home perspective)."""
    score = {2: 1.0, 1: 0.5, 0: 0.0}[result]
    ea = _elo_expected(ra, rb)
    new_ra = ra + k * (score - ea)
    new_rb = rb + k * ((1 - score) - (1 - ea))
    return new_ra, new_rb


def build_elo_series(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, dict]:
    """
    Process matches chronologically, recording pre-match Elo for each row.
    Returns (home_elo_series, away_elo_series, final_elo_dict).
    """
    elo: dict[str, float] = {}
    home_elos, away_elos = [], []

    for _, row in df.iterrows():
        ht = row["home_team"]
        at = row["away_team"]
        ra = elo.get(ht, ELO_BASE)
        rb = elo.get(at, ELO_BASE)
        home_elos.append(ra)
        away_elos.append(rb)
        # Update only for completed matches
        if pd.notna(row.get("home_score")) and pd.notna(row.get("away_score")):
            ra_new, rb_new = _elo_update(ra, rb, int(row["result"]))
            elo[ht] = ra_new
            elo[at] = rb_new

    return pd.Series(home_elos, index=df.index), pd.Series(away_elos, index=df.index), elo


# --------------------------------------------------------------------------- #
# Rolling team stats (form, goals, h2h)
# --------------------------------------------------------------------------- #
def _team_recent_matches(team: str, before_idx: int, all_matches: pd.DataFrame,
                         n: int = 10) -> pd.DataFrame:
    """Return last n completed matches for a team played before row index."""
    mask = (
        ((all_matches["home_team"] == team) | (all_matches["away_team"] == team)) &
        (all_matches.index < before_idx) &
        all_matches["home_score"].notna()
    )
    return all_matches[mask].tail(n)


def _form_score(team: str, recent: pd.DataFrame) -> float:
    """Weighted form: most recent match has highest weight (linear decay)."""
    if recent.empty:
        return 0.5  # neutral prior
    weights = list(range(1, len(recent) + 1))  # older → lower weight
    scores = []
    for _, m in recent.iterrows():
        if m["home_team"] == team:
            s = {2: 1.0, 1: 0.5, 0: 0.0}[int(m["result"])]
        else:
            s = {0: 1.0, 1: 0.5, 2: 0.0}[int(m["result"])]
        scores.append(s)
    return float(np.average(scores, weights=weights))


def _avg_goals(team: str, recent: pd.DataFrame, scored: bool = True) -> float:
    if recent.empty:
        return 1.2  # historical WC avg
    vals = []
    for _, m in recent.iterrows():
        if m["home_team"] == team:
            vals.append(m["home_score"] if scored else m["away_score"])
        else:
            vals.append(m["away_score"] if scored else m["home_score"])
    return float(np.mean(vals))


def _h2h_winrate(home: str, away: str, before_idx: int,
                 all_matches: pd.DataFrame, n: int = 10) -> tuple[float, float]:
    """Return (home_h2h_winrate, away_h2h_winrate) from last n head-to-head."""
    mask = (
        (
            ((all_matches["home_team"] == home) & (all_matches["away_team"] == away)) |
            ((all_matches["home_team"] == away) & (all_matches["away_team"] == home))
        ) &
        (all_matches.index < before_idx) &
        all_matches["home_score"].notna()
    )
    h2h = all_matches[mask].tail(n)
    if h2h.empty:
        return 0.5, 0.5

    home_wins = draws = away_wins = 0
    for _, m in h2h.iterrows():
        if m["home_team"] == home:
            r = int(m["result"])
            if r == 2:   home_wins += 1
            elif r == 1: draws += 1
            else:        away_wins += 1
        else:
            r = int(m["result"])
            if r == 0:   home_wins += 1
            elif r == 1: draws += 1
            else:        away_wins += 1

    total = home_wins + draws + away_wins
    return home_wins / total, away_wins / total


def _rest_days(team: str, current_date: str, before_idx: int,
               all_matches: pd.DataFrame) -> float:
    if not current_date:
        return 7.0  # default
    mask = (
        ((all_matches["home_team"] == team) | (all_matches["away_team"] == team)) &
        (all_matches.index < before_idx) &
        all_matches["date"].notna() & (all_matches["date"] != "")
    )
    prev = all_matches[mask]
    if prev.empty:
        return 14.0
    try:
        last_date = pd.to_datetime(prev.iloc[-1]["date"])
        curr_date = pd.to_datetime(current_date)
        delta = (curr_date - last_date).days
        return max(float(delta), 0.0)
    except Exception:
        return 7.0


# --------------------------------------------------------------------------- #
# Main feature builder
# --------------------------------------------------------------------------- #
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all features for each row in df.
    df must be sorted chronologically and contain: home_team, away_team,
    home_score, away_score, result, year, stage, date.
    """
    global WC_APPEARANCES
    WC_APPEARANCES = _build_wc_appearances(df)

    df = df.copy().reset_index(drop=True)
    df["home_team"] = df["home_team"].map(normalise)
    df["away_team"] = df["away_team"].map(normalise)

    # Build Elo series
    home_elo, away_elo, _ = build_elo_series(df)
    df["home_elo"] = home_elo
    df["away_elo"] = away_elo

    feature_rows = []
    for idx, row in df.iterrows():
        ht = row["home_team"]
        at = row["away_team"]

        # --- Elo ---
        h_elo = row["home_elo"]
        a_elo = row["away_elo"]
        elo_diff = h_elo - a_elo

        # --- FIFA ranking ---
        h_rank = FIFA_RANKINGS_2026.get(ht, DEFAULT_RANKING)
        a_rank = FIFA_RANKINGS_2026.get(at, DEFAULT_RANKING)
        rank_diff = a_rank - h_rank  # positive = home team is better ranked

        # --- Recent form & goals ---
        h_recent = _team_recent_matches(ht, idx, df)
        a_recent = _team_recent_matches(at, idx, df)

        h_form = _form_score(ht, h_recent)
        a_form = _form_score(at, a_recent)

        h_avg_scored    = _avg_goals(ht, h_recent, scored=True)
        h_avg_conceded  = _avg_goals(ht, h_recent, scored=False)
        a_avg_scored    = _avg_goals(at, a_recent, scored=True)
        a_avg_conceded  = _avg_goals(at, a_recent, scored=False)

        # --- Head-to-head ---
        h_h2h, a_h2h = _h2h_winrate(ht, at, idx, df)

        # --- WC experience ---
        h_exp = WC_APPEARANCES.get(ht, 0)
        a_exp = WC_APPEARANCES.get(at, 0)

        # --- Host ---
        h_host = int(ht in HOST_NATIONS_2026)
        a_host = int(at in HOST_NATIONS_2026)

        # --- Rest days ---
        date_str = str(row.get("date", ""))
        h_rest = _rest_days(ht, date_str, idx, df)
        a_rest = _rest_days(at, date_str, idx, df)

        feature_rows.append({
            # identifiers
            "year":              row["year"],
            "stage":             row["stage"],
            "home_team":         ht,
            "away_team":         at,
            "home_score":        row.get("home_score"),
            "away_score":        row.get("away_score"),
            # targets
            "result":            row.get("result"),          # 0/1/2
            "total_goals":       row.get("total_goals"),
            # Elo
            "home_elo":          round(h_elo, 1),
            "away_elo":          round(a_elo, 1),
            "elo_diff":          round(elo_diff, 1),
            # FIFA ranking
            "home_fifa_rank":    h_rank,
            "away_fifa_rank":    a_rank,
            "rank_diff":         rank_diff,
            # form
            "home_form":         round(h_form, 4),
            "away_form":         round(a_form, 4),
            "form_diff":         round(h_form - a_form, 4),
            # goals
            "home_avg_scored":   round(h_avg_scored, 3),
            "home_avg_conceded": round(h_avg_conceded, 3),
            "away_avg_scored":   round(a_avg_scored, 3),
            "away_avg_conceded": round(a_avg_conceded, 3),
            # h2h
            "home_h2h_winrate":  round(h_h2h, 4),
            "away_h2h_winrate":  round(a_h2h, 4),
            # experience
            "home_wc_exp":       h_exp,
            "away_wc_exp":       a_exp,
            "exp_diff":          h_exp - a_exp,
            # host
            "home_is_host":      h_host,
            "away_is_host":      a_host,
            # rest
            "home_rest_days":    round(h_rest, 1),
            "away_rest_days":    round(a_rest, 1),
        })

    return pd.DataFrame(feature_rows)


FEATURE_COLS = [
    "elo_diff", "rank_diff", "form_diff",
    "home_form", "away_form",
    "home_elo", "away_elo",
    "home_fifa_rank", "away_fifa_rank",
    "home_avg_scored", "home_avg_conceded",
    "away_avg_scored", "away_avg_conceded",
    "home_h2h_winrate", "away_h2h_winrate",
    "home_wc_exp", "away_wc_exp", "exp_diff",
    "home_is_host", "away_is_host",
    "home_rest_days", "away_rest_days",
]


def build_features_for_upcoming(upcoming_df: pd.DataFrame,
                                completed_df: pd.DataFrame,
                                final_elo: dict) -> pd.DataFrame:
    """
    Generate features for unplayed 2026 matches.
    Uses Elo from completed matches + rolling stats from completed history.
    """
    global WC_APPEARANCES
    if not WC_APPEARANCES:
        WC_APPEARANCES = _build_wc_appearances(completed_df)

    rows = []
    for _, row in upcoming_df.iterrows():
        ht = normalise(str(row["home_team"]))
        at = normalise(str(row["away_team"]))

        h_elo = final_elo.get(ht, ELO_BASE)
        a_elo = final_elo.get(at, ELO_BASE)
        elo_diff = h_elo - a_elo

        h_rank = FIFA_RANKINGS_2026.get(ht, DEFAULT_RANKING)
        a_rank = FIFA_RANKINGS_2026.get(at, DEFAULT_RANKING)
        rank_diff = a_rank - h_rank

        # Use entire completed history as "before" context
        h_recent = _team_recent_matches(ht, len(completed_df) + 1, completed_df)
        a_recent = _team_recent_matches(at, len(completed_df) + 1, completed_df)

        h_form = _form_score(ht, h_recent)
        a_form = _form_score(at, a_recent)
        h_avg_scored   = _avg_goals(ht, h_recent, scored=True)
        h_avg_conceded = _avg_goals(ht, h_recent, scored=False)
        a_avg_scored   = _avg_goals(at, a_recent, scored=True)
        a_avg_conceded = _avg_goals(at, a_recent, scored=False)

        h_h2h, a_h2h = _h2h_winrate(ht, at, len(completed_df) + 1, completed_df)

        rows.append({
            "year":              2026,
            "stage":             row.get("stage", ""),
            "group":             row.get("group", ""),
            "date":              row.get("date", ""),
            "home_team":         ht,
            "away_team":         at,
            "home_score":        None,
            "away_score":        None,
            "result":            None,
            "total_goals":       None,
            "home_elo":          round(h_elo, 1),
            "away_elo":          round(a_elo, 1),
            "elo_diff":          round(elo_diff, 1),
            "home_fifa_rank":    h_rank,
            "away_fifa_rank":    a_rank,
            "rank_diff":         rank_diff,
            "home_form":         round(h_form, 4),
            "away_form":         round(a_form, 4),
            "form_diff":         round(h_form - a_form, 4),
            "home_avg_scored":   round(h_avg_scored, 3),
            "home_avg_conceded": round(h_avg_conceded, 3),
            "away_avg_scored":   round(a_avg_scored, 3),
            "away_avg_conceded": round(a_avg_conceded, 3),
            "home_h2h_winrate":  round(h_h2h, 4),
            "away_h2h_winrate":  round(a_h2h, 4),
            "home_wc_exp":       WC_APPEARANCES.get(ht, 0),
            "away_wc_exp":       WC_APPEARANCES.get(at, 0),
            "exp_diff":          WC_APPEARANCES.get(ht, 0) - WC_APPEARANCES.get(at, 0),
            "home_is_host":      int(ht in HOST_NATIONS_2026),
            "away_is_host":      int(at in HOST_NATIONS_2026),
            "home_rest_days":    7.0,
            "away_rest_days":    7.0,
        })
    return pd.DataFrame(rows)


def run() -> tuple:
    print("=" * 55)
    print("  FIFA WC 2026 Predictor — Step 2: Feature Engineering")
    print("=" * 55 + "\n")

    matches_path = PROCESSED_DIR / "matches.csv"
    schedule_path = BASE_DIR / "data" / "live" / "schedule_2026.csv"

    if not matches_path.exists():
        raise FileNotFoundError("Run data_pipeline.py first.")

    df = pd.read_csv(matches_path)
    df["home_team"] = df["home_team"].map(normalise)
    df["away_team"] = df["away_team"].map(normalise)
    df = df.sort_values(["year", "stage"]).reset_index(drop=True)

    print(f"Loaded {len(df)} completed matches. Building features...")
    features = build_features(df)
    train = features[features["result"].notna()].copy()

    # Get final Elo after all completed matches
    _, _, final_elo = build_elo_series(df.reset_index(drop=True))

    # Build features for upcoming 2026 matches
    future = pd.DataFrame()
    if schedule_path.exists():
        sched = pd.read_csv(schedule_path)
        sched["home_team"] = sched["home_team"].map(normalise)
        sched["away_team"] = sched["away_team"].map(normalise)
        upcoming = sched[sched["played"] == False].copy()
        print(f"Loaded {len(upcoming)} upcoming 2026 matches from schedule.")
        future = build_features_for_upcoming(upcoming, df, final_elo)
        print(f"Built features for {len(future)} upcoming matches.")
    else:
        print("No schedule_2026.csv found — skipping upcoming features.")

    out_train = PROCESSED_DIR / "features_train.csv"
    out_future = PROCESSED_DIR / "features_2026.csv"
    train.to_csv(out_train, index=False)
    future.to_csv(out_future, index=False)

    print(f"\nTraining features : {len(train)} rows -> {out_train.name}")
    print(f"2026 upcoming     : {len(future)} rows -> {out_future.name}")

    print(f"\n--- Feature sample (last 5 training rows) ---")
    show_cols = ["year", "home_team", "away_team", "elo_diff", "rank_diff",
                 "home_form", "away_form", "home_h2h_winrate", "result"]
    print(train[show_cols].tail(5).to_string(index=False))

    print(f"\n--- Upcoming 2026 sample (first 5) ---")
    if not future.empty:
        print(future[["stage", "home_team", "away_team", "elo_diff", "rank_diff", "home_form", "away_form"]].head(5).to_string(index=False))

    print(f"\n--- Elo top 15 (current) ---")
    elo_sorted = sorted(final_elo.items(), key=lambda x: -x[1])[:15]
    for i, (team, elo) in enumerate(elo_sorted, 1):
        print(f"  {i:2d}. {team:<25} {elo:.1f}")

    print(f"\n--- Class distribution (result) ---")
    print(train["result"].value_counts().rename({0.0: "Away win", 1.0: "Draw", 2.0: "Home win"}).to_string())

    return train, future, final_elo


if __name__ == "__main__":
    run()
