# tools/volatility — Volatility 3 하네스

메모리 이미지(`.vmem`/`.vmss`, `.raw`, `.lime`, `.dmp`, `.elf` 코어, hiberfil)는 **문자열 카빙보다
Volatility 3를 먼저** 돌린다. 이 폴더는 실행 래퍼·추가 심볼·커스텀 플러그인·리눅스 심볼 생성
스크립트를 한곳에 모아 두어, 어떤 에이전트(Claude/Codex)든 같은 명령으로 재현할 수 있게 한다.
운용 절차와 판단 기준은 [ctf-forensics/memory-volatility.md](../../.claude/skills/ctf-forensics/memory-volatility.md)에 있다.

```
tools/volatility/
├─ vol.ps1          호스트(Windows) 래퍼 — 포터블 vol.exe + 이 폴더의 symbols/·plugins/ 자동 전달
├─ vol.sh           ubuntu-ctf 래퍼 — venv의 volatility3 + symbols/·plugins/
├─ bin/             (gitignore) 포터블 volatility3-win-exes-*.zip 을 풀어 둔다. 또는 $env:CTF_VOL_EXE
├─ symbols/         ISF (.json / .json.xz). linux/ 아래에 생성한 커널 심볼을 쌓는다 → symbols/README.md
├─ plugins/         커스텀 플러그인
│   └─ keyring.py   keyring.Keyring — 커널 키링(key_serial_tree) 순회, logon/user 키 payload 덤프 (LUKS2 볼륨키 회수)
└─ scripts/         리눅스 ISF 생성·보조 (호스트 venv: requirements-host.txt / ubuntu-ctf venv 양쪽에서 동작)
    ├─ extract_vmdk_files.py   vmdk/raw 디스크의 ext 파티션에서 파일 추출(마운트 불필요) — /boot/* 등
    ├─ unpack_vmlinuz.py       vmlinuz(gzip/zstd/xz) → vmlinux ELF
    ├─ extract_btf.py          vmlinux ELF → .BTF 섹션 (DWARF 유무도 알려줌)
    ├─ btf2isf.py              .BTF + System.map (+ELF로 linux_banner) → ISF 6.2.0
    ├─ isf_finalize.py         전역 변수 타입 지정 + 커널 6.12/6.18 구조 변경 보정 (idempotent)
    └─ luks2_decrypt.py        LUKS2 헤더 파싱·볼륨키 digest 검증·AES-XTS 복호 (cryptsetup 없이)
```

## 실행

```powershell
# 호스트 (Windows). 포터블 빌드는 https://github.com/volatilityfoundation/volatility3/releases 의 volatility3-win-exes-<ver>.zip
$env:CTF_VOL_EXE = 'C:\path\to\volatility3-win-exes-2.28.2\vol.exe'      # 또는 tools\volatility\bin\vol.exe 로 복사
powershell -NoProfile -File tools\volatility\vol.ps1 -f <image> banners.Banners
powershell -NoProfile -File tools\volatility\vol.ps1 -o <challenge>\work\vol -f <image> linux.pslist
```
```bash
# ubuntu-ctf (venv에 volatility3 고정 버전 포함)
wsl -d ubuntu-ctf bash -lc 'bash /mnt/e/_/Orca/Projects/ctf-workspace/tools/volatility/vol.sh -f /mnt/e/.../mem.raw linux.pslist'
```

호스트 실행이 허용되는 이유: 메모리 덤프는 실행 파일이 아니라 데이터이고 Volatility는 읽기만 한다.
단, `dumpfiles`·`malfind --dump`·`proc.Maps --dump`처럼 덤프에서 **바이너리를 꺼내는** 출력은 챌린지
`work/` 아래 전용 폴더(`-o`)로만 쓰고, 꺼낸 파일은 호스트에서 열거나 실행하지 않는다(필요하면 ubuntu-ctf에서).

## 리눅스 ISF가 없을 때 (10분 안에 끝내는 순서)

1. `banners.Banners` → 배너 문자열 확보.
2. 공개 ISF: `--remote-isf-url https://github.com/Abyss-W4tcher/volatility3-symbols/raw/master/banners/banners.json`
   (Ubuntu/Debian/Kali/Alma/Rocky). 맞으면 끝. 받은 파일을 `symbols/linux/`에 복사해 둔다.
3. 배포판 디버그 커널(`linux-image-*-dbg`, `kernel-debuginfo`)이 있으면 `dwarf2json linux --elf vmlinux --system-map System.map`.
4. **둘 다 없으면(Alpine, 자체 빌드 커널 등) BTF 경로**: 함께 제공된 디스크 이미지에서 커널을 꺼낸다.
   ```bash
   python -I tools/volatility/scripts/extract_vmdk_files.py disk.vmdk work/sym "/boot/*"
   python -I tools/volatility/scripts/unpack_vmlinuz.py work/sym/boot__vmlinuz-virt work/sym/vmlinux.elf
   python -I tools/volatility/scripts/extract_btf.py   work/sym/vmlinux.elf work/sym/vmlinux.btf     # CONFIG_DEBUG_INFO_BTF=y 필요
   python -I tools/volatility/scripts/btf2isf.py work/sym/vmlinux.btf work/sym/boot__System.map-<ver> tools/volatility/symbols/linux/<distro>-<ver>.json work/sym/vmlinux.elf
   python -I tools/volatility/scripts/isf_finalize.py tools/volatility/symbols/linux/<distro>-<ver>.json <CONFIG_NR_CPUS>
   ```
   플러그인이 `Symbol X has no associated type` 으로 죽으면 `isf_finalize.py`의 GLOBALS에 그 심볼의 타입을 한 줄 추가하고 다시 실행한다.
5. ISF JSON을 편집하는 동안 `vol`을 동시에 돌리지 말 것 — 부분 기록을 읽어 "symbol table requirement not fulfilled"가 난다.
