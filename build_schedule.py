"""Generate schedule.html with the current F1 calendar embedded (times shown in Singapore time)."""
import json, urllib.request
races = json.load(urllib.request.urlopen("https://api.jolpi.ca/ergast/f1/current.json", timeout=30))["MRData"]["RaceTable"]["Races"]
keys = [("FirstPractice","FP1"),("SecondPractice","FP2"),("ThirdPractice","FP3"),("SprintQualifying","Sprint Quali"),("Sprint","Sprint"),("Qualifying","Qualifying")]
data = []
for r in races:
    s = [[l, f"{r[k]['date']}T{r[k].get('time','00:00:00Z')}"] for k, l in keys if k in r]
    s.append(["Race", f"{r['date']}T{r.get('time','00:00:00Z')}"])
    data.append({"round": int(r["round"]), "name": r["raceName"], "circuit": r["Circuit"]["circuitName"],
                 "place": f"{r['Circuit']['Location']['locality']}, {r['Circuit']['Location']['country']}", "sessions": s})
html = open("schedule.template.html", encoding="utf-8").read().replace("__DATA__", json.dumps(data))
open("schedule.html", "w", encoding="utf-8").write(html)
print(len(data), "races")
