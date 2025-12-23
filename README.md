# IPO 캘린더 생성 스크립트

공모주/스팩 캘린더를 로컬에서 생성해 `docs/ipo.ics`, `docs/spac.ics`로 저장하는 방법을 안내합니다.

## 준비물
- Python 3.9+ (uv가 이를 사용)
- [uv](https://github.com/astral-sh/uv) 설치
- `scripts/generate_ipo.py` 내 `PHPSESSID` 값이 유효해야 합니다. 만료 시 새 값을 스크립트에 반영하세요.

## 사용 방법
1. 프로젝트 루트에서 실행 (필요 패키지는 uv가 자동 설치):
   ```bash
   uv run --with requests scripts/generate_ipo.py
   ```
2. 프롬프트에 생성할 연월을 `yyyymm` 형식으로 입력 (예: `202501`).
3. 실행 후 프로젝트 루트(`docs/`)에 `ipo.ics`, `spac.ics` 파일이 갱신됩니다.

## 참고
- 파일명에는 연월을 포함하지 않고 매 실행 시 덮어씁니다.
- ICS를 캘린더 앱에서 구독/가져오기 하면 공모주/스팩 일정을 확인할 수 있습니다.
