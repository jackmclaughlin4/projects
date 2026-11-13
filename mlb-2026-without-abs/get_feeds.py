import json, requests, concurrent.futures as cf, pandas as pd
sched=requests.get("https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2026&gameType=R&startDate=2026-03-01&endDate=2026-10-10",timeout=60).json()
games=[(g["gamePk"],g["teams"]["away"]["team"]["id"],g["teams"]["home"]["team"]["id"],g["status"]["detailedState"])
       for d in sched["dates"] for g in d["games"]]
games=[g for g in games if g[3] in ("Final","Completed Early","Game Over")]
games=list({g[0]:g for g in games}.values())
print("games",len(games),flush=True)
def one(g):
    pk=g[0]
    for _ in range(3):
        try:
            f=requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live",timeout=60).json(); break
        except Exception: f=None
    if f is None: return [],pk
    rows=[]
    def revs(obj):
        out=[]
        rd=obj.get("reviewDetails")
        if rd: out.append(rd); out+=rd.get("additionalReviews",[]) or []
        return [r for r in out if r.get("reviewType")=="MJ"]
    for play in f["liveData"]["plays"]["allPlays"]:
        ab=play["about"]["atBatIndex"]+1
        pitches=[e for e in play["playEvents"] if e.get("isPitch")]
        items=[(ev,rd,"pitch") for ev in pitches for rd in revs(ev)]
        if pitches:
            items+=[(pitches[-1],rd,"play") for rd in revs(play)]
        for ev,rd,lvl in items:
                rows.append(dict(game_pk=pk,at_bat_number=ab,pitch_number=ev.get("pitchNumber"),level=lvl,
                    final_call=ev["details"].get("code"),overturned=rd.get("isOverturned"),
                    challenge_team=rd.get("challengeTeamId"),challenger_id=(rd.get("player") or {}).get("id"),
                    challenger=(rd.get("player") or {}).get("fullName"),
                    balls_after=ev["count"]["balls"],strikes_after=ev["count"]["strikes"]))
    return rows,None
out=[];bad=[]
with cf.ThreadPoolExecutor(16) as ex:
    for i,(r,b) in enumerate(ex.map(one,games)):
        out+=r
        if b: bad.append(b)
        if i%300==0: print(i,len(out),flush=True)
pd.DataFrame(out).to_csv("challenges_2026.csv",index=False)
pd.DataFrame(games,columns=["game_pk","away_id","home_id","state"]).to_csv("games_2026.csv",index=False)
teams=requests.get("https://statsapi.mlb.com/api/v1/teams?sportId=1&season=2026",timeout=60).json()["teams"]
pd.DataFrame([dict(team_id=t["id"],abbr=t["abbreviation"],name=t["teamName"]) for t in teams]).to_csv("teams.csv",index=False)
print("done",len(out),"failed",bad,flush=True)
