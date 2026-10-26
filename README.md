# Manager Sacking Index

Transparent Premier League managerial hot-seat rankings for FPL managers.

**v0.2** – Market weight 30% default + **High MSI + Tough upcoming fixtures** flag in the table.

## What it does

Ranks all 20 Premier League managers on a 0–100 **Manager Sacking Index (MSI)**.  
Higher score = higher pressure / hotter seat.

### Default component weights

| Component            | Weight | Signal |
|----------------------|--------|--------|
| Market pressure      | 30%    | Betting odds for “next manager sacked” |
| Results pressure     | 30%    | League position + points per game |
| Form trajectory      | 20%    | Recent results (last ~5–6 games) |
| Underlying gap       | 10%    | Goal difference proxy |
| Tenure & context     | 10%    | Days in charge |

Weights are fully adjustable in the sidebar.

### Risk bands

- **Safe** (0–34)
- **Watch** (35–54)
- **Hot** (55–74)
- **Critical** (75–100)

### High MSI + Tough fixtures flag

Shown when:
- MSI ≥ 55 (Hot or Critical), **and**
- Average FPL difficulty of the next 3 gameweeks ≥ 3.4

These clubs are under pressure *and* face a difficult short-term schedule — higher chance of further poor results or a board reaction. Useful for FPL timing.

Upcoming FDR is pulled live from the FPL API.

## Why it matters for FPL

Managerial changes frequently produce:

- Short-term form spikes (“new manager bounce”)
- Changes in rotation and system
- Ownership and price movements

Use alongside the Fixture Value Index for timing transfers around potential sackings.

## Data notes (prototype)

- Standings / form: 2026/27 season after ~GW8
- Market odds: approximate bookmaker consensus (updated periodically)
- Upcoming FDR: live from FPL API
- Tenure: public appointment dates

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Push to GitHub → deploy on [share.streamlit.io](https://share.streamlit.io) with main file `app.py`.

Embed via iframe on fplanonymous.com the same way as the Fixture Value Index.
