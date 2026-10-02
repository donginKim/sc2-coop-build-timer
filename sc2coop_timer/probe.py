"""SC2 로컬 API 응답을 1초마다 기록한다 (Windows 실측용).

표준 라이브러리만 사용한다. 설치 없이 실행:
    python sc2coop_timer/probe.py [출력파일]
협동전을 시작 → 1분 플레이 → 일시정지 10초 → 게임 종료 → 메뉴 복귀 후 Ctrl+C.
"""

import json
import sys
import time
import urllib.request

BASE = "http://localhost:6119"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path: str, timeout: float = 0.5) -> dict | None:
    try:
        with _opener.open(BASE + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def summarize(game: dict | None, ui: dict | None) -> str:
    if game is None:
        return "연결 안 됨"
    players = game.get("players") or []
    results = ",".join(f"{p.get('type', '?')}:{p.get('result', '?')}" for p in players)
    screens = len((ui or {}).get("activeScreens") or [])
    seconds = float(game.get("displayTime") or 0)
    return f"displayTime={seconds:.1f} players={len(players)} results=[{results}] screens={screens}"


def main(out: str = "probe.jsonl", interval: float = 1.0) -> None:
    print(f"{BASE} 기록 시작 → {out} (Ctrl+C로 종료)")
    with open(out, "a", encoding="utf-8") as f:
        while True:
            game, ui = get("/game"), get("/ui")
            f.write(json.dumps({"t": time.time(), "game": game, "ui": ui}, ensure_ascii=False) + "\n")
            f.flush()
            print(time.strftime("%H:%M:%S"), summarize(game, ui))
            time.sleep(interval)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "probe.jsonl")
    except KeyboardInterrupt:
        pass
