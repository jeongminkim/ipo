# IPO 캘린더 생성 스크립트

공모주/스팩 캘린더를 로컬에서 생성해 `docs/ipo.ics`, `docs/spac.ics`로 저장하는 방법을 안내합니다.
각 캘린더 이름은 구독 시 다음과 같이 표시됩니다:
- 일반기업: `일반기업 공모주 달력`
- 스팩: `스팩 공모주 달력`

## 준비물
- Python 3.9+ (uv가 이를 사용)
- [uv](https://github.com/astral-sh/uv) 설치
- `scripts/generate_ipo.py` 내 `PHPSESSID` 값이 유효해야 합니다. 만료 시 새 값을 스크립트에 반영하세요.

## 사용 방법
1. 프로젝트 루트에서 실행 (필요 패키지는 uv가 자동 설치):
   ```bash
   uv run --with requests scripts/generate_ipo.py
   ```
2. 실행 시 지난달/이번달/다음달의 3개월 데이터를 자동으로 조회합니다.
3. 실행 후 프로젝트 루트(`docs/`)에 `ipo.ics`, `spac.ics` 파일이 갱신됩니다.
   - 기존 일정은 UID 기준으로 유지·갱신되고, 새 일정은 추가됩니다(이전 월 데이터가 지워지지 않음).
   - `공모가/기관 경쟁률/의무보유확약률/일반청약 경쟁률` 값이 `None`, `-`, `0`이면 DESCRIPTION에서 제외됩니다.

## 참고
- 파일명에는 연월을 포함하지 않고 매 실행 시 덮어씁니다.
- ICS를 캘린더 앱에서 URL 구독하면 일정이 자동 반영됩니다. GitHub Pages 배포 URL 예시: `https://jeongminkim.github.io/ipo/ipo.ics`, `https://jeongminkim.github.io/ipo/spac.ics`
- 신규 일정만 텔레그램으로 알림을 받고 싶다면 아래 환경 변수를 설정하세요:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
