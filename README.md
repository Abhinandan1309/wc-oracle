# ⚽ WC Oracle — FIFA World Cup 2026 Predictor

> An end-to-end machine learning project that predicts the FIFA World Cup 2026 winner using an ensemble of XGBoost, Poisson regression, and Elo ratings — with a live React dashboard that auto-updates after every match.

<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/en/thumb/3/30/2026_FIFA_World_Cup.svg/200px-2026_FIFA_World_Cup.svg.png" height="120" alt="FIFA World Cup 2026" />
</p>

---

## Current Predictions *(Round of 16 · 75 matches played · 100,000 simulations)*

| # | Team | 🏆 Win % | Final % | Semi-Final % |
|---|------|-----------|---------|--------------|
| 1 | 🇫🇷 France | **19.3%** | 31.8% | 31.8% |
| 2 | 🇧🇷 Brazil | 14.7% | 23.6% | 23.6% |
| 3 | 🇦🇷 Argentina | 7.0% | 14.0% | 14.0% |
| 4 | 🇪🇸 Spain | 5.2% | 9.8% | 9.8% |
| 5 | 🇲🇽 Mexico | 3.8% | 8.1% | 8.1% |
| 6 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England | 3.7% | 9.0% | 9.0% |
| 7 | 🇵🇹 Portugal | 3.1% | 7.9% | 7.9% |
| 8 | 🇨🇴 Colombia | 3.1% | 7.9% | 7.9% |
| 9 | 🇧🇪 Belgium | 3.0% | 6.4% | 6.4% |
| 10 | 🇳🇴 Norway | 2.1% | 6.1% | 6.1% |

*Recalculated automatically after every match. Netherlands & Germany eliminated.*

---

## Dashboard Features

| Page | Description |
|------|-------------|
| 🔴 **Live Tracker** | Real-time scores from ESPN · Auto-refresh every 30s |
| 📊 **Group Standings** | Live points table for all 12 groups |
| 🔍 **Team Explorer** | Stage-by-stage win probabilities for all 48 teams |
| 🏆 **Bracket Simulator** | Most likely bracket from 100,000 simulations · Re-run on demand |
| 🎯 **Prediction Tracker** | Result accuracy tracking as the tournament progresses |

Built with **React + Vite + Tailwind CSS** (frontend) and **FastAPI** (backend). Full dark mode support.

---

## ML Pipeline

```
openfootball JSON  +  StatsBomb open data
            │
      data_pipeline.py         ← 974 historical WC matches (1930–2026)
            │
  feature_engineering.py       ← 22 features per match
            │
    ┌───────┴────────┬──────────────┐
 XGBoost         Poisson          Elo
 57.4% acc       50.0% acc     55.9% acc
 (weight 37.5%)  (weight 46.8%) (weight 15.7%)
    └───────┬────────┘──────────────┘
         ensemble.py              ← Nelder-Mead weight optimisation
            │                        Log-loss: 1.016
       simulation.py             ← 100,000 Monte Carlo simulations
            │
        api/main.py              ← FastAPI REST endpoints
            │
       frontend/src/             ← React dashboard
            ↑
        scraper.py               ← Fetches live results after each match
            ↑
       scheduler.py              ← Match-aware trigger (kickoff + 150 min)
```

### Model Details

**XGBoost Classifier** — trained on 890 historical WC matches (1930–2022), validated on 2022. Features include Elo difference, FIFA ranking difference, recent form (5-match rolling), head-to-head win rate, WC experience, host nation flag, rest days, and average goals scored/conceded.

**Poisson Goal Model** — estimates each team's attack strength and defensive weakness from historical WC goal data. Samples scorelines from independent Poisson distributions and converts the full score matrix into win/draw/loss probabilities. Home advantage factor: 1.15.

**Elo Rating System** — calculated chronologically from every WC match since 1930. K-factor = 40. Converts Elo difference to 3-way probabilities via a logistic function with a calibrated draw term.

**Ensemble** — weights optimised on the 2022 holdout set via Nelder-Mead (scipy). Minimises log-loss rather than raw accuracy for better probability calibration.

**Monte Carlo Simulation** — 100,000 full tournament simulations. Group stage uses Poisson score sampling; knockout rounds use ensemble win probabilities (no draws). Handles the full 2026 format: 48 teams, 12 groups, 8 best 3rd-place teams rule, 104 total matches.

---

## Setup

### Prerequisites
- Python 3.11+ (via [Miniforge](https://github.com/conda-forge/miniforge))
- Node.js 18+

### 1. Python environment

```bash
conda create -n fifa_wc python=3.11 -y
conda activate fifa_wc
pip install -r requirements.txt
```

### 2. Run the ML pipeline *(one-time)*

```bash
python src/data_pipeline.py          # fetch + merge all data sources
python src/feature_engineering.py    # build 22 features per match
python src/ensemble.py               # train models + generate predictions
python src/simulation.py             # run 100,000 simulations
```

### 3. Start the API

```bash
# Windows
run_api.bat

# macOS / Linux
uvicorn api.main:app --reload --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### 5. Live update scheduler *(optional)*

```bash
python src/scheduler.py
# Fires scraper.py ~150 min after each kickoff (90 min play + 30 min ET + 30 min delay)
# On Windows, copy run_scheduler.bat to the Startup folder to auto-start on reboot
```

---

## Data Sources

| Source | Usage |
|--------|-------|
| [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) | Historical results (1930–2022) + live 2026 match schedule & results |
| [StatsBomb open data](https://github.com/statsbomb/open-data) | Detailed 2018 & 2022 WC match data via `statsbombpy` |
| [ESPN scoreboard API](https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard) | Live in-game scores and match clock (unofficial, no key required) |
| fbref.com | Fallback live score scraper |

---

## Project Structure

```
wc-oracle/
├── api/
│   └── main.py                  # FastAPI — standings, schedule, simulation, live scores
├── frontend/
│   ├── src/
│   │   ├── pages/               # Live, Standings, TeamExplorer, Bracket, Tracker
│   │   ├── components/          # Layout, Sidebar, Header, Ticker, MatchCard, GroupTable
│   │   └── hooks/useApi.js      # React Query data fetching + 30s live polling
│   ├── package.json
│   └── vite.config.js           # Vite proxy → FastAPI on :8000
├── src/
│   ├── data_pipeline.py         # Data fetching + merging
│   ├── feature_engineering.py   # Feature builder (22 features, Elo, form, H2H)
│   ├── models.py                # XGBoost, Poisson, Elo implementations
│   ├── ensemble.py              # Weighted ensemble + weight optimisation
│   ├── simulation.py            # Monte Carlo tournament simulator
│   ├── scraper.py               # Live result scraper (openfootball + fbref)
│   └── scheduler.py             # Match-aware scraper scheduler
├── dashboard/
│   └── app.py                   # Legacy Streamlit dashboard
├── data/
│   ├── processed/               # features, predictions, simulation results
│   └── live/                    # schedule_2026.csv, results
├── models/                      # Trained model artefacts (.joblib, .json)
├── run_api.bat
├── run_frontend.bat
├── run_scheduler.bat
└── requirements.txt
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/standings` | Current group standings (computed from played matches) |
| `GET /api/schedule` | Full match schedule with predictions for upcoming games |
| `GET /api/simulation` | Team win probabilities from Monte Carlo simulation |
| `GET /api/live` | Live scores, upcoming today, and recent results (ESPN) |
| `GET /api/teams` | All 48 teams and group assignments |
| `POST /api/simulate` | Trigger a fresh 10,000-run simulation (async) |

---

*Built by [Abhinandan](https://github.com/Abhinandan1309)*
