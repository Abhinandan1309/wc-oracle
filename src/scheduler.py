"""
Match-aware scraper scheduler for FIFA World Cup 2026.

Reads the live openfootball schedule, converts all kickoff times to UTC,
and fires src/scraper.py ~150 minutes after each match starts
(90 min play + 30 min ET buffer + 30 min results propagation delay).

Usage:
    python src/scheduler.py              # run scheduler (blocks until tournament ends)
    python src/scheduler.py --preview    # print upcoming trigger times and exit
    python src/scheduler.py --now        # trigger scraper immediately, then schedule
"""

import sys
import re
import time
import logging
import argparse
import subprocess
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo   # Python 3.9+ stdlib

BASE_DIR  = Path(__file__).resolve().parent.parent
LIVE_DIR  = BASE_DIR / "data" / "live"
LOG_FILE  = LIVE_DIR / "scheduler.log"
LIVE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S UTC",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json"
    "/master/2026/worldcup.json"
)

# Scraper fires this many minutes after kickoff
TRIGGER_DELAY_MINUTES = 150   # 90 min + 30 min ET buffer + 30 min results delay

# Re-fetch schedule from openfootball this often (to catch any corrections)
SCHEDULE_REFRESH_HOURS = 6


# --------------------------------------------------------------------------- #
# Time parsing
# --------------------------------------------------------------------------- #
def _parse_utc_offset(time_str: str) -> tuple[int, int, int]:
    """
    Parse '13:00 UTC-6' or '20:00 UTC+2' into (hour, minute, utc_offset_hours).
    Returns (hour, minute, offset) where offset is integer hours.
    """
    m = re.match(r"(\d{1,2}):(\d{2})\s*UTC([+-]\d+)", time_str.strip())
    if not m:
        raise ValueError(f"Cannot parse time string: {time_str!r}")
    h, mn, off = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h, mn, off


def to_utc(date_str: str, time_str: str) -> datetime:
    """
    Convert openfootball date + time string to a UTC-aware datetime.

    date_str : '2026-06-11'
    time_str : '13:00 UTC-6'
    """
    h, mn, offset = _parse_utc_offset(time_str)
    local_dt = datetime(
        *[int(x) for x in date_str.split("-")],
        h, mn, 0,
        tzinfo=timezone(timedelta(hours=offset)),
    )
    return local_dt.astimezone(timezone.utc)


def trigger_time_utc(kickoff_utc: datetime) -> datetime:
    """When to fire the scraper for a given match."""
    return kickoff_utc + timedelta(minutes=TRIGGER_DELAY_MINUTES)


# --------------------------------------------------------------------------- #
# Schedule fetcher
# --------------------------------------------------------------------------- #
def fetch_schedule() -> list[dict]:
    """
    Fetch the full 2026 schedule from openfootball.
    Returns list of dicts with keys: team1, team2, kickoff_utc, trigger_utc, played.
    """
    log.info("Fetching match schedule from openfootball...")
    try:
        r = requests.get(OPENFOOTBALL_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.error(f"Failed to fetch schedule: {e}")
        return []

    matches = []
    for m in data.get("matches", []):
        date = m.get("date", "")
        time_str = m.get("time", "")
        if not date or not time_str:
            continue
        try:
            kickoff = to_utc(date, time_str)
            score = m.get("score", {})
            ft = score.get("ft", score.get("FT"))
            played = ft is not None and len(ft) >= 2
            matches.append({
                "team1":       m.get("team1", "?"),
                "team2":       m.get("team2", "?"),
                "stage":       m.get("round", ""),
                "kickoff_utc": kickoff,
                "trigger_utc": trigger_time_utc(kickoff),
                "played":      played,
            })
        except ValueError as e:
            log.warning(f"Skipping match — bad time format: {e}")

    matches.sort(key=lambda x: x["kickoff_utc"])
    log.info(f"  {len(matches)} matches loaded, "
             f"{sum(1 for m in matches if m['played'])} already played.")
    return matches


def upcoming_triggers(matches: list[dict]) -> list[dict]:
    """Return matches whose trigger time is in the future."""
    now = datetime.now(timezone.utc)
    return [m for m in matches if m["trigger_utc"] > now and not m["played"]]


def missed_triggers(matches: list[dict], window_hours: int = 6) -> list[dict]:
    """
    Return matches whose trigger time was missed (passed within the last
    window_hours) and are not yet marked as played in our local data.
    Used at startup to catch up on any results we missed.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)
    return [
        m for m in matches
        if cutoff < m["trigger_utc"] <= now and not m["played"]
    ]


# --------------------------------------------------------------------------- #
# Scraper runner
# --------------------------------------------------------------------------- #
def run_scraper():
    log.info("Firing scraper...")
    result = subprocess.run(
        [sys.executable, "src/scraper.py"],
        capture_output=True, text=True,
        cwd=str(BASE_DIR),
    )
    if result.returncode == 0:
        log.info("Scraper completed successfully.")
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines()[-5:]:
                log.info(f"  scraper: {line}")
    else:
        log.error(f"Scraper failed (exit {result.returncode}).")
        if result.stderr:
            log.error(result.stderr[-300:])


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def run_scheduler(trigger_now: bool = False):
    log.info("=" * 55)
    log.info("  FIFA WC 2026 Match Scheduler started")
    log.info(f"  Trigger delay: {TRIGGER_DELAY_MINUTES} min after kickoff")
    log.info("=" * 55)

    if trigger_now:
        log.info("--now flag set: running scraper immediately.")
        run_scraper()

    last_refresh = datetime.now(timezone.utc) - timedelta(hours=SCHEDULE_REFRESH_HOURS)
    matches = []

    # ── startup catch-up: run scraper for any missed triggers ──────────────
    matches = fetch_schedule()
    last_refresh = datetime.now(timezone.utc)
    missed = missed_triggers(matches, window_hours=6)
    if missed:
        log.info(f"Catching up on {len(missed)} missed trigger(s):")
        for m in missed:
            log.info(f"  Missed: {m['team1']} vs {m['team2']} "
                     f"(was due at {m['trigger_utc'].strftime('%H:%M UTC')})")
        run_scraper()
        matches = fetch_schedule()   # refresh after scrape
        last_refresh = datetime.now(timezone.utc)
    else:
        log.info("No missed triggers on startup.")

    while True:
        now = datetime.now(timezone.utc)

        # Refresh schedule periodically
        if (now - last_refresh).total_seconds() > SCHEDULE_REFRESH_HOURS * 3600:
            matches = fetch_schedule()
            last_refresh = now
            if not matches:
                log.warning("No matches loaded — retrying in 30 min.")
                time.sleep(1800)
                continue

        pending = upcoming_triggers(matches)

        if not pending:
            log.info("All matches have been played or triggered. Scheduler done.")
            break

        next_match = pending[0]
        wait_secs  = (next_match["trigger_utc"] - now).total_seconds()

        log.info(
            f"Next trigger: {next_match['team1']} vs {next_match['team2']} "
            f"({next_match['stage']}) — "
            f"kickoff {next_match['kickoff_utc'].strftime('%Y-%m-%d %H:%M UTC')}, "
            f"scraper fires at {next_match['trigger_utc'].strftime('%H:%M UTC')} "
            f"({wait_secs/3600:.1f}h from now)"
        )

        # Sleep in chunks so we can refresh schedule & log heartbeats
        # Wake every 30 min max; also re-check 5 min before trigger
        while True:
            now = datetime.now(timezone.utc)
            remaining = (next_match["trigger_utc"] - now).total_seconds()

            if remaining <= 0:
                break

            # Wake 5 min before trigger for precision
            if remaining <= 300:
                sleep_secs = remaining + 1
            elif remaining <= 1800:
                sleep_secs = remaining - 240   # wake 4 min early for safety
            else:
                sleep_secs = min(remaining - 300, 1800)  # 30 min max chunk

            log.info(f"  Sleeping {sleep_secs/60:.0f} min "
                     f"(trigger in {remaining/60:.0f} min)...")
            time.sleep(max(sleep_secs, 1))

        # Fire scraper
        log.info(
            f"TRIGGER: {next_match['team1']} vs {next_match['team2']} — "
            f"running scraper now."
        )
        run_scraper()

        # Mark as triggered by refreshing the schedule
        matches = fetch_schedule()
        last_refresh = datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Preview mode
# --------------------------------------------------------------------------- #
def print_preview():
    matches = fetch_schedule()
    pending = upcoming_triggers(matches)
    now = datetime.now(timezone.utc)

    print(f"\n{'='*70}")
    print(f"  Upcoming scraper triggers ({len(pending)} remaining matches)")
    print(f"  Current UTC: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Trigger = kickoff + {TRIGGER_DELAY_MINUTES} min")
    print(f"{'='*70}")
    print(f"  {'#':>3}  {'Date (UTC)':<12} {'Kickoff':>7}  {'Trigger':>7}  {'Match'}")
    print(f"  {'-'*65}")

    # Group by date
    current_date = None
    for i, m in enumerate(pending[:50], 1):
        ko_str = m["kickoff_utc"].strftime("%Y-%m-%d")
        if ko_str != current_date:
            current_date = ko_str
            print()
        in_h = (m["trigger_utc"] - now).total_seconds() / 3600
        print(
            f"  {i:>3}. {m['kickoff_utc'].strftime('%Y-%m-%d'):12}"
            f" {m['kickoff_utc'].strftime('%H:%M'):>7} UTC"
            f"  {m['trigger_utc'].strftime('%H:%M'):>7} UTC"
            f"  {m['team1']} vs {m['team2']}"
            f"  ({in_h:.1f}h)"
        )

    if len(pending) > 50:
        print(f"\n  ... and {len(pending)-50} more matches")
    print()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FIFA WC 2026 match-aware scraper scheduler"
    )
    parser.add_argument("--preview", action="store_true",
                        help="Print upcoming trigger times and exit")
    parser.add_argument("--now", action="store_true",
                        help="Run scraper immediately, then start scheduler")
    args = parser.parse_args()

    if args.preview:
        print_preview()
    else:
        run_scheduler(trigger_now=args.now)
