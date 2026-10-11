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
if [ "${1:-}" = "--review" ]; then
  shift
  exec codex review --uncommitted "${1:-이 변경들에서 정확성 버그와 위험한 가정을 리뷰해줘.}"
fi
[ $# -ge 1 ] || { echo "사용법: $0 \"<질문>\"  |  $0 --review [초점]" >&2; exit 2; }
exec codex exec --sandbox read-only "$*"
