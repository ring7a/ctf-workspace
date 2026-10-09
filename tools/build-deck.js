const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "CTF Team";
pres.title = "CTF 준비 세팅";

// ---- palette ----
const BG = "0B1221";       // deep navy background
const PANEL = "132038";    // panel
const CARD = "182742";     // card
const CARD2 = "1E3250";    // card alt
const CY = "34D3E6";       // cyan accent (primary)
const CY_DK = "1B8FA0";    // darker cyan
const AMBER = "F5B942";    // secondary accent
const TXT = "EAF1FB";      // near-white text
const MUTED = "9DB0CC";    // muted
const LINE = "273B5C";     // hairline

const HF = "Calibri";      // header font (Korean falls back to system Hangul font)
const BFACE = "Calibri";   // body font

// master: dark background + slide number
pres.defineSlideMaster({
  title: "DARK",
  background: { color: BG },
  objects: [
    { text: { text: "2026 영남권 사이버 공격·방어 대회 · CTF 세팅", options: {
      x: 0.5, y: 7.05, w: 9, h: 0.35, fontFace: BFACE, fontSize: 9, color: MUTED, align: "left", isTextBox: true } } },
  ],
  slideNumber: { x: 12.5, y: 7.05, w: 0.6, h: 0.35, fontFace: BFACE, fontSize: 9, color: MUTED },
});

// ---- helpers ----
function title(slide, t, sub) {
  slide.addText(t, { x: 0.6, y: 0.45, w: 12.1, h: 0.7, fontFace: HF, fontSize: 30, bold: true, color: TXT, align: "left", isTextBox: true, margin: 0 });
  // small cyan square accent dot (motif), not a stripe
  slide.addShape(pres.ShapeType.rect, { x: 0.6, y: 0.42, w: 0.12, h: 0.12, fill: { color: CY } });
  if (sub) slide.addText(sub, { x: 0.6, y: 1.12, w: 12.1, h: 0.4, fontFace: BFACE, fontSize: 13, color: MUTED, align: "left", isTextBox: true, margin: 0 });
}
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || CARD }, line: { color: LINE, width: 1 } });
}
function badge(slide, x, y, label) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: 0.46, h: 0.46, fill: { color: CY } });
  slide.addText(label, { x, y, w: 0.46, h: 0.46, fontFace: HF, fontSize: 15, bold: true, color: BG, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}

// =================================================================
// Slide 1 — Title
// =================================================================
let s = pres.addSlide({ masterName: "DARK" });
s.addShape(pres.ShapeType.rect, { x: 0.6, y: 2.05, w: 0.7, h: 0.14, fill: { color: CY } });
s.addText("CTF 대회 준비 세팅 가이드", { x: 0.6, y: 2.3, w: 12, h: 1.0, fontFace: HF, fontSize: 44, bold: true, color: TXT, isTextBox: true, margin: 0 });
s.addText("Claude Code + Codex 협업 환경 구성", { x: 0.6, y: 3.35, w: 12, h: 0.6, fontFace: HF, fontSize: 24, color: CY, isTextBox: true, margin: 0 });
s.addText([
  { text: "2026 제2회 영남권 사이버 공격·방어 대회", options: { fontSize: 14, color: TXT, breakLine: true } },
  { text: "예선 2026-10-14 (온라인 CTF) · 결선 2026-11-04 (오프라인 공방전)", options: { fontSize: 12, color: MUTED } },
], { x: 0.6, y: 4.25, w: 12, h: 0.9, fontFace: BFACE, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
s.addText("재현 가능한 워크스페이스 · 작성일 2026-10-09", { x: 0.6, y: 6.2, w: 12, h: 0.4, fontFace: BFACE, fontSize: 11, italic: true, color: MUTED, isTextBox: true, margin: 0 });

// =================================================================
// Slide 2 — 세팅 한눈에 (overview, 4 pillars)
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "세팅 한눈에", "네 개의 축으로 구성했습니다");
const pillars = [
  ["모델 역할 분담", "깊은 추론은 Claude, 교차 검증은 Codex. 같은 함정에 빠지지 않게 분리."],
  ["검증된 스킬 라이브러리", "오픈소스 ctf-skills 11개 카테고리를 커밋 고정으로 벤더링."],
  ["서브에이전트 자동화", "분류·풀이·검증을 전담 에이전트 3종으로 병렬화."],
  ["재현성 & 공유", "git 버전관리 + 작업 로그 + 원클릭 setup 스크립트."],
];
let px = 0.6, pw = 5.95, ph = 2.15, gap = 0.3;
pillars.forEach((p, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = px + col * (pw + gap), y = 1.75 + row * (ph + gap);
  card(s, x, y, pw, ph, col === row ? CARD : CARD2);
  badge(s, x + 0.3, y + 0.3, String(i + 1));
  s.addText(p[0], { x: x + 0.95, y: y + 0.3, w: pw - 1.2, h: 0.5, fontFace: HF, fontSize: 18, bold: true, color: CY, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(p[1], { x: x + 0.35, y: y + 1.0, w: pw - 0.7, h: 1.0, fontFace: BFACE, fontSize: 13.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });
});

// =================================================================
// Slide 3 — 모델 역할 분담 (table)
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "모델 역할 분담", "핵심 원칙: 같은 문제를 동시에 던지지 말고, 막혔을 때 교차 검증");
const rows = [
  [{ text: "역할", opts: { bold: true } }, { text: "도구 / 모델", opts: { bold: true } }, { text: "이유", opts: { bold: true } }],
  ["메인 솔버 (rev·pwn·crypto)", "Claude Code · Fable 5.1 (high effort)", "긴 추론 체인과 가설 검증에 강함"],
  ["빠른 스크립팅·자동화", "Opus 5.5 fast mode", "파서·디코더는 속도가 관건"],
  ["탐색·문자열 수집(서브)", "Sonnet 5.5", "토큰 절약, 병렬 다수 실행"],
  ["교차 검증·세컨드 오피니언", "Codex (reasoning high)", "다른 모델 계열, 함정 회피"],
];
const tRows = rows.map((r, ri) => r.map((c) => {
  const text = typeof c === "string" ? c : c.text;
  const b = typeof c === "object" && c.opts && c.opts.bold;
  return { text, options: { fontFace: BFACE, fontSize: 13.5, color: ri === 0 ? BG : TXT,
    fill: { color: ri === 0 ? CY : (ri % 2 ? CARD : CARD2) }, bold: !!b || ri === 0,
    align: "left", valign: "middle", margin: [4, 8, 4, 8] } };
}));
s.addTable(tRows, { x: 0.6, y: 1.75, w: 12.1, colW: [3.5, 4.3, 4.3], rowH: 0.85, border: { type: "solid", color: LINE, pt: 1 } });

// =================================================================
// Slide 4 — 워크스페이스 구조
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "워크스페이스 구조", "경로 독립 · 모든 대회를 한 곳에서");
card(s, 0.6, 1.75, 6.3, 4.9, PANEL);
s.addText([
  { text: "ctf/", options: { color: CY, bold: true, breakLine: true } },
  { text: "├─ CLAUDE.md / AGENTS.md   운영 규칙 (공유)", options: { breakLine: true } },
  { text: "├─ .claude\\skills\\        CTF 스킬 11개", options: { breakLine: true } },
  { text: "├─ .claude\\agents\\        triager·solver·verifier", options: { breakLine: true } },
  { text: "├─ .claude\\settings.json  권한 설정", options: { breakLine: true } },
  { text: "├─ events\\<대회>\\         NOTES + challenges", options: { breakLine: true } },
  { text: "├─ tools\\wsl\\             전용 ubuntu-ctf 구축", options: { breakLine: true } },
  { text: "├─ docs\\BOOTSTRAP.md      재구축 온보딩 문서", options: { breakLine: true } },
  { text: "└─ setup.ps1              스킬 재설치", options: {} },
], { x: 0.9, y: 2.0, w: 5.8, h: 4.4, fontFace: "Consolas", fontSize: 12.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.35 });

const notes = [
  ["문제 격리", "원본은 untrusted/, 작업은 work/ 에서만. 호스트에서 바이너리 직접 실행 금지."],
  ["대회별 분리", "events/<대회>/ 아래 NOTES.md에 규칙·서버·플래그 포맷 기록."],
  ["공유 규칙", "CLAUDE.md와 AGENTS.md를 동일하게 유지해 Claude·Codex가 같은 규칙으로 동작."],
];
notes.forEach((n, i) => {
  const y = 1.75 + i * 1.68;
  card(s, 7.1, y, 5.6, 1.5, i % 2 ? CARD2 : CARD);
  s.addText(n[0], { x: 7.35, y: y + 0.18, w: 5.1, h: 0.4, fontFace: HF, fontSize: 15, bold: true, color: CY, isTextBox: true, margin: 0 });
  s.addText(n[1], { x: 7.35, y: y + 0.62, w: 5.1, h: 0.8, fontFace: BFACE, fontSize: 12.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.12 });
});

// =================================================================
// Slide 5 — 스킬 라이브러리
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "스킬 라이브러리: ctf-skills", "오픈소스 ljagiello/ctf-skills · 커밋 c332c7b 고정 벤더링");
const skills = [
  "ctf-web", "ctf-pwn", "ctf-crypto", "ctf-reverse",
  "ctf-forensics", "ctf-malware", "ctf-osint", "ctf-misc",
  "ctf-ai-ml", "ctf-writeup", "solve-challenge", "(+상세 기법 130여 문서)",
];
let sx = 0.6, sw = 3.0, sh = 0.95, sgx = 0.1, sgy = 0.25;
skills.forEach((sk, i) => {
  const col = i % 4, row = Math.floor(i / 4);
  const x = sx + col * (sw + sgx), y = 1.95 + row * (sh + sgy);
  const isDisp = sk === "solve-challenge";
  card(s, x, y, sw, sh, isDisp ? CY_DK : (i === 11 ? PANEL : CARD));
  s.addText(sk, { x: x + 0.1, y, w: sw - 0.2, h: sh, fontFace: "Consolas", fontSize: isDisp ? 14 : 13, bold: isDisp,
    color: i === 11 ? MUTED : TXT, align: "center", valign: "middle", isTextBox: true, margin: 0 });
});
s.addText([
  { text: "solve-challenge", options: { bold: true, color: CY } },
  { text: " 가 디스패처 — 문제를 분류하고 알맞은 ctf-* 스킬로 라우팅합니다.  pwn·crypto·web 스킬에는 실행 가능한 파이썬 스크립트 포함.", options: { color: TXT } },
], { x: 0.6, y: 5.45, w: 12.1, h: 0.9, fontFace: BFACE, fontSize: 13.5, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });

// =================================================================
// Slide 6 — 서브에이전트 3종
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "서브에이전트 3종", "메인 컨텍스트를 깨끗하게 유지하는 분업");
const agents = [
  ["triager", "분류 · 정찰", "모든 문제를 훑어 카테고리·난이도·예상 시간을 표로 정리. 익스플로잇은 하지 않음.", "Sonnet"],
  ["solver", "단일 문제 전담", "worktree 격리로 문제 하나를 끝까지. 가설→실험→기록 루프, 재현 경로 반환.", "inherit"],
  ["verifier", "플래그 검증", "플래그 포맷 확인 + 최소 풀이 재실행으로 재현성 검증. 제출은 사람이.", "Sonnet"],
];
agents.forEach((a, i) => {
  const x = 0.6 + i * 4.12, w = 3.9;
  card(s, x, 1.85, w, 4.4, i === 1 ? CARD2 : CARD);
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: 2.15, w: 0.5, h: 0.5, fill: { color: i === 1 ? AMBER : CY } });
  s.addText(a[0], { x: x + 0.3, y: 2.8, w: w - 0.6, h: 0.5, fontFace: "Consolas", fontSize: 19, bold: true, color: TXT, isTextBox: true, margin: 0 });
  s.addText(a[1], { x: x + 0.3, y: 3.35, w: w - 0.6, h: 0.4, fontFace: HF, fontSize: 14, bold: true, color: i === 1 ? AMBER : CY, isTextBox: true, margin: 0 });
  s.addText(a[2], { x: x + 0.3, y: 3.95, w: w - 0.6, h: 1.8, fontFace: BFACE, fontSize: 13, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
  s.addText("model: " + a[3], { x: x + 0.3, y: 5.75, w: w - 0.6, h: 0.35, fontFace: "Consolas", fontSize: 11, color: MUTED, isTextBox: true, margin: 0 });
});

// =================================================================
// Slide 7 — Claude + Codex 협업
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "Claude + Codex 협업", "두 모델이 다른 가설을 내면, 그 차이가 힌트");
card(s, 0.6, 1.9, 5.9, 2.0, CARD);
s.addText("옵션 A — 셸 교차검증 (구축 완료)", { x: 0.85, y: 2.1, w: 5.4, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: CY, isTextBox: true, margin: 0 });
s.addText([
  { text: "tools/codex-crosscheck.sh \"...\"", options: { fontFace: "Consolas", fontSize: 12, color: TXT, breakLine: true } },
  { text: "codex exec / codex review 호출. 15분 룰 초과 시 교차 검증, --review로 익스플로잇 리뷰.", options: { fontFace: BFACE, fontSize: 12.5, color: MUTED } },
], { x: 0.85, y: 2.55, w: 5.4, h: 1.2, isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });

card(s, 6.8, 1.9, 5.9, 2.0, CARD2);
s.addText("옵션 B — 완전 병렬", { x: 7.05, y: 2.1, w: 5.4, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: AMBER, isTextBox: true, margin: 0 });
s.addText("터미널 두 개로 서로 다른 문제를 담당. 공유 NOTES.md로만 상태 교환. AGENTS.md=CLAUDE.md 로 규칙 일치.",
  { x: 7.05, y: 2.55, w: 5.4, h: 1.2, fontFace: BFACE, fontSize: 12.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });

card(s, 0.6, 4.1, 12.1, 2.15, PANEL);
s.addText("교차 검증 루프", { x: 0.85, y: 4.3, w: 11.6, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: TXT, isTextBox: true, margin: 0 });
const flow = ["막힘(15분)", "가설+반증 근거 전달", "Codex 독립 의견", "의견 상이?", "차이부터 조사"];
flow.forEach((f, i) => {
  const x = 0.9 + i * 2.42;
  s.addShape(pres.ShapeType.roundRect, { x, y: 4.9, w: 2.1, h: 0.95, rectRadius: 0.06, fill: { color: i === 3 ? AMBER : CARD2 }, line: { color: CY, width: 1 } });
  s.addText(f, { x: x + 0.05, y: 4.9, w: 2.0, h: 0.95, fontFace: BFACE, fontSize: 12.5, bold: i === 3, color: i === 3 ? BG : TXT, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  if (i < 4) s.addText("›", { x: x + 2.08, y: 4.9, w: 0.34, h: 0.95, fontFace: HF, fontSize: 22, color: CY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
});

// =================================================================
// Slide 8 — 작업 원칙 (workflow)
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "작업 원칙", "프롬프트 엔지니어링의 90%는 CLAUDE.md 규칙에서 결정");
const steps = [
  ["정찰 먼저", "파일 타입·strings·보호기법·카테고리 식별"],
  ["가설 1개", "익스플로잇 전에 반드시 가설 하나를 세움"],
  ["최소 실험", "가장 작은 실험으로 가설을 검증"],
  ["기록", "사실 / 반증 / 다음 단계를 NOTES.md에"],
  ["다음 가설", "도구부터 난사하지 않음"],
];
steps.forEach((st, i) => {
  const y = 1.85 + i * 0.86;
  badge(s, 0.7, y, String(i + 1));
  card(s, 1.4, y - 0.02, 7.0, 0.72, i % 2 ? CARD2 : CARD);
  s.addText(st[0], { x: 1.65, y: y - 0.02, w: 2.2, h: 0.72, fontFace: HF, fontSize: 15, bold: true, color: CY, valign: "middle", isTextBox: true, margin: 0 });
  s.addText(st[1], { x: 3.8, y: y - 0.02, w: 4.5, h: 0.72, fontFace: BFACE, fontSize: 13, color: TXT, valign: "middle", isTextBox: true, margin: 0 });
});
card(s, 8.8, 1.85, 3.9, 4.3, PANEL);
s.addText("15분 룰", { x: 9.05, y: 2.1, w: 3.4, h: 0.5, fontFace: HF, fontSize: 22, bold: true, color: AMBER, isTextBox: true, margin: 0 });
s.addText("15", { x: 9.05, y: 2.7, w: 3.4, h: 1.1, fontFace: HF, fontSize: 72, bold: true, color: TXT, isTextBox: true, margin: 0 });
s.addText("한 접근법이 15분간 진전이 없으면 전환하고, 전환 사유를 기록합니다. 터널링 방지.",
  { x: 9.05, y: 3.95, w: 3.4, h: 2.0, fontFace: BFACE, fontSize: 13.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });

// =================================================================
// Slide 9 — 재현성 & 기록
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "재현성 & 기록", "모든 작업을 추적하고 한 번에 재생성할 수 있게");
const repro = [
  ["git 버전관리", "저장소 전체를 커밋. 스킬도 커밋 고정으로 포함해 한 번에 복원."],
  ["WORKLOG + 로그", "환경·단계·신뢰 주의를 날짜와 함께 기록, 원본 로그 보관."],
  ["BOOTSTRAP.md", "다른 환경의 Claude가 읽고 바로 재구축 (경로 독립)."],
  ["동결 requirements", "실제 동작하는 174개 패키지 집합을 그대로 재설치."],
];
repro.forEach((r, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.6 + col * 6.25, y = 1.9 + row * 2.2;
  card(s, x, y, 5.9, 1.95, i % 2 ? CARD2 : CARD);
  s.addText(r[0], { x: x + 0.35, y: y + 0.28, w: 5.2, h: 0.5, fontFace: "Consolas", fontSize: 17, bold: true, color: CY, isTextBox: true, margin: 0 });
  s.addText(r[1], { x: x + 0.35, y: y + 0.9, w: 5.2, h: 0.9, fontFace: BFACE, fontSize: 13.5, color: TXT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
});

// =================================================================
// Slide 10 — 당일 운영 루틴
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "당일 운영 루틴", "예선 2026-10-14");
const run = [
  ["시작 10분", "규칙·플래그 포맷을 NOTES.md에 기록 → 전 문제 다운로드 → triager 실행"],
  ["초반", "쉬운 문제부터 solver 병렬 투입. 사람은 가장 어려운 1문제에 집중"],
  ["매 1시간", "전체 NOTES를 메인 세션에 읽혀 우선순위 재조정"],
  ["플래그", "verifier가 형식·재현 검증 → 사람이 직접 제출 (자동 제출 금지)"],
  ["종료 후", "ctf-writeup 스킬로 풀이 정리 → 결선 준비·다음 대회 자산"],
];
run.forEach((r, i) => {
  const y = 1.8 + i * 0.95;
  card(s, 0.6, y, 12.1, 0.82, i % 2 ? CARD2 : CARD);
  s.addText(r[0], { x: 0.85, y, w: 2.6, h: 0.82, fontFace: HF, fontSize: 15, bold: true, color: CY, valign: "middle", isTextBox: true, margin: 0 });
  s.addShape(pres.ShapeType.line, { x: 3.5, y: y + 0.16, w: 0, h: 0.5, line: { color: LINE, width: 1 } });
  s.addText(r[1], { x: 3.75, y, w: 8.7, h: 0.82, fontFace: BFACE, fontSize: 13.5, color: TXT, valign: "middle", isTextBox: true, margin: 0 });
});

// =================================================================
// Slide 11 — 시작 전 TODO
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "구축 완료 체크리스트", "리허설로 전 과정 검증 완료");
const todo = [
  ["격리 실행 환경", "전용 ubuntu-ctf (Ubuntu 26.04) + Docker 29.1 구축", "완료"],
  ["CTF 도구", "pwntools·angr·volatility3 등 174개 (py3.12 venv)", "완료"],
  ["Codex 교차검증", "codex-crosscheck.sh (codex exec / review)", "완료"],
  ["리허설", "CRYPTO1 풀이 성공 — MARINE{...} 복구, 툴체인 검증", "완료"],
  ["규칙 확인", "대회 시작 시 사전 인터뷰(PRE-CTF-INTAKE)로 수집", "대회시작"],
];
todo.forEach((t, i) => {
  const y = 1.8 + i * 0.95;
  card(s, 0.6, y, 12.1, 0.82, i % 2 ? CARD2 : CARD);
  const done = t[2] === "완료";
  s.addShape(pres.ShapeType.rect, { x: 0.85, y: y + 0.26, w: 0.3, h: 0.3, fill: { color: done ? CY : BG }, line: { color: CY, width: 1.5 } });
  if (done) s.addText("✓", { x: 0.85, y: y + 0.19, w: 0.3, h: 0.4, fontFace: HF, fontSize: 14, bold: true, color: BG, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t[0], { x: 1.4, y, w: 3.2, h: 0.82, fontFace: HF, fontSize: 15, bold: true, color: TXT, valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t[1], { x: 4.7, y, w: 6.2, h: 0.82, fontFace: BFACE, fontSize: 12.5, color: MUTED, valign: "middle", isTextBox: true, margin: 0 });
  s.addShape(pres.ShapeType.roundRect, { x: 11.2, y: y + 0.21, w: 1.25, h: 0.4, rectRadius: 0.2, fill: { color: done ? CY_DK : CARD2 }, line: { color: done ? CY : AMBER, width: 1 } });
  s.addText(t[2], { x: 11.2, y: y + 0.21, w: 1.25, h: 0.4, fontFace: HF, fontSize: 10.5, bold: true, color: TXT, align: "center", valign: "middle", isTextBox: true, margin: 0 });
});

// =================================================================
// Slide 12 — 마무리
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
s.addShape(pres.ShapeType.rect, { x: 0.6, y: 2.1, w: 0.7, h: 0.14, fill: { color: CY } });
s.addText("요약", { x: 0.6, y: 2.35, w: 12, h: 0.8, fontFace: HF, fontSize: 40, bold: true, color: TXT, isTextBox: true, margin: 0 });
s.addText([
  { text: "검증된 스킬 + 모델 분업 + 서브에이전트 자동화 + 재현성", options: { fontSize: 18, color: CY, breakLine: true, bold: true } },
  { text: "을 한 워크스페이스에 담았습니다.", options: { fontSize: 18, color: TXT } },
], { x: 0.6, y: 3.3, w: 12, h: 0.6, fontFace: HF, isTextBox: true, margin: 0 });
s.addText([
  { text: "구축 완료:  ", options: { bold: true, color: TXT } },
  { text: "전용 ubuntu-ctf + Docker · CTF 도구 174개 · Codex 교차검증 · 리허설 통과", options: { color: MUTED } },
], { x: 0.6, y: 4.25, w: 12, h: 0.5, fontFace: BFACE, fontSize: 14, isTextBox: true, margin: 0 });
s.addText([
  { text: "남은 것:  ", options: { bold: true, color: TXT } },
  { text: "대회 시작 시 사전 인터뷰 → 규칙 확정 → 풀이. 공유는 원격 저장소로.", options: { color: MUTED } },
], { x: 0.6, y: 4.85, w: 12, h: 0.5, fontFace: BFACE, fontSize: 14, isTextBox: true, margin: 0 });
s.addText("git 커밋 완료  ·  docs/BOOTSTRAP.md 로 어디서든 재구축", { x: 0.6, y: 5.6, w: 12, h: 0.4, fontFace: "Consolas", fontSize: 13, color: CY, isTextBox: true, margin: 0 });

pres.writeFile({ fileName: "<repo>/docs/CTF-Setup-Deck.pptx" }).then((f) => console.log("WROTE", f));
