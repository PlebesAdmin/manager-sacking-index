"""
Manager Sacking Index (MSI) engine
Transparent 0-100 hot-seat ranking for Premier League managers.
Higher score = higher sacking pressure.

Also computes upcoming fixture difficulty (next N GWs) and a combined
"High MSI + Tough fixtures" flag for FPL timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time
from pathlib import Path
import json

import numpy as np
import pandas as pd
import requests


@dataclass
class MSIConfig:
    results_weight: float = 0.30
    form_weight: float = 0.20
    underlying_weight: float = 0.10
    tenure_weight: float = 0.10
    market_weight: float = 0.30  # User preference: market pressure bigger

    # Fixture horizon for "tough upcoming" flag
    upcoming_gws: int = 3
    # Thresholds for the combined flag
    high_msi_threshold: float = 55.0   # Hot or above
    tough_fdr_threshold: float = 3.4   # avg difficulty of upcoming fixtures


FPL_BASE = "https://fantasy.premierleague.com/api"

# Short name → FPL team id (2026/27)
SHORT_TO_ID = {
    "ARS": 1, "AVL": 2, "BOU": 3, "BRE": 4, "BHA": 5,
    "CHE": 6, "COV": 7, "CRY": 8, "EVE": 9, "FUL": 10,
    "HUL": 11, "IPS": 12, "LEE": 13, "LIV": 14, "MCI": 15,
    "MUN": 16, "NEW": 17, "NFO": 18, "TOT": 19, "SUN": 20,
}


# ---------------------------------------------------------------------------
# Static / lightly maintained data for 2026/27 (as of ~25 Oct 2026, GW8)
# Update odds and form regularly for production use.
# ---------------------------------------------------------------------------

MANAGERS: List[Dict] = [
    {
        "manager": "Michael Carrick",
        "club": "Man Utd",
        "short": "MUN",
        "position": 16,
        "pts": 7,
        "gd": -3,
        "played": 8,
        "form": "LDDDL",
        "days": 285,
        "odds": 1.55,
        "note": "Winless run extended; heavy favourite in sack market",
    },
    {
        "manager": "Pierre Sage",
        "club": "Crystal Palace",
        "short": "CRY",
        "position": 17,
        "pts": 7,
        "gd": -10,
        "played": 8,
        "form": "LDWLL",
        "days": 132,
        "odds": 3.50,
        "note": "Heavy defeat at Brighton; short tenure",
    },
    {
        "manager": "Álvaro Arbeloa",
        "club": "Fulham",
        "short": "FUL",
        "position": 15,
        "pts": 8,
        "gd": -2,
        "played": 8,
        "form": "DDLWW",
        "days": 110,
        "odds": 6.50,
        "note": "Slow start after summer appointment",
    },
    {
        "manager": "Oliver Glasner",
        "club": "Nott'm Forest",
        "short": "NFO",
        "position": 18,
        "pts": 6,
        "gd": -4,
        "played": 8,
        "form": "WLLLD",
        "days": 111,
        "odds": 12.0,
        "note": "Bottom-half, limited points",
    },
    {
        "manager": "Matthias Jaissle",
        "club": "Newcastle",
        "short": "NEW",
        "position": 8,
        "pts": 11,
        "gd": -2,
        "played": 8,
        "form": "LWLLW",
        "days": 81,
        "odds": 14.0,
        "note": "Very new; mid-table but mixed results",
    },
    {
        "manager": "Régis Le Bris",
        "club": "Sunderland",
        "short": "SUN",
        "position": 20,
        "pts": 5,
        "gd": -8,
        "played": 8,
        "form": "LLLLD",
        "days": 481,
        "odds": 15.0,
        "note": "Bottom of the table",
    },
    {
        "manager": "Roberto De Zerbi",
        "club": "Spurs",
        "short": "TOT",
        "position": 14,
        "pts": 9,
        "gd": -2,
        "played": 8,
        "form": "DLDWW",
        "days": 208,
        "odds": 13.0,
        "note": "Improved recently after poor start",
    },
    {
        "manager": "Frank Lampard",
        "club": "Coventry City",
        "short": "COV",
        "position": 19,
        "pts": 6,
        "gd": -9,
        "played": 8,
        "form": "LWWLL",
        "days": 331,
        "odds": 20.0,
        "note": "Newly promoted; tough start",
    },
    {
        "manager": "Gary O'Neil",
        "club": "Ipswich Town",
        "short": "IPS",
        "position": 12,
        "pts": 10,
        "gd": -4,
        "played": 8,
        "form": "WLWLD",
        "days": 124,
        "odds": 25.0,
        "note": "Mid-table, some resilience",
    },
    {
        "manager": "Enzo Maresca",
        "club": "Man City",
        "short": "MCI",
        "position": 1,
        "pts": 21,
        "gd": 11,
        "played": 8,
        "form": "WWWWL",
        "days": 118,
        "odds": 30.0,
        "note": "Top of the table; short tenure but excellent results",
    },
    {
        "manager": "David Moyes",
        "club": "Everton",
        "short": "EVE",
        "position": 11,
        "pts": 10,
        "gd": -1,
        "played": 8,
        "form": "DWDL L".replace(" ", ""),
        "days": 287,
        "odds": 40.0,
        "note": "Solid mid-table",
    },
    {
        "manager": "Unai Emery",
        "club": "Aston Villa",
        "short": "AVL",
        "position": 9,
        "pts": 11,
        "gd": -3,
        "played": 8,
        "form": "LWDWW",
        "days": 1425,
        "odds": 50.0,
        "note": "Established; mid-table start",
    },
    {
        "manager": "Marco Rose",
        "club": "Bournemouth",
        "short": "BOU",
        "position": 13,
        "pts": 9,
        "gd": -1,
        "played": 8,
        "form": "DLLWW",
        "days": 146,
        "odds": 40.0,
        "note": "New; improving form",
    },
    {
        "manager": "Sergej Jakirović",
        "club": "Hull City",
        "short": "HUL",
        "position": 10,
        "pts": 10,
        "gd": 1,
        "played": 8,
        "form": "DLDLD",
        "days": 501,
        "odds": 50.0,
        "note": "Solid mid-table for promoted side",
    },
    {
        "manager": "Xabi Alonso",
        "club": "Chelsea",
        "short": "CHE",
        "position": 5,
        "pts": 13,
        "gd": 2,
        "played": 8,
        "form": "DLWWL",
        "days": 116,
        "odds": 60.0,
        "note": "Top-half; new appointment",
    },
    {
        "manager": "Andoni Iraola",
        "club": "Liverpool",
        "short": "LIV",
        "position": 4,
        "pts": 15,
        "gd": 3,
        "played": 8,
        "form": "DWLWW",
        "days": 143,
        "odds": 80.0,
        "note": "Strong start at Anfield",
    },
    {
        "manager": "Keith Andrews",
        "club": "Brentford",
        "short": "BRE",
        "position": 6,
        "pts": 11,
        "gd": 5,
        "played": 8,
        "form": "DWDLD",
        "days": 485,
        "odds": 80.0,
        "note": "Consistent mid/upper table",
    },
    {
        "manager": "Daniel Farke",
        "club": "Leeds",
        "short": "LEE",
        "position": 7,
        "pts": 11,
        "gd": 3,
        "played": 8,
        "form": "WDLDD",
        "days": 1209,
        "odds": 100.0,
        "note": "Solid after promotion",
    },
    {
        "manager": "Fabian Hürzeler",
        "club": "Brighton",
        "short": "BHA",
        "position": 3,
        "pts": 16,
        "gd": 16,
        "played": 8,
        "form": "WWWWL",
        "days": 480,
        "odds": 100.0,
        "note": "Excellent attacking form",
    },
    {
        "manager": "Mikel Arteta",
        "club": "Arsenal",
        "short": "ARS",
        "position": 2,
        "pts": 21,
        "gd": 8,
        "played": 8,
        "form": "WLWWW",
        "days": 2499,
        "odds": 150.0,
        "note": "Longest serving; title challengers",
    },
]


def _form_score(form: str) -> float:
    if not form:
        return 50.0
    points = 0
    for c in form[-6:]:
        if c == "W":
            points += 3
        elif c == "D":
            points += 1
    max_pts = 3 * min(len(form), 6)
    if max_pts == 0:
        return 50.0
    return max(0.0, min(100.0, 100.0 * (1.0 - points / max_pts)))


def _results_score(position: int, pts: int, played: int) -> float:
    pos_score = (position - 1) / 19.0 * 100.0
    ppg = pts / max(played, 1)
    if ppg >= 2.2:
        ppg_score = 0.0
    elif ppg >= 1.5:
        ppg_score = 40.0 * (2.2 - ppg) / 0.7
    elif ppg >= 1.0:
        ppg_score = 40.0 + 30.0 * (1.5 - ppg) / 0.5
    else:
        ppg_score = 70.0 + 30.0 * (1.0 - ppg) / 1.0
    return 0.55 * pos_score + 0.45 * min(100.0, ppg_score)


def _underlying_score(gd: int, played: int) -> float:
    gd_per_game = gd / max(played, 1)
    return max(0.0, min(100.0, 50.0 - gd_per_game * 33.0))


def _tenure_score(days: int) -> float:
    if days < 60:
        return 35.0
    if days < 120:
        return 45.0
    if days < 365:
        return 55.0
    if days < 730:
        return 40.0
    if days < 1460:
        return 25.0
    return 10.0


def _market_score(odds: float) -> float:
    if odds <= 1.01:
        return 100.0
    implied = 1.0 / odds
    raw = implied * 110.0
    return max(0.0, min(100.0, raw))


# ---------------------------------------------------------------------------
# Upcoming fixture difficulty (live from FPL API)
# ---------------------------------------------------------------------------

def _fetch_upcoming_difficulties(n_gws: int = 3) -> Dict[str, Dict]:
    """
    Returns {short_name: {"avg_fdr": float, "fixtures": "OPP (H/A) FDR, ...", "n": int}}
    Falls back to empty dict on network error.
    """
    try:
        # Bootstrap for next event id + team map
        boot = requests.get(f"{FPL_BASE}/bootstrap-static/", timeout=20).json()
        next_gw = next((e["id"] for e in boot["events"] if e.get("is_next")), None)
        if next_gw is None:
            # fallback: first unfinished
            next_gw = next(
                (e["id"] for e in boot["events"] if not e.get("finished")),
                9,
            )
        id_to_short = {t["id"]: t["short_name"] for t in boot["teams"]}

        # Collect difficulties for next n_gws
        from collections import defaultdict
        diffs: Dict[int, List[int]] = defaultdict(list)
        labels: Dict[int, List[str]] = defaultdict(list)

        for offset in range(n_gws):
            gw = next_gw + offset
            try:
                fixtures = requests.get(
                    f"{FPL_BASE}/fixtures/", params={"event": gw}, timeout=15
                ).json()
            except Exception:
                continue
            for f in fixtures:
                if f.get("finished"):
                    continue
                h, a = f["team_h"], f["team_a"]
                hd, ad = f.get("team_h_difficulty"), f.get("team_a_difficulty")
                if hd is not None:
                    diffs[h].append(int(hd))
                    opp = id_to_short.get(a, str(a))
                    labels[h].append(f"{opp} (H) {hd}")
                if ad is not None:
                    diffs[a].append(int(ad))
                    opp = id_to_short.get(h, str(h))
                    labels[a].append(f"{opp} (A) {ad}")

        out = {}
        for short, tid in SHORT_TO_ID.items():
            ds = diffs.get(tid, [])
            if ds:
                avg = sum(ds) / len(ds)
                out[short] = {
                    "avg_fdr": round(avg, 2),
                    "fixtures": ", ".join(labels.get(tid, [])[:4]),
                    "n": len(ds),
                }
            else:
                out[short] = {"avg_fdr": 3.0, "fixtures": "—", "n": 0}
        return out
    except Exception:
        # Offline / API failure → neutral defaults
        return {
            s: {"avg_fdr": 3.0, "fixtures": "n/a", "n": 0} for s in SHORT_TO_ID
        }


def calculate_msi(config: Optional[MSIConfig] = None) -> pd.DataFrame:
    """Return ranked DataFrame with MSI scores, upcoming FDR and combined flag."""
    cfg = config or MSIConfig()

    total = (
        cfg.results_weight
        + cfg.form_weight
        + cfg.underlying_weight
        + cfg.tenure_weight
        + cfg.market_weight
    )
    if total <= 0:
        total = 1.0
    w_r = cfg.results_weight / total
    w_f = cfg.form_weight / total
    w_u = cfg.underlying_weight / total
    w_t = cfg.tenure_weight / total
    w_m = cfg.market_weight / total

    # Live fixture difficulty
    upcoming = _fetch_upcoming_difficulties(cfg.upcoming_gws)

    rows = []
    for m in MANAGERS:
        r = _results_score(m["position"], m["pts"], m["played"])
        f = _form_score(m["form"])
        u = _underlying_score(m["gd"], m["played"])
        t = _tenure_score(m["days"])
        mk = _market_score(m["odds"])

        msi = w_r * r + w_f * f + w_u * u + w_t * t + w_m * mk
        msi = round(float(msi), 1)

        if msi >= 75:
            risk = "Critical"
        elif msi >= 55:
            risk = "Hot"
        elif msi >= 35:
            risk = "Watch"
        else:
            risk = "Safe"

        fx = upcoming.get(m["short"], {"avg_fdr": 3.0, "fixtures": "—", "n": 0})
        avg_fdr = fx["avg_fdr"]
        tough = avg_fdr >= cfg.tough_fdr_threshold
        high_msi = msi >= cfg.high_msi_threshold
        flag = "⚠️ High MSI + Tough" if (high_msi and tough) else ""

        rows.append(
            {
                "manager": m["manager"],
                "club": m["club"],
                "short": m["short"],
                "position": m["position"],
                "pts": m["pts"],
                "gd": m["gd"],
                "played": m["played"],
                "form": m["form"],
                "days": m["days"],
                "odds": m["odds"],
                "note": m["note"],
                "results_score": round(r, 1),
                "form_score": round(f, 1),
                "underlying_score": round(u, 1),
                "tenure_score": round(t, 1),
                "market_score": round(mk, 1),
                "msi": msi,
                "risk": risk,
                "avg_fdr": avg_fdr,
                "upcoming_fixtures": fx["fixtures"],
                "n_upcoming": fx["n"],
                "flag": flag,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("msi", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def risk_colour(risk: str) -> str:
    return {
        "Critical": "#c0392b",
        "Hot": "#e67e22",
        "Watch": "#f1c40f",
        "Safe": "#27ae60",
    }.get(risk, "#7f8c8d")
