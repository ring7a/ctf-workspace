# tools/volatility/symbols

Volatility 3 심볼 디렉터리. `vol.ps1` / `vol.sh`가 `-s`로 자동 전달한다. 하위 폴더는
Volatility 규약(`windows/`, `mac/`, `linux/`)을 따르고 `.json` 또는 `.json.xz`를 둔다.

- Windows 덤프: Volatility가 PDB 심볼을 자동 다운로드하므로 여기 둘 것이 없다.
- Linux 덤프: 커널마다 ISF가 필요하다. 생성 절차는 [../README.md](../README.md) 참조.

| 파일 | 커널 | 출처 | 비고 |
|---|---|---|---|
| `linux/alpine-6.18.35-0-virt.json.xz` | Alpine 3.24.1 `6.18.35-0-virt #1-Alpine` x86_64 | `btf2isf.py` + `isf_finalize.py` (커널 BTF + System.map) | 전역 타입 수동 지정분 포함 |

새 ISF를 추가하면 이 표에 커널 배너·생성 방법을 적는다. 공개 ISF 저장소를 쓸 때는
`--remote-isf-url https://github.com/Abyss-W4tcher/volatility3-symbols/raw/master/banners/banners.json`
를 먹이고, 받아진 파일을 여기에 복사해 오프라인에서도 재현되게 한다.
