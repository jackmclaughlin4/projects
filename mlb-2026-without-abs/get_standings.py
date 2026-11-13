"""Final 2026 standings from the MLB Stats API -> standings_2026.csv"""
import requests
import pandas as pd

r = requests.get("https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=2026"
                 "&standingsTypes=regularSeason", timeout=60).json()
rows = [dict(team_id=t["team"]["id"], team=t["team"]["name"], div=rec["division"]["id"],
             league=rec["league"]["id"], W=t["wins"], L=t["losses"], RS=t["runsScored"],
             RA=t["runsAllowed"], div_rank=int(t["divisionRank"]), wc_rank=t.get("wildCardRank"))
        for rec in r["records"] for t in rec["teamRecords"]]
pd.DataFrame(rows).to_csv("standings_2026.csv", index=False)
print("saved standings_2026.csv")
