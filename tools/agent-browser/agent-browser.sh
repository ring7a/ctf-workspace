#!/usr/bin/env bash
# agent-browser 하네스 헬퍼 — Claude 밖(Git Bash)에서 설치/연결/라이브 라운드트립을 확인한다.
# agent-browser(Vercel Labs)는 CDP 직결 네이티브 CLI 브라우저 자동화 도구로, 접근성 트리 스냅샷과
# @eN ref로 페이지를 토큰 효율적으로 조작한다. 브라우저는 데몬으로 상주하며 커맨드가 그 세션에 붙는다.
#
# 사용법:
#   bash tools/agent-browser/agent-browser.sh version        # 바이너리 버전(설치 확인)
#   bash tools/agent-browser/agent-browser.sh skills          # 제공 스킬 목록
#   bash tools/agent-browser/agent-browser.sh smoke [url]      # 라이브 라운드트립(open→snapshot→close) 검증
#   bash tools/agent-browser/agent-browser.sh smoke-headed [url]  # 헤드리스가 막힐 때 헤드리스=false로 검증
#   bash tools/agent-browser/agent-browser.sh session          # 새 격리 세션 id 발급(export용)
#   bash tools/agent-browser/agent-browser.sh raw <args...>     # 임의 agent-browser 커맨드 패스스루
#
# 바이너리 경로 오버라이드: CTF_AGENT_BROWSER=/path/to/agent-browser
set -u

BIN="${CTF_AGENT_BROWSER:-}"
if [ -z "$BIN" ]; then
  if command -v agent-browser >/dev/null 2>&1; then
    BIN="agent-browser"
  elif [ -x "$HOME/AppData/Roaming/npm/agent-browser" ]; then
    BIN="$HOME/AppData/Roaming/npm/agent-browser"
  else
    echo "agent-browser 바이너리를 찾지 못했습니다. 설치: npm i -g agent-browser && agent-browser install" >&2
    echo "또는 CTF_AGENT_BROWSER 환경변수로 경로를 지정하세요." >&2
    exit 127
  fi
fi

# 라이브 커맨드는 전용 세션에 격리한다(공유 default 세션 하이재킹 방지).
SMOKE_SESSION="${AGENT_BROWSER_SESSION:-ctf-smoke}"

cmd="${1:-help}"; shift || true

case "$cmd" in
  version)
    "$BIN" --version
    ;;
  skills)
    "$BIN" skills list
    ;;
  session)
    # worktree 스코프의 격리 세션 id 발급. 결과를 AGENT_BROWSER_SESSION으로 export해서 쓴다.
    "$BIN" session id --scope worktree --prefix ctf 2>/dev/null || "$BIN" session id 2>/dev/null
    ;;
  smoke|smoke-headed)
    url="${1:-https://example.com}"
    headed=""
    [ "$cmd" = "smoke-headed" ] && headed="--headed"
    export AGENT_BROWSER_SESSION="$SMOKE_SESSION"
    echo "[smoke] session=$AGENT_BROWSER_SESSION url=$url headed=${headed:-no}"
    echo "[smoke] open ..."
    "$BIN" open "$url" $headed --session "$AGENT_BROWSER_SESSION"
    echo "[smoke] snapshot -i ..."
    "$BIN" snapshot -i --session "$AGENT_BROWSER_SESSION" | head -20
    echo "[smoke] close ..."
    "$BIN" close --all
    echo "[smoke] done"
    ;;
  raw)
    "$BIN" "$@"
    ;;
  help|*)
    sed -n '2,15p' "$0"
    ;;
esac
