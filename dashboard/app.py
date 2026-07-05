import sys
import json
import subprocess
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
LIVE      = ROOT / "data" / "live"
SRC       = ROOT / "src"
sys.path.insert(0, str(SRC))

st.set_page_config(
    page_title="WC Oracle — FIFA World Cup 2026",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
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
ALL_TEAMS    = [t for teams in GROUPS_2026.values() for t in teams]
ROUND_LABELS = {
    "R32": "Rd of 32", "R16": "Rd of 16",
    "QF": "Quarter-Final", "SF": "Semi-Final",
    "Final": "Final", "Winner": "Champion",
}
WC_LOGO = (
    "https://upload.wikimedia.org/wikipedia/en/thumb/3/30/"
    "2026_FIFA_World_Cup.svg/200px-2026_FIFA_World_Cup.svg.png"
)
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
PAGE_MAP = {
    "🏠  Live Group Standings": "standings",
    "🔍  Team Explorer":        "team",
    "🏆  Bracket Simulator":   "bracket",
    "📊  Prediction Tracker":  "tracker",
}


def norm(name: str) -> str:
    return NAME_MAP.get(str(name).strip(), str(name).strip())


def safe_prob(val, default: float = 1 / 3) -> float:
    try:
        f = float(val)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def conf_color(p: float) -> str:
    if not isinstance(p, (int, float)) or p != p:
        return "#ea4335"
    if p >= 0.65:
        return "#34a853"
    if p >= 0.50:
        return "#fbbc04"
    return "#ea4335"


def conf_class(p: float) -> str:
    if not isinstance(p, (int, float)) or p != p:
        return "low"
    if p >= 0.65:
        return "high"
    if p >= 0.50:
        return "medium"
    return "low"


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
/* === WC Oracle Design System === */
[data-testid="stAppViewContainer"] { background-color: #f8f9fa !important; }
[data-testid="stMain"]             { background-color: #f8f9fa !important; }
section[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(170deg, #0d1b2a 0%, #1a3a6e 65%, #1565c0 100%);
}
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
#MainMenu, footer, header { visibility: hidden; }

.wco-card {
    background: white; border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 12px;
}
.match-card {
    background: white; border-radius: 12px; padding: 14px 16px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07); margin-bottom: 10px;
    border-left: 4px solid #1a73e8;
    transition: transform 0.15s, box-shadow 0.15s;
}
.match-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(26,115,232,0.18); }
.match-card.high   { border-left-color: #34a853; }
.match-card.medium { border-left-color: #fbbc04; }
.match-card.low    { border-left-color: #ea4335; }

.group-card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 16px; }
.group-header { background: linear-gradient(90deg, #1a3a6e, #1a73e8); color: white !important; font-weight: 700; font-size: 13px; padding: 10px 14px; letter-spacing: 1px; text-transform: uppercase; }
.standing-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.standing-table th { background: #f0f4ff; color: #3c4043; font-size: 11px; font-weight: 700; padding: 7px 6px; text-align: center; text-transform: uppercase; letter-spacing: 0.5px; }
.standing-table th:nth-child(2) { text-align: left; }
.standing-table td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #f5f5f5; }
.standing-table td:nth-child(2) { text-align: left; font-weight: 500; }
.standing-table tr:last-child td { border-bottom: none; }
.standing-table tr.q1 td { background: rgba(52,168,83,0.12); font-weight: 600; }
.standing-table tr.q2 td { background: rgba(52,168,83,0.06); }

.ticker-wrap { background: #0d1b2a; border-radius: 10px; padding: 10px 16px; margin-bottom: 18px; display: flex; align-items: center; gap: 12px; overflow: hidden; }
.ticker-live { background: #ea4335; color: white !important; padding: 3px 10px; border-radius: 5px; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; white-space: nowrap; animation: pulse 1.5s ease-in-out infinite; flex-shrink: 0; }
.ticker-content { overflow: hidden; flex: 1; }
.ticker-scroll { display: inline-block; white-space: nowrap; animation: ticker-anim 50s linear infinite; color: #e8eaed; font-size: 13px; font-weight: 500; }
@keyframes pulse { 0%, 100% { opacity:1; } 50% { opacity:0.6; } }
@keyframes ticker-anim { from { transform: translateX(100%); } to { transform: translateX(-200%); } }

.prob-stage-card { background: white; border-radius: 10px; padding: 12px 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }
.prob-bar-outer { background: #e8f0fe; border-radius: 4px; height: 6px; flex: 1; }
.prob-bar-inner { border-radius: 4px; height: 6px; }

.feat-card { background: white; border-radius: 10px; padding: 14px 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; margin-bottom: 8px; }
.feat-val { font-size: 20px; font-weight: 700; color: #1a73e8; }
.feat-lbl { font-size: 10px; color: #80868b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }

.bracket-team { background: white; border-radius: 8px; padding: 8px 10px; box-shadow: 0 1px 6px rgba(0,0,0,0.08); text-align: center; border-bottom: 3px solid #1a73e8; margin: 4px 0; transition: transform 0.15s; }
.bracket-team:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(26,115,232,0.2); }

.section-title { font-size: 20px; font-weight: 700; color: #0d1b2a; margin-bottom: 4px; margin-top: 8px; }
.section-sub   { font-size: 13px; color: #80868b; margin-bottom: 16px; }
.wco-divider   { border: none; border-top: 1px solid #e0e0e0; margin: 22px 0; }
</style>""", unsafe_allow_html=True)


# ── data loaders ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_schedule() -> pd.DataFrame:
    p = LIVE / "schedule_2026.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["group"]     = df["group"].astype(str).str.replace("Group ", "", regex=False)
    df["home_team"] = df["home_team"].apply(norm)
    df["away_team"] = df["away_team"].apply(norm)
    return df


@st.cache_data(ttl=300)
def load_simulation() -> dict:
    p = PROCESSED / "simulation_results.json"
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


@st.cache_data(ttl=300)
def load_predictions() -> pd.DataFrame:
    p = PROCESSED / "predictions_2026.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


@st.cache_data(ttl=300)
def load_features() -> pd.DataFrame:
    p = PROCESSED / "features_train.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


# ── helpers ───────────────────────────────────────────────────────────────────
def compute_group_standings(schedule: pd.DataFrame) -> dict:
    standings = {
        g: {t: {"Pts": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0}
            for t in teams}
        for g, teams in GROUPS_2026.items()
    }
    played = schedule[schedule["played"] == True]
    for _, m in played.iterrows():
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
            s["Pts"] += pts; s["W"] += w; s["D"] += d; s["L"] += l
            s["GF"] += gf;   s["GA"] += ga; s["GD"] += gf - ga
    result = {}
    for g, ts in standings.items():
        rows = [{"Team": t, **s} for t, s in ts.items()]
        df = (pd.DataFrame(rows)
              .sort_values(["Pts", "GD", "GF"], ascending=False)
              .reset_index(drop=True))
        df.index = df.index + 1
        result[g] = df
    return result


def render_group_table(df: pd.DataFrame, g: str) -> str:
    rows_html = ""
    for rank, row in df.iterrows():
        cls    = "q1" if rank == 1 else ("q2" if rank == 2 else "")
        gd     = row["GD"]
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        gd_col = "#34a853" if gd > 0 else ("#ea4335" if gd < 0 else "#5f6368")
        fw     = "700" if rank == 1 else ("600" if rank == 2 else "400")
        rows_html += f"""
        <tr class="{cls}">
          <td style="color:#80868b;font-size:11px;">{rank}</td>
          <td style="text-align:left;font-weight:{fw};">{row['Team']}</td>
          <td style="font-weight:700;color:#0d1b2a;">{row['Pts']}</td>
          <td>{row['W']}</td><td>{row['D']}</td><td>{row['L']}</td>
          <td>{row['GF']}</td><td>{row['GA']}</td>
          <td style="color:{gd_col};font-weight:600;">{gd_str}</td>
        </tr>"""
    return f"""
    <div class="group-card">
      <div class="group-header">&#9917; Group {g}</div>
      <table class="standing-table">
        <thead>
          <tr><th>#</th><th>Team</th><th>Pts</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


def render_match_card(m: pd.Series, p_home: float, p_draw: float, p_away: float) -> str:
    fav   = m["home_team"] if p_home >= p_away else m["away_team"]
    fav_p = max(p_home, p_away)
    cls   = conf_class(fav_p)
    color = conf_color(fav_p)
    grp   = m.get("group", "?")
    return f"""
    <div class="match-card {cls}">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
        <span style="font-size:11px;color:#80868b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;">Group {grp}</span>
        <span style="font-size:11px;color:{color};font-weight:700;">Fav: {fav} ({fav_p:.0%})</span>
      </div>
      <div style="font-size:15px;font-weight:700;color:#0d1b2a;margin-bottom:10px;">
        {m['home_team']} <span style="color:#1a73e8;">vs</span> {m['away_team']}
      </div>
      <div style="display:flex;gap:6px;font-size:11px;color:#5f6368;">
        <div style="flex:1;text-align:center;">
          <div style="font-weight:700;color:#0d1b2a;">{p_home:.0%}</div>
          <div class="prob-bar-outer"><div class="prob-bar-inner" style="width:{p_home*100:.0f}%;background:#34a853;"></div></div>
          <div style="margin-top:3px;">Home</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-weight:700;color:#0d1b2a;">{p_draw:.0%}</div>
          <div class="prob-bar-outer"><div class="prob-bar-inner" style="width:{p_draw*100:.0f}%;background:#fbbc04;"></div></div>
          <div style="margin-top:3px;">Draw</div>
        </div>
        <div style="flex:1;text-align:center;">
          <div style="font-weight:700;color:#0d1b2a;">{p_away:.0%}</div>
          <div class="prob-bar-outer"><div class="prob-bar-inner" style="width:{p_away*100:.0f}%;background:#ea4335;"></div></div>
          <div style="margin-top:3px;">Away</div>
        </div>
      </div>
    </div>"""


def render_ticker(schedule: pd.DataFrame) -> None:
    if schedule.empty:
        return
    items = []
    for _, m in schedule[schedule["played"] == True].tail(8).iterrows():
        items.append(
            f"&#9989; {m['home_team']} {int(m['home_score'])}&ndash;{int(m['away_score'])} {m['away_team']}"
        )
    for _, m in schedule[schedule["played"] == False].head(5).iterrows():
        items.append(f"&#9200; {m['home_team']} vs {m['away_team']}")
    if not items:
        return
    text = "&nbsp;&nbsp;&nbsp;&#183;&nbsp;&nbsp;&nbsp;".join(items)
    st.markdown(f"""
    <div class="ticker-wrap">
      <span class="ticker-live">LIVE</span>
      <div class="ticker-content">
        <span class="ticker-scroll">{text}</span>
      </div>
    </div>""", unsafe_allow_html=True)


def page_header(title: str, sub: str) -> None:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1b2a 0%,#1a3a6e 50%,#1a73e8 100%);
                border-radius:16px;padding:22px 30px;color:white;margin-bottom:20px;
                display:flex;align-items:center;gap:20px;
                box-shadow:0 4px 24px rgba(26,115,232,0.3);">
      <img src="{WC_LOGO}" style="height:58px;border-radius:8px;" />
      <div>
        <div style="font-size:11px;opacity:0.7;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">WC Oracle</div>
        <div style="font-size:22px;font-weight:800;letter-spacing:-0.5px;margin-top:2px;">{title}</div>
        <div style="font-size:13px;opacity:0.75;margin-top:3px;">{sub}</div>
      </div>
      <div style="margin-left:auto;font-size:11px;opacity:0.6;text-align:right;">
        &#128260; Updates after each match
      </div>
    </div>""", unsafe_allow_html=True)


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:22px 10px 12px;">
      <img src="{WC_LOGO}" style="height:76px;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.4);" />
      <div style="font-size:22px;font-weight:800;margin-top:10px;letter-spacing:-0.5px;">WC Oracle</div>
      <div style="font-size:11px;opacity:0.6;margin-top:2px;">FIFA World Cup 2026</div>
    </div>""", unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigate",
        list(PAGE_MAP.keys()),
        label_visibility="collapsed",
    )
    page_key = PAGE_MAP[page]

    st.divider()

    _sim = load_simulation()
    _meta = _sim.get("_meta", {})
    if _meta:
        st.markdown(f"""
        <div style="font-size:12px;opacity:0.75;padding:0 4px;line-height:2.2;">
          &#127922; <b>{_meta.get('n_simulations', 0):,}</b> simulations<br>
          &#9917; <b>{_meta.get('played_matches', 0)}</b> matches played
        </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:10px;opacity:0.4;text-align:center;margin-top:20px;">
      XGBoost &middot; Poisson &middot; Elo Ensemble
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Live Group Standings
# ══════════════════════════════════════════════════════════════════════════════
if page_key == "standings":
    schedule = load_schedule()
    preds    = load_predictions()

    page_header(
        "Live Group Standings",
        "FIFA World Cup 2026 &middot; All 12 groups",
    )
    render_ticker(schedule)

    if schedule.empty:
        st.error("schedule_2026.csv not found. Run data_pipeline.py first.")
        st.stop()

    standings = compute_group_standings(schedule)

    st.markdown('<div class="section-title">Group Standings</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Top 2 per group advance &middot; 8 best 3rd-place teams also qualify (32 teams total)</div>',
        unsafe_allow_html=True,
    )

    group_letters = list(GROUPS_2026.keys())
    for row_start in range(0, len(group_letters), 3):
        cols = st.columns(3)
        for col, g in zip(cols, group_letters[row_start:row_start + 3]):
            with col:
                st.markdown(render_group_table(standings[g], g), unsafe_allow_html=True)

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Upcoming Matches</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">ML ensemble predictions &middot; XGBoost + Poisson + Elo</div>',
        unsafe_allow_html=True,
    )

    if preds.empty:
        st.info("No predictions loaded. Run ensemble.py first.")
    else:
        upcoming = schedule[schedule["played"] == False].head(12)
        if upcoming.empty:
            st.success("All group stage matches have been played!")
        else:
            merged = upcoming.merge(
                preds[["home_team", "away_team", "p_home_win", "p_draw", "p_away_win"]],
                on=["home_team", "away_team"], how="left",
            )
            cols = st.columns(3)
            for i, (_, m) in enumerate(merged.head(9).iterrows()):
                p_home = safe_prob(m.get("p_home_win"))
                p_draw = safe_prob(m.get("p_draw"))
                p_away = safe_prob(m.get("p_away_win"))
                with cols[i % 3]:
                    st.markdown(render_match_card(m, p_home, p_draw, p_away), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Team Explorer
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "team":
    sim_data = load_simulation()
    page_header("Team Explorer", "Tournament probabilities and key stats for every team")

    if not sim_data:
        st.error("No simulation results. Run simulation.py first.")
        st.stop()

    team = st.selectbox("Select a team", sorted(ALL_TEAMS))
    team_data = sim_data.get(team, {})
    if not team_data:
        st.warning(f"No simulation data for {team}.")
        st.stop()

    group  = team_data.get("group", "?")
    rounds = ["R32", "R16", "QF", "SF", "Final", "Winner"]
    probs  = [safe_prob(team_data.get(r, 0), 0.0) for r in rounds]
    labels = [ROUND_LABELS[r] for r in rounds]
    win_p  = safe_prob(team_data.get("Winner", 0), 0.0)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1b2a 0%,#1a3a6e 60%,#1a73e8 100%);
                border-radius:14px;padding:18px 26px;color:white;margin-bottom:20px;
                box-shadow:0 4px 20px rgba(26,115,232,0.25);">
      <div style="font-size:22px;font-weight:800;">{team}</div>
      <div style="font-size:13px;opacity:0.75;margin-top:4px;">
        Group {group} &middot; <b>{win_p:.1%}</b> chance to win the World Cup
      </div>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown(
            '<div style="font-size:15px;font-weight:700;color:#0d1b2a;margin-bottom:12px;">Advancement Probabilities</div>',
            unsafe_allow_html=True,
        )
        for lbl, p in zip(labels, probs):
            color = conf_color(p)
            bar_w = f"{min(p * 100, 100):.1f}%"
            st.markdown(f"""
            <div class="prob-stage-card">
              <div style="font-size:12px;color:#5f6368;font-weight:600;width:100px;flex-shrink:0;">{lbl}</div>
              <div class="prob-bar-outer">
                <div class="prob-bar-inner" style="width:{bar_w};background:{color};"></div>
              </div>
              <div style="font-size:14px;font-weight:700;color:{color};width:46px;text-align:right;flex-shrink:0;">{p:.1%}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:#0d1b2a;margin-bottom:8px;">Group {group} rivals</div>',
            unsafe_allow_html=True,
        )
        for rival in GROUPS_2026.get(group, []):
            if rival == team:
                continue
            rp    = safe_prob(sim_data.get(rival, {}).get("Winner", 0), 0.0)
            rcolor = conf_color(rp + 0.3)
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:7px 12px;border-radius:8px;background:white;
                        box-shadow:0 1px 5px rgba(0,0,0,0.07);margin-bottom:6px;">
              <span style="font-size:13px;font-weight:500;">{rival}</span>
              <span style="font-size:12px;font-weight:700;color:{rcolor};">{rp:.1%}</span>
            </div>""", unsafe_allow_html=True)

    with col2:
        colors = [conf_color(p) for p in probs]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=[p * 100 for p in probs],
            marker_color=colors,
            marker_line_width=0,
            text=[f"{p:.1%}" for p in probs],
            textposition="outside",
            textfont=dict(size=13, color="#0d1b2a"),
        ))
        fig.update_layout(
            title=dict(text=f"{team} — Path to Glory", font=dict(size=16, color="#0d1b2a"), x=0),
            yaxis=dict(
                title="Probability (%)",
                range=[0, max(probs) * 155 if max(probs) > 0 else 100],
                showgrid=True, gridcolor="#f0f0f0", zeroline=False,
            ),
            xaxis=dict(showgrid=False),
            plot_bgcolor="white",
            paper_bgcolor="white",
            height=340,
            margin=dict(t=50, b=10, l=0, r=0),
            font=dict(family="Inter, system-ui, sans-serif"),
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Key Stats</div>', unsafe_allow_html=True)

    features = load_features()
    if not features.empty:
        team_feats = features[features["home_team"] == team]
        if team_feats.empty:
            team_feats = features[features["away_team"] == team]
        if not team_feats.empty:
            latest = team_feats.iloc[-1]
            prefix = "home" if latest.get("home_team") == team else "away"
            feat_map = {
                "Elo Rating":         latest.get(f"{prefix}_elo", 1500),
                "FIFA Ranking":       latest.get(f"{prefix}_fifa_rank", 60),
                "Recent Form":        latest.get(f"{prefix}_form", 0.5),
                "Avg Goals Scored":   latest.get(f"{prefix}_avg_scored", 1.2),
                "Avg Goals Conceded": latest.get(f"{prefix}_avg_conceded", 1.2),
                "WC Appearances":     latest.get(f"{prefix}_wc_exp", 0),
                "Host Nation":        "Yes" if latest.get(f"{prefix}_is_host", 0) else "No",
            }
            feat_cols = st.columns(len(feat_map))
            for col, (feat, val) in zip(feat_cols, feat_map.items()):
                if isinstance(val, str):
                    disp = val
                else:
                    try:
                        fv = float(val)
                        disp = str(int(fv)) if fv == int(fv) else f"{fv:.2f}"
                    except (TypeError, ValueError):
                        disp = str(val)
                with col:
                    st.markdown(f"""
                    <div class="feat-card">
                      <div class="feat-val">{disp}</div>
                      <div class="feat-lbl">{feat}</div>
                    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Bracket Simulator
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "bracket":
    sim_data = load_simulation()
    page_header(
        "Bracket Simulator",
        "Most likely teams to advance at each stage across 100,000 simulations",
    )

    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        rerun = st.button("🔄 Re-run Simulation", type="primary")
    with col_info:
        meta = sim_data.get("_meta", {})
        if meta:
            st.markdown(f"""
            <div style="padding:8px 0;font-size:13px;color:#5f6368;">
              {meta.get('n_simulations', 0):,} simulations &middot;
              {meta.get('played_matches', 0)} matches played
            </div>""", unsafe_allow_html=True)

    if rerun:
        with st.spinner("Running 10,000 simulations..."):
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0,'src'); "
                 "from simulation import MonteCarloSimulator, save_results; "
                 "s = MonteCarloSimulator(); s.load(); "
                 "r = s.run(10000, verbose=False); save_results(r)"],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            if result.returncode == 0:
                st.cache_data.clear()
                st.success("Simulation updated!")
                sim_data = load_simulation()
            else:
                st.error(f"Simulation failed: {result.stderr[-500:]}")

    if not sim_data:
        st.warning("No simulation data. Run simulation.py first.")
        st.stop()

    def top_teams(rnd: str, n: int) -> list:
        return sorted(
            [(t, safe_prob(sim_data[t].get(rnd, 0), 0.0))
             for t in ALL_TEAMS if t in sim_data and not t.startswith("_")],
            key=lambda x: -x[1],
        )[:n]

    round_keys_b  = ["R32",       "R16",      "QF",             "SF",          "Final",  "Winner"]
    round_lbls_b  = ["Rd of 32",  "Rd of 16", "Quarter-Final",  "Semi-Final",  "Final",  "Champion"]
    n_show_b      = [16,           8,           4,                4,             2,         1]

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)

    for rnd, lbl, n in zip(round_keys_b, round_lbls_b, n_show_b):
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:18px 0 10px;">
          <span style="background:#1a73e8;color:white;padding:4px 14px;border-radius:20px;
                       font-size:12px;font-weight:700;letter-spacing:.5px;white-space:nowrap;">{lbl}</span>
          <hr style="flex:1;border:none;border-top:1px solid #e8eaed;margin:0;">
        </div>""", unsafe_allow_html=True)

        tops = top_teams(rnd, n)
        cols = st.columns(min(n, 8))
        for i, (t, p) in enumerate(tops[:len(cols)]):
            color = conf_color(p)
            with cols[i]:
                st.markdown(f"""
                <div class="bracket-team" style="border-bottom-color:{color};">
                  <div style="font-size:12px;font-weight:700;color:#0d1b2a;">{t}</div>
                  <div style="font-size:13px;font-weight:800;color:{color};margin-top:3px;">{p:.1%}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Win Probability — All 48 Teams</div>', unsafe_allow_html=True)

    treemap_rows = [
        {
            "Team":  t,
            "Group": f"Group {sim_data[t].get('group', '?')}",
            "Win%":  safe_prob(sim_data[t].get("Winner", 0), 0.0) * 100,
        }
        for t in ALL_TEAMS if t in sim_data and not t.startswith("_")
    ]
    tdf = pd.DataFrame(treemap_rows)
    fig = px.treemap(
        tdf[tdf["Win%"] > 0], path=["Group", "Team"], values="Win%",
        color="Win%",
        color_continuous_scale=[[0, "#e8f0fe"], [0.3, "#1a73e8"], [1, "#0d1b2a"]],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value:.1f}%",
        textfont=dict(size=13),
        hovertemplate="<b>%{label}</b><br>Win probability: %{value:.2f}%<extra></extra>",
    )
    fig.update_layout(
        height=560, margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor="#f8f9fa",
        font=dict(family="Inter, system-ui, sans-serif"),
        coloraxis_colorbar=dict(title="Win %", ticksuffix="%"),
    )
    st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Prediction Tracker
# ══════════════════════════════════════════════════════════════════════════════
elif page_key == "tracker":
    schedule = load_schedule()
    page_header(
        "Prediction Tracker",
        "Live results and accuracy tracking for the 2026 World Cup",
    )

    if schedule.empty:
        st.error("No schedule data. Run data_pipeline.py first.")
        st.stop()

    played = schedule[schedule["played"] == True].copy()

    if played.empty:
        st.markdown("""
        <div class="wco-card" style="text-align:center;padding:48px;">
          <div style="font-size:48px;margin-bottom:10px;">&#9203;</div>
          <div style="font-size:18px;font-weight:700;color:#0d1b2a;">No matches played yet</div>
          <div style="font-size:13px;color:#80868b;margin-top:6px;">Check back once the tournament kicks off!</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    n_played  = len(played)
    home_wins = int((played["home_score"].astype(int) > played["away_score"].astype(int)).sum())
    away_wins = int((played["away_score"].astype(int) > played["home_score"].astype(int)).sum())
    draws     = n_played - home_wins - away_wins

    for col, (label, val, color) in zip(
        st.columns(4),
        [
            ("Matches Played", n_played,   "#1a73e8"),
            ("Home Wins",      home_wins,  "#34a853"),
            ("Draws",          draws,      "#fbbc04"),
            ("Away Wins",      away_wins,  "#ea4335"),
        ],
    ):
        with col:
            st.markdown(f"""
            <div class="wco-card" style="text-align:center;padding:16px;">
              <div style="font-size:30px;font-weight:800;color:{color};">{val}</div>
              <div style="font-size:11px;color:#80868b;text-transform:uppercase;letter-spacing:.5px;margin-top:5px;">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:16px;font-weight:700;color:#0d1b2a;margin-bottom:12px;">Completed Matches</div>',
        unsafe_allow_html=True,
    )

    tracker_rows = []
    for _, m in played.iterrows():
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        winner = m["home_team"] if hs > as_ else (m["away_team"] if as_ > hs else "Draw")
        tracker_rows.append({
            "Group":  m.get("group", ""),
            "Home":   m["home_team"],
            "Score":  f"{hs}–{as_}",
            "Away":   m["away_team"],
            "Winner": winner,
        })
    df_tracker = pd.DataFrame(tracker_rows)

    st.dataframe(
        df_tracker,
        hide_index=True,
        width="stretch",
        column_config={
            "Group":  st.column_config.TextColumn("Group",     width="small"),
            "Home":   st.column_config.TextColumn("Home Team", width="medium"),
            "Score":  st.column_config.TextColumn("Score",     width="small"),
            "Away":   st.column_config.TextColumn("Away Team", width="medium"),
            "Winner": st.column_config.TextColumn("Winner",    width="medium"),
        },
    )

    st.markdown('<hr class="wco-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Match Analysis</div>', unsafe_allow_html=True)

    gdf = pd.DataFrame([
        {
            "Home Goals": int(m["home_score"]),
            "Away Goals": int(m["away_score"]),
            "Total":      int(m["home_score"]) + int(m["away_score"]),
        }
        for _, m in played.iterrows()
    ])

    c1, c2, c3 = st.columns(3)

    with c1:
        fig = px.histogram(
            gdf, x="Total", nbins=10, title="Goals per Match",
            color_discrete_sequence=["#1a73e8"],
        )
        fig.update_layout(
            bargap=0.1, height=300, margin=dict(t=44, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False),
            xaxis=dict(showgrid=False),
            font=dict(family="Inter, system-ui, sans-serif"),
        )
        st.plotly_chart(fig, width="stretch")

    with c2:
        fig2 = go.Figure(go.Pie(
            labels=["Home Win", "Draw", "Away Win"],
            values=[home_wins, draws, away_wins],
            marker_colors=["#34a853", "#fbbc04", "#ea4335"],
            hole=0.42,
            textinfo="label+percent",
            textfont_size=13,
        ))
        fig2.update_layout(
            title="Result Distribution",
            height=300, margin=dict(t=44, b=10),
            paper_bgcolor="white", showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif"),
        )
        st.plotly_chart(fig2, width="stretch")

    with c3:
        avg_home  = gdf["Home Goals"].mean() if len(gdf) else 0
        avg_away  = gdf["Away Goals"].mean() if len(gdf) else 0
        avg_total = gdf["Total"].mean()      if len(gdf) else 0
        fig3 = go.Figure(go.Bar(
            x=["Home", "Away"],
            y=[avg_home, avg_away],
            marker_color=["#1a73e8", "#ea4335"],
            marker_line_width=0,
            text=[f"{avg_home:.2f}", f"{avg_away:.2f}"],
            textposition="outside",
        ))
        fig3.update_layout(
            title=f"Avg Goals (match avg: {avg_total:.2f})",
            height=300, margin=dict(t=44, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False, range=[0, max(avg_home, avg_away) * 1.5 + 0.1]),
            xaxis=dict(showgrid=False),
            showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif"),
        )
        st.plotly_chart(fig3, width="stretch")
