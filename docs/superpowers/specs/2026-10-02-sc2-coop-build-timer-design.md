# SC2 협동전 빌드 오더 타이머 — 설계

- 작성일: 2026-10-02
- 상태: 설계 승인됨, 구현 계획 전

## 1. 목적

스타크래프트2 협동전 플레이 중 손이 바쁠 때도 "다음에 뭘 지을지"를 놓치지 않도록, 게임 시간에 맞춰 빌드 단계를 화면 오버레이와 음성으로 알려준다.

이 툴은 **정보 표시만** 한다. 게임 입력·자동 조작은 하지 않는다 (Blizzard 약관 준수).

### 성공 기준

- 게임 시작·일시정지·종료를 사용자 조작 없이 따라간다 (자동 모드).
- 각 빌드 단계를 지정 시각 `lead_seconds` 전에 음성으로 알리고, 오버레이에 다음 3단계를 표시한다.
- 빌드 내용은 YAML 파일 수정만으로 바꿀 수 있다 (exe 재빌드 불필요).

## 2. 환경과 제약

| 항목 | 내용 |
|---|---|
| 실행 환경 | Windows PC (게임과 같은 PC) |
| 개발 환경 | macOS. 단위 테스트는 Mac에서, 실측은 Windows에서 |
| 언어/라이브러리 | Python 3.11+, PySide6, PyYAML, requests, pywin32(SAPI) 또는 pyttsx3 |
| 배포 | PyInstaller 단일 exe |
| 게임 설정 | SC2 디스플레이 모드 "창 모드(전체 화면)" 필수 — 전용 전체화면에서는 오버레이가 가려짐 |

### 미검증 가정 (⚠️, Windows 실측으로 확인)

1. SC2 클라이언트 로컬 API `http://localhost:6119/game` 이 협동전에서도 응답한다.
2. 게임 일시정지 시 `displayTime` 이 멈춘다.
3. PySide6 항상 위·클릭 통과 창이 "창 모드(전체 화면)" SC2 위에 보인다.
4. 이 API로는 선택한 사령관을 알 수 없다 → 사령관은 사용자가 직접 고른다.

가정 1이 거짓이면 수동 모드(F9)가 기본 동작이 된다.

## 3. 구조

```
sc2coop_timer/
  clock.py      6119 API 폴링 → 상태 + 게임 시간
  builds.py     YAML 로드·검증 → Build / Step
  scheduler.py  (게임 시간, steps, 알린 집합) → (새 알림, 표시 목록). 순수 함수
  tts.py        음성 출력. Windows SAPI, 그 외 OS는 콘솔 출력 대체
  overlay.py    PySide6 반투명 오버레이
  app.py        트레이 메뉴, 전역 단축키, 메인 루프 조립
builds/*.yaml   사령관별 내장 빌드 (18개)
tests/          pytest 단위 테스트
```

### 데이터 흐름

```
6119 API ─(1초 폴링)→ clock ─(state, game_seconds)→ scheduler ─→ overlay (다음 3단계)
                                                         └─→ tts (lead_seconds 전 알림)
트레이에서 빌드 선택 → builds → scheduler에 steps 주입
```

### 게임 시계 상태

| 상태 | 판정 | 동작 |
|---|---|---|
| `MENU` | API 응답에 게임 없음 / 플레이어 목록 비어 있음 | 오버레이 숨김, 알린 집합 리셋 |
| `LOADING` | 게임 있음, `displayTime == 0` | 대기 |
| `IN_GAME` | `displayTime > 0`, 결과 미정 | 알림 동작 |
| `ENDED` | 플레이어 result 확정 | 다음 MENU에서 리셋 |

정확한 판정 필드는 실측 응답을 보고 확정한다 (⚠️).

### 수동 모드 (fallback)

- API 3회 연속 연결 실패 시 수동 모드로 전환. 오버레이에 "수동 모드" 표시.
- F9로 시작/정지. 시간은 PC monotonic 시계 기준. 일시정지는 반영 안 됨.
- API 연결이 복구되면 다음 게임부터 자동 모드로 복귀.

### scheduler 계약

```python
def tick(game_seconds: float, steps: list[Step], announced: set[int], lead: float, show: int = 3)
    -> tuple[list[int], list[int]]   # (새로 알릴 step index, 표시할 step index)
```

- step `i`는 `steps[i].at - lead <= game_seconds` 이고 `i not in announced` 일 때 알린다.
- 게임 시간이 역행하면(리플레이 되감기 등) `announced` 에서 `at - lead > game_seconds` 인 항목을 제거한다.
- 한 tick에 여러 step이 걸리면 전부 반환한다 (음성은 순서대로 큐잉).
- 표시 목록: 아직 `at` 이 지나지 않은 step 중 앞에서 `show`개. 지난 step은 2초간 유지 후 제거.

## 4. 빌드 YAML 형식

```yaml
commander: raynor
name: 레이너 기본 (해병 메딕 위주)
verified: false          # 내장 빌드는 전부 false → 오버레이에 ⚠️추정치 표시
lead_seconds: 3          # 선택, 기본 3
steps:
  - at: "0:40"
    do: 보급고
    say: 보급고 올려      # 선택, 없으면 do를 읽음
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave            # 선택: wave | objective → 다른 색
```

검증 규칙:

- 필수: `commander`, `name`, `steps` (1개 이상), 각 step의 `at`, `do`.
- `at` 형식: `M:SS` 또는 `MM:SS`, 초는 00–59.
- steps는 `at` 오름차순이어야 함 (아니면 오류).
- `tag` 는 `wave` / `objective` 외 값이면 오류.

빌드 탐색 순서: `%APPDATA%/sc2coop_timer/builds/*.yaml` → 내장 `builds/*.yaml`. 같은 파일명이면 사용자 폴더 우선. 첫 실행 시 내장 빌드를 사용자 폴더로 복사해 수정 출발점으로 제공.

내장 빌드 18개(레이너, 케리건, 아르타니스, 스완, 자가라, 보라준, 카락스, 아바투르, 알라라크, 노바, 스투코프, 피닉스, 데하카, 한&호너, 타이커스, 제라툴, 스텟먼, 멩스크)는 일반적인 운영 흐름 기반 **추정치**이며 `verified: false` 로 둔다.

## 5. 오버레이

```
 레이너 기본  ⚠️추정치        [12:34]
 ▶ 4:00  첫 공격 웨이브 대비
   4:30  군수공장
   5:10  병영 2개 추가
```

- 기본 위치: 주 모니터 우측 상단, 폭 약 280px. 위치·투명도는 `%APPDATA%/sc2coop_timer/config.yaml` 에 저장.
- 프레임 없음, 항상 위, 클릭 통과, 배경 반투명.
- `at - lead` 이내 step은 강조색. `tag: wave` 빨강 계열, `objective` 노랑 계열.
- 상태가 `MENU` 면 숨김 (F8로 강제 표시 가능).

### 전역 단축키

| 키 | 동작 |
|---|---|
| F8 | 오버레이 표시/숨김 |
| F9 | 수동 모드 시작/정지 |
| F10 | 현재 사령관의 다음 빌드로 순환 |

트레이 메뉴: 사령관 > 빌드 선택, 음성 켜기/끄기, 빌드 폴더 열기, 빌드 다시 읽기, 종료.

첫 실행 시 "SC2를 창 모드(전체 화면)로 설정하세요" 안내 1회.

## 6. 에러 처리

| 상황 | 처리 |
|---|---|
| YAML 파싱/검증 실패 | 해당 파일만 제외, 트레이 알림에 `파일명:줄 사유` 표시. 앱은 계속 |
| 빌드가 하나도 없음 | 오버레이에 "빌드 없음 — 빌드 폴더 확인" 표시 |
| API 연결 실패 | 3회 연속 시 수동 모드 (3장) |
| API 응답 형식 이상 | 해당 tick 무시, 로그 기록 |
| TTS 초기화 실패 | 음성 비활성, 오버레이만 동작, 로그 기록 |

로그: `%APPDATA%/sc2coop_timer/log.txt` (회전, 최대 1MB × 3).

## 7. 테스트

단위 테스트 (pytest, Mac/Windows 공통):

- `scheduler.tick`: 정각, lead 경계, 이미 알린 step, 한 tick 다중 알림, 시간 역행, 빈 steps.
- `builds`: 정상 로드, 필수 필드 누락, `at` 형식 오류, 비정렬, 잘못된 tag, 사용자 폴더 우선순위.
- `clock`: 가짜 HTTP 응답으로 MENU→LOADING→IN_GAME→ENDED→MENU 전이, 연결 실패 3회 후 수동 전환.
- 내장 빌드 18개 전부 검증 통과.

Windows 실측 체크리스트 (사용자 수행):

1. 협동전 중 `http://localhost:6119/game` 응답 확인 (응답 JSON 저장해 판정 필드 확정).
2. 일시정지 시 `displayTime` 정지 여부.
3. 창 모드(전체 화면)에서 오버레이 표시·클릭 통과.
4. 한국어 TTS 음성 출력.

## 8. 범위 밖

리플레이 분석, 사령관 자동 감지, 돌연변이 대응, 맵별 목표 타이밍 자동 연동, 게임 입력·자동화 일체.
