# tools/autopsy — Autopsy MCP 하네스

디스크 이미지(`.vmdk`/`.e01`/`.dd`/`.raw`/`.vhdx`)는 Autopsy에 올려 **MCP로 질의**하는 것을 1차 경로로 한다.
Autopsy(The Sleuth Kit 백엔드)는 파티션·파일시스템·삭제파일·슬랙·레지스트리·웹기록·Prefetch·SRUM을 색인하고,
설치본에 포함된 `autopsy-mcp-stdio` MCP 서버가 **열려 있는 케이스**를 읽기전용으로 질의하게 해준다.
운용 절차와 판단 기준은 [ctf-forensics/autopsy-mcp.md](../../.claude/skills/ctf-forensics/autopsy-mcp.md)에 있다.

```
tools/autopsy/
├─ autopsy-mcp.sh    연결/케이스 상태 프로브 — Claude 밖(Git Bash)에서 MCP 서버에 JSON-RPC 핸드셰이크
└─ README.md
```

## 셋업 (한 번)
```bash
# 1) MCP 서버 등록 (user scope). 버전 경로는 설치본에 맞게.
claude mcp add --scope user autopsy -- "C:/Program Files/Autopsy-4.23.1/bin/autopsy-mcp-stdio.exe"
#    등록 후 /mcp 재연결 또는 세션 재시작 → mcp__autopsy__* 툴 로드
```

## 연결 확인 (Claude 밖에서도)
```bash
bash tools/autopsy/autopsy-mcp.sh status         # {caseOpen:true, caseName:...}
bash tools/autopsy/autopsy-mcp.sh summary        # 데이터소스/파일/아티팩트 수 (artifacts 0 = 인제스트 미완)
bash tools/autopsy/autopsy-mcp.sh datasources    # 이미지 objectId·timezone·획득해시
bash tools/autopsy/autopsy-mcp.sh tools          # 제공 툴 목록
bash tools/autopsy/autopsy-mcp.sh call query_files '{"nameContains":"s.pyw"}'
# 바이너리 경로 오버라이드: CTF_AUTOPSY_MCP=/c/Program\ Files/Autopsy-<ver>/bin/autopsy-mcp-stdio.exe
```

## 사람이 하는 일 (MCP는 읽기 전용)
Autopsy GUI에서: **New Case → Add Data Source → Disk Image → 이미지 선택 → Ingest Modules 선택 → 완료 대기.**
- 실행이력/웹기록/SRUM/키워드/해시가 필요하면 Ingest에 **Recent Activity · Keyword Search · (Hash Lookup)** 를 포함한다.
- 인제스트 진행률은 GUI 우측 하단 상태바(모듈명+진행바), 완료 시 우상단 알림. 끝나면 `summary`의 `totalArtifacts`가 증가한다.
- 플래그 제출·태깅·인제스트 재실행은 사람이 GUI에서. MCP로는 조회만 한다.

## 왜 호스트에서 쓰나
MCP는 Autopsy가 이미 파싱해 둔 케이스 DB를 조회할 뿐, 챌린지 바이너리를 실행하지 않는다(읽기 전용).
디스크 이미지에서 꺼낸 실행파일을 *실행*해야 하면 `untrusted/` 규칙에 따라 ubuntu-ctf에서만 다룬다.
