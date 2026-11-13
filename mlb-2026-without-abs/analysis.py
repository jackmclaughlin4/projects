"""
2026 MLB without ABS: what if every overturned ball/strike challenge had stood as the umpire's call?

Inputs (made by get_statcast.py / get_feeds.py / get_standings.py):
    statcast_2026.parquet   every regular-season pitch (Baseball Savant)
    challenges_2026.csv     every ABS challenge from the MLB game feeds
    standings_2026.csv      final 2026 standings
Outputs: results/*.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path("results")
OUT.mkdir(exist_ok=True)

sc = pd.read_parquet("statcast_2026.parquet")
ch = pd.read_csv("challenges_2026.csv")
st = pd.read_csv("standings_2026.csv")
teams = pd.read_csv("teams.csv")

# ---------------------------------------------------------------- runs per win (2026 run environment)
RPG = st["RS"].sum() / (st["W"] + st["L"]).sum()      # runs per team per game
RPW = 1.5 * RPG + 3                                    # Tango / FanGraphs: ((lgRA + lgRA)/2 + 2) * 1.5
print(f"2026 runs/team/game {RPG:.2f} -> {RPW:.2f} runs per win")

# ---------------------------------------------------------------- run expectancy by outs, bases, count
sc = sc.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
sc["bases"] = (sc["on_1b"].notna() * 1 + sc["on_2b"].notna() * 2 + sc["on_3b"].notna() * 4).astype(int)
half = ["game_pk", "inning", "inning_topbot"]
sc["inning_end_score"] = sc.groupby(half)["post_bat_score"].transform("max")
sc["runs_rest"] = sc["inning_end_score"] - sc["bat_score"]
# Drop innings that ended early (walk-offs) and extra-inning ghost-runner innings - they bias run expectancy.
full = sc[(sc["inning"] <= 9) & ~((sc["inning"] == 9) & (sc["inning_topbot"] == "Bot"))]
full = full[full["balls"].between(0, 3) & full["strikes"].between(0, 2)]
RE = full.groupby(["outs_when_up", "bases", "balls", "strikes"])["runs_rest"].mean()


def re(outs, bases, balls, strikes):
    if outs >= 3:
        return 0.0
    return RE.get((outs, bases, balls, strikes), np.nan)


def walk(bases):
    """Bases after a walk and runs forced in."""
    b1, b2, b3 = bases & 1, bases >> 1 & 1, bases >> 2 & 1
    if not b1:
        return bases | 1, 0
    if not b2:
        return bases | 3, 0
    if not b3:
        return 7, 0
    return 7, 1


def after_ball(o, bases, b, s):
    if b < 3:
        return re(o, bases, b + 1, s)
    nb, runs = walk(bases)
    return runs + re(o, nb, 0, 0)


def after_strike(o, bases, b, s):
    if s < 2:
        return re(o, bases, b, s + 1)
    return re(o + 1, bases, 0, 0)          # strikeout


# ---------------------------------------------------------------- overturned calls
m = ch.merge(sc, on=["game_pk", "at_bat_number", "pitch_number"], how="left", indicator=True)
print("challenges matched to Statcast:", (m["_merge"] == "both").mean().round(4))
m = m[m["_merge"] == "both"].copy()
ball_desc = {"ball", "blocked_ball", "automatic_ball", "pitchout"}
m["final_is_ball"] = m["description"].isin(ball_desc)
m["value_ball_minus_strike"] = [
    after_ball(o, b_, b, s) - after_strike(o, b_, b, s)
    for o, b_, b, s in zip(m["outs_when_up"], m["bases"], m["balls"], m["strikes"])]
# Runs the BATTING team gained because the call was overturned (0 if confirmed).
m["bat_runs"] = np.where(m["overturned"],
                         np.where(m["final_is_ball"], 1, -1) * m["value_ball_minus_strike"], 0.0)

m["bat_team"] = np.where(m["inning_topbot"] == "Top", m["away_team"], m["home_team"])
m["fld_team"] = np.where(m["inning_topbot"] == "Top", m["home_team"], m["away_team"])
abbr = dict(zip(teams["team_id"], teams["abbr"]))
m["challenging_team"] = m["challenge_team"].map(abbr)
m["challenged_by"] = np.where(m["challenging_team"] == m["bat_team"], "batter", "fielder")
to_ball = m["overturned"] & m["final_is_ball"]
to_strike = m["overturned"] & ~m["final_is_ball"]
m["walk_gained"] = to_ball & (m["balls"] == 3)          # umpire said strike, ABS said ball four
m["k_erased"] = to_ball & (m["strikes"] == 2)           # umpire said strike three, ABS said ball
m["k_gained"] = to_strike & (m["strikes"] == 2)         # umpire said ball, ABS said strike three
m["walk_erased"] = to_strike & (m["balls"] == 3)        # umpire said ball four, ABS said strike
m["pa_end_flip"] = m[["walk_gained", "k_erased", "k_gained", "walk_erased"]].any(axis=1)
m.to_csv(OUT / "challenges_valued.csv", index=False)

ov = m[m["overturned"]]
print(f"overturned calls {len(ov):,}; avg swing {ov['value_ball_minus_strike'].abs().mean():.3f} runs; "
      f"PA-ending flips {ov['pa_end_flip'].sum():,}")

# ---------------------------------------------------------------- team impact
statcast_abbr = sorted(set(sc["home_team"]))
off = m.groupby("bat_team")["bat_runs"].sum()            # runs my offense gained from overturns
dfn = -m.groupby("fld_team")["bat_runs"].sum()           # runs my defense saved from overturns
team = pd.DataFrame({"off_runs": off, "def_runs": dfn}).fillna(0)
team["net_runs"] = team["off_runs"] + team["def_runs"]
team["net_wins"] = team["net_runs"] / RPW
own = m[m["overturned"]].groupby("challenging_team").size()
tried = m.groupby("challenging_team").size()
team["challenges"] = tried
team["overturns"] = own
team["overturn_pct"] = 100 * own / tried

# link Statcast abbreviations to standings
sc_to_id = {}
for _, t in teams.iterrows():
    sc_to_id[t["abbr"]] = t["team_id"]
fix = {"AZ": "ARI", "ATH": "ATH", "CWS": "CWS", "KC": "KC", "SD": "SD", "SF": "SF", "TB": "TB", "WSH": "WSH"}
team.index.name = "abbr"
team = team.reset_index()
team["team_id"] = team["abbr"].map(lambda a: sc_to_id.get(a, sc_to_id.get(fix.get(a, a))))
missing = team[team["team_id"].isna()]["abbr"].tolist()
assert not missing, f"unmatched team abbreviations: {missing}"
team = team.merge(st, on="team_id")
team["W_noABS"] = team["W"] - team["net_wins"]
team["RD"] = team["RS"] - team["RA"]
team["RD_noABS"] = team["RD"] - team["net_runs"]
team = team.sort_values("net_runs", ascending=False)
team.to_csv(OUT / "team_impact.csv", index=False)

# ---------------------------------------------------------------- players
pit_names = sc.drop_duplicates("pitcher").set_index("pitcher")["player_name"].map(
    lambda n: " ".join(reversed(n.split(", "))) if isinstance(n, str) else n)

# batters: runs from overturns in their plate appearances, split by who challenged
bat = m.groupby(["batter", "challenged_by"])["bat_runs"].sum().unstack(fill_value=0)
bat.columns = [f"runs_from_{c}_challenges" for c in bat.columns]
bat["net_runs"] = bat.sum(axis=1)
for c in ["walk_gained", "k_erased", "k_gained", "walk_erased"]:
    bat[c] = m.groupby("batter")[c].sum()
bat = bat.fillna(0)
import requests
ids, bnames = list(bat.index), {}
for i in range(0, len(ids), 150):
    r = requests.get("https://statsapi.mlb.com/api/v1/people",
                     params={"personIds": ",".join(map(str, ids[i:i + 150]))}, timeout=60).json()
    bnames.update({p["id"]: p["fullName"] for p in r["people"]})
bat.insert(0, "name", bat.index.map(bnames))
bat.to_csv(OUT / "batter_impact.csv")

# pitchers: runs SAVED (positive = good for pitcher)
pit = (-m.groupby(["pitcher", "challenged_by"])["bat_runs"].sum()).unstack(fill_value=0)
pit.columns = [f"runs_from_{c}_challenges" for c in pit.columns]
pit["net_runs_saved"] = pit.sum(axis=1)
for c in ["walk_gained", "k_erased", "k_gained", "walk_erased"]:
    pit[c] = m.groupby("pitcher")[c].sum()
pit = pit.fillna(0)
pit.insert(0, "name", pit_names.reindex(pit.index))
pit.to_csv(OUT / "pitcher_impact.csv")

# challengers (catchers + hitters): runs their own challenges produced for their team
mine = m.copy()
mine["team_runs"] = np.where(mine["challenged_by"] == "batter", mine["bat_runs"], -mine["bat_runs"])
chal = mine.groupby(["challenger_id", "challenger", "challenged_by"]).agg(
    challenges=("overturned", "size"), overturns=("overturned", "sum"), team_runs=("team_runs", "sum")
).reset_index()
chal["overturn_pct"] = 100 * chal["overturns"] / chal["challenges"]
chal.sort_values("team_runs", ascending=False).to_csv(OUT / "challenger_impact.csv", index=False)

pd.Series({"RPG": RPG, "RPW": RPW, "challenges": len(m), "overturns": int(m["overturned"].sum()),
           "total_runs_moved": ov["value_ball_minus_strike"].abs().sum()}).to_csv(OUT / "summary.csv")
print(team[["abbr", "W", "L", "off_runs", "def_runs", "net_runs", "net_wins", "W_noABS"]].round(2).to_string(index=False))
