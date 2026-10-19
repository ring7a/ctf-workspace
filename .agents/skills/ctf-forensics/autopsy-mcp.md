# Disk Forensics — Autopsy MCP first (workspace procedure)

> 로컬 추가 문서. upstream `disk-and-memory.md`/`windows.md`의 수작업 카빙(TSK `fls`/`icat`, 레지스트리,
> Prefetch 파서)을 보완하며, 이 워크스페이스에서 **디스크 이미지(.vmdk/.e01/.dd/.raw/.vhdx)는 Autopsy에
> 올려 MCP로 질의하는 것을 1차 경로로** 한다는 운영 규칙의 실행 절차다.
> 실행 래퍼·연결 확인 헬퍼는 [tools/autopsy/](../../../tools/autopsy/README.md)에 있다.

## 0. 무엇인가 / 왜 "Autopsy MCP 먼저"인가
Autopsy(The Sleuth Kit 백엔드)는 디스크 이미지를 파싱해 파티션·파일시스템·삭제파일·슬랙·레지스트리·
웹기록·Prefetch·SRUM 등을 하나의 케이스로 색인한다. 설치본에 **`autopsy-mcp-stdio` MCP 서버**가 포함돼
있어, Autopsy GUI에 **열려 있는 케이스**를 Claude/Codex가 읽기전용으로 질의할 수 있다(파일·타임라인·
아티팩트·OS계정·파일내용). 수작업 `fls`/`icat`/하이브 파싱보다 빠르고, 질의·objectId가 그대로 보고서 근거가 된다.

| | strings/수동 TSK 카빙 | Autopsy MCP 질의 |
|---|---|---|
| 말해주는 것 | "이 바이트열이 어딘가 있다" | 파일 경로·타임스탬프(UTC)·소유자·슬랙·파싱된 아티팩트 |
| 삭제물 | 오프셋 수동 카빙 | unallocated/슬랙을 `query_files(allocated=false)`로 열람, SQLite 슬랙 문자열까지 노출 |
| 보고서 | 추정 서술 | `query_*` 질의 + objectId + crtime이 그대로 근거 |

**중요: 사람이 케이스를 연다.** MCP는 읽기 전용이며 이미지를 직접 마운트하지 않는다. 분석가(사용자)가
Autopsy GUI에서 케이스를 만들고 이미지를 데이터소스로 추가한 뒤에야 질의가 가능하다. 플래그 제출·GUI 조작은 사람 몫.

## 1. 셋업 (한 번)
1. MCP 서버 등록(세션당 1회, 이미 돼 있으면 생략):
   ```bash
   claude mcp add --scope user autopsy -- "C:/Program Files/Autopsy-4.23.1/bin/autopsy-mcp-stdio.exe"
   # 등록 후 /mcp 재연결 또는 세션 재시작 → mcp__autopsy__* 툴 로드
   ```
2. 연결·케이스 상태를 Claude 밖에서도 확인:
   ```bash
   bash tools/autopsy/autopsy-mcp.sh status      # {caseOpen:true, caseName:...} 이어야 함
   ```
3. 분석가가 GUI에서 할 일: **New Case → Add Data Source → (Disk Image) → 이미지 선택 → Ingest Modules 선택 → 완료 대기.**

## 2. 트리아지 질의 순서 (가설 1개씩, 챌린지 NOTES.md에 기록)
```
get_server_status                     # caseOpen=true 확인 (항상 먼저)
get_case_summary                      # 데이터소스 수 / totalFiles / totalArtifacts
query_data_sources                    # 분석 대상 이미지의 objectId·획득해시·timezone 확인
get_data_source_tree(dataSourceId=N)  # 파티션/파일시스템 구조, 메인 NTFS/ext fs objectId
get_os_accounts                       # 사용자/관리자/서비스 계정
summarize_timeline(start,end)         # 기간별 활동량(File System/Web/Misc) 먼저 → 그 다음 상세
```
그 다음 질문 유형별로:
- 파일/침해물: `query_files(nameContains / pathContains / extension / createdAfter / md5 / allocated=false …)`
- 내용 확인: `get_file_content(objectId[, offset, maxBytes])` — 소스코드·스크립트·태스크 XML·SQLite 문자열
- 실행 이력: `query_data_artifacts(artifactType=TSK_PROG_RUN)` (Prefetch 파싱) / 웹: `TSK_WEB_HISTORY`·`TSK_WEB_DOWNLOAD`
- 설치·USB·최근문서: `TSK_INSTALLED_PROG`·`TSK_DEVICE_ATTACHED`·`TSK_RECENT_OBJECT`
- 분석결론: `query_analysis_results(artifactType=TSK_KEYWORD_HIT / TSK_HASHSET_HIT / TSK_ENCRYPTION_SUSPECTED …)`
- 시점 중심: `query_timeline(startTime,endTime,textFilter)` — 파일시각+아티팩트를 한 번에 시간순
- 리포트: `list_reports` → `get_report_content(objectId)`

## 3. 질문 → 질의 매핑 (DFIR 전형)
| 질문 | Autopsy 경로 |
|---|---|
| 최초 침해/유입 파일 시점 | `query_files(nameContains=<임플란트>)` → crtime(=생성, UTC). 다운로드 근거는 앱 DB/웹다운로드 아티팩트 |
| 어떤 프로그램이 언제 실행됐나 | `TSK_PROG_RUN`(Recent Activity). 미생성 시 **Prefetch 파일 자체**: `query_files(nameContains="X.EXE", extension="pf")` → crtime=최초실행, mtime=최종실행 |
| 지속성(스케줄 태스크/Run키) | `query_files(pathContains="/System32/Tasks")` → `get_file_content`(UTF-16 XML: Trigger/RunLevel/Exec). Run키는 레지스트리 아티팩트 또는 SOFTWARE 하이브 |
| 권한상승/UAC LOLBin | CMSTP/CONSENT/FODHELPER/SCHTASKS 등 Prefetch 시각 + 생성된 임시 ini/파일 |
| 계정·공격자 귀속 | `get_os_accounts` + 앱 DB(SQLite) `get_file_content` 문자열(access_log/users) |
| 삭제·안티포렌식 | `query_files(allocated=false)` + SQLite 파일의 슬랙 문자열(삭제 레코드 잔존) |
| C2/네트워크 | 키워드 히트(IP/도메인), 웹기록, SRUM(NetworkUsages) 아티팩트 |

## 4. 함정 (실측)
- **데이터소스 스코프**: 한 케이스에 여러 이미지가 있으면 `query_files`가 전부 긁는다. 경로/`dataSourceId`로
  한정하라(`query_data_artifacts`/`timeline`은 `dataSourceId` 인자 있음, `query_files`는 `pathContains`로 구분).
- **타임존**: MCP 파일 타임스탬프는 **UTC("Z")로 반환**된다(데이터소스를 KST로 추가했어도). 반면 태스크 XML 등
  파일 *내용*은 시스템 로컬 시각일 수 있다 — 둘의 차로 로컬 오프셋을 교차검증하라.
- **인제스트는 모듈 하나라도 시작 실패하면 전체가 취소된다 → `totalArtifacts: 0`**. 전형적 원인:
  "Central Repository: Central repository required, but not enabled" (Central Repository 모듈이 못 뜸).
  해결 = ① Tools → Options → Central Repository → "Use a central repository"(SQLite) 체크 후 재실행, 또는
  ② Run Ingest Modules에서 Central Repository/상관분석 모듈을 체크 해제하고 재실행. 우리가 쓰는
  **Recent Activity · Keyword Search · Hash Lookup** 은 Central Repository가 필요 없다.
- **`totalArtifacts: 0` = 인제스트 미완/미선택**. Prefetch·웹기록·SRUM·키워드·해시 아티팩트가 안 나온다.
  파일시스템 메타데이터·내용은 그래도 완전하므로 "파일 시각·소스 내용"형 질문(최초접근·취약코드)은 바로 풀린다.
  실행이력·C2 키워드·SRUM 유출량이 필요하면 **Recent Activity + Keyword Search + (Hash Lookup)** 인제스트를
  완료시킨 뒤 `query_*_artifacts`로 보강한다. (Prefetch 파일시각은 인제스트 없이도 §3 기법으로 대체 가능.)
- **대용량 결과**: `query_files(limit≤500)`·`get_file_content(maxBytes≤1MB)`. 결과가 토큰 한도를 넘으면 툴이
  파일로 떨궈준다 → 셰어파일을 `python -I`로 문자열 추출(SQLite .db는 ASCII 런 스캔으로 테이블/레코드가 보인다).
- **해시 비교**: 인제스트 전엔 `md5Hash=null`. 동일성은 크기+`get_file_content` 바이트 비교, 또는 해시 인제스트 후 `md5` 필터.
- **읽기 전용**: 태깅·인제스트 재실행·이미지 추가는 분석가가 GUI에서. MCP로는 생성/수정 불가.

## 5. 증거 기록 규칙
플래그/결론마다 (질의, 핵심 인자, 반환 objectId, 타임스탬프)를 챌린지 `work/`의 NOTES/findings에 남긴다.
보고서에는 평가자가 같은 케이스에서 재현할 수 있도록 **질의 시퀀스(툴명·objectId)** 를 명시하고, 각 결론마다 Autopsy 질의·objectId를 병기한다.
