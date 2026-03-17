import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ==============================
# 설정
# ==============================

API_URL = "https://www.finuts.co.kr/html/task/ipo/ipoCalendarListQuery.php"

OUTPUT_DIR = (Path(__file__).resolve().parent.parent / "docs").resolve()
CALENDAR_DOMAIN = "ipo-calendar.github"

# ⚠️ 로컬에서 확인한 PHPSESSID (만료되면 다시 갱신 필요)
PHPSESSID = "m9lgq2lor5h69ccfqf62glb855"

HEADERS = {
    "accept": "*/*",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
    "priority": "u=0, i",
    "referer": "https://www.finuts.co.kr/html/ipo/",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}

COOKIES = {
    "PHPSESSID": PHPSESSID,
}

# ==============================
# ICS 유틸
# ==============================


def ymd_to_ics(d: str) -> str:
    return d.replace("-", "")


def ics_escape(text: str) -> str:
    # RFC5545 escaping
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def ics_unescape(text: str) -> str:
    # RFC5545 unescaping
    # we might have multiple levels of escaping due to the bug
    # loop until no more changes to handle "compounded" escaping
    current = text
    while True:
        next_val = (
            current.replace("\\n", "\n")
            .replace("\\N", "\n")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\\\", "\\")
        )
        if next_val == current:
            break
        current = next_val
    return current


def fold_line(line: str, limit: int = 75) -> str:
    # RFC5545 line folding (CRLF + space), count by octet length
    if len(line.encode("utf-8")) <= limit:
        return line

    parts = []
    current = ""
    current_len = 0

    for ch in line:
        ch_len = len(ch.encode("utf-8"))
        if current_len + ch_len > limit:
            parts.append(current)
            current = " " + ch
            current_len = 1 + ch_len  # leading space counts in length
        else:
            current += ch
            current_len += ch_len

    if current:
        parts.append(current)

    return "\r\n".join(parts)


def fmt_line(key: str, value: str) -> str:
    return fold_line(f"{key}:{value}")


def build_uid(item):
    return f"{item['IPO_SN']}-{item['SCHDL_SE_CD']}-{item['IPO_DATE']}@{CALENDAR_DOMAIN}"


def parse_uid(uid: str):
    """
    UID format (we generate):
      {IPO_SN}-{SCHDL_SE_CD}-{IPO_DATE}@{domain}
    Returns (ipo_sn, schdl_se_cd, ipo_date) or None if not parseable.
    """
    if not uid:
        return None
    left = uid.split("@", 1)[0]
    parts = left.split("-", 2)
    if len(parts) != 3:
        return None
    ipo_sn, schdl_se_cd, ipo_date = parts
    if not ipo_sn or not schdl_se_cd or not ipo_date:
        return None
    return ipo_sn, schdl_se_cd, ipo_date


def uid_month(uid: str):
    parsed = parse_uid(uid)
    if not parsed:
        return None
    _, _, ipo_date = parsed
    try:
        return datetime.strptime(ipo_date, "%Y-%m-%d").strftime("%Y.%m")
    except ValueError:
        return None


def has_value(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        lowered = s.lower()
        if lowered in {"none", "null", "-"}:
            return False
        try:
            num = float(s.replace(",", ""))
        except ValueError:
            return True
        return num != 0
    try:
        return float(v) != 0
    except Exception:
        return bool(v)


def clean_description_text(desc_text: str) -> str:
    # desc_text is the literal string from the ICS file (potentially escaped)
    unescaped = ics_unescape(desc_text)
    raw_lines = unescaped.split("\n")
    cleaned = []

    for line in raw_lines:
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        value = value.strip()

        if label == "구분":
            cleaned.append(f"{label}: {value}")
            continue

        # strip common unit suffix for numeric check
        numeric_value = (
            value.replace("원", "")
            .replace("%", "")
            .replace(",", "")
            .strip()
        )

        if has_value(numeric_value):
            cleaned.append(f"{label}: {value}")

    return "\n".join(cleaned)

def unfold_lines(lines):
    unfolded = []
    for line in lines:
        if line.startswith(" ") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def extract_uid(lines):
    for line in lines:
        upper = line.upper()
        if upper.startswith("UID:") or upper.startswith("UID;"):
            return line.split(":", 1)[1]
    return None


def load_existing_events(path: Path):
    if not path.exists():
        return {}

    events = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    current = []

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = [line]
        elif current:
            current.append(line)
            if line == "END:VEVENT":
                unfolded = unfold_lines(current)
                uid = extract_uid(unfolded)
                if uid:
                    for idx, l in enumerate(unfolded):
                        upper = l.upper()
                        if upper.startswith("DESCRIPTION:") or upper.startswith("DESCRIPTION;"):
                            key = l.split(":", 1)[0]
                            cleaned = clean_description_text(l.split(":", 1)[1])
                            unfolded[idx] = fmt_line(key, ics_escape(cleaned))
                            break
                    events[uid] = "\r\n".join(unfolded)
                current = []

    return events


def format_date_range(start: str, end: str) -> str:
    return start if start == end else f"{start}~{end}"


def build_summary(item) -> str:
    category = "청약" if item["SCHDL_SE_CD"] == "S" else "상장"
    
    # 청약인 경우 주관사 정보를 포함
    if category == "청약" and has_value(item.get("INDCT_JUGANSA_NM")):
        jugansa = item["INDCT_JUGANSA_NM"].strip()
        return f"[{category}/{jugansa}] {item['ENT_NM']}"
    
    return f"[{category}] {item['ENT_NM']}"


def build_new_events_message(items, title: str) -> str:
    lines = [f"{title} 신규 일정"]

    for item in items:
        start = item["BGNG_YMD"]
        end = item["END_YMD"]
        lines.append(f"- {format_date_range(start, end)} {build_summary(item)}")

    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def build_event(item):
    is_subscription = item["SCHDL_SE_CD"] == "S"
    category = "청약" if is_subscription else "상장"

    start = item["BGNG_YMD"]
    end = item["END_YMD"]

    end_plus = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")

    desc = [f"구분: {category}"]

    if has_value(item.get("PSS_PRC")):
        desc.append(f"공모가: {item['PSS_PRC']}원")
    if has_value(item.get("INST_CMPET_RT")):
        desc.append(f"기관 경쟁률: {item['INST_CMPET_RT']}")
    if has_value(item.get("DUTY_HOLD_DFPR_RT")):
        desc.append(f"의무보유확약률: {item['DUTY_HOLD_DFPR_RT']}%")
    if has_value(item.get("SCSCS_CMPET_RT")):
        desc.append(f"일반청약 경쟁률: {item['SCSCS_CMPET_RT']}")
    if has_value(item.get("INDCT_JUGANSA_NM")):
        desc.append(f"주관사: {item['INDCT_JUGANSA_NM']}")

    # 실제 개행을 사용하고 나중에 ics_escape에서 \n 처리
    description = "\n".join(desc)

    summary = build_summary(item)

    lines = [
        "BEGIN:VEVENT",
        fmt_line("UID", ics_escape(build_uid(item))),
        fmt_line("DTSTAMP", datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")),
        fmt_line("DTSTART;VALUE=DATE", ymd_to_ics(start)),
        fmt_line("DTEND;VALUE=DATE", end_plus),
        fmt_line("SUMMARY", ics_escape(summary)),
        fmt_line("DESCRIPTION", ics_escape(description)),
        fmt_line("CATEGORIES", ics_escape(category)),
        "END:VEVENT",
    ]

    return "\r\n".join(lines)


def build_calendar(events, cal_name: str):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IPO Calendar KR//EN",
        "CALSCALE:GREGORIAN",
        fmt_line("X-WR-CALNAME", cal_name),
        fmt_line("X-WR-TIMEZONE", "UTC"),
    ]

    for event in events:
        lines.extend(event.splitlines())

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


# ==============================
# API 호출
# ==============================


def fetch_calendar(month: str, session: requests.Session):
    params = {
        "calendarDate": month,
        "checkedValue[]": ["chk2", "chk4"],
        "_": int(time.time() * 1000),
    }

    resp = session.get(API_URL, params=params, headers=HEADERS, cookies=COOKIES, timeout=15)
    resp.raise_for_status()

    return resp.json().get("data", [])


# ==============================
# 기간
# ==============================


def target_months():
    base = date.today().replace(day=1)

    prev_month = (base - timedelta(days=1)).replace(day=1)
    next_month = (base + timedelta(days=32)).replace(day=1)

    return [
        prev_month.strftime("%Y.%m"),
        base.strftime("%Y.%m"),
        next_month.strftime("%Y.%m"),
    ]


# ==============================
# 메인
# ==============================


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    ipo_path = OUTPUT_DIR / "ipo.ics"
    spac_path = OUTPUT_DIR / "spac.ics"

    ipo_existing = load_existing_events(ipo_path)
    spac_existing = load_existing_events(spac_path)

    ipo_events_new = {}
    spac_events_new = {}
    new_ipo_items = []
    new_spac_items = []

    target_month_set = set(target_months())
    ipo_new_keys = set()
    spac_new_keys = set()

    def event_key_from_item(item):
        # Stable key for "same company + same schedule type" regardless of IPO_DATE changes.
        # (IPO / SPAC is already separated into different output files.)
        return str(item.get("IPO_SN", "")).strip(), str(item.get("SCHDL_SE_CD", "")).strip()

    def event_key_from_uid(uid: str):
        parsed = parse_uid(uid)
        if not parsed:
            return None
        ipo_sn, schdl_se_cd, _ = parsed
        return ipo_sn, schdl_se_cd

    def drop_existing_by_key(existing_events: dict, key):
        # Remove any old UIDs matching the same (IPO_SN, SCHDL_SE_CD) key.
        if not key or not key[0] or not key[1]:
            return
        to_delete = []
        for existing_uid in existing_events.keys():
            if event_key_from_uid(existing_uid) == key:
                to_delete.append(existing_uid)
        for existing_uid in to_delete:
            existing_events.pop(existing_uid, None)

    for month_for_api in target_months():
        print(f"{month_for_api} 데이터 수집 중...")
        items = fetch_calendar(month_for_api, session)

        for item in items:
            uid = build_uid(item)
            event = build_event(item)

            if item.get("SE_CD") == "IPO":
                key = event_key_from_item(item)
                ipo_new_keys.add(key)
                # If UID changed due to schedule changes, drop old event(s) first.
                drop_existing_by_key(ipo_existing, key)
                ipo_events_new[uid] = event
                if uid not in ipo_existing:
                    new_ipo_items.append(item)
            elif item.get("SE_CD") == "SPAC":
                key = event_key_from_item(item)
                spac_new_keys.add(key)
                drop_existing_by_key(spac_existing, key)
                spac_events_new[uid] = event
                if uid not in spac_existing:
                    new_spac_items.append(item)

    # Prune cancelled/missing events within the fetched month window.
    def prune_cancelled(existing_events: dict, new_keys: set):
        to_delete = []
        for existing_uid in existing_events.keys():
            m = uid_month(existing_uid)
            if m not in target_month_set:
                continue
            key = event_key_from_uid(existing_uid)
            if key and key not in new_keys:
                to_delete.append(existing_uid)
        for existing_uid in to_delete:
            existing_events.pop(existing_uid, None)

    prune_cancelled(ipo_existing, ipo_new_keys)
    prune_cancelled(spac_existing, spac_new_keys)

    ipo_merged = {**ipo_existing}
    ipo_merged.update(ipo_events_new)

    spac_merged = {**spac_existing}
    spac_merged.update(spac_events_new)

    ipo_path.write_text(build_calendar(ipo_merged.values(), "일반기업 공모주 달력"), encoding="utf-8")
    spac_path.write_text(build_calendar(spac_merged.values(), "스팩 공모주 달력"), encoding="utf-8")

    print(f"✔ 생성 완료: {ipo_path}")
    print(f"✔ 생성 완료: {spac_path}")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        parts = []
        if new_ipo_items:
            parts.append(build_new_events_message(new_ipo_items, "일반기업 공모주 달력"))
        if new_spac_items:
            parts.append(build_new_events_message(new_spac_items, "스팩 공모주 달력"))
        if parts:
            try:
                send_telegram_message(token, chat_id, "\n\n".join(parts))
                print("✔ 텔레그램 알림 전송 완료")
            except requests.RequestException as e:
                print(f"⚠️ 텔레그램 알림 실패: {e}")


if __name__ == "__main__":
    main()
