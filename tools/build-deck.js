// CTF Workspace — project deck generator (pptxgenjs).
// Focus: concept, architecture, download/install, usage flow, skills,
// adding more skill repos, tooling, and how to keep it updated.
// Build:  cd <repo> && npm install pptxgenjs && node tools/build-deck.js
// Output: docs/CTF-Setup-Deck.pptx  (gitignored — a local build artifact)
const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "CTF Team";
pres.title = "CTF Workspace — Claude Code + Codex";

// ---- palette ----
const BG = "0B1221";
const PANEL = "132038";
const CARD = "182742";
const CARD2 = "1E3250";
const CY = "34D3E6";
const CY_DK = "1B8FA0";
const AMBER = "F5B942";
const GREEN = "5AD19A";
const TXT = "EAF1FB";
const MUTED = "9DB0CC";
const LINE = "273B5C";

const HF = "Calibri";
const BFACE = "Calibri";

pres.defineSlideMaster({
  title: "DARK",
  background: { color: BG },
  objects: [
    { text: { text: "CTF Workspace · Claude Code + Codex", options: {
      x: 0.5, y: 7.05, w: 9, h: 0.35, fontFace: BFACE, fontSize: 9, color: MUTED, align: "left", isTextBox: true } } },
  ],
  slideNumber: { x: 12.5, y: 7.05, w: 0.6, h: 0.35, fontFace: BFACE, fontSize: 9, color: MUTED },
});

// ---- helpers ----
function title(slide, t, sub) {
  slide.addText(t, { x: 0.6, y: 0.42, w: 12.1, h: 0.7, fontFace: HF, fontSize: 28, bold: true, color: TXT, align: "left", isTextBox: true, margin: 0 });
  slide.addShape(pres.ShapeType.rect, { x: 0.6, y: 0.4, w: 0.12, h: 0.12, fill: { color: CY } });
  if (sub) slide.addText(sub, { x: 0.6, y: 1.06, w: 12.1, h: 0.4, fontFace: BFACE, fontSize: 13, color: MUTED, align: "left", isTextBox: true, margin: 0 });
}
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || CARD }, line: { color: LINE, width: 1 } });
}
function badge(slide, x, y, label, col) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: 0.46, h: 0.46, fill: { color: col || CY } });
  slide.addText(label, { x, y, w: 0.46, h: 0.46, fontFace: HF, fontSize: 15, bold: true, color: BG, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
function chip(slide, x, y, w, label, col) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h: 0.34, rectRadius: 0.17, fill: { color: CARD2 }, line: { color: col || CY_DK, width: 1 } });
  slide.addText(label, { x, y, w, h: 0.34, fontFace: BFACE, fontSize: 10.5, color: col || CY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
// cardTitle + body bullets inside a card
function cardText(slide, x, y, w, head, lines, headCol) {
  slide.addText(head, { x: x + 0.22, y: y + 0.14, w: w - 0.44, h: 0.38, fontFace: HF, fontSize: 14.5, bold: true, color: headCol || TXT, isTextBox: true, margin: 0 });
  const runs = lines.map((t, i) => ({ text: t, options: { bullet: { code: "2022", indent: 12 }, color: MUTED, fontSize: 11, breakLine: true, paraSpaceAfter: 3 } }));
  slide.addText(runs, { x: x + 0.22, y: y + 0.56, w: w - 0.44, h: 1.6, fontFace: BFACE, isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.02 });
}
function codeBox(slide, x, y, w, h, lines) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.05, fill: { color: "0E1A30" }, line: { color: LINE, width: 1 } });
  const runs = lines.map((t) => ({ text: t, options: { color: t.startsWith("#") ? MUTED : CY, fontSize: 11, breakLine: true, paraSpaceAfter: 2 } }));
  slide.addText(runs, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: h - 0.24, fontFace: "Consolas", isTextBox: true, margin: 0, valign: "top" });
}

// =================================================================
// 1 — Title
// =================================================================
let s = pres.addSlide({ masterName: "DARK" });
s.addShape(pres.ShapeType.rect, { x: 0.6, y: 2.0, w: 0.7, h: 0.14, fill: { color: CY } });
s.addText("CTF Workspace", { x: 0.6, y: 2.25, w: 12, h: 1.0, fontFace: HF, fontSize: 46, bold: true, color: TXT, isTextBox: true, margin: 0 });
s.addText("Claude Code + Codex 기반 재현 가능한 CTF 분석 환경", { x: 0.6, y: 3.35, w: 12, h: 0.6, fontFace: HF, fontSize: 23, color: CY, isTextBox: true, margin: 0 });
s.addText([
  { text: "한 번 clone + 스크립트 한 줄로 동일한 격리 분석 환경이 재현됩니다.", options: { fontSize: 14, color: TXT, breakLine: true } },
  { text: "github.com/ring7a/ctf-workspace", options: { fontSize: 13, color: AMBER } },
], { x: 0.6, y: 4.3, w: 12, h: 0.9, fontFace: BFACE, isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
s.addText("개념 · 아키텍처 · 설치 · 사용 · 툴링 · 확장", { x: 0.6, y: 6.2, w: 12, h: 0.4, fontFace: BFACE, fontSize: 11, italic: true, color: MUTED, isTextBox: true, margin: 0 });

// =================================================================
// 2 — Concept
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "개념 — 무엇이고 왜 쓰는가", "CTF 팀을 위한 재현 가능·격리·규율·협업형 분석 워크스페이스");
const c2 = [
  ["재현성", GREEN, ["git clone + setup 스크립트 1회로 동일 환경", "동결된 패키지 집합 + 핀 고정 커밋", "머신/단말기 간 git pull 로 동기화"]],
  ["격리", CY, ["신뢰 못 할 바이너리는 WSL ubuntu-ctf 안에서만 실행", "호스트는 건드리지 않음", "원본은 untrusted/, 작업은 work/"]],
  ["규율", AMBER, ["가설 1개 → 최소 실험 → NOTES 기록", "15분 룰: 진전 없으면 접근 전환", "solve-challenge 디스패처로 분류·라우팅"]],
  ["협업", CY, ["공개 git 리포로 팀 공유 (플래그는 비공개)", "Codex 2차 의견·코드 리뷰", "verifier 가 포맷 검증, 제출은 사람이"]],
];
let cx = 0.6, cw = 2.95, gap = 0.17;
c2.forEach((it, i) => {
  const x = cx + i * (cw + gap);
  card(s, x, 1.7, cw, 4.3, CARD);
  s.addShape(pres.ShapeType.rect, { x: x, y: 1.7, w: cw, h: 0.1, fill: { color: it[1] } });
  cardText(s, x, 1.85, cw, it[0], it[2], it[1]);
});

// =================================================================
// 3 — Architecture
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "아키텍처", "분석 지능(Claude + Codex) · 격리 실행(WSL) · 재현 자산(git) 의 분리");
// top: git repo
card(s, 0.6, 1.65, 12.1, 0.95, PANEL);
s.addText("공개 Git 리포  ·  github.com/ring7a/ctf-workspace", { x: 0.85, y: 1.78, w: 8, h: 0.4, fontFace: HF, fontSize: 15, bold: true, color: TXT, isTextBox: true, margin: 0 });
s.addText("규칙 · 스킬 · 에이전트 · 설정 · 툴링 스크립트 · 문서 (events/* 와 플래그는 ignore)", { x: 0.85, y: 2.2, w: 11.6, h: 0.35, fontFace: BFACE, fontSize: 11.5, color: MUTED, isTextBox: true, margin: 0 });
// three columns
const col = [
  ["Claude Code", CY, ["CLAUDE.md 운영 규칙", ".claude/skills — 벤더된 11개 CTF 스킬", ".claude/agents — triager·solver·verifier"]],
  ["Codex (2차 모델)", AMBER, ["tools/codex-crosscheck.sh", "독립 의견: codex exec (read-only)", "코드 리뷰: codex review --uncommitted"]],
  ["WSL ubuntu-ctf (격리)", GREEN, ["~/.ctf-tools/venv — Python 3.12 툴체인", "gdb·radare2·binwalk·Docker 등", "untrusted 바이너리는 여기서만 실행"]],
];
col.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 2.85, 3.97, 2.55, CARD);
  s.addShape(pres.ShapeType.rect, { x, y: 2.85, w: 3.97, h: 0.1, fill: { color: it[1] } });
  cardText(s, x, 3.0, 3.97, it[0], it[2], it[1]);
});
// bottom: events
card(s, 0.6, 5.6, 12.1, 0.75, CARD2);
s.addText([
  { text: "events/<대회>/ ", options: { color: TXT, bold: true, fontSize: 12 } },
  { text: " — 대회별 챌린지 데이터·NOTES·플래그. git 추적 제외(gitignore), 머신 로컬 유지.", options: { color: MUTED, fontSize: 12 } },
], { x: 0.85, y: 5.75, w: 11.6, h: 0.45, fontFace: BFACE, isTextBox: true, margin: 0, valign: "middle" });

// =================================================================
// 4 — Download & install
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "다운로드 & 설치", "새 머신에서: clone → 스크립트 1개 → 완료 (재현 가능)");
const steps = [
  ["리포 clone", ["git clone 로 공개 리포를 받는다", "폴더명은 자유 (원격은 영향 없음)"]],
  ["setup 스크립트 실행", ["pwsh tools\\wsl\\setup-ubuntu-ctf.ps1", "ubuntu-ctf 배포판 생성 + 프로비저닝"]],
  ["자동 프로비저닝", ["uv + Python 3.12 venv 생성", "동결 requirements + apt 시스템 툴 설치", "로그인 셸에 venv 자동 활성화"]],
  ["Codex 로그인(1회)", ["codex 로그인(ChatGPT) 확인", "이후 codex-crosscheck.sh 바로 사용"]],
];
steps.forEach((it, i) => {
  const y = 1.75 + i * 1.18;
  badge(s, 0.7, y + 0.18, String(i + 1));
  card(s, 1.4, y, 11.3, 1.02, CARD);
  s.addText(it[0], { x: 1.65, y: y + 0.1, w: 4.2, h: 0.5, fontFace: HF, fontSize: 15, bold: true, color: CY, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(it[1].map((t) => ({ text: t, options: { bullet: { code: "2022" }, color: MUTED, fontSize: 11, breakLine: true } })),
    { x: 5.4, y: y + 0.08, w: 7.1, h: 0.86, fontFace: BFACE, isTextBox: true, margin: 0, valign: "middle" });
});
// =================================================================
// 5 — Usage flow (per event / per challenge)
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "사용 플로우", "대회 시작 → 문제별 반복 루프 → 검증·제출");
// intake banner
card(s, 0.6, 1.65, 12.1, 0.8, PANEL);
s.addText("① 대회 시작 — Pre-CTF 인테이크", { x: 0.85, y: 1.72, w: 11, h: 0.3, fontFace: HF, fontSize: 13, bold: true, color: AMBER, isTextBox: true, margin: 0 });
s.addText("docs/PRE-CTF-INTAKE.md 로 플래그 포맷·범위·AI 도구 규정을 먼저 확인해 events/<대회>/NOTES.md 에 기록 (블로킹 항목 확정 전 풀이 금지)",
  { x: 0.85, y: 2.04, w: 11.6, h: 0.35, fontFace: BFACE, fontSize: 11, color: MUTED, isTextBox: true, margin: 0 });
// loop steps
const loop = [
  ["recon / 분류", "solve-challenge 디스패처가 카테고리 판별 → 해당 스킬로 라우팅"],
  ["가설 1개", "익스플로잇 돌리기 전에 가설을 하나만 세운다"],
  ["최소 실험", "가장 작은 실험으로 검증 (WSL 격리 환경에서)"],
  ["NOTES 기록", "사실/반증/다음 단계를 challenge NOTES.md 에 남김"],
  ["15분 룰 / Codex", "진전 없으면 접근 전환 + codex-crosscheck 로 2차 의견"],
  ["검증 · 제출", "verifier 가 포맷·재현 확인 → 사람이 제출 (자동 제출 없음)"],
];
loop.forEach((it, i) => {
  const xcol = i % 2, yrow = Math.floor(i / 2);
  const x = 0.6 + xcol * 6.15, y = 2.65 + yrow * 1.25;
  card(s, x, y, 5.95, 1.1, CARD);
  badge(s, x + 0.18, y + 0.32, String(i + 1), i >= 4 ? AMBER : CY);
  s.addText(it[0], { x: x + 0.8, y: y + 0.12, w: 5.0, h: 0.4, fontFace: HF, fontSize: 14, bold: true, color: TXT, isTextBox: true, margin: 0 });
  s.addText(it[1], { x: x + 0.8, y: y + 0.5, w: 5.0, h: 0.5, fontFace: BFACE, fontSize: 10.5, color: MUTED, isTextBox: true, margin: 0 });
});

// =================================================================
// 6 — Skills system
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "스킬 시스템", "벤더된 CTF 스킬이 분류·기법을 제공 — 디스패처가 올바른 스킬로 보냄");
const skills = ["ctf-web", "ctf-pwn", "ctf-crypto", "ctf-reverse", "ctf-forensics", "ctf-malware", "ctf-osint", "ctf-misc", "ctf-ai-ml", "solve-challenge", "ctf-writeup"];
skills.forEach((k, i) => {
  const xcol = i % 4, yrow = Math.floor(i / 4);
  const x = 0.6 + xcol * 3.07, y = 1.75 + yrow * 0.95;
  card(s, x, y, 2.9, 0.78, CARD);
  const isMeta = k === "solve-challenge" || k === "ctf-writeup";
  s.addText(k, { x: x + 0.18, y: y + 0.08, w: 2.6, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: isMeta ? AMBER : CY, isTextBox: true, margin: 0 });
  s.addText(isMeta ? (k === "solve-challenge" ? "디스패처 / recon" : "풀이 writeup") : "카테고리 기법", { x: x + 0.18, y: y + 0.42, w: 2.6, h: 0.28, fontFace: BFACE, fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
});
card(s, 0.6, 4.75, 12.1, 1.5, PANEL);
cardText(s, 0.6, 4.78, 12.1, "출처와 무결성", [
  "github.com/ljagiello/ctf-skills 를 핀 고정 커밋(c332c7b)으로 벤더링 — 스킬 11종 · 문서 124개",
  "각 스킬은 SKILL.md + 하위 기법 문서 구조. 서브에이전트: triager(분류) · solver(단일 문제) · verifier(검증)",
  "tools/vendor-ctf-skills/scripts/skill_security_auditor.py 로 보안 감사 후 커밋",
], TXT);

// =================================================================
// 7 — Adding more skill repos
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "스킬 레포 더 추가하기", "ctf-skills 외에도 좋은 스킬 모음을 같은 방식으로 벤더링");
const add = [
  ["어디서 찾나", ["Anthropic 공식 스킬 모음", "커뮤니티 \"awesome Claude / skills\" 모음", "다른 CTF 스킬 컬렉션 리포", "핵심: SKILL.md 구조 + 신뢰 가능한 출처"]],
  ["어떻게 벤더링", ["해당 리포를 핀 고정 커밋으로 clone", "스킬 디렉터리를 .claude/skills/ 로 복사", "원본·LICENSE·핀 커밋을 tools/vendor-*/ 에 보존", "skill_security_auditor.py 로 감사 후 커밋"]],
  ["주의할 점", ["스킬은 Claude 가 따르는 '지시'다 — 출처 신뢰 필수", "버전은 핀 고정 (재현성·감사 가능성)", "이름 충돌 피하고, CLAUDE.md 라우팅에 반영", "라이선스 확인"]],
];
add.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 1.7, 3.97, 3.5, CARD);
  s.addShape(pres.ShapeType.rect, { x, y: 1.7, w: 3.97, h: 0.1, fill: { color: i === 2 ? AMBER : CY } });
  cardText(s, x, 1.85, 3.97, it[0], it[1], i === 2 ? AMBER : CY);
});
codeBox(s, 0.6, 5.5, 12.1, 0.95, [
  "# 패턴: 핀 고정 clone → 스킬 복사 → 감사 → 커밋 (ctf-skills 를 넣은 방식과 동일)",
  "git clone --depth 1 <skill-repo> && cp -r <repo>/<skill> .claude/skills/",
]);

// =================================================================
// 8 — Tooling
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "구성된 툴링", "WSL ubuntu-ctf 안에 분석 전 카테고리용 도구가 준비됨");
const tool = [
  ["Python venv (~/.ctf-tools/venv)", CY, ["pwntools (asm/shellcraft, 원격 익스플로잇)", "angr · unicorn · capstone · keystone", "z3 · sympy · gmpy2 · fpylll (격자)", "volatility3 · scapy · pefile · yara", "ropper · ROPgadget · hlextend · sgp4"]],
  ["시스템 도구", GREEN, ["gdb 17.1 + gdb-multiarch (ARM/MIPS)", "radare2 6.0.7 · binwalk · nc", "objdump · readelf · nm · strings · file", "Docker 29.1 (챌린지 컨테이너용)"]],
  ["협업 · 재현", AMBER, ["Codex CLI — 독립 의견 / 코드 리뷰", "uv — 결정적 venv 구성", "frozen requirements (핀 고정 버전)", "setup/provision 스크립트로 1커맨드 재현"]],
];
tool.forEach((it, i) => {
  const x = 0.6 + i * (3.97 + 0.1);
  card(s, x, 1.7, 3.97, 4.3, CARD);
  s.addShape(pres.ShapeType.rect, { x, y: 1.7, w: 3.97, h: 0.1, fill: { color: it[1] } });
  cardText(s, x, 1.85, 3.97, it[0], it[2], it[1]);
});

// =================================================================
// 9 — Keeping it updated
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "업데이트 & 유지", "스킬·툴체인을 안전하게 갱신하고 팀과 동기화");
const upd = [
  ["스킬 갱신", ["ctf-skills 를 더 최신 핀 커밋으로 재벤더링", "setup.ps1 이 재현을 돕는다"]],
  ["툴체인 갱신", ["tools/wsl/ctf-venv-requirements.txt 에 패키지 추가/핀", "ubuntu-ctf 재프로비저닝으로 반영"]],
  ["동기화", ["git pull 로 다른 머신/단말기와 동기화", "메모리는 머신 로컬 — 리포로는 안 따라감"]],
  ["공개 리포 위생", ["events/* 는 ignore — 플래그·챌린지 데이터 절대 커밋 금지", "blanket add 대신 특정 경로만 git add"]],
];
upd.forEach((it, i) => {
  const xcol = i % 2, yrow = Math.floor(i / 2);
  const x = 0.6 + xcol * 6.15, y = 1.75 + yrow * 2.1;
  card(s, x, y, 5.95, 1.9, CARD);
  s.addShape(pres.ShapeType.rect, { x, y, w: 0.1, h: 1.9, fill: { color: i === 3 ? AMBER : CY } });
  cardText(s, x + 0.05, y, 5.9, it[0], it[1], i === 3 ? AMBER : CY);
});

// =================================================================
// 10 — Why it's good (benefits)
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "이 프로젝트의 이점", "왜 이렇게 세팅해두면 좋은가");
const ben = [
  ["빠른 출발", "스킬 + 툴체인이 미리 준비 — 대회 시작하자마자 분석"],
  ["안전", "신뢰 못 할 바이너리를 격리 환경에서만 실행 (호스트 보호)"],
  ["재현성", "새 팀원·새 머신도 clone + 1스크립트로 동일 환경"],
  ["일관된 품질", "가설→실험→기록 규율 + 15분 룰로 터널링 방지"],
  ["교차 검증", "Codex 2차 의견으로 편향·실수 감소"],
  ["팀 공유", "공개 git 로 공유하되 플래그·풀이는 비공개 유지"],
];
ben.forEach((it, i) => {
  const xcol = i % 3, yrow = Math.floor(i / 3);
  const x = 0.6 + xcol * 4.07, y = 1.8 + yrow * 2.2;
  card(s, x, y, 3.9, 2.0, CARD);
  badge(s, x + 0.2, y + 0.22, String(i + 1), i % 2 ? AMBER : CY);
  s.addText(it[0], { x: x + 0.8, y: y + 0.22, w: 2.95, h: 0.45, fontFace: HF, fontSize: 15, bold: true, color: TXT, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(it[1], { x: x + 0.22, y: y + 0.85, w: 3.5, h: 1.0, fontFace: BFACE, fontSize: 11.5, color: MUTED, isTextBox: true, margin: 0, valign: "top" });
});

// =================================================================
// 11 — References / pointers
// =================================================================
s = pres.addSlide({ masterName: "DARK" });
title(s, "참고 포인터", "더 깊이 들어갈 때 보는 파일들");
const refs = [
  ["CLAUDE.md", "운영 규칙 (워크플로·15분 룰·플래그·Codex)"],
  ["AGENTS.md", "Codex 가 따르는 동일 규칙 미러"],
  ["docs/BOOTSTRAP.md", "개념 + 새 환경에서 재구축하는 법"],
  ["docs/WORKLOG.md", "날짜별 전체 구축 이력"],
  ["docs/PRE-CTF-INTAKE.md", "대회 시작 시 물어볼 인테이크 질문"],
  ["tools/wsl/*", "setup-ubuntu-ctf.ps1 · provision · frozen reqs"],
  ["tools/codex-crosscheck.sh", "Codex 독립 의견 / 코드 리뷰"],
  ["tools/vendor-ctf-skills/", "스킬 출처·핀 커밋·보안 감사 스크립트"],
];
refs.forEach((it, i) => {
  const xcol = i % 2, yrow = Math.floor(i / 2);
  const x = 0.6 + xcol * 6.15, y = 1.75 + yrow * 1.1;
  card(s, x, y, 5.95, 0.95, CARD);
  s.addText(it[0], { x: x + 0.22, y: y + 0.12, w: 5.5, h: 0.38, fontFace: "Consolas", fontSize: 13, bold: true, color: CY, isTextBox: true, margin: 0 });
  s.addText(it[1], { x: x + 0.22, y: y + 0.5, w: 5.5, h: 0.35, fontFace: BFACE, fontSize: 11, color: MUTED, isTextBox: true, margin: 0 });
});
s.addText("github.com/ring7a/ctf-workspace", { x: 0.6, y: 6.5, w: 12, h: 0.4, fontFace: BFACE, fontSize: 13, bold: true, color: AMBER, isTextBox: true, margin: 0 });

pres.writeFile({ fileName: "docs/CTF-Setup-Deck.pptx" }).then((f) => console.log("wrote", f));
