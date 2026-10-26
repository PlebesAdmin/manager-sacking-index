"""
Manager Sacking Index – Streamlit app
Transparent Premier League managerial hot-seat rankings.
Includes High MSI + Tough upcoming fixtures flag.
"""

import streamlit as st
import pandas as pd

from msi_engine import MSIConfig, calculate_msi, risk_colour


st.set_page_config(
    page_title="Manager Sacking Index",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔥 Manager Sacking Index")
st.caption(
    "Transparent ranking of Premier League managerial pressure — "
    "useful for FPL because sackings often produce short-term form swings, "
    "rotation changes and price movements. "
    "Clubs with **High MSI + Tough upcoming fixtures** are flagged for extra attention."
)

with st.expander("📖 How the index works (click to open)", expanded=False):
    st.markdown(
        """
**MSI (0–100)** — higher score = hotter seat.

**Default weights (adjustable in sidebar)**  
- **Market pressure 30%** — betting odds for “next manager sacked” (short odds → high pressure)  
- **Results pressure 30%** — current league position + points-per-game  
- **Form trajectory 20%** — recent results (last ~5–6 games)  
- **Underlying gap 10%** — goal difference as simple performance proxy  
- **Tenure & context 10%** — days in charge (very new managers get a mild buffer; long-tenured have more credit)

**Risk bands**  
- 0–34 → **Safe**  
- 35–54 → **Watch**  
- 55–74 → **Hot**  
- 75–100 → **Critical**

**⚠️ High MSI + Tough fixtures flag**  
Shown when MSI ≥ 55 (Hot or above) **and** average FPL difficulty of the next 3 gameweeks ≥ 3.4.  
These are the clubs where pressure is already high *and* the fixture list offers little immediate relief — higher chance of further poor results (or a board reaction).

**Data notes (prototype)**  
- Standings & form: current 2026/27 season (after ~GW8)  
- Market odds: approximate consensus from bookmakers (updated periodically)  
- Upcoming FDR: live from FPL API (next 3 GWs)  
- Tenure: public appointment dates  

Market component is deliberately given higher default weight because bookmakers react quickly to results, media noise and insider flow — often the best real-time pressure signal available publicly.
        """
    )

with st.sidebar:
    st.header("⚙️ MSI weights")
    st.caption("Values are normalised automatically. Market is deliberately higher by default.")

    w_market = st.slider("Market pressure %", 0, 50, 30, 5)
    w_results = st.slider("Results pressure %", 0, 50, 30, 5)
    w_form = st.slider("Form trajectory %", 0, 40, 20, 5)
    w_underlying = st.slider("Underlying (GD) %", 0, 30, 10, 5)
    w_tenure = st.slider("Tenure & context %", 0, 30, 10, 5)

    total = w_market + w_results + w_form + w_underlying + w_tenure
    if total == 0:
        st.warning("Weights cannot all be zero.")
        st.stop()

    st.divider()
    st.markdown("### Flag thresholds")
    high_msi_th = st.slider("High MSI threshold", 40, 75, 55, 5)
    tough_fdr_th = st.slider("Tough FDR threshold (avg)", 2.5, 4.5, 3.4, 0.1)
    n_gws = st.slider("Upcoming GWs for FDR", 2, 5, 3, 1)

    cfg = MSIConfig(
        market_weight=w_market / total,
        results_weight=w_results / total,
        form_weight=w_form / total,
        underlying_weight=w_underlying / total,
        tenure_weight=w_tenure / total,
        upcoming_gws=n_gws,
        high_msi_threshold=float(high_msi_th),
        tough_fdr_threshold=float(tough_fdr_th),
    )

    st.caption(
        f"Current mix → Market {cfg.market_weight*100:.0f}% · "
        f"Results {cfg.results_weight*100:.0f}% · "
        f"Form {cfg.form_weight*100:.0f}% · "
        f"Underlying {cfg.underlying_weight*100:.0f}% · "
        f"Tenure {cfg.tenure_weight*100:.0f}%"
    )

    if st.button("↺ Reset to defaults"):
        st.rerun()

    st.divider()
    st.markdown("### Why this matters for FPL")
    st.markdown(
        """
- Managerial change often produces a short-term “new manager bounce”
- Squad rotation and system changes can create differentials
- Player values and ownership can swing quickly after a sacking
- **High MSI + Tough fixtures** = pressure is high *and* the schedule offers little relief → elevated risk of further poor results or a board decision
- Use MSI alongside Fixture Value Index for timing transfers
        """
    )

# Calculate
with st.spinner("Calculating Manager Sacking Index + upcoming fixtures…"):
    df = calculate_msi(cfg)

# Summary metrics
col1, col2, col3, col4, col5 = st.columns(5)
critical = (df["risk"] == "Critical").sum()
hot = (df["risk"] == "Hot").sum()
watch = (df["risk"] == "Watch").sum()
safe = (df["risk"] == "Safe").sum()
flagged = (df["flag"] != "").sum()

col1.metric("Critical", int(critical), help="MSI ≥ 75")
col2.metric("Hot", int(hot), help="MSI 55–74")
col3.metric("Watch", int(watch), help="MSI 35–54")
col4.metric("Safe", int(safe), help="MSI < 35")
col5.metric("⚠️ Flagged", int(flagged), help="High MSI + Tough upcoming fixtures")

# Highlight flagged clubs at the top if any
flagged_df = df[df["flag"] != ""]
if not flagged_df.empty:
    st.warning(
        f"**⚠️ High MSI + Tough fixtures:** "
        + ", ".join(
            f"{r['manager']} ({r['club']}) — MSI {r['msi']:.0f}, FDR {r['avg_fdr']:.1f}"
            for _, r in flagged_df.iterrows()
        )
    )

st.divider()

# Main table
st.subheader("Current rankings")

display = df[
    [
        "rank",
        "manager",
        "club",
        "msi",
        "risk",
        "avg_fdr",
        "flag",
        "position",
        "pts",
        "form",
        "odds",
        "days",
    ]
].copy()
display.columns = [
    "Rank",
    "Manager",
    "Club",
    "MSI",
    "Risk",
    "Upcoming FDR",
    "Flag",
    "Pos",
    "Pts",
    "Form",
    "Odds",
    "Days in charge",
]


def colour_risk(val):
    colour = risk_colour(val)
    return f"background-color: {colour}; color: white; font-weight: 600"


def colour_flag(val):
    if val:
        return "background-color: #8e44ad; color: white; font-weight: 700"
    return ""


def colour_fdr(val):
    try:
        v = float(val)
    except Exception:
        return ""
    if v >= 4.0:
        return "background-color: #c0392b; color: white"
    if v >= 3.4:
        return "background-color: #e67e22; color: white"
    if v <= 2.5:
        return "background-color: #27ae60; color: white"
    return ""


styled = (
    display.style.map(colour_risk, subset=["Risk"])
    .map(colour_flag, subset=["Flag"])
    .map(colour_fdr, subset=["Upcoming FDR"])
    .format({"MSI": "{:.1f}", "Odds": "{:.2f}", "Upcoming FDR": "{:.2f}"})
)

st.dataframe(styled, use_container_width=True, hide_index=True, height=720)

st.caption(
    "Upcoming FDR = average FPL difficulty of the next "
    f"{cfg.upcoming_gws} gameweeks (higher = tougher). "
    "Flag = MSI ≥ threshold **and** FDR ≥ tough threshold."
)

st.divider()

# Expandable detail cards
st.subheader("Detailed breakdown")

for _, row in df.iterrows():
    risk = row["risk"]
    colour = risk_colour(risk)
    flag_txt = f"  ·  {row['flag']}" if row["flag"] else ""
    with st.expander(
        f"**#{int(row['rank'])}  {row['manager']}** ({row['club']})  —  "
        f"MSI **{row['msi']:.1f}**  ·  {risk}{flag_txt}",
        expanded=(row["rank"] <= 3 or bool(row["flag"])),
    ):
        c1, c2, c3 = st.columns([1.2, 1, 1.5])

        with c1:
            st.markdown(
                f"**Risk band:** <span style='color:{colour};font-weight:700'>{risk}</span>",
                unsafe_allow_html=True,
            )
            if row["flag"]:
                st.markdown(
                    f"<span style='background:#8e44ad;color:white;padding:2px 8px;"
                    f"border-radius:4px;font-weight:700'>{row['flag']}</span>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"**League position:** {int(row['position'])}  "
                f"({int(row['pts'])} pts, GD {int(row['gd'])})"
            )
            st.markdown(f"**Recent form:** `{row['form']}`")
            st.markdown(f"**Days in charge:** {int(row['days'])}")
            st.markdown(f"**Market odds (next sacked):** {row['odds']:.2f}")
            st.markdown(
                f"**Upcoming FDR (next {cfg.upcoming_gws}):** "
                f"**{row['avg_fdr']:.2f}**  ({int(row['n_upcoming'])} fixtures)"
            )
            if row["upcoming_fixtures"] and row["upcoming_fixtures"] not in ("—", "n/a"):
                st.caption(row["upcoming_fixtures"])

        with c2:
            st.markdown("**Component scores (0–100)**")
            st.progress(min(1.0, row["market_score"] / 100), text=f"Market  {row['market_score']:.0f}")
            st.progress(min(1.0, row["results_score"] / 100), text=f"Results  {row['results_score']:.0f}")
            st.progress(min(1.0, row["form_score"] / 100), text=f"Form  {row['form_score']:.0f}")
            st.progress(min(1.0, row["underlying_score"] / 100), text=f"Underlying  {row['underlying_score']:.0f}")
            st.progress(min(1.0, row["tenure_score"] / 100), text=f"Tenure  {row['tenure_score']:.0f}")

        with c3:
            st.markdown("**Key note**")
            st.info(row["note"])
            st.caption(
                f"Weighted contribution (approx): "
                f"Market {cfg.market_weight*row['market_score']:.1f} · "
                f"Results {cfg.results_weight*row['results_score']:.1f} · "
                f"Form {cfg.form_weight*row['form_score']:.1f}"
            )

st.divider()
st.caption(
    "Prototype · Data as of late October 2026 (after ~GW8) · "
    "Market odds approximate · Upcoming FDR live from FPL API · "
    "Not financial or betting advice · Built for FPLanonymous"
)
