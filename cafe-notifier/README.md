# 카페 게스트 구인글 → 텔레그램 알림

네이버·다음 카페 게시판을 **1시간마다** 확인해서, 조건에 맞는
**게스트 구인글**이 올라오면 **글 제목과 URL**을 텔레그램으로 보내줍니다.

- 대상 1: 네이버 카페 게시판 (회원 전용 → 로그인 필요)
- 대상 2: 다음 카페 게시판 (회원 전용 → 로그인 필요)
- 조건: `토·일 / 게스트 / 구인` 키워드 매칭 (config.yaml에서 자유롭게 수정)
- 중복 방지: 이미 알린 글은 다시 안 보냄

> 로그인은 **최초 1회 브라우저에서 직접** 합니다(2FA 포함). 아이디/비밀번호를
> 코드나 파일에 저장하지 않고, 저장된 브라우저 세션(쿠키)만 재사용합니다.

---

## 1. 준비물

1. **텔레그램 봇 토큰** — 텔레그램에서 `@BotFather` → `/newbot` → 토큰 발급
2. **본인 chat_id** — 텔레그램에서 `@userinfobot` 에게 말 걸면 숫자로 알려줌
   - 봇이 나에게 메시지를 보내려면, 먼저 **내가 그 봇에게 아무 메시지나 한 번** 보내야 합니다.
3. 네이버 / 다음 계정 (해당 카페 가입 상태)

## 2. 설치

Python 3.10+ 필요.

```bash
cd cafe-notifier
python -m venv .venv
source .venv/bin/activate        # 윈도우: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

라즈베리파이(리눅스)에서 브라우저 실행에 필요한 시스템 패키지가 없다면:

```bash
python -m playwright install-deps chromium   # 또는 sudo 로 실행
```

## 3. 설정

chat_id 는 `config.yaml` 의 `telegram.chat_id` 에 이미 설정돼 있으므로,
**봇 토큰만** 넣으면 됩니다.

```bash
cp .env.example .env
# .env 를 열어 TELEGRAM_BOT_TOKEN 만 채우기
```

이어서 텔레그램 연결이 되는지 **한 줄로 확인**하세요:

```bash
python main.py --test
```

텔레그램으로 "연결 성공" 메시지가 오면 토큰·chat_id 설정이 정상입니다.
(메시지가 안 오면 봇 토큰이 맞는지, 그리고 텔레그램에서 **내 봇에게 먼저
아무 메시지나 한 번 보냈는지** 확인하세요.)

`config.yaml` 에서 확인 주기·키워드·대상 게시판을 조정할 수 있습니다.

## 4. 로그인 (최초 1회)

```bash
python login.py
```

브라우저 창이 뜨면 **네이버**와 **다음(Daum)** 에 각각 로그인한 뒤,
터미널로 돌아와 Enter 를 누르세요. 세션이 `user-data/` 에 저장됩니다.

> 라즈베리파이를 **화면 없이(headless)** 쓰는 경우엔, 화면이 있는 PC에서
> `login.py` 를 실행해 만들어진 `user-data/` 폴더를 라즈베리파이로 복사하면 됩니다.
> (세션은 시간이 지나면 만료될 수 있어, 알림이 끊기면 `login.py` 를 다시 실행하세요.)

## 5. 동작 확인

먼저 네트워크·로그인 없이 **매칭/필터 로직이 정상인지** 오프라인 테스트로 확인할 수 있습니다:

```bash
python tests/test_pipeline.py
```

(2단계 필터·본문 조회·요일 기반 오늘/내일·제외어·중복 방지를 가짜 데이터로 검증합니다.)

이어서 실제 사이트 대상으로, 텔레그램 전송 없이 어떤 글이 추출·매칭되는지 확인:

```bash
python main.py --once --debug --dry-run
```

- 글이 하나도 안 잡히면 → 로그인 세션이 유효한지, `config.yaml` 의
  `link_pattern` 이 실제 글 링크와 맞는지 확인하세요. `--debug` 출력에
  실제 링크 후보가 찍힙니다.
- 매칭이 너무 많거나 적으면 → `config.yaml` 의 `match` 규칙을 조정하세요.

문제 없으면 실제 전송 테스트:

```bash
python main.py --once
```

## 6. 24시간 자동 실행

### 방법 A — 내장 루프 (가장 간단)

```bash
python main.py            # config.yaml 의 interval_minutes(기본 60)마다 실행
```

터미널을 닫아도 돌게 하려면 `nohup python main.py &` 또는 `tmux`/`screen` 사용.

### 방법 B — cron (라즈베리파이 권장)

`crontab -e` 에 아래 추가 (매시 정각 실행):

```cron
0 * * * * cd /home/pi/cafe-notifier && /home/pi/cafe-notifier/.venv/bin/python main.py --once >> cron.log 2>&1
```

### 방법 C — systemd 서비스 (부팅 시 자동 시작)

`/etc/systemd/system/cafe-notifier.service`:

```ini
[Unit]
Description=Cafe guest post telegram notifier
After=network-online.target

[Service]
WorkingDirectory=/home/pi/cafe-notifier
ExecStart=/home/pi/cafe-notifier/.venv/bin/python main.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now cafe-notifier
```

## 키워드 규칙 (config.yaml) — 2단계 필터

키워드를 **이름 붙은 그룹**으로 관리하고, 각 단계에서 어떤 그룹을 볼지 지정합니다.
각 그룹은 OR(단어 중 하나라도), 요구 그룹들 간에는 AND(모두)로 판정합니다.

```yaml
match:
  scan_body: true
  groups:
    guest:   ["게스트", ...]
    recruit: ["구인", "모집", ...]
    weekend: ["토", "일요일", "주말", ...]
    region:  ["인천", "경기", "김포", "서구", "부평", "부천"]
    time:    ["6시", "9시", "06", "09", "오전", ...]

  title_require: ["region", "weekend"]                       # 1단계(제목)
  body_require:  ["guest", "recruit", "weekend", "region", "time"]  # 2단계(제목+본문)
  exclude: ["마감", "완료", ...]
```

**동작:**

1. **1단계 (제목):** 제목에 `region`+`weekend` 가 있으면 → 그 글의 본문을 확인
   (지역·날짜만으로 느슨하게 걸러 불필요한 본문 조회를 줄임)
2. **2단계 (제목+본문):** 상세 페이지 본문까지 합쳐 `guest`·`recruit`·`weekend`
   ·`region`·`time` 이 모두 있으면 → 텔레그램 알림

시간·장소 같은 상세 정보는 보통 본문에 있으므로, 이렇게 하면 **제목만 볼 때
놓치던 글**을 잡아냅니다. 어떤 단계에서 무엇을 볼지는 `title_require` /
`body_require` 의 그룹 이름만 바꿔 자유롭게 조정할 수 있습니다.

- 본문 조회를 아예 끄려면 `scan_body: false` (그러면 제목만으로 `body_require` 판정).
- 사이트별 `body_selector` 로 본문 영역을 지정합니다. 비우거나 못 찾으면 페이지
  전체 텍스트를 사용하며, `--debug` 로 실제 수집된 본문 길이를 확인할 수 있습니다.
- 차단 방지를 위해 `scraping.max_body_fetches`(사이클당 상한)와 `body_delay_ms`
  (조회 간 대기)를 조정하세요. 1단계에서 걸러지므로 실제 본문 조회는 보통 소수입니다.

### '오늘' / '내일' 자동 처리 (relative_weekend)

글에 요일 대신 **'오늘'/'내일'** 만 적힌 경우를 위해, **프로그램이 실행되는 날의
요일**을 계산해 주말일 때만 주말 조건으로 인정합니다.

- `오늘` → 실행일이 **토/일** 일 때만 주말로 인정
- `내일` → 실행일이 **금/토** 일 때만(=내일이 토/일) 주말로 인정

예) 금요일에 "내일 게스트 구인" 글이 올라오면 내일=토요일이라 알림이 갑니다.
반대로 화요일의 "오늘 게스트 구인"은 평일이라 알림이 가지 않습니다.
(1시간마다 실행되므로 날짜 기준은 항상 최신입니다.)

## 파일 구조

```
cafe-notifier/
├── main.py              # 실행 진입점 (--once / 루프)
├── login.py             # 최초 1회 로그인 세션 생성
├── config.yaml          # 주기 / 키워드 / 대상 게시판
├── .env                 # 텔레그램 토큰 (직접 생성, git 제외)
├── requirements.txt
└── notifier/
    ├── config.py        # 설정 로딩
    ├── matcher.py       # 조건 매칭
    ├── store.py         # 중복 방지(seen.json)
    ├── telegram.py      # 텔레그램 전송
    ├── runner.py        # 한 사이클 오케스트레이션
    └── scrapers/base.py # Playwright 크롤링
```

## 참고 / 한계

- 카페 UI 가 바뀌면 `link_pattern` 조정이 필요할 수 있습니다(`--debug` 로 확인).
- 너무 잦은 요청은 차단될 수 있어 1시간 주기를 권장합니다.
- 로그인 세션은 만료될 수 있으니, 알림이 끊기면 `login.py` 를 다시 실행하세요.
