"""
Live results scraper for FIFA World Cup 2026.

Primary  : openfootball JSON (updates daily, no scraping needed)
Fallback : fbref.com HTML table (BeautifulSoup)

Usage:
    python src/scraper.py              # run once
    python src/scraper.py --watch 60   # poll every 60 minutes
"""

import json
import re
import sys
import time
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

BASE_DIR    = Path(__file__).resolve().parent.parent
LIVE_DIR    = BASE_DIR / "data" / "live"
PROCESSED   = BASE_DIR / "data" / "processed"
LIVE_DIR.mkdir(parents=True, exist_ok=True)

SCHEDULE_CSV = LIVE_DIR / "schedule_2026.csv"
RESULTS_CSV  = LIVE_DIR / "results_2026.csv"
LOG_FILE     = LIVE_DIR / "scraper.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json"
    "/master/2026/worldcup.json"
)
FBREF_URL = "https://fbref.com/en/comps/1/schedule/World-Cup-Scores-and-Fixtures"

KNOCKOUT_RESULTS_JSON = LIVE_DIR / "knockout_results.json"

# openfootball round name → internal stage code
ROUND_STAGE_MAP = {
    "Round of 32":          "R32",
    "Round of 16":          "R16",
    "Quarter-final":        "QF",
    "Semi-final":           "SF",
    "Final":                "Final",
    "Match for third place": "3rd",
}
KNOCKOUT_STAGES = set(ROUND_STAGE_MAP.values())

# Team name normalisations (fbref uses different names)
FBREF_NAME_MAP = {
    "Czech Republic":       "Czechia",
    "Cape Verde":           "Cabo Verde",
    "Cote d'Ivoire":        "Ivory Coast",
    "IR Iran":              "Iran",
    "Korea Republic":       "South Korea",
    "Bosnia & Herzegovina": "Bosnia-Herzegovina",
    "Bosnia-Herzegovina":   "Bosnia-Herzegovina",
    "United States":        "USA",
    "Curacao":              "Curacao",
}


def _norm(name: str) -> str:
    return FBREF_NAME_MAP.get(name.strip(), name.strip())


# --------------------------------------------------------------------------- #
# Source 1: openfootball JSON
# --------------------------------------------------------------------------- #
def _ko_winner(score: dict, home: str, away: str) -> str | None:
    """Determine winner from openfootball score dict (ft/et/p)."""
    ft = score.get("ft")
    if ft is None or len(ft) < 2:
        return None
    if ft[0] > ft[1]:
        return home
    if ft[1] > ft[0]:
        return away
    # Draw after 90 min — check ET
    et = score.get("et")
    if et and len(et) >= 2:
        if et[0] > et[1]:
            return home
        if et[1] > et[0]:
            return away
    # Penalty shootout
    p = score.get("p")
    if p and len(p) >= 2:
        if p[0] > p[1]:
            return home
        if p[1] > p[0]:
            return away
    return None


def fetch_openfootball() -> pd.DataFrame:
    log.info("Fetching openfootball 2026 JSON...")
    try:
        r = requests.get(OPENFOOTBALL_URL, timeout=20, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning(f"openfootball fetch failed: {e}")
        return pd.DataFrame()

    rows = []
    ko_results: dict[str, list] = {s: [] for s in KNOCKOUT_STAGES}

    for m in data.get("matches", []):
        score  = m.get("score", {})
        ft     = score.get("ft", score.get("FT"))
        t1     = m.get("team1", "TBD")
        t2     = m.get("team2", "TBD")
        home   = _norm(t1 if isinstance(t1, str) else t1.get("name", "TBD"))
        away   = _norm(t2 if isinstance(t2, str) else t2.get("name", "TBD"))
        played = ft is not None and len(ft) >= 2
        round_name = m.get("round", "")
        stage  = ROUND_STAGE_MAP.get(round_name, round_name)

        row = {
            "year":       2026,
            "date":       m.get("date", ""),
            "stage":      stage,
            "group":      str(m.get("group", "")).replace("Group ", ""),
            "home_team":  home,
            "away_team":  away,
            "home_score": int(ft[0]) if played else None,
            "away_score": int(ft[1]) if played else None,
            "played":     played,
            "source":     "openfootball",
        }

        if stage in KNOCKOUT_STAGES and played:
            winner = _ko_winner(score, home, away)
            row["winner"] = winner
            if winner:
                loser = away if winner == home else home
                ko_results[stage].append({
                    "home": home, "away": away,
                    "home_score": int(ft[0]), "away_score": int(ft[1]),
                    "winner": winner, "loser": loser,
                    "date": m.get("date", ""),
                })

        rows.append(row)

    df = pd.DataFrame(rows)
    played_count = int(df["played"].sum())
    log.info(f"openfootball: {len(df)} total matches, {played_count} played")

    # Save knockout results
    _save_knockout_results(ko_results)

    return df


def _save_knockout_results(ko_results: dict):
    with open(KNOCKOUT_RESULTS_JSON, "w") as f:
        json.dump(ko_results, f, indent=2)
    total = sum(len(v) for v in ko_results.values())
    log.info(f"Saved {total} knockout result(s) -> {KNOCKOUT_RESULTS_JSON.name}")


# --------------------------------------------------------------------------- #
# Source 2: fbref.com HTML scrape
# --------------------------------------------------------------------------- #
def fetch_fbref() -> pd.DataFrame:
    log.info("Fetching fbref.com WC 2026 schedule...")
    try:
        r = requests.get(FBREF_URL, timeout=30, headers=HEADERS)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"fbref fetch failed: {e}")
        return pd.DataFrame()

    soup  = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": re.compile(r"sched")})
    if table is None:
        # Try any table with schedule-like headers
        for t in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in t.find_all("th")]
            if "Home" in headers and "Score" in headers:
                table = t
                break

    if table is None:
        log.warning("fbref: could not find schedule table")
        return pd.DataFrame()

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) < 5:
            continue
        texts = [td.get_text(strip=True) for td in tds]

        # Try to extract date, home, score, away
        try:
            date_td  = tr.find("td", {"data-stat": "date"})
            home_td  = tr.find("td", {"data-stat": "home_team"})
            score_td = tr.find("td", {"data-stat": "score"})
            away_td  = tr.find("td", {"data-stat": "away_team"})

            if not all([home_td, score_td, away_td]):
                continue

            home  = _norm(home_td.get_text(strip=True))
            away  = _norm(away_td.get_text(strip=True))
            score = score_td.get_text(strip=True)
            date  = date_td.get_text(strip=True) if date_td else ""

            if "–" in score or "-" in score:
                sep  = "–" if "–" in score else "-"
                parts = score.split(sep)
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    hs, as_ = int(parts[0].strip()), int(parts[1].strip())
                    rows.append({
                        "date":       date,
                        "home_team":  home,
                        "away_team":  away,
                        "home_score": hs,
                        "away_score": as_,
                        "played":     True,
                        "source":     "fbref",
                    })
        except Exception:
            continue

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not df.empty:
        log.info(f"fbref: {len(df)} played matches scraped")
    else:
        log.warning("fbref: no completed matches found")
    return df


# --------------------------------------------------------------------------- #
# Merge new results into existing schedule
# --------------------------------------------------------------------------- #
def update_schedule(new_results: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Merge newly scraped results into schedule_2026.csv.
    Returns (updated_schedule, n_new_results).
    """
    if not SCHEDULE_CSV.exists():
        log.warning("schedule_2026.csv not found — saving results as new schedule")
        new_results.to_csv(SCHEDULE_CSV, index=False)
        return new_results, len(new_results)

    existing = pd.read_csv(SCHEDULE_CSV)

    # Build lookup of existing played matches
    played_keys = set(
        zip(
            existing.loc[existing["played"] == True, "home_team"],
            existing.loc[existing["played"] == True, "away_team"],
        )
    )

    # Build a key set of ALL existing rows (played or not)
    all_keys = set(zip(existing["home_team"], existing["away_team"]))

    n_new = 0
    new_rows = []

    for _, row in new_results.iterrows():
        key  = (row["home_team"], row["away_team"])
        rkey = (row["away_team"], row["home_team"])
        is_played = bool(row.get("played", False))

        if key in all_keys:
            # Row exists — update score if newly played or changed
            if is_played:
                idx = existing[
                    (existing["home_team"] == row["home_team"]) &
                    (existing["away_team"] == row["away_team"])
                ].index
                if len(idx) > 0:
                    old_hs = existing.loc[idx[0], "home_score"]
                    new_hs = row["home_score"]
                    if pd.isna(old_hs) or (not pd.isna(new_hs) and int(old_hs) != int(new_hs)):
                        existing.loc[idx[0], "home_score"] = new_hs
                        existing.loc[idx[0], "away_score"] = row["away_score"]
                        existing.loc[idx[0], "played"]     = True
                        existing.loc[idx[0], "source"]     = row.get("source", "scraper")
                        if "winner" in row and pd.notna(row.get("winner")):
                            existing.loc[idx[0], "winner"] = row["winner"]
                        n_new += 1
                        log.info(f"  Updated: {row['home_team']} {int(new_hs)}-"
                                  f"{int(row['away_score'])} {row['away_team']}")

        elif rkey not in all_keys:
            # Completely new row (e.g. a knockout match not in original schedule)
            new_rows.append(row.to_dict())
            all_keys.add(key)
            if is_played:
                n_new += 1
                score_str = (f"{int(row['home_score'])}-{int(row['away_score'])}"
                             if is_played else "TBD")
                log.info(f"  New match: [{row.get('stage','?')}] "
                          f"{row['home_team']} {score_str} {row['away_team']}")

    if new_rows:
        existing = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)

    existing.to_csv(SCHEDULE_CSV, index=False)

    # Also save a clean results-only CSV
    results_only = existing[existing["played"] == True].copy()
    results_only.to_csv(RESULTS_CSV, index=False)

    log.info(f"Schedule updated: {n_new} new results | "
             f"{int(existing['played'].sum())} total played")
    return existing, n_new


# --------------------------------------------------------------------------- #
# Re-run pipeline after new results
# --------------------------------------------------------------------------- #
def refresh_predictions():
    """Re-run Elo update + feature engineering + simulation after new results."""
    log.info("Refreshing features and simulation...")
    import subprocess
    python = sys.executable

    # Step 0: update Elo ratings with latest WC 2026 results
    log.info("  Updating live Elo ratings...")
    res = subprocess.run(
        [python, "src/elo_updater.py"],
        capture_output=True, text=True, cwd=str(BASE_DIR),
    )
    if res.returncode != 0:
        log.warning(f"  Elo update failed:\n{res.stderr[-300:]}")
    else:
        log.info("  Elo update done.")

    steps = [
        (["src/feature_engineering.py"],               "Feature Engineering"),
        (["src/ensemble.py"],                           "Ensemble Predictions"),
        (["src/simulation.py", "--n", "10000"],         "Monte Carlo Simulation (10k)"),
    ]
    for args, label in steps:
        log.info(f"  Running {label}...")
        result = subprocess.run(
            [python] + args,
            capture_output=True, text=True,
            cwd=str(BASE_DIR),
        )
        if result.returncode != 0:
            log.error(f"  {label} failed:\n{result.stderr[-500:]}")
        else:
            log.info(f"  {label} done.")


# --------------------------------------------------------------------------- #
# Main scrape cycle
# --------------------------------------------------------------------------- #
def scrape_once(auto_refresh: bool = True) -> int:
    """
    Fetch latest results, update schedule, optionally refresh predictions.
    Returns number of new results found.
    """
    log.info("=" * 50)
    log.info(f"Scrape run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 50)

    # Try openfootball first
    df = fetch_openfootball()

    # Fallback to fbref if openfootball has no played matches
    if df.empty or df["played"].sum() == 0:
        log.info("Trying fbref fallback...")
        df_fbref = fetch_fbref()
        if not df_fbref.empty:
            df = df_fbref

    if df.empty:
        log.error("All sources failed — no data retrieved.")
        return 0

    _, n_new = update_schedule(df)

    if n_new > 0 and auto_refresh:
        log.info(f"Found {n_new} new result(s) — refreshing predictions...")
        refresh_predictions()
    elif n_new == 0:
        log.info("No new results since last run.")
    else:
        log.info(f"Found {n_new} new result(s) — skipping auto-refresh (disabled).")

    return n_new


def watch(interval_minutes: int = 60):
    """Poll for new results every interval_minutes."""
    log.info(f"Watching for new results every {interval_minutes} minutes. Ctrl+C to stop.")
    try:
        while True:
            scrape_once()
            next_run = datetime.now().strftime("%H:%M:%S")
            log.info(f"Next check in {interval_minutes} min (Ctrl+C to stop).")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        log.info("Scraper stopped.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FIFA WC 2026 live results scraper")
    parser.add_argument("--watch",        type=int, default=0,
                        metavar="MINUTES",
                        help="Poll interval in minutes (0 = run once)")
    parser.add_argument("--no-refresh",   action="store_true",
                        help="Skip re-running predictions after new results")
    args = parser.parse_args()

    if args.watch > 0:
        watch(args.watch)
    else:
        n = scrape_once(auto_refresh=not args.no_refresh)
        sys.exit(0 if n >= 0 else 1)
