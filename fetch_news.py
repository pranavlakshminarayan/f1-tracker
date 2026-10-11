"""Collect F1 headlines from public RSS feeds into news.json (headline, short snippet, image, link back to the source)."""
import html, json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = {
    "BBC Sport": "https://feeds.bbci.co.uk/sport/formula1/rss.xml",
    "Motorsport.com": "https://www.motorsport.com/rss/f1/news/",
    "The Race": "https://www.the-race.com/category/formula-1/feed/",
    "Sky Sports": "https://www.skysports.com/rss/12433",
    "Formula1.com": "https://www.formula1.com/content/fom-website/en/latest/all.xml",
    "Crash.net": "https://www.crash.net/rss/f1",
}
NS = {"media": "http://search.yahoo.com/mrss/", "content": "http://purl.org/rss/1.0/modules/content/"}


def clean(s, n=220):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def image(it):
    for tag in ("media:thumbnail", "media:content"):
        e = it.find(tag, NS)
        if e is not None and e.get("url"):
            return e.get("url")
    e = it.find("enclosure")
    if e is not None and (e.get("type") or "").startswith("image"):
        return e.get("url")
    m = re.search(r'<img[^>]+src="([^"]+)"', (it.findtext("description") or "") + (it.findtext("content:encoded", namespaces=NS) or ""))
    return m.group(1) if m else None


items = {}
for source, url in FEEDS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        print("skip", source, e); continue
    for it in root.iter("item"):
        link, title = (it.findtext("link") or "").strip(), clean(it.findtext("title"), 200)
        try:
            when = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            continue
        if link and title:
            items[link] = {"title": title, "link": link, "source": source, "time": when.isoformat(),
                           "summary": clean(it.findtext("description")), "image": image(it)}
out = sorted(items.values(), key=lambda x: x["time"], reverse=True)[:80]
json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": out}, open("news.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(out), "items")
