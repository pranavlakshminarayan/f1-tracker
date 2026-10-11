"""Regenerate README.md with the latest F1 results and standings (run automatically by the news workflow)."""
import json, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.jolpi.ca/ergast/f1/current/"
SITE = "https://pranavlakshminarayan.github.io/f1-tracker/"
SGT = timezone(timedelta(hours=8))
MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def get(path):
    with urllib.request.urlopen(API + path, timeout=30) as r:
        return json.load(r)["MRData"]


def code(d):
    return d.get("code") or d["familyName"][:3].upper()


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(" --- " for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def pos(p):
    return f"{MEDAL[int(p)]} {p}" if int(p) in MEDAL else p


def when(race):
    dt = datetime.fromisoformat(f"{race['date']}T{race.get('time', '00:00:00Z')}".replace("Z", "+00:00")).astimezone(SGT)
    return dt


races = get("races.json")["RaceTable"]["Races"]
last = (get("last/results.json")["RaceTable"]["Races"] or [None])[0]
now = datetime.now(timezone.utc)
nxt = next((r for r in races if when(r) + timedelta(hours=2) > now), None)

md = ["<h1 align=\"center\">🏁 F1 Tracker</h1>",
      "<p align=\"center\"><b>Race schedule · results · standings · news</b><br>Updates itself after every Grand Prix and sends it to Telegram.</p>",
      f"<p align=\"center\"><a href=\"{SITE}\"><b>Schedule</b></a> · <a href=\"{SITE}standings.html\"><b>Standings</b></a> · <a href=\"{SITE}news.html\"><b>News</b></a></p>", ""]

if nxt:
    sess = [(l, nxt[k]) for k, l in [("FirstPractice", "FP1"), ("SecondPractice", "FP2"), ("ThirdPractice", "FP3"),
                                      ("SprintQualifying", "Sprint Quali"), ("Sprint", "Sprint"), ("Qualifying", "Qualifying")] if k in nxt]
    sess.append(("Race", nxt))
    loc = nxt["Circuit"]["Location"]
    md += [f"## 🔴 Next race: {nxt['raceName']} (Round {nxt['round']})",
           f"{nxt['Circuit']['circuitName']} · {loc['locality']}, {loc['country']}", "",
           table(["Session", "Time (Singapore)"], [(l, when(s).strftime("%a %d %b · %H:%M")) for l, s in sess]), ""]

if last:
    rows = [(pos(r["position"]), code(r["Driver"]), r["Constructor"]["name"], r.get("Time", {}).get("time", r["status"]), r["points"]) for r in last["Results"][:10]]
    md += [f"## 🏆 Last race: {last['raceName']} (Round {last['round']})", table(["Pos", "Driver", "Team", "Time / Status", "Pts"], rows), ""]
    rnd = last["round"]
    for kind, title in (("driver", "Driver standings"), ("constructor", "Constructor standings")):
        lists = get(f"{rnd}/{kind}standings.json")["StandingsTable"]["StandingsLists"] or get(f"{kind}standings.json")["StandingsTable"]["StandingsLists"]
        if not lists:
            continue
        if kind == "driver":
            rows = [(pos(s["position"]), code(s["Driver"]), s["Constructors"][0]["name"], s["wins"], s["points"]) for s in lists[0]["DriverStandings"][:10]]
            md += [f"## 👤 {title} (after Round {rnd})", table(["Pos", "Driver", "Team", "Wins", "Pts"], rows), ""]
        else:
            rows = [(pos(s["position"]), s["Constructor"]["name"], s["wins"], s["points"]) for s in lists[0]["ConstructorStandings"]]
            md += [f"## 🏎️ {title} (after Round {rnd})", table(["Pos", "Team", "Wins", "Pts"], rows), ""]

done = [r for r in races if when(r) + timedelta(hours=2) <= now]
md += [f"## 📅 Season progress", f"{len(done)} of {len(races)} races complete.", "",
       "## ⚙️ How it works",
       "- **Telegram bot** posts the results, standings and next-race block after each race, and live positions during the race.",
       "- **Website** (GitHub Pages) reads live data every time it opens.",
       "- **GitHub Actions** run everything on a schedule. No server needed.",
       "- Data: [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) and [OpenF1](https://openf1.org); news headlines from public RSS feeds.", "",
       ""]
open("README.md", "w", encoding="utf-8").write("\n".join(md))
print("README written")
