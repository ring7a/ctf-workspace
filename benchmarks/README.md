# CTF 하네스 비교 실험

이 디렉터리는 실제 Claude/Codex CLI로 동일한 로컬 합성 입력을 푸는 세 가지 작업 흐름을 비교하는 러너와 채점 기준을 담는다. 외부 대상 접근, 인터넷 탐색, 스코어보드 접근, 플래그 자동 제출은 하지 않는다. 결과는 수동 검토가 끝날 때까지 로컬에 보관하며 계획값과 관측값을 구별해 보고한다.

현재 사전 등록은 **protocol v6 / suite v3**다. 과거 protocol v4 진단 파일럿은 Codex read-only sandbox가 `ubuntu-ctf` WSL 접근을 차단해 계획한 흐름을 수행하지 못했으므로 성공률·시간·토큰 비교에서 제외한다.

## 본 실험 완료 — 2026-10-12

48/48 시행과 독립 재실행·증적·준수 대조를 마쳤다. [최종 보고서](../docs/BENCHMARK-RESULTS-2026-10-12.md)와 [안전 집계 JSON](results-summary.json)을 함께 읽는다.

| 조건 | 주요 성공 / 16 | 원/새 입력 스크립트 재현 | 전체 풀이 시간 중앙값 | 증적 평균 / 8 | 시작된 CLI 단계 |
|---|---:|---:|---:|---:|---:|
| Claude 단독 | 15 (93.75%) | 16 · 16 | 29.289초 | 6.8125 | 16 |
| Codex 단독 | 14 (87.50%) | 14 · 14 | 92.508초 | 6.9375 | 16 |
| 프로젝트 하네스 | 11 (68.75%) | 16 · 16 | 103.555초 | 7.2500 | 43 |

하네스 검토 60초 상한 초과 5회는 최종화를 생략했다. Codex 단독 2회는 도구 실행 전 제공자 차단으로 스크립트가 없었다. 이번 설정에서는 Claude 대비 스크립트 정확도 향상을 확인하지 못했다. 증적 평균은 모든 시작 시도 기준이며 Codex 제공자 오류 2회도 무증적 0점으로 포함한다. 시간은 `elapsed_seconds`로 종료 정리 제외·240초 상한이다. 토큰 누락·paired 비교·유효 부분집합·작은 합성 표본의 한계는 보고서에 보존한다. 파일럿·보정은 아래의 제외 이력이며 본 실험에 합치지 않았다.

## 유효한 easy 파일럿과 제외 결정

`v7`은 실행 root의 이력 라벨이며 protocol 버전이 아니다. easy v7 LCG 파일럿의 실제 고정 설정은 **protocol v5 / suite v1**이며 당시 독립 재현·준수·증적 검토를 통과한 유효 실행이다. 세 조건이 모두 성공한 **천장 효과 진단**이므로 본 실험 효과 추정에서는 제외한다. protocol v6/suite v3의 강화된 무결성 요구를 소급 적용해 통과했다고 주장하지 않는다.

| 조건 | protocol-valid 성공률 | 증적 점수(8점 만점) | 경과 시간 | 시작된 모델 단계 |
|---|---:|---:|---:|---:|
| Claude 단독 | 100% | 6 | 23.516초 | 1 |
| Codex 단독 | 100% | 8 | 60.062초 | 1 |
| 프로젝트 하네스 | 100% | 8 | 90.828초 | 3 |

하네스의 성공률 차이는 Claude 단독과 Codex 단독에 대해 모두 **0%p**였다. 하네스 경과 시간은 Claude 단독보다 **67.312초**, Codex 단독보다 **30.766초** 길었다. 이 파일럿은 러너와 채점 경로가 작동한다는 증거와 쉬운 과제의 천장 효과만 보여 주며 아래 hard-family 본 실험의 결과에 합치지 않는다.

## 사전 등록 설계

비교 대상은 다음 **세 가지 전체 작업 흐름**이다. 조건별 새 세션, 동일한 paired 입력, 시도당 총 240초의 공통 시간 예산을 사용한다. 제공자별 실행 정책은 protocol v6에 고정하고 순서는 고정 schedule seed로 회전해 순서 효과를 줄인다.

| 조건 | 작업 흐름 | 시도당 시간 예산 |
|---|---|---|
| Claude 단독 | 프로젝트 자산 없이 표준 문제·안전 지시만 받은 Claude가 풀이 | 총 240초 |
| Codex 단독 | 프로젝트 자산 없이 표준 문제·안전 지시만 받은 Codex가 풀이 | 총 240초 |
| 프로젝트 하네스 | 규칙·스킬·증적 템플릿을 적용해 Claude 풀이 → Codex 검토 → Claude 수정 | 총 240초, 단계별 상한 120/60/60초 |

본 실험은 suite v3의 네 hard family를 사용한다.

| family | hard variant |
|---|---|
| `lcg_stream` | 공개되지 않은 31-bit prime modulus와 상태 18개 중 2개 오류를 함께 복원한 뒤 stream을 복호화한다. |
| `shared_rsa` | 단일 modulus에서 알려진 offset을 더한 관련 메시지 4개의 `e=3` ciphertext 중 1개 오류를 배제해 메시지를 복원한다. |
| `byte_machine` | 여섯 가역 opcode의 출력에서 하위 6bit만 관측하며, 입력 의존 상태와 최종 상태 제약을 함께 풀어 유일한 flag 경로를 찾는다. |
| `fragment_log` | zlib 전송의 누락 fragment 2개를 GF(256) 이중 parity로 복원하고 bad CRC/retransmission과 decoy를 구별한다. |

각 family에 master seed로 결정되는 paired instance 4개를 만들어 **4 families × 4 instances = 16개 입력**을 세 조건 모두에 공급한다. 따라서 본 실험은 **48개 최종 trial**이다. 모든 단계가 실제로 시작될 때 Claude 단독 16회 + Codex 단독 16회 + 하네스 16×3회로 최대 **80회 모델 단계 호출**이다. 마감시간 소진으로 기록만 생기고 프로세스가 시작되지 않은 단계는 호출로 세지 않는다. 같은 family의 instance는 관련 표본이므로 16개를 독립적인 난이도·카테고리 표본으로 해석하지 않는다.

단독 조건에는 문제·범위와 공통 안전·출력 조건만 공급한다. 하네스에는 저장소 규칙·스킬·증적 템플릿과 참조 의존성의 스냅샷을 공급한다. 모든 조건에 solve script와 writeup을 요청한다. 지정된 하네스 단계 외 추가 에이전트·모델 호출과 설치는 허용하지 않는다. 하네스는 같은 trial의 최초 풀이와 증적을 Codex review에 전달하고 그 검토를 Claude 수정 단계에 전달한다. 최종 수정 산출물을 채점하며 최초 풀이와 검토 결과도 보존한다.

이 비교는 **프로젝트 작업 흐름 전체가 단독 모델보다 얼마나 나아지는지**를 측정한다. 규칙·스킬·증적 요구와 두 번째 모델 검토가 함께 바뀌므로, 프롬프트만의 효과나 검토 모델만의 인과적 기여를 분리해 주장하지 않는다.

실험 작업 디렉터리를 이 저장소의 하위에 만들면 단독 조건도 AGENTS.md/CLAUDE.md를 상속하므로 비교가 오염된다. 실행 디렉터리는 별도의 임시 루트 아래에 만들며 각 모델의 실제 시스템·도구 환경과 외부 전역 설정의 한계를 기록한다. 데이터 분석과 solve script 실행은 `ubuntu-ctf`에서, 작업물은 `challenge/work`, 입력은 `challenge/untrusted` 아래에서 처리한다.

## 보정 실행과 동결 규칙

본 실험 전에 네 family의 instance를 하나씩 쓰는 **4 families × 1 instance = 4개 입력, 12개 최종 trial, 최대 20회 모델 단계 호출** 보정을 별도 root에서 수행한다. suite v2 보정 r1은 12/12가 same/unseen 재현까지 성공한 천장 run이었다. 사전등록한 한 번의 구조 조정으로 suite v3를 만들고, 새 seed와 root의 보정 r2를 확인한 뒤 결과와 무관하게 동결한다. 두 보정 결과는 본 실험의 성공률·시간·토큰·증적 통계에서 제외한다.

어떤 family에서 세 조건이 모두 성공하거나 모두 실패하면 그 family의 난이도를 **최대 한 번만** 조정할 수 있다. 반복적으로 모델 결과에 맞추지 않으며 조정 후 generator와 protocol을 동결한 다음 새 root에서 4-instance 본 실험을 시작한다. 본 실험을 시작한 뒤에는 family, 생성 규칙, 모델, 예산, 순서, workers를 바꾸지 않는다.

## protocol v6 commitment와 재현 채점

러너는 32-byte private master seed를 생성하지만 trial workspace, prompt, 로그, protocol에 복사하거나 출력하지 않는다. protocol의 seed 식별값은 `master_seed_sha256`이며, 각 unseen instance에는 입력 파일 hash map과 그 canonical digest, flag SHA-256 commitment만 남는다. 실제 unseen 입력이나 평문 flag는 남기지 않는다. 전체 protocol에는 seed에서 전용 domain key로 계산한 `protocol_hmac_sha256` 인증 태그를 붙이되 seed 자체나 파생 key는 저장하지 않는다.

준비 단계는 unseen commitment를 임시 생성한 뒤 입력을 제거한다. 따라서 모델 단계가 실행되는 동안 unseen 입력은 존재하지 않는다. 각 arm의 모델 실행이 끝난 뒤 trusted verifier가 같은 seed와 instance ID로 **세 arm에 동일한 unseen 입력**을 WSL 임시 경로에 다시 생성하고 solve script를 원 입력과 unseen 입력에 각각 실행한다. 재생성한 입력 digest와 flag hash가 protocol commitment와 정확히 일치해야 한다. 재개 시 private seed, unseen commitment, suite·하네스·벤치마크 코드 또는 고정 실행 정책이 달라지면 기존 root를 이어서 실행하지 않는다.

verifier는 solve script의 원문 stdout/stderr를 결과나 영구 로그에 남기지 않는다. `same_execution`과 `new_execution`에는 return code, 출력 byte 수와 SHA-256, 발견한 candidate flag의 SHA-256과 개수만 기록한다. 재생성 과정에서 관측한 `unseen_hashes`, `unseen_input_digest`, `new_expected_flag_sha256`를 protocol의 expected hash map·digest·flag hash와 각각 비교하며 세 값이 모두 정확히 일치해야 `unseen_commitment_match`가 성립한다.

protocol과 result의 HMAC key는 서로 다른 domain label로 분리한다. 재개 시 protocol 파일이 regular non-link인지 확인하고 HMAC을 검증한 뒤에야 그 안의 필드를 사용한다. trial archive를 만든 뒤 러너는 `archive_path`와 전체 `archive_tree_digest`를 결과에 넣고 전체 결과의 `result_hmac_sha256`을 계산한다. 기존 결과는 HMAC, 정확한 trial spec, archive 경로와 tree digest를 확인한 뒤에만 재사용한다. `benchmark_code_hashes`도 고정 artifact에 포함해 각 trial 전후에 검사하므로 모델·verifier 실행 중 `benchmarks/*.py`가 바뀌면 critical integrity error로 중단한다. 집계기도 private seed hash, protocol HMAC과 재생성 commitment를 다시 확인하고 protocol·result·archive가 regular non-link인지 검사하며, result HMAC이나 archive tree digest가 맞지 않으면 전체 집계를 거부한다.

주요 성공인 **protocol-valid success**는 다음 조건을 모두 만족해야 한다.

1. 최종 출력의 flag가 원 instance 정답과 정확히 일치한다.
2. verifier 상태가 `ran`이다.
3. solve script가 같은 instance에서 재현된다.
4. solve script가 새 unseen instance에서도 재현된다.
5. 재생성된 unseen 입력 digest와 flag hash가 해당 instance commitment와 정확히 일치한다.
6. 원본 보존과 수동 준수 검토가 모두 `valid`다.

## 측정과 해석

- **시간:** trial 전체와 각 단계의 벽시계 시간을 기록한다. 하네스는 전체 240초와 풀이/검토/수정의 120/60/60초 상한을 함께 적용한다. timeout 종료 처리 시간은 별도로 보존한다. 전체 결과와 primary 성공 결과의 시간을 구별하며 성공 건의 대표값은 `primary_success_median_seconds`로 보고한다. paired 비교는 전체 결과와 양쪽 모두 primary 성공한 결과를 따로 제시한다. 채점 시간은 풀이 시간에 포함하지 않는다.
- **사용량:** 시작된 각 모델 단계의 input/output/cache token과 원시 usage를 보존한다. 누락은 0으로 대체하지 않는다. Claude prompt 합계에는 cache read/write를 더하지만 Codex input에는 cached input이 이미 포함되므로 중복 합산하지 않는다. 제공자별 토큰을 같은 비용으로 간주하지 않으며 CLI 추정치를 실제 구독 청구액으로 해석하지 않는다.
- **증적:** [EVIDENCE-RUBRIC.md](EVIDENCE-RUBRIC.md)의 hypothesis, commands, observations, writeup을 각각 0~2점으로 독립 평가하고 다른 평가자가 근거를 대조한다. 로그로 조건을 추론할 수 있어 완전한 블라인드는 아니다. 두 원점수·최종 점수·근거·일치율을 보존한다. NOTES 길이와 writeup 존재는 의미적 품질 점수가 아니다.
- **실패:** 풀이 실패와 인프라·인증·모델 한도 실패를 분리하되 원시 결과를 삭제하지 않는다. 조건별 계획 수·관측 수·누락 수를 함께 제시하고 미실행 건을 임의의 실패나 0점으로 채우지 않는다.

`mechanical_flag_correct`와 `rate_mechanical_flag_correct_all_attempts`는 최종 flag만 본 기계적 보조 지표로 남긴다. `reproducible_correct`와 그 비율은 두 재현 검사를 통과한 중간 지표다. 주요 결론에는 모든 계획 trial과 준수 검토가 끝난 뒤 `primary_success_count`와 `primary_success_rate_all_attempts`를 사용한다. timeout·인프라 오류·운영 위반·미해결 준수 상태는 성공 분자에 들어가지 않는다. `valid`/`violation`/`unreviewed`/`unresolved` 수를 함께 공개하고 `primary_success_rate_protocol_valid_only`는 선택 편향이 가능한 민감도 분석으로만 제시한다. paired 결과의 discordance·성공률 차이·양쪽 성공 시간은 `primary_success_*`로 보고한다. 사전 commitment가 같은 쌍 수(`pairs_with_matching_planned_unseen_commitment`)와 실제 verifier digest까지 관측되어 같은 쌍 수(`pairs_with_matching_observed_unseen_digest`)도 분리한다.

평가자는 실험 후 `reviews/evidence.json`을 작성한다. 집계기는 이 파일을 읽어 평가 완료 수·평균 점수·평가자 간 일치율을 계산한다. 자동 집계가 증적을 읽고 채점해 주는 것은 아니다. 파일 형식과 준수 항목은 rubric을 따른다.

이 실험은 네 종류의 로컬 합성 교육 과제로 작업 흐름 전체의 효과를 보는 소표본이다. 공개 대회 분포, 어려운 pwn/원격 web, OSINT·malware·AI/ML, 장시간 탐색, 15분 전환 규칙을 대표하지 않는다. 규칙·스킬·증적 요구와 두 번째 모델 검토가 함께 바뀌므로 프롬프트만의 효과나 Codex review만의 인과적 기여를 분리하지 않는다. Wilson 구간은 관련된 소표본을 요약하는 설명용 수치다. 성공률, 시간, 토큰, 추가 호출, 증적을 함께 보고하며 하네스 이점이 없거나 음수인 결과도 그대로 남긴다.

승인 범위는 자체 생성한 로컬 입력과 지정한 세 조건이다. 사용자 확인 근거, `BENCH{32 lowercase hex digits}` 형식, trial 수·예산과 결과 비공개 상태를 이벤트 NOTES와 로컬 인테이크에 기록한다. 결과 공개는 검토 후 별도로 결정하며 raw 실행 자료와 private seed를 학생 Git 저장소에 넣지 않는다.

## 실행 방법

어댑터는 Windows의 로그인된 Claude/Codex CLI를 실행하고 문제 분석과 풀이 재실행은 `ubuntu-ctf`에서 수행한다. CLI 버전, 요청 모델, prompt, stdout/stderr, 입력·하네스·벤치마크 코드 SHA-256과 종료 상태를 보존한다. 최신 사용자 확인을 `intake.local.json`의 `user_confirmation`과 이벤트 NOTES에 기록한다. 이미 승인된 로컬 실행을 다시 승인 대기로 표시하지 않으며 실행 승인을 공개 승인으로 간주하지 않는다.

실행 root는 이 저장소 밖에 두어 단독 조건이 AGENTS.md/CLAUDE.md를 상속하지 않게 한다. 아래 명령은 모두 `workers=1`을 고정하며 보정과 본 실험은 서로 다른 새 root를 사용한다.

```powershell
# 제외 대상 calibration: 4 families × 1 deterministic instance
python -I benchmarks/run_benchmark.py --root E:\ctf-bench-v6-hard-calibration-20261012 --intake benchmarks/intake.local.json --workers 1 --repeats 1 --tasks lcg_stream shared_rsa byte_machine fragment_log --prepare-only
python -I benchmarks/run_benchmark.py --root E:\ctf-bench-v6-hard-calibration-20261012 --intake benchmarks/intake.local.json --workers 1 --repeats 1 --tasks lcg_stream shared_rsa byte_machine fragment_log

# 동결 후 main: 4 families × 4 deterministic paired instances
python -I benchmarks/run_benchmark.py --root E:\ctf-bench-v6-hard-main-20261012 --intake benchmarks/intake.local.json --workers 1 --repeats 4 --tasks lcg_stream shared_rsa byte_machine fragment_log --prepare-only
python -I benchmarks/run_benchmark.py --root E:\ctf-bench-v6-hard-main-20261012 --intake benchmarks/intake.local.json --workers 1 --repeats 4 --tasks lcg_stream shared_rsa byte_machine fragment_log

# 모든 수동 증적 검토를 reviews/evidence.json에 저장한 뒤 main을 집계한다.
python -I benchmarks/summarize.py E:\ctf-bench-v6-hard-main-20261012 --output benchmarks/results-summary.json
```

`--prepare-only`도 main suite와 private seed를 만들므로 승인된 범위와 root를 먼저 확인한다. 완료된 결과는 재실행하지 않는다. runner는 OS 파일 잠금으로 중복 실행을 막고 partial trial을 자동 재시작하지 않는다. 종료되지 않은 PID는 `logs/<trial>/process.json`과 시작 시각·로그로 확인한 뒤 해당 시도를 실패로 보존하거나 새 protocol root에서 다시 실행한다. 관측 도구의 timeout만으로 프로세스가 종료됐다고 판단하지 않는다.

## 현재 검증 상태

protocol v6 / suite v3 기준으로 Windows runner mock **134개**, summary **55개**, suite v3 생성기 **10개**, WSL verifier **7개**, WSL common benchmark **8개**, 총 **214개 검사**가 통과했다. 별도 24개 seed의 192개 hard instance도 생성·참조 복원을 통과했다. 여기에는 fallback 결과도 archive·result HMAC을 거쳐 집계기가 다시 검증하는 round-trip 회귀가 포함된다. 이는 모의 프로세스·이벤트·결과 fixture, 결정적 생성기, verifier와 bwrap의 무해한 스크립트 검사이며 실제 모델 성공 건수가 아니다.

## 격리와 공정성의 정확한 범위

- 정답 키에는 임의 128bit flag의 SHA-256만 기록한다. 정규식 일치와 별개로 해시를 정확 대조한다.
- 새 재현 입력은 제출 모델이 종료된 뒤 WSL 임시 경로에서 생성한다. 동일 제출 스크립트를 별도 work에 복사해 원 입력과 새 입력을 각각 실행하며, 성공 종료 코드와 정답 일치를 모두 요구한다.
- 재실행은 bwrap로 네트워크·호스트 마운트·자격증명·다른 trial을 숨기고 시간/메모리/파일 출력 크기를 제한한다. 이것은 **채점 단계**의 격리다.
- native CLI 풀이 단계는 동일 사용자 계정에서 실행하지만 provider 권한은 같지 않다. Codex의 `danger-full-access`는 WSL 접근에 필요하며, 다른 trial·답안·외부 대상 접근 금지는 프롬프트와 사후 준수 검토로 강제한다. `--ignore-user-config`는 Codex config.toml을 제외할 뿐 모든 전역 스킬·hooks·메모리를 제거한다는 뜻이 아니다.
- 중첩 모델 호출은 `claude`·`codex` 명령명 deny shim으로 막고 단계별 stdout/stderr를 보존한다. 이 장치는 OS sandbox나 절대 경로 실행 차단이 아니므로 trace에서 다른 trial·답안 경로 접근이 보이면 해당 실험을 오염으로 표시한다.
- Codex review 직전과 직후에 **전체 trial tree hash**를 비교한다. 하나라도 바뀌면 critical integrity error로 전체 실행을 중단하고 active pointer와 workspace를 조사용으로 보존하며 terminal 결과를 만들지 않는다. 성공 시 digest-only `review_integrity`(`before_digest`, `after_digest`, `verified`, `enforcement`)를 review phase와 최종 trial result에 영속화해 직접 감사할 수 있다. review의 `read_only`는 Codex CLI sandbox가 아니라 이 불변식으로 강제한다.
- Windows 자식 프로세스 트리는 timeout/취소 시 종료한다. WSL에서 별도로 daemonize한 프로세스까지 완전히 회수하는 보장은 없다. foreground-only를 요구하고, 비정상 종료 시 WSL의 해당 trial 경로 프로세스를 별도로 확인한다. 강한 OS 격리가 필요한 확장 실험에서는 모델별 격리 런타임을 별도로 설계한다.
- 증적 품질은 별도 수동 평가를 마쳐야 결과로 보고할 수 있다. 단독 모델과 하네스 전체의 차이를 보고하며, 프롬프트와 두 번째 모델 검토의 개별 기여나 어려운 실전 과제에 대한 우위를 이 결과만으로 주장하지 않는다.
