"""
Game-by-game version: value each overturned call by how much it changed the challenging-side team's
chance of winning THAT game (win probability), instead of converting season runs to wins with a formula.

Win probability for any game situation comes from MLB's own win-expectancy numbers in Statcast
(home_win_exp, recorded before every pitch), averaged over every 2026 pitch thrown in that situation.
Run after analysis.py.
"""
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path("results")
sc = pd.read_parquet("statcast_2026.parquet")
ch = pd.read_csv(OUT / "challenges_valued.csv")
st = pd.read_csv("standings_2026.csv")
team_tab = pd.read_csv(OUT / "team_impact.csv")[["abbr", "team", "W", "L", "net_wins"]]

# ---------------------------------------------------------------- win-probability table
sc["bases"] = (sc["on_1b"].notna() * 1 + sc["on_2b"].notna() * 2 + sc["on_3b"].notna() * 4).astype(int)
sc["diff"] = (sc["home_score"] - sc["away_score"]).clip(-8, 8)       # home lead
sc["inn"] = sc["inning"].clip(upper=10)                              # 10 = extra innings
sc["bot"] = (sc["inning_topbot"] == "Bot").astype(int)
sc = sc[sc["balls"].between(0, 3) & sc["strikes"].between(0, 2)]
K1 = ["inn", "bot", "diff", "outs_when_up", "bases", "balls", "strikes"]
K2 = ["inn", "bot", "diff", "outs_when_up", "bases"]
K3 = ["inn", "bot", "diff", "outs_when_up"]
T = {}
for keys in (K1, K2, K3):
    agg = sc.groupby(keys)["home_win_exp"].agg(["mean", "size"])
    T[tuple(keys)] = {idx: m for idx, (m, n) in zip(agg.index, agg.to_numpy()) if n >= 15}
MIN_N = 15


def wp_home(inn, bot, diff, outs, bases, balls, strikes):
    """Home team's chance of winning from a game situation (handles innings/game ending)."""
    inn = min(inn, 10)
    if outs >= 3:                                   # half-inning over
        if bot == 0:                                # end of top half
            if inn >= 9 and diff > 0:
                return 1.0                          # home leads after top of 9th+: game over
            return wp_home(inn, 1, diff, 0, 0, 0, 0)
        if inn >= 9 and diff != 0:
            return 1.0 if diff > 0 else 0.0
        return wp_home(min(inn + 1, 10), 0, diff, 0, 0, 0, 0)
    if bot == 1 and inn >= 9 and diff > 0:
        return 1.0                                  # walk-off
    diff = max(-8, min(8, diff))
    for keys, vals in [(K1, (inn, bot, diff, outs, bases, balls, strikes)),
                       (K2, (inn, bot, diff, outs, bases)), (K3, (inn, bot, diff, outs))]:
        hit = T[tuple(keys)].get(tuple(int(v) for v in vals))
        if hit is not None:
            return float(hit)
    return 1.0 if diff > 0 else 0.0 if diff < 0 else 0.5


def walk(bases):
    if not bases & 1:
        return bases | 1, 0
    if not bases & 2:
        return bases | 3, 0
    if not bases & 4:
        return 7, 0
    return 7, 1


def wp_after(call, inn, bot, diff, outs, bases, b, s):
    """Home win prob right after a called ball ('B') or strike ('S')."""
    sign = 1 if bot else -1                          # a run for the batting team moves diff this way
    if call == "B":
        if b < 3:
            return wp_home(inn, bot, diff, outs, bases, b + 1, s)
        nb, runs = walk(bases)
        return wp_home(inn, bot, diff + sign * runs, outs, nb, 0, 0)
    if s < 2:
        return wp_home(inn, bot, diff, outs, bases, b, s + 1)
    return wp_home(inn, bot, diff, outs + 1, bases, 0, 0)


# ---------------------------------------------------------------- value each overturn in win probability
ov = ch[ch["overturned"]].copy()
ov["bases"] = (ov["on_1b"].notna() * 1 + ov["on_2b"].notna() * 2 + ov["on_3b"].notna() * 4).astype(int)
ov["bot"] = (ov["inning_topbot"] == "Bot").astype(int)
ov["diff"] = ov["home_score"] - ov["away_score"]
args = list(zip(ov["inning"], ov["bot"], ov["diff"], ov["outs_when_up"], ov["bases"], ov["balls"], ov["strikes"]))
wp_ball = np.array([wp_after("B", *a) for a in args])
wp_strike = np.array([wp_after("S", *a) for a in args])
# wp_ball/wp_strike are HOME win probs; batting team's gain = home change if home bats, else minus it
home_change = np.where(ov["final_is_ball"], wp_ball - wp_strike, wp_strike - wp_ball)
ov["home_wp_change"] = home_change
ov["bat_wp_gain"] = np.where(ov["bot"] == 1, home_change, -home_change)

# ---------------------------------------------------------------- game by game
ov["home"], ov["away"] = ov["home_team"], ov["away_team"]
g = ov.groupby("game_pk").agg(home=("home", "first"), away=("away", "first"),
                              home_wp=("home_wp_change", "sum"), n=("home_wp_change", "size"),
                              biggest=("home_wp_change", lambda x: x.loc[x.abs().idxmax()]))
final = sc.sort_values(["game_pk", "at_bat_number", "pitch_number"]).groupby("game_pk").agg(
    date=("game_date", "first"), home_final=("post_home_score", "last"), away_final=("post_away_score", "last"))
g = g.join(final)
g["home_won"] = g["home_final"] > g["away_final"]
g["winner"] = np.where(g["home_won"], g["home"], g["away"])
g["winner_wp_from_abs"] = np.where(g["home_won"], g["home_wp"], -g["home_wp"])
g.to_csv(OUT / "games_abs.csv")
ov.to_csv(OUT / "overturns_winprob.csv", index=False)

rows = []
for t in sorted(set(g["home"]) | set(g["away"])):
    gh, ga = g[g["home"] == t], g[g["away"] == t]
    exp = gh["home_wp"].sum() - ga["home_wp"].sum()
    mine = pd.concat([gh.assign(my=gh["home_wp"], won=gh["home_won"]),
                      ga.assign(my=-ga["home_wp"], won=~ga["home_won"])])
    off = ov.loc[ov["bat_team"] == t, "bat_wp_gain"].sum()
    dfn = -ov.loc[ov["fld_team"] == t, "bat_wp_gain"].sum()
    rows.append(dict(abbr=t, wins_from_abs_gamebygame=exp, off_wins=off, def_wins=dfn,
                     games_likely_won_by_abs=int(((mine["my"] >= 0.5) & mine["won"]).sum()),
                     games_likely_lost_by_abs=int(((mine["my"] <= -0.5) & ~mine["won"]).sum())))
tg = pd.DataFrame(rows).merge(team_tab, on="abbr")
tg = tg.merge(pd.read_csv(OUT / "team_impact.csv")[["abbr", "league", "div"]], on="abbr")
tg["W_noABS_gamebygame"] = tg["W"] - tg["wins_from_abs_gamebygame"]
tg = tg.sort_values("wins_from_abs_gamebygame", ascending=False)
tg.to_csv(OUT / "team_impact_gamebygame.csv", index=False)

print(f"overturns valued: {len(ov):,};  avg |win-prob swing| {ov['home_wp_change'].abs().mean():.3f}")
print("league total (should be ~0):", round(tg["wins_from_abs_gamebygame"].sum(), 3))
print("corr with season-runs method:", round(np.corrcoef(tg["wins_from_abs_gamebygame"], tg["net_wins"])[0, 1], 3))
print(tg[["team", "W", "wins_from_abs_gamebygame", "net_wins", "games_likely_won_by_abs",
          "games_likely_lost_by_abs"]].round(2).to_string(index=False))
big = ov.reindex(ov["home_wp_change"].abs().sort_values(ascending=False).index).head(10)
print(big[["game_date", "away_team", "home_team", "inning", "inning_topbot", "outs_when_up", "balls", "strikes",
           "bases", "diff", "challenger", "description", "home_wp_change"]].to_string(index=False))


# ---------------------------------------------------------------- playoff picture without ABS
def field(df, col):
    out = {}
    for lg, gg in df.groupby("league"):
        winners = gg.sort_values(col, ascending=False).groupby("div").head(1)
        wc = gg[~gg["abbr"].isin(winners["abbr"])].sort_values(col, ascending=False)
        out[lg] = (sorted(winners["abbr"]), list(wc["abbr"].head(3)), wc.iloc[2][col] - wc.iloc[3][col])
    return out
print("actual:", field(tg, "W"))
print("no ABS:", field(tg, "W_noABS_gamebygame"))
