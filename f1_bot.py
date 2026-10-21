"""Daily F1 check: on days with a session (Singapore time), send a Telegram message."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))
API = "https://api.jolpi.ca/ergast/f1/current.json"
WATCH_URL = os.environ.get("WATCH_URL", "https://watchitbetter.com")
SESSIONS = [("FirstPractice", "FP1"), ("SecondPractice", "FP2"), ("ThirdPractice", "FP3"),
            ("SprintQualifying", "Sprint Quali"), ("Sprint", "Sprint"),
            ("Qualifying", "Qualifying")]


def get_races():
    with urllib.request.urlopen(API, timeout=30) as r:
        return json.load(r)["MRData"]["RaceTable"]["Races"]


def sessions_of(race):
    out = [(label, race[key]) for key, label in SESSIONS if key in race]
    out.append(("Race", race))
    result = []
    for label, d in out:
        dt = datetime.fromisoformat(f"{d['date']}T{d.get('time', '00:00:00Z')}".replace("Z", "+00:00"))
        result.append((label, dt.astimezone(SGT)))
    return sorted(result, key=lambda s: s[1])


SITE = "https://pranavlakshminarayan.github.io/f1-tracker/"
REMIND_DAYS = 4


def build_message(now):
    for race in get_races():
        ses = sessions_of(race)
        if (ses[-1][1].date() - now.date()).days == REMIND_DAYS:
            loc = race["Circuit"]["Location"]
            lines = [f"⏰ {race['raceName']} is {REMIND_DAYS} days away (Round {race['round']})",
                     f"{race['Circuit']['circuitName']} · {loc['locality']}, {loc['country']}", ""]
            lines += [f"• {n}: {t:%a %d %b, %H:%M} SGT" for n, t in ses]
            lines += ["", f"Schedule: {SITE}", f"News: {SITE}news.html"]
            return "\n".join(lines)
        today = [s for s in ses if s[1].date() == now.date()]
        if today:
            loc = race["Circuit"]["Location"]
            lines = [f"🏁 Watch today's F1 link", f"{race['raceName']} – {loc['locality']}, {loc['country']}", ""]
            lines += [f"• {n}: {t:%H:%M} SGT" for n, t in today]
            lines += ["", WATCH_URL, "(Link may only go live close to the session.)"]
            return "\n".join(lines)
    return None


def send(text):
    data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}).encode()
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    urllib.request.urlopen(url, data, timeout=30).read()


if __name__ == "__main__":
    msg = build_message(datetime.now(SGT))
    if "--force-test" in sys.argv:
        msg = (msg or "No F1 session today.") + "\n\n(test message)"
    if msg:
        send(msg)
        print("sent")
    else:
        print("no session today")
