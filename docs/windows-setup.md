# Windows 설정·실측 가이드

## 1. 준비

1. uv 설치 (PowerShell):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. 이 저장소 폴더를 Windows PC로 복사 (USB·클라우드 드라이브 등).
3. 폴더에서:
   ```powershell
   uv sync --extra win
   ```

## 2. API 실측 (먼저 할 것)

SC2 실행 → 협동전 시작 직전에:

```powershell
uv run python -m sc2coop_timer.probe
```

1분 플레이 → Esc로 일시정지 10초 → 게임 종료(승리/항복) → 메뉴 복귀 → Ctrl+C.
생성된 `probe.jsonl`을 개발 쪽에 전달하면 상태 판정 규칙을 실측값으로 확정한다.

## 3. 실행

```powershell
uv run python -m sc2coop_timer
```

- SC2 설정 → 그래픽 → 디스플레이 모드: **창 모드(전체 화면)**
- 트레이 아이콘 우클릭 → 사령관 → 빌드 선택
- F8 오버레이 표시/숨김, F9 수동 시작/정지, F10 다음 빌드
- 빌드 수정: 트레이 → 빌드 폴더 열기 → YAML 편집(UTF-8 저장) → 빌드 다시 읽기

## 4. exe 빌드

```powershell
.\build_exe.bat
```

결과: `dist\sc2coop_timer.exe`. 이 파일 하나만 있으면 실행된다.

## 5. 실측 체크리스트

- [ ] 협동전 중 `probe` 출력에 `displayTime`이 증가한다
- [ ] 일시정지 동안 `displayTime`이 멈춘다
- [ ] 창 모드(전체 화면)에서 오버레이가 게임 위에 보이고, 클릭이 게임으로 통과한다
- [ ] 한국어 음성으로 단계가 읽힌다 (없으면 설정 → 시간 및 언어 → 음성에서 한국어 음성 추가)
- [ ] 게임 중 F8/F9/F10이 동작한다 (안 되면 앱을 관리자 권한으로 실행해 볼 것)
- [ ] exe 실행 시 내장 빌드 18개가 트레이 메뉴에 보인다
