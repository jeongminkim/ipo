import requests
from datetime import date, datetime, timedelta
from pathlib import Path
import time

# ==============================
# 설정
# ==============================

API_URL = "https://www.finuts.co.kr/html/task/ipo/ipoCalendarListQuery.php"

OUTPUT_DIR = Path("calendar")
IPO_ICS = OUTPUT_DIR / "ipo.ics"
SPAC_ICS = OUTPUT_DIR / "spac.ics"

CALENDAR_DOMAIN = "ipo-calendar.github"

HEADERS = {
    "accept": "*/*",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://www.finuts.co.kr/html/ipo/",
    "user-agent": "Mozilla/5.0 (GitHub Actions)"
}

# ==============================
# 날짜 유틸
# ==============================

def target_months():
    """지난달 / 이번달 / 다음달 yyyy.mm"""
    base = date.today().replace(day=1)

    prev_month = (base - timedelta(days=1)).replace(day=1)
    next_month = (base + timedelta(days=32)).replace(day=1)

    return [
        prev_month.strftime("%Y.%m"),
        base.strftime("%Y.%m"),
        next_month.strftime("%Y.%m"),
    ]

# ==============================
# ICS 유틸
# ==============================

def ymd_to_ics(d: str) -> str:
    return d.replace("-", "")

def build_uid(item):
    return f"{item['IPO_SN']}-{item['SCHDL_SE_CD']}-{item['IPO_DATE']}@{CALENDAR_DOMAIN}"

def build_event(item):
    is_subscription = item["SCHDL_SE_CD"] == "S"
    category = "청약" if is_subscription else "상장"

    start = item["BGNG_YMD"]
    end = item["END_YMD"]

    end_plus = (
        datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")

    desc = [
        f"구분: {category}",
        f"공모가: {item['PSS_PRC']}원",
        f"기관 경쟁률: {item['INST_CMPET_RT']}",
        f"의무보유확약률: {item['DUTY_HOLD_DFPR_RT']}%",
        f"일반청약 경쟁률: {item['SCSCS_CMPET_RT']}",
        f"주관사: {item['INDCT_JUGANSA_NM']}",
    ]

    description = "\\n".join(desc)

    return f"""BEGIN:VEVENT
UID:{build_uid(item)}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART;VALUE=DATE:{ymd_to_ics(start)}
DTEND;VALUE=DATE:{end_plus}
SUMMARY:{item['ENT_NM']}
DESCRIPTION:{description}
CATEGORIES:{category}
END:VEVENT
"""

def build_calendar(events):
    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//IPO Calendar KR//EN\n"
        "CALSCALE:GREGORIAN\n"
        + "".join(events) +
        "END:VCALENDAR\n"
    )

# ==============================
# API 호출
# ==============================

def fetch_calendar(month: str):
    params = {
        "calendarDate": month,
        "checkedValue[]": ["chk2", "chk4"],
        "_": int(time.time() * 1000)
    }

    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    return resp.json().get("data", [])

# ==============================
# 메인
# ==============================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ipo_events = []
    spac_events = []

    for month in target_months():
        print(f"Fetching {month}...")
        items = fetch_calendar(month)

        for item in items:
            event = build_event(item)

            if item["SE_CD"] == "IPO":
                ipo_events.append(event)
            elif item["SE_CD"] == "SPAC":
                spac_events.append(event)

    IPO_ICS.write_text(build_calendar(ipo_events), encoding="utf-8")
    SPAC_ICS.write_text(build_calendar(spac_events), encoding="utf-8")

    print(f"✔ Generated {IPO_ICS}")
    print(f"✔ Generated {SPAC_ICS}")

if __name__ == "__main__":
    main()
