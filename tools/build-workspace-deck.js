// CTF Workspace — 통합 소개 덱 (pptxgenjs). CTF-Setup-Deck + Harness-Prompting
// 을 합치고 "repo를 Claude+Codex에 적용하는 방법(설치·연동)"을 포함.
// 라이트 Office 스타일(참고: Week5 BINREX 덱).
// Build:  cd <repo> && node tools/build-workspace-deck.js
// Output: docs/CTF-Workspace-Deck.pptx
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "CTF Team";
pres.title = "CTF Workspace — Claude Code + Codex";

// ---- palette ----
const WHITE = "FFFFFF";
const NAVY  = "0E2841";
const BLUE  = "156082";
const ORANGE= "C55A11";
const GREEN = "1E6B2A";
const RED   = "9A3B38";
const INK   = "1A2230";
const MUTED = "6B7280";
const PANEL = "F3F5F8";
const PANEL2= "E9EEF4";
const LINE  = "D9DEE6";
const NUMG  = "DCE4EC";
const CODEBG= "0E2841";
const CODETX= "CFE3EC";
const CODEAC= "6FC3D6";

const FONT = "맑은 고딕";
const MONO = "Consolas";

pres.defineSlideMaster({
  title: "LIGHT",
  background: { color: WHITE },
  objects: [
    { text: { text: "CTF Workspace · Claude Code + Codex", options: {
      x: 0.6, y: 7.06, w: 9, h: 0.33, fontFace: FONT, fontSize: 9, color: MUTED, align: "left", isTextBox: true, margin: 0 } } },
  ],
  slideNumber: { x: 12.5, y: 7.06, w: 0.5, h: 0.33, fontFace: FONT, fontSize: 9, color: MUTED },
});

function header(s, num, section, titleText, subText, sourceText) {
  s.addText(num, { x: 11.2, y: 0.2, w: 1.55, h: 1.1, fontFace: FONT, fontSize: 66, bold: true, color: NUMG, align: "right", valign: "top", isTextBox: true, margin: 0 });
  s.addText([
    { text: num + "  ", options: { color: ORANGE, bold: true } },
    { text: section, options: { color: BLUE, bold: true } },
  ], { x: 0.6, y: 0.46, w: 10.4, h: 0.32, fontFace: FONT, fontSize: 13, align: "left", isTextBox: true, margin: 0, charSpacing: 1 });
  s.addText(titleText, { x: 0.6, y: 0.82, w: 10.5, h: 0.72, fontFace: FONT, fontSize: 27, bold: true, color: NAVY, align: "left", isTextBox: true, margin: 0 });
  if (subText) s.addText(subText, { x: 0.6, y: 1.55, w: 11.8, h: 0.4, fontFace: FONT, fontSize: 13.5, color: INK, align: "left", isTextBox: true, margin: 0 });
  if (sourceText) s.addText(sourceText, { x: 0.6, y: 6.72, w: 11.8, h: 0.3, fontFace: FONT, fontSize: 9, italic: true, color: MUTED, align: "left", isTextBox: true, margin: 0 });
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.07, fill: { color: fill || PANEL }, line: { color: LINE, width: 1 } });
}
function badge(s, x, y, label, col) {
  s.addShape(pres.ShapeType.ellipse, { x, y, w: 0.44, h: 0.44, fill: { color: col || BLUE } });
  s.addText(label, { x, y, w: 0.44, h: 0.44, fontFace: FONT, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
function bullets(s, x, y, w, h, lines, col) {
  const runs = lines.map((t, i) => ({ text: t, options: {
    bullet: { code: "2022", indent: 14 }, color: col || INK, fontSize: 11.5,
    breakLine: i !== lines.length - 1, paraSpaceAfter: 5 } }));
  s.addText(runs, { x, y, w, h, fontFace: FONT, isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.03 });
}
function cardHead(s, x, y, w, head, col) {
  s.addText(head, { x: x + 0.22, y: y + 0.16, w: w - 0.44, h: 0.4, fontFace: FONT, fontSize: 15, bold: true, color: col || NAVY, isTextBox: true, margin: 0 });
}
function stat(s, x, y, w, big, label, col) {
  s.addText(big, { x, y, w, h: 0.9, fontFace: FONT, fontSize: 46, bold: true, color: col || NAVY, align: "left", isTextBox: true, margin: 0 });
  s.addText(label, { x: x + 0.02, y: y + 0.9, w, h: 0.6, fontFace: FONT, fontSize: 11.5, color: MUTED, align: "left", isTextBox: true, margin: 0, valign: "top" });
}
function codeBox(s, x, y, w, h, lines) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.05, fill: { color: CODEBG } });
  const runs = lines.map((t, i) => ({ text: t, options: {
    color: t.startsWith("#") ? "8CA6B8" : (t.startsWith(">") ? CODEAC : CODETX),
    fontSize: 11, breakLine: i !== lines.length - 1, paraSpaceAfter: 3 } }));
  s.addText(runs, { x: x + 0.22, y: y + 0.14, w: w - 0.44, h: h - 0.28, fontFace: MONO, isTextBox: true, margin: 0, valign: "top" });
}

// =================================================================
// 1 — Title
// =================================================================
let s = pres.addSlide({ masterName: "LIGHT" });
s.addText("CTF Workspace", { x: 0.75, y: 1.45, w: 11, h: 0.4, fontFace: FONT, fontSize: 14, bold: true, color: BLUE, isTextBox: true, margin: 0, charSpacing: 2 });
s.addText("Claude Code + Codex 기반 CTF 분석 환경", { x: 0.72, y: 1.9, w: 11.8, h: 1.0, fontFace: FONT, fontSize: 40, bold: true, color: NAVY, isTextBox: true, margin: 0 });
s.addText("지시(프롬프트)와 실행 틀(하네스)을 코드처럼 관리 — clone 한 번으로 동일 환경을 재현한다", { x: 0.75, y: 3.0, w: 11.8, h: 0.7, fontFace: FONT, fontSize: 17, color: INK, isTextBox: true, margin: 0 });
card(s, 0.75, 4.05, 11.8, 1.55, PANEL);
s.addText([
  { text: "개념 · 아키텍처 · 적용 방법(설치 · Claude+Codex 연동) · 운영 규칙 · 프롬프트 자산", options: { color: INK, fontSize: 13.5, bold: true, breakLine: true } },
  { text: "사용 플로우 · 툴링 · 정량 효과 · 미적용 대비 이점 · 확장/유지", options: { color: MUTED, fontSize: 12.5, breakLine: true } },
], { x: 1.05, y: 4.25, w: 9.0, h: 1.15, fontFace: FONT, isTextBox: true, margin: 0, valign: "middle", lineSpacingMultiple: 1.35 });
s.addText([
  { text: "GitHub", options: { color: MUTED, fontSize: 11, breakLine: true } },
  { text: "github.com/ring7a/ctf-workspace", options: { color: BLUE, fontSize: 12.5, bold: true } },
], { x: 9.0, y: 4.35, w: 3.4, h: 1.0, fontFace: MONO, isTextBox: true, margin: 0, valign: "middle", lineSpacingMultiple: 1.2 });
s.addText("Claude Code(운영 규칙·스킬·에이전트) + Codex(교차검증) + WSL(격리) + git(재현)", { x: 0.75, y: 6.05, w: 11.8, h: 0.4, fontFace: FONT, fontSize: 11, italic: true, color: MUTED, isTextBox: true, margin: 0 });

// =================================================================
// 2 — 개념
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "01", "개념", "지시와 실행 틀을 '파일'로 고정·버전관리·재현한다",
  "네 개 레이어: 지식(스킬) · 규칙(프롬프트) · 자동화(에이전트) · 런타임(격리 Linux).",
  "출처: 리포 CLAUDE.md · AGENTS.md · .claude/skills · .claude/agents · tools/");
const c2 = [
  ["지식 = 스킬", BLUE, ["11개 CTF 스킬 + 하위 기법 문서 124개", "핀 고정 커밋으로 벤더링(재현·감사)", "solve-challenge 디스패처가 라우팅"]],
  ["규칙 = 프롬프트", BLUE, ["CLAUDE.md / AGENTS.md 가 핵심 지시", "워크플로·15분 룰·보고 형식·플래그 처리", "모든 챌린지에 강제되는 가드레일"]],
  ["자동화 = 에이전트", BLUE, ["triager — 분류(읽기 전용)", "solver — 한 문제를 끝까지", "verifier — 포맷·재현 검증"]],
  ["런타임 = 격리", GREEN, ["WSL ubuntu-ctf 에서만 untrusted 실행", "~/.ctf-tools/venv 동결 툴체인", "호스트는 건드리지 않음"]],
];
let cx = 0.6, cw = 2.95, gap = 0.17;
c2.forEach((it, i) => {
  const x = cx + i * (cw + gap);
  card(s, x, 2.15, cw, 3.9, i === 3 ? PANEL2 : PANEL);
  badge(s, x + 0.22, 2.38, String(i + 1), it[1]);
  cardHead(s, x, 2.78, cw, it[0], it[1]);
  bullets(s, x + 0.24, 3.52, cw - 0.46, 2.4, it[2], INK);
});

// =================================================================
// 3 — 아키텍처
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "02", "아키텍처", "분석 지능 · 격리 실행 · 재현 자산을 분리한다",
  "지능(Claude+Codex)은 규칙·스킬을 따르고, 실행은 WSL에 격리하며, 모든 자산은 git으로 재현한다.", null);
card(s, 0.6, 2.1, 12.1, 0.8, PANEL2);
s.addText("공개 Git 리포  ·  github.com/ring7a/ctf-workspace", { x: 0.85, y: 2.2, w: 7.5, h: 0.6, fontFace: FONT, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle" });
s.addText("규칙 · 스킬 · 에이전트 · 툴링 스크립트 · 문서를 버전관리", { x: 7.2, y: 2.2, w: 5.3, h: 0.6, fontFace: FONT, fontSize: 11, color: MUTED, isTextBox: true, margin: 0, valign: "middle", align: "right" });
const col = [
  ["Claude Code", BLUE, ["CLAUDE.md — 운영 규칙(프롬프트)", ".claude/skills — 11개 CTF 스킬", ".claude/agents — triager·solver·verifier"]],
  ["Codex (2차 모델)", ORANGE, ["tools/codex-crosscheck.sh", "독립 의견: codex exec (read-only)", "코드 리뷰: codex review --uncommitted"]],
  ["WSL ubuntu-ctf (격리)", GREEN, ["~/.ctf-tools/venv — Python 툴체인", "pwntools·angr·z3·volatility3·Docker", "untrusted 바이너리는 여기서만 실행"]],
];
col.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 3.1, 3.97, 2.6, PANEL);
  cardHead(s, x, 3.12, 3.97, it[0], it[1]);
  bullets(s, x + 0.24, 3.78, 3.55, 1.8, it[2], INK);
});
card(s, 0.6, 5.85, 12.1, 0.7, PANEL);
s.addText([
  { text: "events/<대회>/ ", options: { bold: true, color: NAVY, fontSize: 12 } },
  { text: "— 대회별 챌린지·NOTES·플래그. git 추적 제외(.gitignore), 머신 로컬 유지.", options: { color: MUTED, fontSize: 12 } },
], { x: 0.85, y: 5.95, w: 11.6, h: 0.5, fontFace: FONT, isTextBox: true, margin: 0, valign: "middle" });

// =================================================================
// 4 — 적용 방법 ① 설치
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "03", "적용 방법 · 설치", "clone → 스크립트 1개 → 완료",
  "새 머신에서 동일한 격리 분석 환경을 재현한다 (경로 독립).",
  "출처: docs/BOOTSTRAP.md · tools/wsl/setup-ubuntu-ctf.ps1 · provision-ubuntu-ctf.sh");
const steps = [
  ["리포 clone", ["git clone — 폴더명 자유, 경로에 독립"]],
  ["setup 실행 (Windows)", ["pwsh -File tools\\wsl\\setup-ubuntu-ctf.ps1"]],
  ["자동 프로비저닝", ["ubuntu-ctf 배포판 생성", "uv + Python 3.12 venv + 동결 requirements + apt 도구"]],
  ["완료", ["wsl -d ubuntu-ctf 진입 → venv 자동 활성화"]],
];
steps.forEach((it, i) => {
  const y = 2.2 + i * 0.84;
  badge(s, 0.7, y + 0.06, String(i + 1), i === 3 ? GREEN : BLUE);
  s.addText(it[0], { x: 1.35, y: y, w: 3.6, h: 0.56, fontFace: FONT, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(it[1].map((t, j) => ({ text: t, options: { bullet: { code: "2022" }, color: MUTED, fontSize: 11, breakLine: j !== it[1].length - 1 } })),
    { x: 5.0, y: y, w: 7.5, h: 0.56, fontFace: FONT, isTextBox: true, margin: 0, valign: "middle" });
});
codeBox(s, 0.6, 5.75, 12.1, 0.75, [
  "# 네이티브 Linux/macOS/컨테이너: .ps1 없이 직접 재현",
  "> uv venv --python 3.12 ~/.ctf-tools/venv && uv pip install -r tools/wsl/ctf-venv-requirements.txt",
]);

// =================================================================
// 5 — 적용 방법 ② Claude + Codex 연동
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "04", "적용 방법 · Claude + Codex", "하나의 리포를 두 모델에 연결한다",
  "같은 규칙·스킬 세트를 Claude Code와 Codex가 함께 따른다 (AGENTS.md == CLAUDE.md).", null);
card(s, 0.6, 2.15, 5.95, 3.1, PANEL);
cardHead(s, 0.6, 2.17, 5.95, "Claude Code 연동", BLUE);
bullets(s, 0.84, 2.85, 5.5, 2.2, [
  "리포 루트에서 Claude Code 실행 → .claude/ 자동 발견",
  "CLAUDE.md(운영 규칙) + .claude/skills(11) + .claude/agents(3) 로드",
  "solve-challenge 로 분류 → 카테고리 스킬로 라우팅",
  ".claude/settings.json 으로 도구 권한 관리",
], INK);
card(s, 6.75, 2.15, 5.95, 3.1, PANEL2);
cardHead(s, 6.75, 2.17, 5.95, "Codex 연동 (2차 모델)", ORANGE);
bullets(s, 6.99, 2.85, 5.5, 2.2, [
  "AGENTS.md(=CLAUDE.md)로 동일 규칙을 따름",
  "tools/codex-crosscheck.sh — 독립 의견 / 코드 리뷰",
  "codex exec (read-only) · codex review --uncommitted",
  "MCP 등록: claude mcp add codex (선택)",
], INK);
card(s, 0.6, 5.45, 12.1, 0.85, PANEL);
s.addText([
  { text: "핵심  ", options: { bold: true, color: NAVY, fontSize: 12.5 } },
  { text: "AGENTS.md == CLAUDE.md 를 유지해 두 모델이 동일한 가드레일을 따른다. 15분 룰을 넘겨 막히면 Codex에 가설+반증 증거를 넘겨 교차검증.", options: { color: INK, fontSize: 11.5 } },
], { x: 0.85, y: 5.55, w: 11.6, h: 0.65, fontFace: FONT, isTextBox: true, margin: 0, valign: "middle", lineSpacingMultiple: 1.2 });

// =================================================================
// 6 — 운영 규칙
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "05", "운영 규칙", "운영 규칙을 하나의 프롬프트로 고정한다",
  "CLAUDE.md / AGENTS.md 에 모든 챌린지에 강제되는 워크플로와 가드레일을 담았다.",
  "출처: 리포 CLAUDE.md · AGENTS.md · docs/PRE-CTF-INTAKE.md (한글화 적용)");
const wf = ["정찰", "가설 1개", "최소 실험", "NOTES 기록", "다음 가설"];
wf.forEach((t, i) => {
  const x = 0.6 + i * 2.46;
  badge(s, x, 2.3, String(i + 1), BLUE);
  s.addText(t, { x: x + 0.52, y: 2.3, w: 1.7, h: 0.44, fontFace: FONT, fontSize: 13, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle" });
  if (i < wf.length - 1) s.addText("→", { x: x + 2.02, y: 2.3, w: 0.4, h: 0.44, fontFace: FONT, fontSize: 16, color: LINE, isTextBox: true, margin: 0, valign: "middle", align: "center" });
});
s.addText("가설 없이 도구를 난사하지 않는다 — 가장 작은 실험으로 하나씩 검증", { x: 0.6, y: 2.85, w: 12, h: 0.35, fontFace: FONT, fontSize: 11.5, italic: true, color: MUTED, isTextBox: true, margin: 0 });
const rules = [
  ["15분 룰", BLUE, ["진전이 없으면 접근을 전환", "전환 이유를 NOTES.md에 기록", "한 곳만 파고들지(tunnel) 않는다"]],
  ["3줄 보고 형식", BLUE, ["가설: …", "확인된 사실: …", "다음 실험: …"]],
  ["플래그 처리", ORANGE, ["verifier가 포맷·재현 검증", "제출은 사람이 (자동 제출 없음)", "플래그는 로컬 — 리포에 커밋 금지"]],
];
rules.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 3.5, 3.97, 2.65, i === 2 ? PANEL2 : PANEL);
  cardHead(s, x, 3.52, 3.97, it[0], it[1]);
  bullets(s, x + 0.24, 4.2, 3.55, 1.8, it[2], INK);
});

// =================================================================
// 7 — 프롬프트 자산 (스킬 · 에이전트)
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "06", "프롬프트 자산", "스킬·에이전트를 핀 고정해 재현·감사 가능하게",
  "외부 스킬 모음을 특정 커밋으로 벤더링하고 보안 감사 후 커밋한다.",
  "출처: tools/vendor-ctf-skills/ (출처·LICENSE·핀 커밋 보존) · 핀 커밋 c332c7b");
stat(s, 0.7, 2.2, 2.7, "11", "CTF 스킬 (카테고리 9 + 디스패처·writeup)", BLUE);
stat(s, 3.7, 2.2, 2.7, "124", "스킬 하위 기법 문서", BLUE);
stat(s, 6.7, 2.2, 2.7, "3", "서브에이전트 (triager·solver·verifier)", BLUE);
stat(s, 9.7, 2.2, 2.9, "1", "핀 고정 출처 커밋 (감사 가능)", ORANGE);
card(s, 0.6, 4.3, 5.95, 1.95, PANEL);
cardHead(s, 0.6, 4.32, 5.95, "디스패처 라우팅", BLUE);
bullets(s, 0.84, 4.98, 5.5, 1.2, [
  "solve-challenge 가 카테고리를 판별",
  "→ ctf-web / pwn / crypto / reverse / forensics / malware / osint / misc / ai-ml",
  "풀이 후 ctf-writeup 으로 재현 가능한 기록",
], INK);
card(s, 6.75, 4.3, 5.95, 1.95, PANEL);
cardHead(s, 6.75, 4.32, 5.95, "출처·무결성", GREEN);
bullets(s, 6.99, 4.98, 5.5, 1.2, [
  "ljagiello/ctf-skills 를 핀 커밋으로 벤더링",
  "skill_security_auditor.py 로 보안 감사 후 커밋",
  "스킬 = Claude가 따르는 '지시' → 출처 신뢰·버전 고정 필수",
], INK);

// =================================================================
// 8 — 사용 플로우
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "07", "사용 플로우", "대회 시작 → 문제별 루프 → 검증·제출",
  "인테이크로 규칙을 먼저 확정하고, 문제마다 동일한 루프를 반복한다.", null);
card(s, 0.6, 2.1, 12.1, 0.85, PANEL2);
s.addText([
  { text: "① 대회 시작 — Pre-CTF 인테이크  ", options: { bold: true, color: NAVY, fontSize: 13 } },
  { text: "13문항(블로킹 5)으로 플래그 포맷·범위·AI 규정 확정 · bash tools/new-challenge.sh <대회> <이름> 으로 챌린지 골격", options: { color: MUTED, fontSize: 11 } },
], { x: 0.85, y: 2.2, w: 11.6, h: 0.65, fontFace: FONT, isTextBox: true, margin: 0, valign: "middle" });
const loop = [
  ["recon / 분류", "solve-challenge 디스패처 → 해당 스킬"],
  ["가설 1개", "익스플로잇 전에 가설을 하나만"],
  ["최소 실험", "가장 작은 실험으로 WSL 격리 검증"],
  ["NOTES 기록", "사실/반증/다음 단계를 남김"],
  ["15분 룰 · Codex", "진전 없으면 전환 + 2차 의견"],
  ["검증 · 제출", "verifier 포맷·재현 → 사람이 제출"],
];
loop.forEach((it, i) => {
  const xcol = i % 3, yrow = Math.floor(i / 3);
  const x = 0.6 + xcol * 4.07, y = 3.15 + yrow * 1.45;
  card(s, x, y, 3.9, 1.25, PANEL);
  badge(s, x + 0.2, y + 0.4, String(i + 1), i >= 4 ? ORANGE : BLUE);
  s.addText(it[0], { x: x + 0.78, y: y + 0.16, w: 3.0, h: 0.4, fontFace: FONT, fontSize: 13.5, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  s.addText(it[1], { x: x + 0.78, y: y + 0.56, w: 3.0, h: 0.6, fontFace: FONT, fontSize: 10.5, color: MUTED, isTextBox: true, margin: 0, valign: "top" });
});

// =================================================================
// 9 — 툴링
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "08", "툴링", "WSL 안에 카테고리별 분석 도구가 준비됨",
  "~/.ctf-tools/venv 에 동결된 176개 패키지 + 시스템 도구.", "출처: tools/wsl/ctf-venv-requirements.txt · install_ctf_tools.sh");
const tool = [
  ["Python venv", BLUE, ["pwntools (원격 익스플로잇)", "angr · unicorn · capstone", "z3 · sympy · gmpy2 · fpylll(격자)", "volatility3 · scapy · pefile · yara"]],
  ["시스템 도구", GREEN, ["gdb + gdb-multiarch (ARM/MIPS)", "radare2 · binwalk · nc", "objdump·readelf·nm·strings·file", "Docker (챌린지 컨테이너용)"]],
  ["협업 · 재현", ORANGE, ["Codex CLI — 독립 의견/코드 리뷰", "uv — 결정적 venv 구성", "frozen requirements (버전 핀)", "setup/provision 스크립트 1커맨드"]],
];
tool.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 2.15, 3.97, 3.95, i === 2 ? PANEL2 : PANEL);
  cardHead(s, x, 2.17, 3.97, it[0], it[1]);
  bullets(s, x + 0.24, 2.85, 3.55, 3.0, it[2], INK);
});

// =================================================================
// 10 — 정량 효과
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "09", "정량 효과", "규율이 남긴 정량적 산출물",
  "한 문제에서만 규율이 만든 감사 추적의 규모.", "출처: events/2026-yeongnam/challenges/*/NOTES.md · 리포 구성 수치");
stat(s, 0.7, 2.25, 3.0, "~75", "한 WEB 문제에 기록된 가설 — 각 최소 실험 + 반증", ORANGE);
stat(s, 4.0, 2.25, 2.7, "0", "무가설 도구 난사 (가설→실험→기록 강제)", GREEN);
stat(s, 6.9, 2.25, 2.6, "176", "핀 고정 Python 패키지", BLUE);
stat(s, 9.7, 2.25, 2.9, "2", "교차검증 모델 계보 (Claude + Codex)", BLUE);
card(s, 0.6, 4.4, 12.1, 1.85, PANEL);
cardHead(s, 0.6, 4.42, 12.1, "왜 이 숫자가 중요한가", NAVY);
bullets(s, 0.84, 5.05, 11.6, 1.2, [
  "모든 시도가 '가설 / 확인된 사실 / 다음 실험'으로 NOTES에 남아 — 중복 시도·헛수고가 제거되고 인수인계·재현이 즉시 가능",
  "clone + 스크립트 1개로 동일 환경 재현 (176개 패키지 버전 고정) — 새 팀원·새 머신도 수 분 내 동일 조건",
  "두 모델이 교차검증해 단일 모델의 편향·실수를 조기에 잡아냄",
], INK);

// =================================================================
// 11 — 적용 vs 미적용
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "10", "미적용 대비 이점", "하네스·프롬프트를 적용하면 무엇이 달라지나",
  "같은 모델·같은 사람이라도, 틀의 유무가 결과의 품질을 가른다.", null);
const cmp = [
  ["시도 추적", "흩어진 기억 · 추적 불가", "~75건 NOTES 감사 추적"],
  ["재현", "수동 세팅, 수 시간", "clone + 스크립트 1개"],
  ["격리", "호스트 오염 위험", "WSL 전용 실행"],
  ["검증", "단일 모델 편향", "2계보 교차검증"],
  ["규율", "도구 난사 · 터널링", "1가설 · 15분 룰"],
  ["공유", "플래그 유출 위험", "events gitignore · 포맷 검증 후 사람 제출"],
];
s.addText("항목", { x: 0.7, y: 2.15, w: 2.2, h: 0.5, fontFace: FONT, fontSize: 12, bold: true, color: MUTED, isTextBox: true, margin: 0, valign: "middle" });
s.addText("미적용", { x: 3.2, y: 2.15, w: 4.4, h: 0.5, fontFace: FONT, fontSize: 12, bold: true, color: RED, isTextBox: true, margin: 0, valign: "middle" });
s.addText("적용", { x: 7.9, y: 2.15, w: 4.6, h: 0.5, fontFace: FONT, fontSize: 12, bold: true, color: GREEN, isTextBox: true, margin: 0, valign: "middle" });
cmp.forEach((it, i) => {
  const y = 2.72 + i * 0.68;
  s.addText(it[0], { x: 0.7, y, w: 2.3, h: 0.6, fontFace: FONT, fontSize: 12.5, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle" });
  card(s, 3.1, y + 0.02, 4.4, 0.56, PANEL);
  s.addText([{ text: "✕  ", options: { color: RED, bold: true } }, { text: it[1], options: { color: INK } }],
    { x: 3.28, y: y + 0.02, w: 4.1, h: 0.56, fontFace: FONT, fontSize: 11.5, isTextBox: true, margin: 0, valign: "middle" });
  card(s, 7.7, y + 0.02, 4.9, 0.56, PANEL2);
  s.addText([{ text: "✓  ", options: { color: GREEN, bold: true } }, { text: it[2], options: { color: INK } }],
    { x: 7.88, y: y + 0.02, w: 4.6, h: 0.56, fontFace: FONT, fontSize: 11.5, isTextBox: true, margin: 0, valign: "middle" });
});

// =================================================================
// 12 — 확장 · 유지 · 참고
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
header(s, "11", "확장 · 유지 · 참고", "안전하게 확장하고 팀과 동기화한다",
  "스킬·툴체인을 핀 고정 방식으로 갱신하고, 운영 규칙·문서는 한글화해 유지한다.", null);
const ext = [
  ["스킬 레포 추가", BLUE, ["핀 커밋으로 clone → .claude/skills 복사", "출처·LICENSE·핀 커밋 보존 → 보안 감사 후 커밋"]],
  ["툴체인 갱신", BLUE, ["ctf-venv-requirements.txt 에 추가/핀", "ubuntu-ctf 재프로비저닝으로 반영"]],
  ["동기화 · 위생", GREEN, ["git pull 로 다른 머신과 동기화", "events/* gitignore — 플래그·챌린지 데이터 커밋 금지"]],
  ["한글화 적용", ORANGE, ["README·BOOTSTRAP·TROUBLESHOOTING", "CLAUDE.md·AGENTS.md·에이전트·crosscheck 하네스"]],
];
ext.forEach((it, i) => {
  const xcol = i % 2, yrow = Math.floor(i / 2);
  const x = 0.6 + xcol * 6.15, y = 2.2 + yrow * 1.55;
  card(s, x, y, 5.95, 1.4, i === 3 ? PANEL2 : PANEL);
  cardHead(s, x, y, 5.95, it[0], it[1]);
  bullets(s, x + 0.24, y + 0.64, 5.5, 0.7, it[2], INK);
});
card(s, 0.6, 5.4, 12.1, 0.95, PANEL);
s.addText([
  { text: "참고 포인터  ", options: { bold: true, color: NAVY, fontSize: 12 } },
  { text: "README.md · CLAUDE.md · AGENTS.md · docs/BOOTSTRAP.md · docs/PRE-CTF-INTAKE.md · docs/TROUBLESHOOTING.md · tools/wsl/* · tools/codex-crosscheck.sh", options: { color: MUTED, fontSize: 11 } },
], { x: 0.85, y: 5.5, w: 11.6, h: 0.75, fontFace: MONO, isTextBox: true, margin: 0, valign: "middle", lineSpacingMultiple: 1.2 });

// =================================================================
// 13 — 마무리 / GitHub
// =================================================================
s = pres.addSlide({ masterName: "LIGHT" });
s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: NAVY } });
s.addText("한 번 clone으로, 규율 있는 분석 환경을 재현한다", { x: 0.9, y: 2.5, w: 11.5, h: 1.2, fontFace: FONT, fontSize: 33, bold: true, color: WHITE, isTextBox: true, margin: 0 });
s.addText("지시(프롬프트)와 실행 틀(하네스)을 파일로 고정 → 재현 · 격리 · 규율 · 교차검증 · 안전한 공유", { x: 0.9, y: 3.7, w: 11.5, h: 0.6, fontFace: FONT, fontSize: 15, color: "CADCFC", isTextBox: true, margin: 0 });
s.addText([
  { text: "GitHub  ", options: { color: "9DB0CC", fontSize: 13 } },
  { text: "github.com/ring7a/ctf-workspace", options: { color: "6FC3D6", fontSize: 18, bold: true } },
], { x: 0.9, y: 4.7, w: 11.5, h: 0.5, fontFace: MONO, isTextBox: true, margin: 0 });

pres.writeFile({ fileName: "docs/CTF-Workspace-Deck.pptx" }).then((f) => console.log("wrote", f));
