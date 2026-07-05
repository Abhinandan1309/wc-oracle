"""WC Oracle — FastAPI backend."""
import json
import math
import sys
import subprocess
import requests as _requests
from datetime import timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT      = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
LIVE      = ROOT / "data" / "live"
DIST      = ROOT / "frontend" / "dist"
sys.path.insert(0, str(ROOT / "src"))

app = FastAPI(title="WC Oracle API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
ALL_TEAMS = [t for g in GROUPS_2026.values() for t in g]

NAME_MAP = {
    "Czech Republic":         "Czechia",
    "Cape Verde":             "Cabo Verde",
    "Bosnia & Herzegovina":   "Bosnia-Herzegovina",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Curaçao":                "Curacao",
    "Cote d'Ivoire":          "Ivory Coast",
    "IR Iran":                "Iran",
    "Korea Republic":         "South Korea",
    "United States":          "USA",
    "West Germany":           "Germany",
}


def norm(name: str) -> str:
    return NAME_MAP.get(str(name).strip(), str(name).strip())


def safe_float(val, default: float = 0.0) -> float:
    try:
        f = float(val)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _load_schedule() -> pd.DataFrame:
    p = LIVE / "schedule_2026.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["group"]     = df["group"].astype(str).str.replace("Group ", "", regex=False)
    df["home_team"] = df["home_team"].apply(norm)
    df["away_team"] = df["away_team"].apply(norm)
    return df


def _compute_standings(schedule: pd.DataFrame) -> dict:
    standings = {
        g: {t: {"pts": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0}
            for t in teams}
        for g, teams in GROUPS_2026.items()
    }
    for _, m in schedule[schedule["played"] == True].iterrows():
        g = str(m.get("group", "")).replace("Group ", "").strip()
        if g not in standings:
            continue
        ht, at = str(m["home_team"]), str(m["away_team"])
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        if ht not in standings[g] or at not in standings[g]:
            continue
        if hs > as_:
            hp, ap, hw, aw, hd, ad, hl, al = 3, 0, 1, 0, 0, 0, 0, 1
        elif hs == as_:
            hp, ap, hw, aw, hd, ad, hl, al = 1, 1, 0, 0, 1, 1, 0, 0
        else:
            hp, ap, hw, aw, hd, ad, hl, al = 0, 3, 0, 1, 0, 0, 1, 0
        for team, pts, w, d, l, gf, ga in [
            (ht, hp, hw, hd, hl, hs, as_),
            (at, ap, aw, ad, al, as_, hs),
        ]:
            s = standings[g][team]
            s["pts"] += pts; s["w"] += w; s["d"] += d; s["l"] += l
            s["gf"] += gf; s["ga"] += ga; s["gd"] += gf - ga
    result = {}
    for g, ts in standings.items():
        rows = [{"team": t, **s} for t, s in ts.items()]
        rows.sort(key=lambda x: (-x["pts"], -x["gd"], -x["gf"]))
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        result[g] = rows
    return result


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/standings")
def get_standings():
    schedule = _load_schedule()
    if schedule.empty:
        return {}
    return _compute_standings(schedule)


@app.get("/api/schedule")
def get_schedule():
    schedule = _load_schedule()
    if schedule.empty:
        return {"played": [], "upcoming": []}

    pred_map: dict = {}
    pred_path = PROCESSED / "predictions_2026.csv"
    if pred_path.exists():
        preds = pd.read_csv(pred_path)
        for _, row in preds.iterrows():
            key = f"{row['home_team']}|{row['away_team']}"
            pred_map[key] = {
                "p_home": safe_float(row.get("p_home_win"), 1 / 3),
                "p_draw": safe_float(row.get("p_draw"),     1 / 3),
                "p_away": safe_float(row.get("p_away_win"), 1 / 3),
            }

    played = []
    for _, m in schedule[schedule["played"] == True].iterrows():
        played.append({
            "group":      str(m.get("group", "")),
            "stage":      str(m.get("stage", "Group Stage")),
            "home_team":  m["home_team"],
            "away_team":  m["away_team"],
            "home_score": int(m["home_score"]),
            "away_score": int(m["away_score"]),
            "date":       str(m.get("date", "")),
        })

    upcoming = []
    for _, m in schedule[schedule["played"] == False].iterrows():
        key = f"{m['home_team']}|{m['away_team']}"
        prb = pred_map.get(key, {"p_home": 1 / 3, "p_draw": 1 / 3, "p_away": 1 / 3})
        upcoming.append({
            "group":     str(m.get("group", "")),
            "stage":     str(m.get("stage", "Group Stage")),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "date":      str(m.get("date", "")),
            **prb,
        })

    return {"played": played, "upcoming": upcoming}


@app.get("/api/simulation")
def get_simulation():
    p = PROCESSED / "simulation_results.json"
    if not p.exists():
        raise HTTPException(404, "Run simulation.py first.")
    with open(p) as f:
        data = json.load(f)

    teams = []
    for name in ALL_TEAMS:
        d = data.get(name, {})
        teams.append({
            "name":   name,
            "group":  d.get("group", "?"),
            "R32":    safe_float(d.get("R32",    0)),
            "R16":    safe_float(d.get("R16",    0)),
            "QF":     safe_float(d.get("QF",     0)),
            "SF":     safe_float(d.get("SF",     0)),
            "Final":  safe_float(d.get("Final",  0)),
            "Winner": safe_float(d.get("Winner", 0)),
        })

    return {"teams": teams, "meta": data.get("_meta", {})}


@app.get("/api/teams")
def get_teams():
    return {"teams": ALL_TEAMS, "groups": GROUPS_2026}


@app.post("/api/simulate")
async def run_simulation(background_tasks: BackgroundTasks):
    def _run():
        subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'src'); "
             "from simulation import MonteCarloSimulator, save_results; "
             "s = MonteCarloSimulator(); s.load(); "
             "r = s.run(10000, verbose=False); save_results(r)"],
            cwd=str(ROOT), capture_output=True,
        )
    background_tasks.add_task(_run)
    return {"status": "started"}


ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
)
_ESPN_HEADERS = {"User-Agent": "Mozilla/5.0 (WC Oracle/1.0)"}


def _parse_espn(data: dict) -> list[dict]:
    matches = []
    for event in data.get("events", []):
        comp        = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"),
                    competitors[0] if competitors else {})
        away = next((c for c in competitors if c.get("homeAway") == "away"),
                    competitors[1] if len(competitors) > 1 else {})

        status      = event.get("status", {})
        status_type = status.get("type", {})
        state       = status_type.get("state", "pre")  # "pre" | "in" | "post"

        def _score(c):
            s = c.get("score")
            if s is None:
                return None
            try:
                return int(s)
            except (TypeError, ValueError):
                return None

        venue_info  = comp.get("venue", {})
        city        = (venue_info.get("address") or {}).get("city", "")
        venue       = ", ".join(filter(None, [venue_info.get("fullName", ""), city]))
        group_name  = (comp.get("groups") or {}).get("name", "")

        matches.append({
            "id":                  event.get("id", ""),
            "state":               state,
            "status_detail":       status_type.get("shortDetail", ""),
            "status_description":  status_type.get("description", ""),
            "clock":               status.get("displayClock", ""),
            "date":                event.get("date", ""),
            "home_team":           (home.get("team") or {}).get("displayName", ""),
            "home_abbr":           (home.get("team") or {}).get("abbreviation", ""),
            "home_score":          _score(home),
            "home_logo":           (home.get("team") or {}).get("logo", ""),
            "away_team":           (away.get("team") or {}).get("displayName", ""),
            "away_abbr":           (away.get("team") or {}).get("abbreviation", ""),
            "away_score":          _score(away),
            "away_logo":           (away.get("team") or {}).get("logo", ""),
            "venue":               venue,
            "group":               group_name,
        })
    return matches


@app.get("/api/live")
def get_live():
    """Live scores + today's schedule from ESPN's unofficial scoreboard API."""
    try:
        resp = _requests.get(ESPN_URL, headers=_ESPN_HEADERS, timeout=10)
        resp.raise_for_status()
        espn_data = resp.json()
    except Exception as e:
        raise HTTPException(503, f"ESPN API unavailable: {e}")

    matches = _parse_espn(espn_data)

    # Attach our ML predictions to upcoming matches where names align
    pred_map: dict = {}
    pred_path = PROCESSED / "predictions_2026.csv"
    if pred_path.exists():
        preds = pd.read_csv(pred_path)
        for _, row in preds.iterrows():
            key = f"{norm(str(row['home_team']))}|{norm(str(row['away_team']))}"
            pred_map[key] = {
                "p_home": safe_float(row.get("p_home_win"), 1 / 3),
                "p_draw": safe_float(row.get("p_draw"),     1 / 3),
                "p_away": safe_float(row.get("p_away_win"), 1 / 3),
            }

    for m in matches:
        ht = norm(m["home_team"])
        at = norm(m["away_team"])

        if m["state"] == "pre":
            key = f"{ht}|{at}"
            if key in pred_map:
                m.update(pred_map[key])

        elif m["state"] == "in":
            # Add live win probability using Poisson model
            try:
                clock_str = m.get("clock", "0") or "0"
                minute = int("".join(filter(str.isdigit, clock_str.split(":")[0])) or "0")
                remaining = max(90 - minute, 3)
                frac = remaining / 90.0
                lh, la = _match_lambdas(ht, at, frac)
                sh = m.get("home_score") or 0
                sa = m.get("away_score") or 0
                pw, pd_, pl = _live_probs(lh, la, int(sh), int(sa))
                m["live_p_home"] = round(pw, 3)
                m["live_p_draw"] = round(pd_, 3)
                m["live_p_away"] = round(pl, 3)
                m["minute"]      = minute
            except Exception:
                pass

    from datetime import datetime
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "live":       [m for m in matches if m["state"] == "in"],
        "upcoming":   [m for m in matches if m["state"] == "pre"],
        "recent":     [m for m in matches if m["state"] == "post"],
        "fetched_at": now_iso,
    }


# ── Bracket ────────────────────────────────────────────────────────────────────

# All 32 R32 fixtures (hardcoded from FIFA 2026 draw)
_R32 = {
    73: {"home": "South Africa",      "away": "Canada",              "date": "2026-06-28", "venue": "Los Angeles"},
    74: {"home": "Germany",            "away": "Paraguay",            "date": "2026-06-29", "venue": "Boston"},
    75: {"home": "Netherlands",        "away": "Morocco",             "date": "2026-06-29", "venue": "Monterrey"},
    76: {"home": "Brazil",             "away": "Japan",               "date": "2026-06-29", "venue": "Houston"},
    77: {"home": "France",             "away": "Sweden",              "date": "2026-06-30", "venue": "New York/NJ"},
    78: {"home": "Ivory Coast",        "away": "Norway",              "date": "2026-06-30", "venue": "Dallas"},
    79: {"home": "Mexico",             "away": "Ecuador",             "date": "2026-06-30", "venue": "Mexico City"},
    80: {"home": "England",            "away": "DR Congo",            "date": "2026-07-01", "venue": "Atlanta"},
    81: {"home": "USA",                "away": "Bosnia-Herzegovina",  "date": "2026-07-01", "venue": "San Francisco"},
    82: {"home": "Belgium",            "away": "Senegal",             "date": "2026-07-01", "venue": "Seattle"},
    83: {"home": "Portugal",           "away": "Croatia",             "date": "2026-07-02", "venue": "Toronto"},
    84: {"home": "Spain",              "away": "Austria",             "date": "2026-07-02", "venue": "Los Angeles"},
    85: {"home": "Switzerland",        "away": "Algeria",             "date": "2026-07-02", "venue": "Vancouver"},
    86: {"home": "Argentina",          "away": "Cabo Verde",          "date": "2026-07-03", "venue": "Miami"},
    87: {"home": "Colombia",           "away": "Ghana",               "date": "2026-07-03", "venue": "Kansas City"},
    88: {"home": "Australia",          "away": "Egypt",               "date": "2026-07-03", "venue": "Dallas"},
}
_R16 = {
    89: {"date": "2026-07-04", "venue": "Philadelphia",  "src": (74, 77)},
    90: {"date": "2026-07-04", "venue": "Houston",       "src": (73, 75)},
    91: {"date": "2026-07-05", "venue": "New York/NJ",  "src": (76, 78)},
    92: {"date": "2026-07-05", "venue": "Mexico City",  "src": (79, 80)},
    93: {"date": "2026-07-06", "venue": "Dallas",        "src": (83, 84)},
    94: {"date": "2026-07-06", "venue": "Seattle",       "src": (81, 82)},
    95: {"date": "2026-07-07", "venue": "Atlanta",       "src": (86, 88)},
    96: {"date": "2026-07-07", "venue": "Vancouver",     "src": (85, 87)},
}
_LATER = {
    97:  {"round": "QF",    "date": "2026-07-09", "venue": "Boston",      "src": (89, 90)},
    98:  {"round": "QF",    "date": "2026-07-10", "venue": "Los Angeles", "src": (93, 94)},
    99:  {"round": "QF",    "date": "2026-07-11", "venue": "Miami",       "src": (91, 92)},
    100: {"round": "QF",    "date": "2026-07-11", "venue": "Kansas City", "src": (95, 96)},
    101: {"round": "SF",    "date": "2026-07-14", "venue": "Dallas",      "src": (97, 98)},
    102: {"round": "SF",    "date": "2026-07-15", "venue": "Atlanta",     "src": (99, 100)},
    104: {"round": "Final", "date": "2026-07-19", "venue": "New York/NJ", "src": (101, 102)},
}
BRACKET_STRUCTURE = {
    "sf1": {
        "sf": 101,
        "qf": [
            {"match": 97, "r16": [{"match": 89, "r32": [74, 77]}, {"match": 90, "r32": [73, 75]}]},
            {"match": 98, "r16": [{"match": 93, "r32": [83, 84]}, {"match": 94, "r32": [81, 82]}]},
        ],
    },
    "sf2": {
        "sf": 102,
        "qf": [
            {"match": 99,  "r16": [{"match": 91, "r32": [76, 78]}, {"match": 92, "r32": [79, 80]}]},
            {"match": 100, "r16": [{"match": 95, "r32": [86, 88]}, {"match": 96, "r32": [85, 87]}]},
        ],
    },
    "final": 104,
}


def _team_strength(name: str | None, sim: dict) -> float:
    if not name:
        return 0.001
    d = sim.get(name, {})
    return max(safe_float(d.get("Winner", 0)), 0.001)


def _h2h(home: str | None, away: str | None, sim: dict) -> tuple[float, float]:
    sh, sa = _team_strength(home, sim), _team_strength(away, sim)
    t = sh + sa
    return round(sh / t, 3), round(sa / t, 3)


def _most_likely(home: str | None, away: str | None, sim: dict) -> str | None:
    if not home or not away:
        return home or away
    return home if _team_strength(home, sim) >= _team_strength(away, sim) else away


@app.get("/api/bracket")
def get_bracket():
    sim: dict = {}
    sim_path = PROCESSED / "simulation_results.json"
    if sim_path.exists():
        with open(sim_path) as f:
            sim = json.load(f)

    # Load all knockout results that have been played
    ko_path = LIVE / "knockout_results.json"
    ko_results: dict = {}
    if ko_path.exists():
        with open(ko_path) as f:
            ko_results = json.load(f)

    # Build (home, away) → {winner, home_score, away_score} lookup
    played_map: dict[tuple, dict] = {}
    for _rnd, mlist in ko_results.items():
        for m in mlist:
            played_map[(m["home"], m["away"])] = m

    # Map (home, away) → R32 match_num
    r32_by_teams: dict[tuple, int] = {}
    for num, info in _R32.items():
        r32_by_teams[(info["home"], info["away"])] = num

    # Resolve winner for each match (populated as we process rounds in order)
    match_winners: dict[int, str] = {}

    def _look_up_result(home: str | None, away: str | None):
        """Returns (played, winner, home_score, away_score)."""
        if not home or not away:
            return False, None, None, None
        for key in [(home, away), (away, home)]:
            if key in played_map:
                m = played_map[key]
                hs, as_ = m["home_score"], m["away_score"]
                if key == (away, home):
                    hs, as_ = as_, hs
                return True, m["winner"], hs, as_
        return False, None, None, None

    def _build_match(num: int, rnd: str, date: str, venue: str,
                     home: str | None, away: str | None,
                     home_src: int | None = None, away_src: int | None = None) -> dict:
        played, winner, hs, as_ = _look_up_result(home, away)
        if winner:
            match_winners[num] = winner
        ph, pa = _h2h(home, away, sim)
        predicted = _most_likely(home, away, sim)
        return {
            "num": num, "round": rnd, "date": date, "venue": venue,
            "home": home, "away": away,
            "home_src": home_src, "away_src": away_src,
            "played": played,
            "home_score": hs, "away_score": as_,
            "winner": winner,
            "p_home": ph, "p_away": pa,
            "predicted": predicted,
        }

    all_matches: dict[int, dict] = {}

    # R32 — teams are known
    for num, info in _R32.items():
        m = _build_match(num, "R32", info["date"], info["venue"],
                         info["home"], info["away"])
        all_matches[num] = m
        # also populate match_winners from r32 played_map directly
        for key in [(info["home"], info["away"]), (info["away"], info["home"])]:
            if key in played_map:
                match_winners[num] = played_map[key]["winner"]

    # R16 — teams resolved from R32 winners
    for num, info in _R16.items():
        sa, sb = info["src"]
        home = match_winners.get(sa)
        away = match_winners.get(sb)
        m = _build_match(num, "R16", info["date"], info["venue"],
                         home, away, sa, sb)
        all_matches[num] = m

    # QF / SF / Final
    for num, info in _LATER.items():
        sa, sb = info["src"]
        home = match_winners.get(sa)
        away = match_winners.get(sb)
        m = _build_match(num, info["round"], info["date"], info["venue"],
                         home, away, sa, sb)
        all_matches[num] = m

    return {"matches": all_matches, "structure": BRACKET_STRUCTURE}


# ── Bracket traversal helpers ──────────────────────────────────────────────────

# For each match, which match does its winner advance to?
_WINNER_ADVANCES_TO: dict[int, int] = {}
for _r16n, _r16i in _R16.items():
    for _src in _r16i["src"]:
        _WINNER_ADVANCES_TO[_src] = _r16n
for _latn, _lati in _LATER.items():
    for _src in _lati["src"]:
        _WINNER_ADVANCES_TO[_src] = _latn

# team → their R32 match number
_TEAM_R32: dict[str, int] = {}
for _num, _info in _R32.items():
    _TEAM_R32[_info["home"]] = _num
    _TEAM_R32[_info["away"]] = _num


# ── Path to Final ──────────────────────────────────────────────────────────────

@app.get("/api/paths")
def get_paths():
    """For every team, return their projected bracket path with per-match win probs."""
    sim: dict = {}
    sim_path = PROCESSED / "simulation_results.json"
    if sim_path.exists():
        with open(sim_path) as f:
            sim = json.load(f)

    # Rebuild match tree (reuse bracket logic)
    bracket = get_bracket()
    all_matches = bracket["matches"]

    # Build match_winners from played results in all_matches
    match_winners: dict[int, str] = {}
    for num_str, m in all_matches.items():
        num = int(num_str)
        if m.get("winner"):
            match_winners[num] = m["winner"]

    paths: dict[str, list] = {}
    for team in ALL_TEAMS:
        r32_match = _TEAM_R32.get(team)
        if r32_match is None:
            paths[team] = []
            continue

        path = []
        current = r32_match
        while current is not None:
            m = all_matches.get(str(current)) or all_matches.get(current)
            if m is None:
                break

            home = m.get("home")
            away = m.get("away")
            opponent = away if home == team else (home if away == team else None)

            played  = bool(m.get("played"))
            winner  = m.get("winner")
            won     = played and winner == team
            elim    = played and winner != team and winner is not None

            ph = m.get("p_home", 0.5)
            pa = m.get("p_away", 0.5)
            p_win = ph if home == team else pa

            path.append({
                "round":    m.get("round"),
                "match":    current,
                "opponent": opponent,
                "p_win":    round(p_win, 3),
                "played":   played,
                "won":      won,
                "eliminated": elim,
                "score":    f"{m['home_score']}-{m['away_score']}" if played and m.get("home_score") is not None else None,
            })

            if elim:
                break
            current = _WINNER_ADVANCES_TO.get(current)

        paths[team] = path

    return {"paths": paths}


# ── What-if simulator ──────────────────────────────────────────────────────────

class WhatIfRequest(BaseModel):
    overrides: dict[str, str] = {}   # {match_num_str: winner_team_name}


@app.post("/api/bracket/whatif")
def bracket_whatif(body: WhatIfRequest):
    """
    Apply user-specified match result overrides and propagate deterministically
    through the bracket using Elo predictions for unplayed future matches.
    Returns same shape as /api/bracket.
    """
    sim: dict = {}
    sim_path = PROCESSED / "simulation_results.json"
    if sim_path.exists():
        with open(sim_path) as f:
            sim = json.load(f)

    ko_path = LIVE / "knockout_results.json"
    ko_results: dict = {}
    if ko_path.exists():
        with open(ko_path) as f:
            ko_results = json.load(f)

    played_map: dict[tuple, dict] = {}
    for _rnd, mlist in ko_results.items():
        for m in mlist:
            played_map[(m["home"], m["away"])] = m

    # Convert override keys to int
    overrides: dict[int, str] = {int(k): v for k, v in body.overrides.items()}

    # Merge actual winners + overrides
    match_winners: dict[int, str] = {}
    for key, m in played_map.items():
        for num, info in _R32.items():
            if (info["home"], info["away"]) == key:
                match_winners[num] = m["winner"]

    for num, winner in overrides.items():
        match_winners[num] = winner

    override_set = set(overrides.keys())

    def _resolve(home, away):
        if not home and not away:
            return None
        if not home or not away:
            return home or away
        return _most_likely(home, away, sim)

    def _build(num, rnd, date, venue, home, away):
        winner = match_winners.get(num)
        if not winner:
            winner = _resolve(home, away)
            played = False
        else:
            played = (num in override_set) or (num in {k for k, m in played_map.items()
                                                        for n2, i2 in _R32.items()
                                                        if (i2["home"], i2["away"]) == k and n2 == num})
        if winner:
            match_winners[num] = winner
        ph, pa = _h2h(home, away, sim)
        return {
            "num": num, "round": rnd, "date": date, "venue": venue,
            "home": home, "away": away,
            "played": played, "winner": winner,
            "home_score": None, "away_score": None,
            "p_home": ph, "p_away": pa,
            "predicted": _resolve(home, away),
            "is_override": num in override_set,
        }

    all_matches: dict = {}

    for num, info in _R32.items():
        m = _build(num, "R32", info["date"], info["venue"], info["home"], info["away"])
        # restore actual scores from played_map
        for key, pm in played_map.items():
            if (info["home"], info["away"]) == key and num not in override_set:
                m["home_score"] = pm["home_score"]
                m["away_score"] = pm["away_score"]
                m["played"] = True
        all_matches[num] = m

    for num, info in _R16.items():
        sa, sb = info["src"]
        home = match_winners.get(sa)
        away = match_winners.get(sb)
        m = _build(num, "R16", info["date"], info["venue"], home, away)
        all_matches[num] = m

    for num, info in _LATER.items():
        sa, sb = info["src"]
        home = match_winners.get(sa)
        away = match_winners.get(sb)
        m = _build(num, info["round"], info["date"], info["venue"], home, away)
        all_matches[num] = m

    return {"matches": all_matches, "structure": BRACKET_STRUCTURE}


# ── Champion probability history ───────────────────────────────────────────────

@app.get("/api/champion-history")
def get_champion_history():
    """Return time-series of champion probabilities from successive simulation runs."""
    p = LIVE / "champion_history.json"
    if not p.exists():
        return {"history": []}
    with open(p) as f:
        history = json.load(f)
    return {"history": history}


# ── Prediction accuracy (Brier score) ─────────────────────────────────────────

@app.get("/api/accuracy")
def get_accuracy():
    """
    Score the model's pre-match predictions against actual results.
    Returns per-match Brier scores and overall accuracy stats.
    """
    sched = _load_schedule()
    if sched.empty:
        return {"matches": [], "summary": {}}

    pred_path = PROCESSED / "predictions_2026.csv"
    if not pred_path.exists():
        return {"matches": [], "summary": {}}

    preds = pd.read_csv(pred_path)
    pred_map: dict[tuple, dict] = {}
    for _, row in preds.iterrows():
        key = (norm(str(row["home_team"])), norm(str(row["away_team"])))
        pred_map[key] = {
            "p_home": safe_float(row.get("p_home_win"), 1/3),
            "p_draw": safe_float(row.get("p_draw"),     1/3),
            "p_away": safe_float(row.get("p_away_win"), 1/3),
        }

    played = sched[sched["played"] == True].copy()
    records = []
    brier_sum = 0.0
    correct_fav = 0
    n = 0

    for _, m in played.iterrows():
        ht  = str(m["home_team"])
        at  = str(m["away_team"])
        hs  = int(m["home_score"])
        as_ = int(m["away_score"])

        key  = (ht, at)
        rkey = (at, ht)
        p = pred_map.get(key) or pred_map.get(rkey)
        if p is None:
            continue

        if key == rkey:   # swap if prediction was stored reversed
            ph = p.get("p_away", 1/3)
            pa = p.get("p_home", 1/3)
        else:
            ph = p.get("p_home", 1/3) if key in pred_map else p.get("p_away", 1/3)
            pa = p.get("p_away", 1/3) if key in pred_map else p.get("p_home", 1/3)
        pd_ = p.get("p_draw", 1/3)

        actual_h = 1 if hs > as_ else 0
        actual_d = 1 if hs == as_ else 0
        actual_a = 1 if as_ > hs else 0

        brier = ((ph - actual_h)**2 + (pd_ - actual_d)**2 + (pa - actual_a)**2) / 3
        brier_sum += brier
        n += 1

        winner = ht if hs > as_ else (at if as_ > hs else "Draw")
        fav    = ht if ph >= pa else at
        if winner not in ("Draw",) and fav == winner:
            correct_fav += 1

        records.append({
            "home": ht, "away": at,
            "score": f"{hs}-{as_}",
            "p_home": round(ph, 3), "p_draw": round(pd_, 3), "p_away": round(pa, 3),
            "brier": round(brier, 4),
            "correct": fav == winner and winner != "Draw",
        })

    records.sort(key=lambda x: -x["brier"])

    summary = {
        "matches_scored": n,
        "avg_brier":      round(brier_sum / n, 4) if n else None,
        "accuracy":       round(correct_fav / n, 3) if n else None,
        "correct_favs":   correct_fav,
    }
    return {"matches": records, "summary": summary}


# ── Squad availability (injuries / suspensions) ────────────────────────────────

AVAILABILITY_JSON = LIVE / "availability.json"


def _load_availability() -> dict:
    if not AVAILABILITY_JSON.exists():
        return {}
    with open(AVAILABILITY_JSON) as f:
        return json.load(f)


class AvailabilityUpdate(BaseModel):
    status: str        # "full" | "injury" | "suspension"
    player: str = ""
    elo_penalty: int = 0   # Elo points to subtract (0-80)
    notes: str = ""


@app.get("/api/availability")
def get_availability():
    return {"availability": _load_availability()}


@app.put("/api/availability/{team}")
def set_availability(team: str, body: AvailabilityUpdate):
    if team not in ALL_TEAMS:
        raise HTTPException(404, f"Unknown team: {team}")
    data = _load_availability()
    if body.status == "full" and not body.notes:
        data.pop(team, None)
    else:
        data[team] = body.dict()
    with open(AVAILABILITY_JSON, "w") as f:
        json.dump(data, f, indent=2)
    # Trigger background Elo rebuild with penalties
    return {"availability": data}


# ── In-match Poisson win probability ──────────────────────────────────────────

def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _live_probs(lam_h: float, lam_a: float, sh: int, sa: int,
                max_k: int = 10) -> tuple[float, float, float]:
    """Compute P(home win | current score sh-sa, remaining lambdas lam_h/lam_a)."""
    p_hw = p_draw = p_aw = 0.0
    for h in range(max_k):
        ph = _poisson_pmf(h, lam_h)
        if ph < 1e-9:
            break
        for a in range(max_k):
            pa = _poisson_pmf(a, lam_a)
            if pa < 1e-9:
                break
            p = ph * pa
            tot_h, tot_a = sh + h, sa + a
            if   tot_h > tot_a: p_hw  += p
            elif tot_h < tot_a: p_aw  += p
            else:               p_draw += p
    total = p_hw + p_draw + p_aw
    if total == 0:
        return 1/3, 1/3, 1/3
    return p_hw / total, p_draw / total, p_aw / total


# Load Poisson model once at startup
_POISSON_MODEL: dict = {}
_pm_path = ROOT / "models" / "poisson_model.json"
if _pm_path.exists():
    with open(_pm_path) as _f:
        _POISSON_MODEL = json.load(_f)


def _match_lambdas(home_team: str, away_team: str, fraction: float = 1.0) -> tuple[float, float]:
    """Expected goals for each team over 'fraction' of a match."""
    att  = _POISSON_MODEL.get("attack",  {})
    def_ = _POISSON_MODEL.get("defence", {})
    avg  = _POISSON_MODEL.get("avg_goals", 1.35)
    hadv = _POISSON_MODEL.get("home_adv",  1.15)

    ht = norm(home_team)
    at = norm(away_team)
    lh = att.get(ht, 1.0) * def_.get(at, 1.0) * avg * hadv * fraction
    la = att.get(at, 1.0) * def_.get(ht, 1.0) * avg         * fraction
    return lh, la


# Serve built React app in production
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
