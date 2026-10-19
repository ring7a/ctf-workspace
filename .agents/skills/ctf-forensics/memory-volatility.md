# Memory Forensics — Volatility 3 first (workspace procedure)

> 로컬 추가 문서. upstream `disk-and-memory.md`의 Windows 플러그인 사전을 보완하며, 이 워크스페이스에서
> **메모리 이미지는 문자열 카빙 전에 Volatility 3를 먼저** 돌린다는 운영 규칙의 실행 절차다.
> 실행 래퍼·심볼·플러그인·스크립트는 [tools/volatility/](../../../tools/volatility/README.md)에 있다.

## 0. 왜 "Volatility 먼저"인가

| | strings/grep 카빙 | Volatility (구조체 순회) |
|---|---|---|
| 말해주는 것 | "이 바이트열이 어딘가 있다" | "커널이 그 순간 무엇을 하고 있었다" (프로세스·마운트·키링·소켓) |
| 키 회수 | 후보 전수 탐색 + 검증 루프 | 키를 보관하는 구조체에서 직접 읽음 |
| 오류 양상 | 잔존물·이전 세션 데이터를 현재 상태로 오인 | 심볼이 없으면 아예 안 돌아감 |
| 보고서 | 추정 서술 | 플러그인 이름·오프셋·타임스탬프가 그대로 근거 |

카빙은 잔존물·이전 세션 데이터를 현재 상태로 오인하기 쉽다(예: "볼륨이 마운트돼 있었다"고 단정하지만
`linux.mountinfo`는 미마운트를 보이고, 반포렌식 와이프나 입력 중이던 미실행 명령은 구조체 순회로만 드러난다).
카빙은 **1차 후보 확보**에, Volatility는 **상태 판정과 근거**에 쓴다. 둘을 함께 쓴다.

## 1. 10분 트리아지 (가설 1개씩, NOTES.md에 기록)

```bash
VOL="powershell -NoProfile -File tools/volatility/vol.ps1"      # ubuntu-ctf: bash tools/volatility/vol.sh
$VOL -f mem.img banners.Banners            # Linux: 커널 배너 / Windows: windows.info
$VOL -f mem.img linux.pslist               # 또는 windows.pslist — 무엇이 돌고 있었나 (kcryptd, sshd, 셸…)
$VOL -f mem.img linux.psaux                # 명령줄 — 어떤 인자로
$VOL -f mem.img linux.mountinfo            # 무엇이 마운트돼 있었나 (dm-*, loop, tmpfs, 네트워크 FS)
$VOL -f mem.img linux.lsmod                # dm_crypt, vboxguest, 커스텀 .ko …
$VOL -f mem.img linux.kmsg                 # dmesg — 장치 생성/오류 타임라인
$VOL -f mem.img linux.pagecache.Files      # 메모리에 남은 파일 목록(경로·inode·크기·mtime). 수천 줄 → grep
$VOL -f mem.img linux.sockstat / linux.ip.Addr   # 네트워크 상태
```
VMware `.vmem`은 같은 이름의 `.vmss`/`.vmsn`이 옆에 있으면 자동으로 레이어를 잡는다. `.vmx`의
`checkpoint.vmState`·`memsize`로 "서스펜드(전원 유지) 확보"인지 먼저 확인하고 기록한다.

## 2. 질문 → 플러그인 매핑

| 질문 | 플러그인 | 메모 |
|---|---|---|
| 사용자가 무엇을 쳤나 | `linux.bash` (bash만) → 비어 있으면 **셸 PID의 `linux.proc.Maps --pid N --dump`** 후 힙·.data 덤프를 strings | busybox ash/zsh/fish는 `linux.bash`가 못 본다. ash 히스토리는 힙에, 편집 중 명령은 .data 라인버퍼에 남는다 |
| 디스크와 메모리 파일 내용이 다른가 | `linux.pagecache.Files` → `linux.pagecache.InodePages --inode <addr> --dump` | 플래그에 `dirty`가 있으면 디스크에 아직 안 쓰인 내용 |
| 열린 파일/소켓 | `linux.lsof --pid N`, `linux.sockstat` | |
| 환경변수 | `linux.envars --pid N` | HISTFILE, 토큰 |
| 커널 키링(LUKS 볼륨키, user/logon 키, 커널 서명키) | **`keyring.Keyring --dump`** (로컬 플러그인) | `logon` `cryptsetup:<UUID>-d<n>` = LUKS2 마스터키 64 B |
| dm-crypt/LUKS 매핑 존재 | `linux.pslist`의 `kworker/R-kcryp*`, `dmcrypt_write/*`, `kdmflush`; `pagecache.Files`의 `/dev/mapper/<name>`, `/sys/.../block/dm-0` | 마운트 여부는 별도로 `mountinfo`로 |
| 커널 변조/루트킷 | `linux.check_syscall`, `linux.check_modules`, `linux.hidden_modules`, `linux.check_creds` | |
| Windows | `windows.pslist/cmdline/netscan/filescan/dumpfiles/hashdump/registry.*` | upstream `disk-and-memory.md` |
| 프로세스 메모리 안의 비밀 | `linux.proc.Maps --dump` → strings/정규식; Windows `windows.memmap --dump` | 덤프는 `work/` 전용 폴더에만 |

## 3. 리눅스 심볼(ISF) 결정 트리

```
banners.Banners
 ├─ Ubuntu/Debian/Kali/Alma/Rocky → --remote-isf-url .../Abyss-W4tcher/.../banners.json  (받은 json은 tools/volatility/symbols/linux/에 보관)
 ├─ 배포판 -dbg 커널 있음        → dwarf2json linux --elf vmlinux --system-map System.map
 └─ 없음 (Alpine, 커스텀, 최신)   → 디스크 이미지의 /boot에서 vmlinuz·System.map·config 추출
                                    CONFIG_DEBUG_INFO_BTF=y 이면  unpack_vmlinuz → extract_btf → btf2isf → isf_finalize
                                    BTF도 없으면 Volatility 포기, 카빙으로 전환하고 NOTES에 사유 기록 (15분 규칙)
```
`isf_finalize.py`가 해 주는 것: BTF에 없는 전역 변수 타입(`init_task`, `modules`, `mount_hashtable`, `prb`,
`key_serial_tree` …) 지정, 커널 6.12+ `page.index→__folio_index` 별칭, 6.18+ `page.flags` 구조체→정수.
새 커널에서 `Symbol X has no associated type` 이 나오면 GLOBALS 표에 한 줄 추가가 전부다.

## 4. LUKS/dm-crypt 사건 패턴 (대표 예시)

상황: 서스펜드로 확보된 Alpine VM(1 GiB vmem + vmdk). 디스크에 LUKS2 컨테이너, 패스프레이즈는 argon2id(352 MiB)라 무차별 대입 불가.

1. `pslist`: `kworker/R-kcryp*`·`dmcrypt_write/*` → dm-crypt 타깃 활성. `lsmod`: `dm_crypt`,`dm_mod`. `kmsg`: device-mapper 초기화 시각.
2. `mountinfo`: `/dev/mapper/vault` 마운트 **없음** → 열려 있으나 미마운트. `pagecache.Files`: `/dev/mapper/vault` ctime = open 시각, `/mnt/vault` 아래 캐시 0건.
3. `keyring.Keyring --dump` → `logon cryptsetup:<UUID>-d0`, datalen 64 → 볼륨키. 디스크에서 꺼낸 `vault.img` 헤더의 digest(pbkdf2-sha256)로 `luks2_decrypt.py`가 키를 검증하고 복호.
4. 복호 ext4를 `dissect.extfs`로 읽어 파일 획득. (cryptsetup이 있으면 `cryptsetup open --volume-key-file key.bin vault.img v && mount -o ro /dev/mapper/v /mnt/v`)
5. 셸 PID의 `proc.Maps --dump` → 힙에 `cryptsetup open …`, `dd if=/dev/zero of=/zfill`(여유 공간 와이프), .data에 미실행 `cryptsetup close vault` → "닫기 직전 서스펜드" 서사. `.ash_history` 더티 페이지가 디스크 사본보다 한 줄 많음.

함정: dm-crypt `plain64` IV는 섹터 크기가 4096이어도 **512바이트 섹터 번호**로 센다(`iv_large_sectors` 미설정 시).
4096 단위로 계산하면 첫 섹터만 맞고 나머지는 쓰레기가 되어 "플래그가 없다"는 오판으로 이어진다 — GDT 블록이
정상(`block_bitmap=3…`)으로 풀리는지로 확인한다.

## 5. 증거 기록 규칙 (SKILL-INTEGRATION 준수)

- 입력 이미지 MD5/SHA-256, `.vmx`의 suspend 증거, 사용한 ISF 파일명과 생성 명령을 NOTES에 적는다.
- 플러그인 출력은 `work/vol/<plugin>.txt`로 저장하고 핵심 줄만 NOTES에 인용한다. 덤프(`--dump`, `-o`)는 `work/vol/dumps/`.
- 회수한 키·복호 산출물은 SHA-256과 함께 기록하고, 키가 진짜임을 **헤더 digest 일치**로 증명한다(열렸다는 사실만으로 끝내지 않는다).
- Volatility 버전(`vol -h` 첫 줄), ISF 해시, 스크립트 커밋을 라이트업 도구 표에 넣는다.
