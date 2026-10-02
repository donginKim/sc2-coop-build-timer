# SC2 협동전 빌드 오더 타이머

스타크래프트2 협동전에서 게임 시간에 맞춰 빌드 순서를 **화면 오버레이**와 **한국어 음성**으로 알려주는 Windows 트레이 앱입니다.

```
 레이너 · 레이너 경제 빌드  ⚠️추정치   [0:37]
 ▶ 0:40 [16]  사령부 (바위 위치)
   1:05 [19]  병영
   1:15 [20]  궤도 사령부 변환
```

> 이 앱은 **정보 표시만** 합니다. 키 입력이나 마우스 조작 같은 게임 자동화 기능은 없습니다.

## 주요 기능

- **게임 시간 자동 동기화**: SC2 클라이언트가 PC 안에서 여는 로컬 API(`http://localhost:6119/game`)를 0.5초마다 읽습니다. 게임 시작, 일시정지, 종료를 알아서 따라갑니다.
- **오버레이**: 화면 우측 상단에 다음 3단계를 보여줍니다. 반투명이고 클릭은 게임으로 그대로 통과합니다.
- **음성 알림**: 각 단계 3초 전에 Windows 기본 음성(SAPI)으로 읽어줍니다.
- **사령관 18명 기본 빌드 내장**: [starcraft2coop.com](https://starcraft2coop.com) 공략의 빌드 오더(인구수 기준)를 옮겼습니다. YAML 파일이라 메모장으로 고칠 수 있습니다.
- **인구수 표시와 단계 넘기기**: 각 단계에 출처의 인구수(`[14]`)를 함께 보여줍니다. 실제로 지었으면 단축키로 다음 단계로 넘깁니다.
- **수동 모드**: 로컬 API에 연결되지 않으면 단축키로 직접 타이머를 시작합니다. 게임 도중에 연결이 끊기면 마지막 시간에서 이어서 셉니다.

## 현재 상태

macOS에서 개발했고 단위 테스트 119개가 통과합니다. **Windows 실기 검증은 아직 하지 않았습니다.** 아래 항목은 확인 전까지 추정입니다. ⚠️

- 협동전에서도 로컬 API가 응답하는지, 일시정지하면 시간이 멈추는지
- 메뉴, 로딩, 게임 중, 종료 상태를 판정하는 규칙
- "창 모드(전체 화면)"에서 오버레이가 게임 위에 보이는지
- `Ctrl+Alt+F8/F9/F10` 단축키가 SC2 키 설정과 겹치지 않는지
- 내장 빌드의 시간. 순서와 인구수는 출처를 따르지만, 시간은 인구수로부터 추정했습니다. 4:00 웨이브 대비 이후 단계는 출처에 없는 일반 단계입니다. 모든 빌드가 `verified: false`이며, 오버레이에 `⚠️추정치`로 표시됩니다.

## 설치와 실행 (Windows)

1. [uv](https://docs.astral.sh/uv/)를 설치합니다.
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. 저장소를 받아 의존성을 설치합니다.
   ```powershell
   git clone https://github.com/donginKim/sc2-coop-build-timer.git
   cd sc2-coop-build-timer
   uv sync --extra win
   ```
3. SC2 설정에서 **그래픽 → 디스플레이 모드**를 **창 모드(전체 화면)**으로 바꿉니다. 전용 전체 화면에서는 오버레이가 가려집니다.
4. 앱을 실행합니다.
   ```powershell
   uv run python -m sc2coop_timer
   ```
5. 트레이 아이콘을 우클릭한 뒤 **사령관 → 빌드**를 고릅니다. 사령관은 자동으로 감지되지 않습니다.

### exe로 만들기

```powershell
.\build_exe.bat
```

`dist\sc2coop_timer.exe` 파일 하나만 있으면 실행됩니다.

## 단축키

| 키 | 동작 |
|---|---|
| `Ctrl+Alt+F8` | 오버레이 표시/숨김 |
| `Ctrl+Alt+F9` | 수동 타이머 시작/정지 |
| `Ctrl+Alt+F10` | 같은 사령관의 다음 빌드로 전환 |
| `Ctrl+Alt+F11` | 다음 단계 넘기기 (실제로 지었을 때, 트레이 메뉴에도 있음) |

게임 중에 단축키가 먹지 않으면 앱을 관리자 권한으로 실행해 보세요.

## 빌드 파일 고치기

트레이 메뉴의 **빌드 폴더 열기**를 누르면 `%APPDATA%\sc2coop_timer\builds`가 열립니다. 처음 실행할 때 내장 빌드가 이 폴더로 복사되고, 같은 이름이면 이 폴더의 파일이 우선입니다. 파일을 고친 뒤 **빌드 다시 읽기**를 누르면 반영됩니다.

```yaml
commander: raynor            # 사령관 id (아래 표 참고)
name: 레이너 기본             # 메뉴에 보일 이름
verified: false              # true로 바꾸면 ⚠️추정치 표시가 사라짐
lead_seconds: 3              # 몇 초 먼저 알릴지 (생략 시 3)
steps:
  - at: "0:40"               # 게임 시간 M:SS
    supply: 14               # 인구수 (생략 가능, 표시용)
    do: 보급고                # 오버레이에 보일 문구
    say: 보급고 올려          # 읽어줄 문구 (생략 시 do를 읽음)
  - at: "4:00"
    do: 첫 공격 웨이브 대비
    tag: wave                # wave(빨강) 또는 objective(노랑), 생략 가능
```

- 단계는 시간 순서대로 적어야 합니다.
- 파일은 **UTF-8**로 저장해야 합니다. 메모장에서 "다른 이름으로 저장"을 열어 인코딩을 UTF-8로 고르면 됩니다.
- 한 사령관에 빌드 파일을 여러 개 둘 수 있습니다. 예: `raynor_bio.yaml`, `raynor_mech.yaml`.
- 형식이 틀린 파일은 건너뛰고 트레이 알림으로 알려줍니다.

| id | 사령관 | id | 사령관 | id | 사령관 |
|---|---|---|---|---|---|
| `raynor` | 레이너 | `vorazun` | 보라준 | `stukov` | 스투코프 |
| `kerrigan` | 케리건 | `karax` | 카락스 | `fenix` | 피닉스 |
| `artanis` | 아르타니스 | `abathur` | 아바투르 | `dehaka` | 데하카 |
| `swann` | 스완 | `alarak` | 알라라크 | `han_horner` | 한&호너 |
| `zagara` | 자가라 | `nova` | 노바 | `tychus` | 타이커스 |
| `zeratul` | 제라툴 | `stetmann` | 스텟먼 | `mengsk` | 멩스크 |

## 내장 빌드 출처와 라이선스

`sc2coop_timer/builds/*.yaml`의 빌드 오더는 [starcraft2coop.com](https://starcraft2coop.com)의 사령관 공략(원저자 Aommaster, [CC-BY-NC-SA-4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/))을 바탕으로 합니다. 한국어로 옮기고 게임 시간을 덧붙인 2차 저작물이므로 이 폴더의 빌드 파일은 같은 CC-BY-NC-SA-4.0을 따릅니다. 각 파일 상단에 사령관별 원문 링크가 있습니다.

일부 사령관 고유 유닛과 연구 이름(예: `Billy`, `Shadowguard`, `Primal Warden`)은 한국어 공식 명칭을 확인하지 못해 영어로 두었습니다.

## 로컬 API 실측 도구

협동전 중에 로컬 API 응답을 1초마다 `probe.jsonl`에 기록합니다. 상태 판정 규칙을 확정하는 데 씁니다.

```powershell
uv run python -m sc2coop_timer.probe
```

권장 순서는 협동전 시작, 1분 플레이, 일시정지 10초, 게임 종료, 메뉴 복귀, `Ctrl+C`입니다.

## 파일 위치

| 항목 | 경로 |
|---|---|
| 사용자 빌드 | `%APPDATA%\sc2coop_timer\builds\` |
| 설정 (오버레이 위치·투명도 등) | `%APPDATA%\sc2coop_timer\config.yaml` |
| 로그 | `%APPDATA%\sc2coop_timer\log.txt` |

오버레이는 클릭이 통과하기 때문에 드래그로 옮길 수 없습니다. 위치는 `config.yaml`의 `x`, `y`를, 투명도는 `opacity`(0.2–1.0)를 고쳐서 바꿉니다.

## 개발

```bash
uv sync
uv run pytest -q                                   # 단위 테스트
uv run python -m sc2coop_timer --demo 10           # SC2 없이 가짜 시계 10배속으로 오버레이 확인
```

macOS와 Linux에서는 음성 대신 콘솔에 `[TTS] ...`를 출력하고, 전역 단축키는 꺼집니다.

```
sc2coop_timer/
  clock.py          로컬 API 폴링, 게임 상태 판정, 수동 모드
  scheduler.py      게임 시간 → 알릴 단계·표시할 단계 계산 (순수 함수)
  session.py        시계 값 → 화면·음성 출력
  builds.py         빌드 YAML 로드·검증
  overlay_model.py  오버레이 내용 계산
  overlay.py        PySide6 오버레이 창
  tts.py            음성 큐 (SAPI / 콘솔)
  app.py, main.py   트레이 메뉴, 단축키, 진입점
  probe.py          로컬 API 실측 도구 (표준 라이브러리만 사용)
  builds/*.yaml     내장 빌드 18개
docs/
  windows-setup.md  Windows 실측 체크리스트
  superpowers/      설계 문서, 구현 계획
```
