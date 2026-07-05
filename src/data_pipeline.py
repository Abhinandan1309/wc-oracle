import os
import itertools
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LIVE_DIR = BASE_DIR / "data" / "live"

for d in [RAW_DIR, PROCESSED_DIR, LIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# 2026 Groups (hardcoded backup schedule)
# --------------------------------------------------------------------------- #
GROUPS_2026 = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Qatar", "Switzerland", "Bosnia-Herzegovina"],
    "C": ["Brazil", "Scotland", "Morocco", "Haiti"],
    "D": ["USA", "Australia", "Turkey", "Paraguay"],
    "E": ["Germany", "Ecuador", "Ivory Coast", "Curacao"],
    "F": ["Netherlands", "Sweden", "Tunisia", "Japan"],
    "G": ["Belgium", "Iran", "New Zealand", "Egypt"],
    "H": ["Spain", "Saudi Arabia", "Uruguay", "Cabo Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# 2026 completed results (hardcoded fallback for match data)
RESULTS_2026_HARDCODED = [
    {"home_team": "Mexico",       "away_team": "South Africa",           "home_score": 2, "away_score": 0, "stage": "Matchday 1", "group": "A"},
    {"home_team": "South Korea",  "away_team": "Czechia",                "home_score": 2, "away_score": 1, "stage": "Matchday 1", "group": "A"},
    {"home_team": "Canada",       "away_team": "Bosnia-Herzegovina",     "home_score": 1, "away_score": 1, "stage": "Matchday 1", "group": "B"},
    {"home_team": "Netherlands",  "away_team": "Japan",                  "home_score": 2, "away_score": 2, "stage": "Matchday 1", "group": "F"},
    {"home_team": "Sweden",       "away_team": "Tunisia",                "home_score": 5, "away_score": 1, "stage": "Matchday 1", "group": "F"},
    {"home_team": "Belgium",      "away_team": "Egypt",                  "home_score": 1, "away_score": 1, "stage": "Matchday 1", "group": "G"},
    {"home_team": "Iran",         "away_team": "New Zealand",            "home_score": 2, "away_score": 2, "stage": "Matchday 1", "group": "G"},
    {"home_team": "Spain",        "away_team": "Cabo Verde",             "home_score": 0, "away_score": 0, "stage": "Matchday 1", "group": "H"},
    {"home_team": "Saudi Arabia", "away_team": "Uruguay",                "home_score": 1, "away_score": 1, "stage": "Matchday 1", "group": "H"},
]

# --------------------------------------------------------------------------- #
# Generate full group-stage schedule from GROUPS_2026 (round-robin)
# --------------------------------------------------------------------------- #
def _build_group_schedule() -> list[dict]:
    """Generate all 3 matchdays per group (round-robin, 6 matches per group)."""
    # Standard round-robin pairing order for 4 teams: md1, md2, md3
    MATCHDAY_PAIRS = [(0, 3), (1, 2), (0, 1), (2, 3), (0, 2), (1, 3)]
    rows = []
    md_map = {0: "Matchday 1", 1: "Matchday 1", 2: "Matchday 2", 3: "Matchday 2", 4: "Matchday 3", 5: "Matchday 3"}
    for group, teams in GROUPS_2026.items():
        for idx, (i, j) in enumerate(MATCHDAY_PAIRS):
            rows.append({
                "group": group,
                "stage": md_map[idx],
                "home_team": teams[i],
                "away_team": teams[j],
                "home_score": None,
                "away_score": None,
                "played": False,
                "source": "schedule_generated",
            })
    return rows


# --------------------------------------------------------------------------- #
# Source 1: openfootball/worldcup.json
# --------------------------------------------------------------------------- #
OPENFOOTBALL_BASE = "https://raw.githubusercontent.com/openfootball/worldcup.json/master"
OPENFOOTBALL_YEARS = [1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966,
                      1970, 1974, 1978, 1982, 1986, 1990, 1994, 1998,
                      2002, 2006, 2010, 2014, 2018, 2022]


def _extract_team_name(t) -> str:
    if isinstance(t, str):
        return t
    return t.get("name", t.get("code", "Unknown"))


def _parse_openfootball_completed(data: dict, year: int) -> list[dict]:
    """Parse only completed matches (with ft scores)."""
    rows = []
    for m in data.get("matches", []):
        score = m.get("score", {})
        ft = score.get("ft", score.get("FT"))
        if ft is None or len(ft) < 2:
            continue
        rows.append({
            "year": year,
            "stage": m.get("round", "Group Stage"),
            "group": m.get("group", ""),
            "date": m.get("date", ""),
            "home_team": _extract_team_name(m.get("team1", "Unknown")),
            "away_team": _extract_team_name(m.get("team2", "Unknown")),
            "home_score": int(ft[0]),
            "away_score": int(ft[1]),
            "tournament": "FIFA World Cup",
            "source": "openfootball",
            "played": True,
        })
    return rows


def _parse_openfootball_full_schedule(data: dict, year: int) -> list[dict]:
    """Parse all matches — completed and upcoming — for schedule/simulation."""
    rows = []
    for m in data.get("matches", []):
        score = m.get("score", {})
        ft = score.get("ft", score.get("FT"))
        played = ft is not None and len(ft) >= 2
        rows.append({
            "year": year,
            "stage": m.get("round", "Group Stage"),
            "group": m.get("group", ""),
            "date": m.get("date", ""),
            "home_team": _extract_team_name(m.get("team1", "TBD")),
            "away_team": _extract_team_name(m.get("team2", "TBD")),
            "home_score": int(ft[0]) if played else None,
            "away_score": int(ft[1]) if played else None,
            "played": played,
        })
    return rows


def fetch_openfootball_historical() -> pd.DataFrame:
    print("Fetching openfootball historical data (1930-2022)...")
    all_rows = []
    for year in OPENFOOTBALL_YEARS:
        url = f"{OPENFOOTBALL_BASE}/{year}/worldcup.json"
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            rows = _parse_openfootball_completed(r.json(), year)
            all_rows.extend(rows)
            print(f"  {year}: {len(rows)} matches")
        except Exception as e:
            print(f"  {year}: failed — {e}")
    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"  Total historical: {len(df)} matches\n")
    return df


def fetch_openfootball_2026() -> pd.DataFrame:
    """Fetch completed 2026 matches for training data merge."""
    print("Fetching openfootball 2026 completed results...")
    url = f"{OPENFOOTBALL_BASE}/2026/worldcup.json"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        rows = _parse_openfootball_completed(r.json(), 2026)
        print(f"  2026 completed: {len(rows)} matches\n")
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        print(f"  openfootball 2026 failed ({e}), using hardcoded results.\n")
        return _build_hardcoded_2026_df()


def fetch_full_2026_schedule() -> pd.DataFrame:
    """
    Fetch all 104 scheduled 2026 matches (played + unplayed).
    Falls back to generated schedule + hardcoded results if openfootball unavailable.
    """
    print("Fetching full 2026 schedule (all 104 matches)...")
    url = f"{OPENFOOTBALL_BASE}/2026/worldcup.json"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        rows = _parse_openfootball_full_schedule(data, 2026)
        played = sum(1 for row in rows if row["played"])
        print(f"  Full schedule: {len(rows)} matches total, {played} played\n")

        if len(rows) < 100:
            print("  Warning: fewer than 100 matches found — merging with generated schedule.\n")
            rows = _merge_schedule_with_generated(rows)

        df = pd.DataFrame(rows)
        df.to_csv(LIVE_DIR / "schedule_2026.csv", index=False)
        return df

    except Exception as e:
        print(f"  openfootball 2026 schedule failed ({e}), building from hardcoded groups.\n")
        return _build_fallback_schedule()


def _merge_schedule_with_generated(live_rows: list[dict]) -> list[dict]:
    """Fill gaps in live schedule with generated group-stage fixtures."""
    existing = {(r["home_team"], r["away_team"]) for r in live_rows}
    generated = _build_group_schedule()
    for g in generated:
        key = (g["home_team"], g["away_team"])
        rkey = (g["away_team"], g["home_team"])
        if key not in existing and rkey not in existing:
            g["year"] = 2026
            g["tournament"] = "FIFA World Cup"
            live_rows.append(g)
    return live_rows


def _build_fallback_schedule() -> pd.DataFrame:
    """Build full 2026 schedule from hardcoded groups + known results."""
    rows = _build_group_schedule()
    # Apply known results
    known = {(r["home_team"], r["away_team"]): r for r in RESULTS_2026_HARDCODED}
    for row in rows:
        key = (row["home_team"], row["away_team"])
        rkey = (row["away_team"], row["home_team"])
        if key in known:
            row["home_score"] = known[key]["home_score"]
            row["away_score"] = known[key]["away_score"]
            row["played"] = True
        elif rkey in known:
            k = known[rkey]
            row["home_score"] = k["away_score"]
            row["away_score"] = k["home_score"]
            row["played"] = True

    for row in rows:
        row.setdefault("year", 2026)
        row.setdefault("date", "")
        row.setdefault("tournament", "FIFA World Cup")
        row.setdefault("source", "hardcoded")

    df = pd.DataFrame(rows)
    df.to_csv(LIVE_DIR / "schedule_2026.csv", index=False)
    played = df["played"].sum()
    print(f"  Fallback schedule: {len(df)} group-stage matches, {played} played\n")
    return df


def _build_hardcoded_2026_df() -> pd.DataFrame:
    rows = [dict(r, year=2026, tournament="FIFA World Cup",
                 source="hardcoded", played=True) for r in RESULTS_2026_HARDCODED]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Source 2: StatsBomb via statsbombpy
# --------------------------------------------------------------------------- #
STATSBOMB_SEASONS = [
    (43, 106, 2022),
    (43, 3,   2018),
]


def fetch_statsbomb() -> pd.DataFrame:
    print("Fetching StatsBomb open data...")
    try:
        from statsbombpy import sb
    except ImportError:
        print("  statsbombpy not installed — skipping.\n")
        return pd.DataFrame()

    all_rows = []
    for comp_id, season_id, year in STATSBOMB_SEASONS:
        try:
            matches = sb.matches(competition_id=comp_id, season_id=season_id)
            for _, m in matches.iterrows():
                all_rows.append({
                    "year": year,
                    "stage": m.get("competition_stage", "Unknown"),
                    "group": "",
                    "date": str(m.get("match_date", "")),
                    "home_team": m["home_team"],
                    "away_team": m["away_team"],
                    "home_score": int(m["home_score"]),
                    "away_score": int(m["away_score"]),
                    "tournament": "FIFA World Cup",
                    "source": f"statsbomb_{year}",
                    "played": True,
                })
            print(f"  StatsBomb {year}: {len(matches)} matches")
        except Exception as e:
            print(f"  StatsBomb {year}: failed — {e}")

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"  Total StatsBomb: {len(df)} matches\n")
    return df


# --------------------------------------------------------------------------- #
# Merge & deduplicate for model training data
# --------------------------------------------------------------------------- #
def _outcome(row) -> int:
    if row["home_score"] > row["away_score"]:
        return 2
    elif row["home_score"] == row["away_score"]:
        return 1
    return 0


def merge_and_save(df_hist: pd.DataFrame, df_2026: pd.DataFrame, df_sb: pd.DataFrame) -> pd.DataFrame:
    frames = [f for f in [df_hist, df_2026, df_sb] if f is not None and not f.empty]
    if not frames:
        raise RuntimeError("No match data fetched from any source.")

    df = pd.concat(frames, ignore_index=True)

    # Prefer statsbomb > openfootball > hardcoded for overlapping years
    priority = {"statsbomb_2022": 0, "statsbomb_2018": 1, "openfootball": 2,
                "worldcup26.ir": 3, "hardcoded": 4}
    df["_p"] = df["source"].map(lambda s: priority.get(s, 99))
    df = (df.sort_values("_p")
            .drop_duplicates(subset=["year", "home_team", "away_team"])
            .drop(columns=["_p"])
            .sort_values(["year", "stage"])
            .reset_index(drop=True))

    df["result"] = df.apply(_outcome, axis=1)
    df["total_goals"] = df["home_score"] + df["away_score"]
    return df


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run() -> pd.DataFrame:
    print("=" * 55)
    print("  FIFA WC 2026 Predictor — Step 1: Data Pipeline")
    print("=" * 55 + "\n")

    df_hist = fetch_openfootball_historical()
    df_2026 = fetch_openfootball_2026()
    df_sched = fetch_full_2026_schedule()
    df_sb = fetch_statsbomb()

    # Save raws
    if df_hist is not None and not df_hist.empty:
        df_hist.to_csv(RAW_DIR / "openfootball_historical.csv", index=False)
    if df_2026 is not None and not df_2026.empty:
        df_2026.to_csv(RAW_DIR / "results_2026.csv", index=False)
    if df_sb is not None and not df_sb.empty:
        df_sb.to_csv(RAW_DIR / "statsbomb_matches.csv", index=False)

    df = merge_and_save(df_hist, df_2026, df_sb)
    out_path = PROCESSED_DIR / "matches.csv"
    df.to_csv(out_path, index=False)

    print("=" * 55)
    print(f"  Pipeline complete!")
    print(f"  Training data  : {len(df)} matches")
    print(f"  Years covered  : {sorted(df['year'].unique().tolist())}")
    print(f"  2026 schedule  : {len(df_sched)} total matches "
          f"({int(df_sched['played'].sum())} played)" if df_sched is not None and not df_sched.empty else "  2026 schedule  : unavailable")
    print(f"  Output         : {out_path}")
    print("=" * 55 + "\n")

    cols = ["year", "stage", "home_team", "away_team", "home_score", "away_score", "result", "source"]
    print("--- Last 10 training rows ---")
    print(df[cols].tail(10).to_string(index=False))

    print("\n--- Matches per year ---")
    print(df.groupby("year").size().to_string())

    if df_sched is not None and not df_sched.empty:
        print("\n--- 2026 Schedule preview (first 12) ---")
        scols = ["stage", "group", "home_team", "away_team", "home_score", "away_score", "played"]
        print(df_sched[scols].head(12).to_string(index=False))

    return df


if __name__ == "__main__":
    run()
