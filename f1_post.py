"""After a race: send results, driver standings and the next-race block to Telegram as images."""
import io, json, os, sys, time, urllib.request, uuid
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

API = "https://api.jolpi.ca/ergast/f1/current/"
SGT = timezone(timedelta(hours=8))
RED, BLACK, WHITE, GREY, PANEL = "#E10600", "#15151E", "#FFFFFF", "#A0A0B0", "#1F1F2B"
PAGE_URL = os.environ.get("PAGE_URL", "https://pranavlakshminarayan.github.io/f1-tracker/")
FONTS = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]


def font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def get(path):
    with urllib.request.urlopen(API + path, timeout=30) as r:
        return json.load(r)["MRData"]


def table_image(title, sub, header, rows, widths):
    W, row_h, top = sum(widths) + 60, 46, 130
    img = Image.new("RGB", (W, top + row_h * (len(rows) + 1) + 30), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=RED)
    d.text((30, 28), title, font=font(34), fill=WHITE)
    d.text((30, 78), sub, font=font(20), fill=GREY)
    for r, cells in enumerate([header] + rows):
        y = top + r * row_h
        if r == 0:
            d.text((30, y + 10), "", font=font(18))
        elif r % 2:
            d.rectangle([20, y, W - 20, y + row_h - 2], fill=PANEL)
        if 1 <= r <= 3 and header[0] == "POS":
            d.rectangle([20, y, 26, y + row_h - 2], fill=RED)
        x = 30
        for c, w in zip(cells, widths):
            d.text((x, y + 10), str(c), font=font(18 if r == 0 else 22), fill=GREY if r == 0 else WHITE)
            x += w
    return img


def next_race_image(race):
    rows = []
    keys = [("FirstPractice", "FP1"), ("SecondPractice", "FP2"), ("ThirdPractice", "FP3"),
            ("SprintQualifying", "Sprint Quali"), ("Sprint", "Sprint"), ("Qualifying", "Qualifying")]
    ses = [(l, race[k]) for k, l in keys if k in race] + [("Race", race)]
    for l, s in ses:
        dt = datetime.fromisoformat(f"{s['date']}T{s.get('time', '00:00:00Z')}".replace("Z", "+00:00")).astimezone(SGT)
        rows.append((l, dt.strftime("%a %d %b  %H:%M")))
    img = Image.new("RGB", (900, 200 + 44 * len(rows)), RED)
    d = ImageDraw.Draw(img)
    d.text((40, 30), f"NEXT RACE  ·  ROUND {race['round']}", font=font(20), fill="#FFD6D4")
    d.text((40, 62), race["raceName"].upper(), font=font(40), fill=WHITE)
    loc = race["Circuit"]["Location"]
    d.text((40, 118), f"{race['Circuit']['circuitName']}  ·  {loc['locality']}, {loc['country']}", font=font(22), fill=WHITE)
    for i, (l, t) in enumerate(rows):
        y = 175 + i * 44
        d.text((40, y), l, font=font(24), fill=WHITE)
        d.text((260, y), t + " SGT", font=font(24), fill=WHITE)
    return img


def send_photo(img, caption):
    buf = io.BytesIO(); img.save(buf, "PNG")
    b, chat = uuid.uuid4().hex, os.environ["TELEGRAM_CHAT_ID"]
    parts = b""
    for k, v in (("chat_id", chat), ("caption", caption)):
        parts += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    parts += f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="f.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + buf.getvalue() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto", parts,
                                 {"Content-Type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=60).read()


POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
OF1 = "https://api.openf1.org/v1/"


def of1(path):
    with urllib.request.urlopen(OF1 + path, timeout=40) as r:
        return json.load(r)


def dcode(d):
    return d.get("code") or d["familyName"][:3].upper()


def official(expect_date):
    race = (get("last/results.json")["RaceTable"]["Races"] or [None])[0]
    if not race or (expect_date and race["date"] != expect_date):
        return None
    res = [[r["position"], dcode(r["Driver"]), r["Constructor"]["name"][:16], r.get("Time", {}).get("time", r["status"]), r["points"]] for r in race["Results"][:10]]
    st = get("driverstandings.json")["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
    stand = [[s["position"], dcode(s["Driver"]), s["Constructors"][0]["name"][:16], s["wins"], s["points"]] for s in st[:10]]
    return race["raceName"], race["round"], res, stand, False


def provisional(expect_date):
    """Same tables built from OpenF1 final positions while the official results feed lags."""
    race = next((r for r in get("races.json")["RaceTable"]["Races"] if r["date"] == expect_date), None)
    sess = next((s for s in of1(f"sessions?year={expect_date[:4]}&session_name=Race") if s["date_start"][:10] == expect_date), None)
    if not race or not sess:
        return None
    key = sess["session_key"]
    drv = {d["driver_number"]: d["name_acronym"] for d in of1(f"drivers?session_key={key}")}
    final = {}
    for p in of1(f"position?session_key={key}"):
        final[p["driver_number"]] = p["position"]
    order = [drv.get(n, str(n)) for n, _ in sorted(final.items(), key=lambda x: x[1])]
    base = get("driverstandings.json")["StandingsTable"]["StandingsLists"][0]
    last = (get("last/results.json")["RaceTable"]["Races"] or [{"round": 0}])[0]
    if int(last["round"]) >= int(race["round"]):
        return None  # standings already include this race
    tbl = {dcode(s["Driver"]): {"team": s["Constructors"][0]["name"], "pts": float(s["points"]), "wins": int(s["wins"])} for s in base["DriverStandings"]}
    res = []
    for pos, c in enumerate(order, 1):
        pts = POINTS[pos - 1] if pos <= 10 else 0
        if c in tbl:
            tbl[c]["pts"] += pts
            tbl[c]["wins"] += 1 if pos == 1 else 0
        res.append([pos, c, tbl.get(c, {}).get("team", "")[:16], "provisional", pts])
    ranked = sorted(tbl.items(), key=lambda x: (-x[1]["pts"], -x[1]["wins"]))
    stand = [[i, c, v["team"][:16], v["wins"], int(v["pts"])] for i, (c, v) in enumerate(ranked[:10], 1)]
    return race["raceName"], race["round"], res[:10], stand, True


def post(expect_date=None, tries=40):
    data = None
    for n in range(tries):
        data = official(expect_date)
        if data:
            break
        if n < tries - 1:
            time.sleep(60)
    if not data and expect_date:
        data = provisional(expect_date)
    if not data:
        print("results not available"); return
    name, rnd, res, stand, prov = data
    tag = " · PROVISIONAL" if prov else ""
    send_photo(table_image(f"{name} – Result", f"Round {rnd} · Top 10{tag}", ["POS", "DRIVER", "TEAM", "TIME / STATUS", "PTS"],
                           res, [90, 130, 260, 230, 70]), f"Round {rnd} result" + (" (provisional, official results pending)" if prov else ""))
    send_photo(table_image("Driver Standings", f"After round {rnd}{tag}", ["POS", "DRIVER", "TEAM", "WINS", "PTS"], stand, [90, 130, 260, 120, 90]), "Championship standings")
    nxt = next((r for r in get("races.json")["RaceTable"]["Races"] if int(r["round"]) > int(rnd)), None)
    if nxt:
        send_photo(next_race_image(nxt), f"Next: {nxt['raceName']}")
    msg = "Schedule: " + PAGE_URL + "\nStandings: " + PAGE_URL + "standings.html\nNews: " + PAGE_URL + "news.html"
    body = ("chat_id=" + os.environ["TELEGRAM_CHAT_ID"] + "&text=" + urllib.request.quote(msg)).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage", body, timeout=30).read()




# ---- automatic mode: run on a schedule, post once after each race, remember what was posted ----
STATE = "post_state.json"


def race_end(race):
    """Real end time from OpenF1 when known, otherwise scheduled start + 3h."""
    start = datetime.fromisoformat(f"{race['date']}T{race.get('time', '00:00:00Z')}".replace("Z", "+00:00"))
    try:
        s = next((x for x in of1(f"sessions?year={race['season']}&session_name=Race") if x["date_start"][:10] == race["date"]), None)
        if s:
            return datetime.fromisoformat(s["date_end"])
    except Exception:
        pass
    return start + timedelta(hours=3)


def auto():
    now = datetime.now(timezone.utc)
    races = get("races.json")["RaceTable"]["Races"]
    done = [r for r in races if now > race_end(r) + timedelta(minutes=20)]
    if not done:
        print("no finished race yet"); return
    r = done[-1]
    key = f"{r['season']}-{int(r['round'])}"
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if state.get("last") == key:
        print("already posted", key); return
    post(r["date"], tries=1)
    json.dump({"last": key}, open(STATE, "w"))
    print("posted", key)


if __name__ == "__main__":
    if "--auto" in sys.argv:
        auto()
    else:
        post(next((a.split("=")[1] for a in sys.argv if a.startswith("--date=")), None), tries=1)
