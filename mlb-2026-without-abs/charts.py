"""Charts for the 2026 no-ABS study. Run after analysis.py."""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
GAIN, LOSS = "#2a78d6", "#eb6834"       # helped by ABS / hurt by ABS
R = "results"
t = pd.read_csv(f"{R}/team_impact.csv")
b = pd.read_csv(f"{R}/batter_impact.csv", index_col=0)
p = pd.read_csv(f"{R}/pitcher_impact.csv", index_col=0)
s = pd.read_csv(f"{R}/summary.csv", index_col=0).iloc[:, 0]
RPW = s["RPW"]
SRC = ("Data: MLB Statcast (Baseball Savant) + MLB game feeds, 2026 regular season. Runs = change in run "
       f"expectancy (outs, runners, count). {RPW:.1f} runs = 1 win (Tango formula, 2026 scoring).")


def base(ax):
    ax.set_facecolor(SURF)
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    ax.axvline(0, color=INK2, lw=1)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


# Team colors (primary, secondary) for the abbreviation badges.
TEAM_COLORS = {
    "ARI": ("#A71930", "#E3D4AD"), "AZ": ("#A71930", "#E3D4AD"), "ATL": ("#13274F", "#CE1141"),
    "BAL": ("#DF4601", "#000000"), "BOS": ("#BD3039", "#0C2340"), "CHC": ("#0E3386", "#CC3433"),
    "CWS": ("#27251F", "#C4CED4"), "CIN": ("#C6011F", "#000000"), "CLE": ("#00385D", "#E50022"),
    "COL": ("#33006F", "#C4CED4"), "DET": ("#0C2340", "#FA4616"), "HOU": ("#002D62", "#EB6E1F"),
    "KC": ("#004687", "#BD9B60"), "LAA": ("#BA0021", "#003263"), "LAD": ("#005A9C", "#EF3E42"),
    "MIA": ("#00A3E0", "#EF3340"), "MIL": ("#12284B", "#FFC52F"), "MIN": ("#002B5C", "#D31145"),
    "NYM": ("#002D72", "#FF5910"), "NYY": ("#0C2340", "#C4CED4"), "ATH": ("#003831", "#EFB21E"),
    "PHI": ("#E81828", "#002D72"), "PIT": ("#27251F", "#FDB827"), "SD": ("#2F241D", "#FFC425"),
    "SF": ("#FD5A1E", "#27251F"), "SEA": ("#0C2C56", "#005C5C"), "STL": ("#C41E3A", "#0C2340"),
    "TB": ("#092C5C", "#8FBCE6"), "TEX": ("#003278", "#C0111F"), "TOR": ("#134A8E", "#E8291C"),
    "WSH": ("#AB0003", "#14225A"),
}


def badges(ax, abbrs, x):
    """Team-color badge with the abbreviation at each y position (replaces the y tick labels)."""
    ax.set_yticks([])
    for y, a in enumerate(abbrs):
        fill, edge = TEAM_COLORS.get(a, (INK2, INK2))
        ax.text(x, y, a, ha="center", va="center", fontsize=9, fontweight="bold", color="white",
                transform=ax.get_yaxis_transform(), clip_on=False,
                bbox=dict(boxstyle="round,pad=0.38,rounding_size=0.5", fc=fill, ec=edge, lw=2, alpha=1))


g = pd.read_csv(f"{R}/team_impact_gamebygame.csv")
SRC_G = ("Data: MLB Statcast (Baseball Savant) + MLB game feeds, 2026 regular season. Each overturned call is valued "
         "by how much it changed that team's chance of winning that game (MLB win probability).")

# ------------------------------------------------ 1. team wins (game by game)
d = g.sort_values("wins_from_abs_gamebygame").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(11, 11.5), facecolor=SURF)
base(ax)
v = d["wins_from_abs_gamebygame"]
ax.barh(range(len(d)), v, color=[GAIN if x > 0 else LOSS for x in v], height=0.68)
for y, (x, w, wn, name) in enumerate(zip(v, d["W"], d["W_noABS_gamebygame"], d["team"])):
    lab = f"{x:+.1f}" if abs(x) >= 0.05 else "0.0"
    ax.text(x + (0.04 if x >= 0 else -0.04), y, f"{lab}   {name}: {w} → {wn:.1f} W",
            va="center", ha="left" if x >= 0 else "right", fontsize=9, color=INK2)
badges(ax, d["abbr"], -0.04)
ax.set_ylim(-0.8, len(d) - 0.2)
ax.set_xlim(-2.6, 3.0)
ax.set_xlabel("Wins ABS added (+) or took away (−) in 2026", color=INK2)
fig.text(0.02, 0.97, "Who did the ABS challenge system help in 2026?", fontsize=18, fontweight="bold", color=INK)
fig.text(0.02, 0.945, "Added up game by game: how much every overturned ball/strike call changed each team's chance "
         "of winning.\nLabels: actual wins → wins without ABS.", fontsize=11, color=INK2, va="top")
fig.text(0.02, 0.012, SRC_G, fontsize=8, color=MUTED)
plt.subplots_adjust(left=0.08, right=0.97, top=0.90, bottom=0.07)
fig.savefig("chart_team_wins.png", dpi=180, facecolor=SURF)

# ------------------------------------------------ 2. offense vs defense (game by game)
d = g.sort_values("wins_from_abs_gamebygame").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(11, 11.5), facecolor=SURF)
base(ax)
y = range(len(d))
ax.barh([i + 0.18 for i in y], d["def_wins"], height=0.34, color=GAIN, label="Defense: wins from overturns while pitching")
ax.barh([i - 0.18 for i in y], d["off_wins"], height=0.34, color=LOSS, label="Offense: wins from overturns while batting")
ax.scatter(d["wins_from_abs_gamebygame"], list(y), color=INK, s=34, zorder=5, label="Net wins")
badges(ax, d["abbr"], -0.04)
ax.set_ylim(-0.8, len(d) - 0.2)
ax.set_xlabel("Wins (positive = good for that team)", color=INK2)
ax.legend(loc="lower right", frameon=False, fontsize=10)
neg_off = int((g["off_wins"] < 0).sum())
pos_def = int((g["def_wins"] > 0).sum())
fig.text(0.02, 0.97, "Catchers won the challenge game", fontsize=18, fontweight="bold", color=INK)
fig.text(0.02, 0.945, f"{neg_off} of 30 teams lost wins from overturns while batting; {pos_def} gained wins while "
         "pitching.", fontsize=11, color=INK2)
fig.text(0.02, 0.012, SRC_G, fontsize=8, color=MUTED)
plt.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.07)
fig.savefig("chart_offense_defense.png", dpi=180, facecolor=SURF)

# ------------------------------------------------ 3. players
fig, axes = plt.subplots(2, 2, figsize=(14, 10.5), facecolor=SURF)


def panel(ax, df, col, title, note, color, n=8):
    base(ax)
    d = df.sort_values(col, ascending=False).head(n).iloc[::-1]
    ax.barh(d["name"], d[col], color=color, height=0.65)
    for yy, (v, (_, r)) in enumerate(zip(d[col], d.iterrows())):
        ax.text(v + 0.08, yy, f"{v:.1f}   {note(r)}", va="center", ha="left", fontsize=9, color=INK2)
    ax.set_xlim(0, d[col].max() * 2.0)
    ax.tick_params(axis="y", labelsize=10, labelcolor=INK)
    ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=10)


b["runs_lost"] = -b["net_runs"]
p["runs_lost"] = -p["net_runs_saved"]
i = int
panel(axes[0, 0], b, "net_runs", "Hitters ABS helped most  (runs gained)",
      lambda r: f"+{i(r.walk_gained)} BB, {i(r.k_erased)} K erased", GAIN)
panel(axes[0, 1], b, "runs_lost", "Hitters ABS hurt most  (runs lost)",
      lambda r: f"+{i(r.k_gained)} K, {i(r.walk_erased)} BB taken away", LOSS)
panel(axes[1, 0], p, "net_runs_saved", "Pitchers ABS helped most  (runs saved)",
      lambda r: f"+{i(r.k_gained)} K, {i(r.walk_erased)} BB erased", GAIN)
panel(axes[1, 1], p, "runs_lost", "Pitchers ABS hurt most  (runs cost)",
      lambda r: f"+{i(r.walk_gained)} BB, {i(r.k_erased)} K taken away", LOSS)
fig.text(0.02, 0.975, "Who would have been better off without ABS?", fontsize=18, fontweight="bold", color=INK)
fig.text(0.02, 0.948, "Net runs from overturned calls in each player's plate appearances, 2026.  "
         "Blue = would be worse without ABS.  Orange = would be better without ABS.", fontsize=10.5, color=INK2)
fig.text(0.02, 0.012, SRC, fontsize=8, color=MUTED)
plt.subplots_adjust(left=0.13, right=0.98, top=0.88, bottom=0.07, hspace=0.38, wspace=0.42)
fig.savefig("chart_players.png", dpi=180, facecolor=SURF)
print("saved charts")
