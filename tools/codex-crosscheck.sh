#!/usr/bin/env bash
# Codex(다른 계보의 두 번째 모델)로부터 독립적인 의견 / 코드 리뷰를 받는다.
# Codex는 이미 로그인되어 있다(ChatGPT). MCP 서버는 필요 없다.
#
#   tools/codex-crosscheck.sh "<질문>"          # 독립 의견, 읽기 전용
#   tools/codex-crosscheck.sh --review          # 커밋되지 않은 변경 리뷰
#   tools/codex-crosscheck.sh --review "<초점>" # 초점 지시와 함께 리뷰
#
# CLAUDE.md에 따라 사용: 15분 규칙을 넘겨 막혔을 때 현재 가설과 그것을
# 반증하는 증거를 함께 Codex에게 넘긴다. 두 의견이 갈리면, 계속하기 전에
# 그 차이를 먼저 조사한다.
set -euo pipefail
[ $# -ge 1 ] || { echo "사용법: bash $0 \"<질문>\"  |  bash $0 --review [초점]" >&2; exit 2; }
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT"
if command -v codex >/dev/null 2>&1; then
  CODEX="$(command -v codex)"
elif command -v codex.exe >/dev/null 2>&1; then
  CODEX="$(command -v codex.exe)"
else
  echo "Codex CLI not found. Install it and run codex login in this environment." >&2
  exit 127
fi
CODEX_ROOT="$ROOT"
# Windows Codex launched through WSL expects a Windows --cd path.
if [[ "$CODEX" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
  CODEX_ROOT="$(wslpath -w "$ROOT")"
fi
if [ "${1:-}" = "--review" ]; then
  shift
  if [ "$#" -eq 0 ]; then
    exec "$CODEX" exec --sandbox read-only --cd "$CODEX_ROOT" review --uncommitted
  fi
  # Codex rejects --uncommitted together with a positional review prompt.
  # A focused review therefore uses an explicit, read-only exec task.
  exec "$CODEX" exec --sandbox read-only --cd "$CODEX_ROOT" -- \
    "Review all staged, unstaged, and untracked changes in this repository for correctness bugs and risky assumptions. Do not modify files. Review focus: $*"
fi
exec "$CODEX" exec --sandbox read-only --cd "$CODEX_ROOT" -- "$*"
