"""extract_btf.py - save the .BTF section of a (stripped) vmlinux ELF to a file for btf2isf.py.
usage: extract_btf.py <vmlinux.elf> <out.btf>
Also prints whether DWARF is present (then prefer dwarf2json) and the kernel banner if .rodata holds one.
"""
import re
import sys

from elftools.elf.elffile import ELFFile

src, out = sys.argv[1], sys.argv[2]
f = ELFFile(open(src, 'rb'))
names = [s.name for s in f.iter_sections()]
print('sections:', ', '.join(n for n in names if n))
print('DWARF present:', '.debug_info' in names, ' BTF present:', '.BTF' in names)
btf = f.get_section_by_name('.BTF')
if btf is None:
    sys.exit('no .BTF section: kernel built without CONFIG_DEBUG_INFO_BTF; need DWARF/dbg package instead')
data = btf.data()
open(out, 'wb').write(data)
print(f'wrote {out} ({len(data)} bytes, magic {data[:2].hex()})')
rod = f.get_section_by_name('.rodata')
if rod:
    m = re.search(rb'Linux version [0-9][^\x00]{0,200}', rod.data())
    if m:
        print('banner:', m.group().decode('latin-1').strip())
