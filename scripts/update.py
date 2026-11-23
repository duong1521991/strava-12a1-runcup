#!/usr/bin/env python3
"""Lấy feed club Strava, gộp vào data.json. Cần biến môi trường STRAVA_COOKIE (giá trị _strava4_session)."""
import html, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

CLUB = "604553"
TYPES = {"Run", "TrailRun", "VirtualRun", "Walk", "Hike"}  # chạy bộ và đi bộ đều được tính
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data.json")
VN = timezone(timedelta(hours=7))
now = datetime.now(VN)

cookie = os.environ.get("STRAVA_COOKIE", "").strip()
if not cookie:
    sys.exit("Thiếu STRAVA_COOKIE")
if "=" not in cookie:
    cookie = "_strava4_session=" + cookie


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={
        "Accept": accept, "X-Requested-With": "XMLHttpRequest", "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/157.0.0.0 Safari/537.36"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def parse_date(s):
    s = s.strip()
    if s.startswith("Today"):
        return now.date()
    if s.startswith("Yesterday"):
        return (now - timedelta(days=1)).date()
    m = re.match(r"([A-Za-z]+ \d{1,2}, \d{4})", s)
    if m:
        return datetime.strptime(m.group(1), "%B %d, %Y").date()
    return None


def strip(v):
    return html.unescape(re.sub(r"<[^>]+>", "", v)).strip()


def seconds(v):
    t = 0
    for n, u in re.findall(r"(\d+)\s*(h|m|s)\b", strip(v)):
        t += int(n) * {"h": 3600, "m": 60, "s": 1}[u]
    return t


try:
    old = json.load(open(DATA))
except FileNotFoundError:
    old = {"members": [], "activities": []}
acts = {a["id"]: a for a in old["activities"]}
members = {m["id"]: m for m in old["members"]}

try:
    feed = json.loads(get(f"https://www.strava.com/clubs/{CLUB}/feed?feed_type=club&club_id={CLUB}&num_entries=100"))
except Exception as e:
    sys.exit(f"Không lấy được feed (cookie hết hạn?): {e}")
if "entries" not in feed:
    sys.exit("Phản hồi không có entries (cookie hết hạn?)")

new = 0
for e in feed["entries"]:
    a = e.get("activity")
    if not a or a.get("type") not in TYPES:
        continue
    st = {s["key"]: s["value"] for s in a["stats"]}
    if "km" not in st.get("stat_one", ""):
        continue
    d = parse_date(a["timeAndLocation"]["displayDateAtTime"])
    aid = str(a["id"])
    if aid in acts:           # giữ ngày đã chốt từ lần trước
        continue
    if d is None:
        continue
    ath = a["athlete"]
    acts[aid] = {"id": aid, "m": ath["athleteId"], "d": d.isoformat(),
                 "km": float(strip(st["stat_one"]).split()[0]), "s": seconds(st["stat_three"]), "t": a["type"]}
    members.setdefault(ath["athleteId"], {"id": ath["athleteId"], "n": ath["athleteName"], "avatar": ath.get("avatarUrl")})
    new += 1

if old["activities"] and sorted(old["activities"], key=lambda x: x["id"]) == sorted(acts.values(), key=lambda x: x["id"]) and len(old["members"]) == len(members):
    print("Không có thay đổi"); sys.exit(0)
out = {"updated": now.isoformat(), "members": list(members.values()),
       "activities": sorted(acts.values(), key=lambda x: (x["d"], x["id"]), reverse=True)}
json.dump(out, open(DATA, "w"), ensure_ascii=False, indent=1)
print(f"OK: {len(out['activities'])} buổi chạy, thêm {new}")
