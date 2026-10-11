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


def post(expect_date=None, tries=40):
    for _ in range(tries):
        race = (get("last/results.json")["RaceTable"]["Races"] or [None])[0]
        if race and (expect_date is None or race["date"] == expect_date):
            break
        time.sleep(60)
    else:
        print("results not published"); return
    res = [[r["position"], r["Driver"]["code"] if "code" in r["Driver"] else r["Driver"]["familyName"][:3].upper(),
            r["Constructor"]["name"][:16], r.get("Time", {}).get("time", r["status"]), r["points"]] for r in race["Results"][:10]]
    send_photo(table_image(f"{race['raceName']} – Result", f"Round {race['round']} · Top 10", ["POS", "DRIVER", "TEAM", "TIME / STATUS", "PTS"],
                           res, [90, 130, 260, 230, 70]), f"Round {race['round']} result")
    st = get("driverstandings.json")["StandingsTable"]["StandingsLists"][0]["DriverStandings"][:10]
    rows = [[s["position"], s["Driver"].get("code", s["Driver"]["familyName"][:3].upper()), s["Constructors"][0]["name"][:16], s["wins"], s["points"]] for s in st]
    send_photo(table_image("Driver Standings", f"After round {race['round']}", ["POS", "DRIVER", "TEAM", "WINS", "PTS"], rows, [90, 130, 260, 120, 90]), "Championship standings")
    nxt = next((r for r in get("races.json")["RaceTable"]["Races"] if int(r["round"]) > int(race["round"])), None)
    if nxt:
        send_photo(next_race_image(nxt), f"Next: {nxt['raceName']}")
    else:
        print("season finished")
    # text link message
    data = ("chat_id=" + os.environ["TELEGRAM_CHAT_ID"] + "&text=" + urllib.request.quote(f"Full schedule, results and standings: {PAGE_URL}")).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage", data, timeout=30).read()


if __name__ == "__main__":
    post(next((a.split("=")[1] for a in sys.argv if a.startswith("--date=")), None), tries=1)
