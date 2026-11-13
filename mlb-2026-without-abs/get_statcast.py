import pandas as pd
from pybaseball import statcast, cache
cache.enable()
parts=[]
for s,e in [("2026-03-20","2026-04-30"),("2026-05-01","2026-05-31"),("2026-06-01","2026-06-30"),
            ("2026-07-01","2026-07-31"),("2026-08-01","2026-08-31"),("2026-09-01","2026-10-05")]:
    d=statcast(s,e,verbose=False)
    d=d[d.game_type=="R"]
    print(s,len(d),flush=True); parts.append(d)
pd.concat(parts).to_parquet("statcast_2026.parquet")
print("done",flush=True)
