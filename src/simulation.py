"""
Monte Carlo tournament simulation for FIFA World Cup 2026.

Tournament format:
  48 teams, 12 groups of 4
  Top 2 per group (24) + 8 best 3rd-place teams = 32 → Round of 32
  R32 (16) → R16 (8) → QF (4) → SF (2) → 3rd place (1) + Final (1)
  Total: 72 group + 32 knockout = 104 matches
"""

import json
import time
import numpy as np
import pandas as pd
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LIVE_DIR = BASE_DIR / "data" / "live"
MODELS_DIR = BASE_DIR / "models"

KNOCKOUT_RESULTS_JSON = LIVE_DIR / "knockout_results.json"


def load_knockout_losers() -> dict[str, str]:
    """
    Returns {team_name: round_name} for every team that has already been
    eliminated in a knockout round.  E.g. {"Netherlands": "R32", ...}
    """
    if not KNOCKOUT_RESULTS_JSON.exists():
        return {}
    with open(KNOCKOUT_RESULTS_JSON) as f:
        ko = json.load(f)
    losers: dict[str, str] = {}
    for round_name, matches in ko.items():
        for m in matches:
            loser = m.get("loser")
            if loser and loser not in losers:
                losers[loser] = round_name
    return losers

# --------------------------------------------------------------------------- #
# Groups & bracket
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

# Round of 32 bracket: which group winners/runners-up/3rd teams play each other.
# Follows FIFA 2026 announced bracket structure (simplified).
# Format: [(side_1, side_2), ...] where each entry is (position_description)
# We implement this after computing qualified teams from group stage.
R32_BRACKET_TEMPLATE = [
    # (group_winner, opponent_type)  -- 16 matches
    ("1A", "3CDEF"),
    ("1B", "3ABIJ"),
    ("1C", "3GHKL"),
    ("1D", "3EFGH"),
    ("1E", "3ABCD"),
    ("1F", "3IJKL"),
    ("1G", "2L"),
    ("1H", "2K"),
    ("1I", "2J"),
    ("1J", "2I"),
    ("1K", "2H"),
    ("1L", "2G"),
    ("2A", "2F"),
    ("2B", "2E"),
    ("2C", "2D"),
    ("2?", "2?"),   # filled from best remaining
]
GROUP_LETTERS = list("ABCDEFGHIJKL")


# --------------------------------------------------------------------------- #
# Poisson score sampler (fast, no model calls in hot loop)
# --------------------------------------------------------------------------- #
class FastPoissonSampler:
    """Pre-compute lambda tables for all team pairs to speed up simulations."""

    def __init__(self, attack: dict, defence: dict, avg_goals: float,
                 home_adv: float = 1.15):
        self.attack = attack
        self.defence = defence
        self.avg_goals = avg_goals
        self.home_adv = home_adv
        self._cache: dict[tuple, tuple] = {}

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        key = (home, away)
        if key not in self._cache:
            att_h = self.attack.get(home, 1.0)
            def_a = self.defence.get(away, 1.0)
            att_a = self.attack.get(away, 1.0)
            def_h = self.defence.get(home, 1.0)
            lh = att_h * def_a * self.avg_goals * self.home_adv
            la = att_a * def_h * self.avg_goals
            self._cache[key] = (lh, la)
        return self._cache[key]

    def sample_score(self, home: str, away: str, rng: np.random.Generator) -> tuple[int, int]:
        lh, la = self.lambdas(home, away)
        return int(rng.poisson(lh)), int(rng.poisson(la))


# --------------------------------------------------------------------------- #
# Pre-compute ensemble win probabilities for knockout matchups
# --------------------------------------------------------------------------- #
class KnockoutProbCache:
    """Cache P(home beats away in knockout) for team pairs."""

    def __init__(self, elo_ratings: dict):
        self.elo = elo_ratings
        self._cache: dict[tuple, float] = {}

    def p_home_wins(self, home: str, away: str) -> float:
        key = (home, away)
        if key not in self._cache:
            ra = self.elo.get(home, 1500.0)
            rb = self.elo.get(away, 1500.0)
            # Standard Elo 2-outcome probability (no draws in knockout)
            p = 1 / (1 + 10 ** ((rb - ra) / 400))
            self._cache[key] = p
        return self._cache[key]


# --------------------------------------------------------------------------- #
# Group stage simulation
# --------------------------------------------------------------------------- #
def _group_result_outcome(hs: int, as_: int) -> tuple[int, int, int, int]:
    """Returns (home_pts, away_pts, home_gd_delta, away_gd_delta)."""
    gd = hs - as_
    if hs > as_:
        return 3, 0, gd, -gd
    elif hs == as_:
        return 1, 1, 0, 0
    else:
        return 0, 3, gd, -gd


def simulate_group_stage(
    played_results: list[dict],
    schedule_df: pd.DataFrame,
    sampler: FastPoissonSampler,
    rng: np.random.Generator,
) -> dict[str, dict[str, dict]]:
    """
    Returns standings: {group: {team: {pts, gd, gf, ga, w, d, l}}}
    Uses actual played results + samples unplayed matches.
    """
    standings: dict[str, dict[str, dict]] = {
        g: {t: {"pts": 0, "gd": 0, "gf": 0, "ga": 0, "w": 0, "d": 0, "l": 0}
            for t in teams}
        for g, teams in GROUPS_2026.items()
    }

    def apply_result(group: str, home: str, away: str, hs: int, as_: int):
        if group not in standings:
            return
        hpts, apts, hgd, agd = _group_result_outcome(hs, as_)
        for team, pts, gd, gf, ga in [
            (home, hpts, hgd, hs, as_),
            (away, apts, agd, as_, hs),
        ]:
            if team in standings[group]:
                s = standings[group][team]
                s["pts"] += pts
                s["gd"]  += gd
                s["gf"]  += gf
                s["ga"]  += ga
                if pts == 3:   s["w"] += 1
                elif pts == 1: s["d"] += 1
                else:          s["l"] += 1

    # Apply already-played results
    for r in played_results:
        apply_result(r["group"], r["home_team"], r["away_team"],
                     int(r["home_score"]), int(r["away_score"]))

    # Simulate unplayed group stage matches
    unplayed = schedule_df[
        (schedule_df["played"] == False) &
        (schedule_df["stage"].str.startswith("Matchday"))
    ]
    for _, m in unplayed.iterrows():
        home, away = str(m["home_team"]), str(m["away_team"])
        group = str(m.get("group", "")).replace("Group ", "")
        hs, as_ = sampler.sample_score(home, away, rng)
        apply_result(group, home, away, hs, as_)

    return standings


def rank_group(team_stats: dict[str, dict]) -> list[str]:
    """Sort group teams: pts → gd → gf → name (tiebreaker)."""
    return sorted(
        team_stats.keys(),
        key=lambda t: (-team_stats[t]["pts"], -team_stats[t]["gd"],
                       -team_stats[t]["gf"], t),
    )


def select_qualified_teams(standings: dict[str, dict[str, dict]]) -> dict:
    """
    Returns:
      winners: {group: team}
      runners_up: {group: team}
      third_place_qualified: [team]  (8 best 3rd-place teams)
    """
    winners: dict[str, str] = {}
    runners_up: dict[str, str] = {}
    third_place: list[tuple] = []  # (pts, gd, gf, group, team)

    for group in GROUP_LETTERS:
        ranked = rank_group(standings[group])
        winners[group]    = ranked[0]
        runners_up[group] = ranked[1]
        t = standings[group][ranked[2]]
        third_place.append((t["pts"], t["gd"], t["gf"], group, ranked[2]))

    # Best 8 third-place teams
    third_place.sort(key=lambda x: (-x[0], -x[1], -x[2]))
    top8_third = [(g, team) for _, _, _, g, team in third_place[:8]]

    return {
        "winners":    winners,
        "runners_up": runners_up,
        "third_place_qualified": top8_third,  # list of (group, team)
    }


# --------------------------------------------------------------------------- #
# Knockout stage
# --------------------------------------------------------------------------- #
def ko_winner(home: str, away: str, cache: KnockoutProbCache,
              rng: np.random.Generator) -> str:
    """Sample the winner of a knockout match (no draws)."""
    p = cache.p_home_wins(home, away)
    return home if rng.random() < p else away


def simulate_knockout(qualified: dict, cache: KnockoutProbCache,
                      rng: np.random.Generator) -> dict[str, list[str]]:
    """
    Build R32 bracket and simulate through the Final.
    Returns {round: [teams_that_reached_this_round]}.
    """
    winners   = qualified["winners"]      # {group: team}
    runners   = qualified["runners_up"]   # {group: team}
    thirds    = qualified["third_place_qualified"]  # [(group, team), ...]

    # Assign 3rd-place teams to bracket slots (top-ranked first)
    third_teams = [t for _, t in thirds]

    # Build R32 fixtures (32 teams → 16 matches)
    # FIFA 2026 bracket: winners face 3rd-place, runners face each other
    # We use a fixed ordered bracket across group letters
    r32_fixtures = []

    # 12 winners vs slots (8 face 3rd-place, 4 face runners-up cross-group)
    for i, g in enumerate(GROUP_LETTERS):
        if i < 8:  # first 8 winners face 3rd-place teams
            opp = third_teams[i] if i < len(third_teams) else runners[GROUP_LETTERS[11 - i]]
            r32_fixtures.append((winners[g], opp))
        else:      # last 4 winners face runners-up from opposite side
            opp_g = GROUP_LETTERS[11 - i]
            r32_fixtures.append((winners[g], runners[opp_g]))

    # Remaining 4 runner-up vs runner-up matches
    used_runners = {GROUP_LETTERS[11 - i] for i in range(8, 12)}
    remaining_runner_groups = [g for g in GROUP_LETTERS if g not in used_runners]
    for i in range(0, len(remaining_runner_groups), 2):
        if i + 1 < len(remaining_runner_groups):
            r32_fixtures.append((runners[remaining_runner_groups[i]],
                                  runners[remaining_runner_groups[i + 1]]))

    # Track advancement
    advancement: dict[str, list[str]] = defaultdict(list)

    def play_round(fixtures: list[tuple], round_name: str) -> list[str]:
        round_winners = []
        for home, away in fixtures:
            w = ko_winner(home, away, cache, rng)
            advancement[round_name].append(w)
            round_winners.append(w)
        return round_winners

    # R32 → R16 → QF → SF
    r16_teams   = play_round(r32_fixtures, "R32")
    r16_fixtures = [(r16_teams[i], r16_teams[i + 1]) for i in range(0, len(r16_teams), 2)]

    qf_teams    = play_round(r16_fixtures, "R16")
    qf_fixtures  = [(qf_teams[i], qf_teams[i + 1]) for i in range(0, len(qf_teams), 2)]

    sf_teams    = play_round(qf_fixtures, "QF")
    sf_fixtures  = [(sf_teams[0], sf_teams[1]), (sf_teams[2], sf_teams[3])]

    finalists   = []
    third_place_teams = []
    for home, away in sf_fixtures:
        w = ko_winner(home, away, cache, rng)
        loser = away if w == home else home
        finalists.append(w)
        third_place_teams.append(loser)
        advancement["SF"].append(w)

    # 3rd place match
    third_winner = ko_winner(third_place_teams[0], third_place_teams[1], cache, rng)
    advancement["3rd"].append(third_winner)

    # Final
    champion = ko_winner(finalists[0], finalists[1], cache, rng)
    advancement["Final"].append(finalists[0])
    advancement["Final"].append(finalists[1])
    advancement["Winner"].append(champion)

    return dict(advancement)


# --------------------------------------------------------------------------- #
# Monte Carlo runner
# --------------------------------------------------------------------------- #
class MonteCarloSimulator:

    ROUND_NAMES = ["R32", "R16", "QF", "SF", "Final", "Winner"]

    def __init__(self):
        self.sampler: FastPoissonSampler | None = None
        self.cache:   KnockoutProbCache  | None = None
        self.schedule_df: pd.DataFrame   | None = None
        self.played_results: list[dict]  | None = None

    def load(self):
        """Load models and data needed for simulation."""
        import json
        # Load Poisson parameters
        with open(MODELS_DIR / "poisson_model.json") as f:
            pm = json.load(f)
        self.sampler = FastPoissonSampler(pm["attack"], pm["defence"], pm["avg_goals"])

        # Load Elo ratings (prefer WC 2026-updated live ratings if available)
        _elo_live = LIVE_DIR / "elo_live.json"
        _elo_path = _elo_live if _elo_live.exists() else (MODELS_DIR / "elo_ratings.json")
        with open(_elo_path) as f:
            elo = json.load(f)
        src = "live-updated" if _elo_live.exists() else "base"
        print(f"  Elo: {src} ratings loaded.")
        self.cache = KnockoutProbCache(elo)

        # Load schedule
        sched_path = LIVE_DIR / "schedule_2026.csv"
        self.schedule_df = pd.read_csv(sched_path)
        self.schedule_df["home_team"] = self.schedule_df["home_team"].astype(str)
        self.schedule_df["away_team"] = self.schedule_df["away_team"].astype(str)

        # Build played results list with group info
        played = self.schedule_df[self.schedule_df["played"] == True].copy()
        self.played_results = []
        for _, row in played.iterrows():
            group = str(row.get("group", "")).replace("Group ", "")
            if group and group in GROUP_LETTERS:
                self.played_results.append({
                    "group":      group,
                    "home_team":  str(row["home_team"]),
                    "away_team":  str(row["away_team"]),
                    "home_score": int(row["home_score"]),
                    "away_score": int(row["away_score"]),
                })
        print(f"  Loaded {len(self.played_results)} played group results.")
        print(f"  Loaded {(self.schedule_df['played'] == False).sum()} upcoming matches.")
        return self

    def run(self, n_simulations: int = 100_000, seed: int = 42,
            verbose: bool = True) -> dict:
        """
        Run n_simulations full tournaments.
        Returns probability tables per team per round.
        """
        if self.sampler is None or self.cache is None:
            raise RuntimeError("Call .load() first.")

        all_teams = [t for teams in GROUPS_2026.values() for t in teams]
        counts: dict[str, dict[str, int]] = {
            t: {r: 0 for r in ["GroupExit", "R32", "R16", "QF", "SF", "Final", "Winner"]}
            for t in all_teams
        }

        # Teams already eliminated in knockout — they can't advance further
        ko_losers = load_knockout_losers()  # {team: round_eliminated}

        rng = np.random.default_rng(seed)
        t0 = time.time()
        batch = max(1, n_simulations // 10)

        for i in range(n_simulations):
            if verbose and (i + 1) % batch == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                remaining = (n_simulations - i - 1) / rate
                print(f"  {i+1:>7,}/{n_simulations:,}  "
                      f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s left)")

            # Simulate group stage
            standings = simulate_group_stage(
                self.played_results, self.schedule_df, self.sampler, rng)

            # Determine qualified teams
            qualified = select_qualified_teams(standings)

            # All teams that didn't qualify are group exits
            qualified_set = (
                set(qualified["winners"].values()) |
                set(qualified["runners_up"].values()) |
                {t for _, t in qualified["third_place_qualified"]}
            )
            for team in all_teams:
                if team not in qualified_set:
                    counts[team]["GroupExit"] += 1

            # Simulate knockout
            adv = simulate_knockout(qualified, self.cache, rng)

            # Strip teams already eliminated from the actual tournament
            for team, elim_round in ko_losers.items():
                elim_idx = self.ROUND_NAMES.index(elim_round)
                for rnd in self.ROUND_NAMES[elim_idx:]:
                    rnd_list = adv.get(rnd, [])
                    if team in rnd_list:
                        rnd_list.remove(team)

            for round_name in self.ROUND_NAMES:
                for team in adv.get(round_name, []):
                    if team in counts:
                        counts[team][round_name] += 1

        elapsed = time.time() - t0
        print(f"\n  {n_simulations:,} simulations completed in {elapsed:.1f}s "
              f"({n_simulations/elapsed:.0f}/s)")

        # Convert to probabilities
        results = {}
        for team in all_teams:
            results[team] = {
                "group": _find_group(team),
                "GroupExit": round(counts[team]["GroupExit"] / n_simulations, 4),
                "R32":       round(counts[team]["R32"]       / n_simulations, 4),
                "R16":       round(counts[team]["R16"]       / n_simulations, 4),
                "QF":        round(counts[team]["QF"]        / n_simulations, 4),
                "SF":        round(counts[team]["SF"]        / n_simulations, 4),
                "Final":     round(counts[team]["Final"]     / n_simulations, 4),
                "Winner":    round(counts[team]["Winner"]    / n_simulations, 4),
            }

        results["_meta"] = {
            "n_simulations": n_simulations,
            "elapsed_seconds": round(elapsed, 1),
            "played_matches": len(self.played_results),
        }
        return results


def _find_group(team: str) -> str:
    for g, teams in GROUPS_2026.items():
        if team in teams:
            return g
    return "?"


CHAMPION_HISTORY_JSON = LIVE_DIR / "champion_history.json"


def _append_champion_history(results: dict):
    """Append a timestamped snapshot of champion probabilities for trending."""
    from datetime import datetime
    history: list[dict] = []
    if CHAMPION_HISTORY_JSON.exists():
        try:
            with open(CHAMPION_HISTORY_JSON) as f:
                history = json.load(f)
        except Exception:
            history = []

    snapshot = {
        "ts":    datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "n":     results.get("_meta", {}).get("n_simulations", 0),
        "probs": {t: d["Winner"] for t, d in results.items()
                  if not t.startswith("_")},
    }
    history.append(snapshot)
    history = history[-100:]   # keep last 100 runs

    with open(CHAMPION_HISTORY_JSON, "w") as f:
        json.dump(history, f)


# --------------------------------------------------------------------------- #
# Save / load results
# --------------------------------------------------------------------------- #
def save_results(results: dict, path: Path | None = None):
    out = path or (PROCESSED_DIR / "simulation_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved simulation results -> {out.name}")
    _append_champion_history(results)


def load_results(path: Path | None = None) -> dict:
    p = path or (PROCESSED_DIR / "simulation_results.json")
    with open(p) as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Pretty-print summary
# --------------------------------------------------------------------------- #
def print_summary(results: dict, top_n: int = 20):
    meta = results.get("_meta", {})
    print(f"\n{'='*65}")
    print(f"  Simulation Results  ({meta.get('n_simulations', '?'):,} runs)")
    print(f"{'='*65}")
    print(f"  {'Team':<22} {'Group':>5}  {'R32':>6}  {'R16':>6}  {'QF':>6}  {'SF':>6}  {'Final':>6}  {'Win':>6}")
    print(f"  {'-'*60}")

    teams = [(t, d) for t, d in results.items() if not t.startswith("_")]
    teams.sort(key=lambda x: -x[1]["Winner"])

    for team, d in teams[:top_n]:
        print(
            f"  {team:<22} "
            f"{'Gp'+d['group']:>5}  "
            f"{d['R32']:>5.1%}  "
            f"{d['R16']:>5.1%}  "
            f"{d['QF']:>5.1%}  "
            f"{d['SF']:>5.1%}  "
            f"{d['Final']:>5.1%}  "
            f"{d['Winner']:>5.1%}"
        )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(n: int = 100_000):
    print("=" * 55)
    print("  FIFA WC 2026 Predictor — Step 5: Simulation")
    print("=" * 55 + "\n")

    sim = MonteCarloSimulator()
    sim.load()

    # Quick test run first
    print(f"\nTest run: 1,000 simulations...")
    test_results = sim.run(n_simulations=1_000, verbose=False)
    print("  Test passed. Sample winners:")
    teams = [(t, d["Winner"]) for t, d in test_results.items() if not t.startswith("_")]
    for team, p in sorted(teams, key=lambda x: -x[1])[:5]:
        print(f"    {team:<20} {p:.1%}")

    # Full run
    print(f"\nFull run: {n:,} simulations...")
    results = sim.run(n_simulations=n, verbose=True)
    save_results(results)
    print_summary(results)
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100_000)
    args = parser.parse_args()
    run(n=args.n)
