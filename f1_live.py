"""Live race positions to Telegram: one message, edited every ~30s while a Race session runs (OpenF1 data)."""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

OF1 = "https://api.openf1.org/v1/"
TG = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/"
CHAT = os.environ["TELEGRAM_CHAT_ID"]
UTC = timezone.utc


def of1(path, **q):
    url = OF1 + path + "?" + "&".join(f"{k}={urllib.parse.quote(str(v), safe='<>=')}" for k, v in q.items())
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(3)
    return []


def tg(method, **data):
    req = urllib.request.Request(TG + method, urllib.parse.urlencode(data).encode())
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        print("telegram error", e)
        return {}


def ts(s):
    return datetime.fromisoformat(s)


def find_session(now, session_key=None):
    if session_key:
        return (of1("sessions", session_key=session_key) or [None])[0]
    for s in of1("sessions", year=now.year, session_name="Race"):
        if ts(s["date_start"]) - timedelta(minutes=20) <= now <= ts(s["date_end"]) + timedelta(minutes=10):
            return s


def snapshot(s, ref):
    drivers = {d["driver_number"]: d for d in of1("drivers", session_key=s["session_key"])}
    pos = {}
    for p in of1("position", session_key=s["session_key"], **{"date<": ref.isoformat()}):
        pos[p["driver_number"]] = p  # rows are time-ordered, last wins
    gaps = {}
    for i in of1("intervals", session_key=s["session_key"], **{"date>": (ref - timedelta(seconds=90)).isoformat(), "date<": ref.isoformat()}):
        gaps[i["driver_number"]] = i.get("gap_to_leader")
    laps = of1("laps", session_key=s["session_key"], **{"date_start<": ref.isoformat()})
    lap = max((l["lap_number"] for l in laps), default=None)
    rows = sorted(pos.values(), key=lambda p: p["position"])
    lines = [f"🏁 {s['location']} GP – " + ("FINAL" if ref >= ts(s["date_end"]) else "LIVE") + (f" · Lap {lap}" if lap else ""), ""]
    for p in rows:
        d = drivers.get(p["driver_number"], {})
        g = gaps.get(p["driver_number"])
        g = "" if p["position"] == 1 else (f"+{g}" if isinstance(g, (int, float)) else (g or ""))
        lines.append(f"{p['position']:>2}. {d.get('name_acronym', p['driver_number'])}  {d.get('team_name', '')[:14]:<14} {g}")
    lines.append(f"\nUpdated {ref.astimezone(timezone(timedelta(hours=8))):%H:%M:%S} SGT")
    return "<pre>" + "\n".join(lines) + "</pre>"


def main():
    once = "--once" in sys.argv
    key = next((a.split("=")[1] for a in sys.argv if a.startswith("--session=")), None)
    msg_id = None
    while True:
        now = datetime.now(UTC)
        s = find_session(now, key)
        if not s:
            print("no live race"); return
        ref = min(now, ts(s["date_end"]))
        text = snapshot(s, ref)
        if msg_id is None:
            msg_id = tg("sendMessage", chat_id=CHAT, text=text, parse_mode="HTML").get("result", {}).get("message_id")
        else:
            tg("editMessageText", chat_id=CHAT, message_id=msg_id, text=text, parse_mode="HTML")
        if once:
            return
        if now > ts(s["date_end"]) + timedelta(minutes=5):
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
