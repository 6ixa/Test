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

```bash
cp .env.example .env
# .env 를 열어 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 채우기
```

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

```bash
# 텔레그램 전송 없이, 어떤 글이 추출·매칭되는지 확인
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

## 키워드 규칙 (config.yaml)

```yaml
match:
  all_groups:        # "모든 그룹"에서 각각 최소 1개 단어가 있어야 매칭 (AND of OR)
    - ["게스트", ...]  # (1) 게스트
    - ["구인", ...]    # (2) 구인
    - ["토", "일", ...] # (3) 주말
  exclude: ["마감", "완료", ...]   # 이 단어가 있으면 제외
```

- **오전 6~9시**까지 엄격히 거르고 싶으면** `config.yaml` 의 시간대 그룹 주석을
  해제하세요. 단, 시간 정보가 제목엔 없고 본문에만 있는 글이 많아 **알림이 누락될
  수 있으니**, 처음엔 넓게 잡고 텔레그램으로 받아본 뒤 좁히는 걸 권장합니다.

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
