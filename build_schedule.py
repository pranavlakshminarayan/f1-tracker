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
last = json.load(urllib.request.urlopen("https://api.jolpi.ca/ergast/f1/current/last/results.json", timeout=30))["MRData"]["RaceTable"]["Races"][0]
res = {"name": last["raceName"], "round": int(last["round"]), "rows": [[r["position"], r["Driver"].get("code", r["Driver"]["familyName"][:3].upper()), r["Constructor"]["name"], r.get("Time", {}).get("time", r["status"]), r["points"]] for r in last["Results"][:10]]}
st = json.load(urllib.request.urlopen("https://api.jolpi.ca/ergast/f1/current/driverstandings.json", timeout=30))["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
stand = [[s["position"], s["Driver"].get("code", s["Driver"]["familyName"][:3].upper()), s["Constructors"][0]["name"], s["wins"], s["points"]] for s in st[:10]]
html = open("schedule.template.html", encoding="utf-8").read().replace("__DATA__", json.dumps(data)).replace("__RESULT__", json.dumps(res)).replace("__STAND__", json.dumps(stand))
open("schedule.html", "w", encoding="utf-8").write(html)
print(len(data), "races")
