import sys, gzip, zlib, io, lzma
import zstandard
src, out = sys.argv[1], sys.argv[2]
b = open(src,'rb').read()
cands = []
for magic, name in [(b'\x1f\x8b\x08','gzip'),(b'\x28\xb5\x2f\xfd','zstd'),(b'\xfd7zXZ\x00','xz'),(b'\x5d\x00\x00','lzma'),(b'\x02!L\x18','lz4'),(b'BZh','bzip2')]:
    i = b.find(magic)
    while i != -1 and len(cands) < 50:
        cands.append((i, name)); i = b.find(magic, i+1)
cands.sort()
print("candidates:", cands[:20])
for off, name in cands:
    try:
        if name == 'gzip':
            d = zlib.decompressobj(16+zlib.MAX_WBITS); data = d.decompress(b[off:])
        elif name == 'zstd':
            data = zstandard.ZstdDecompressor().decompressobj().decompress(b[off:])
        elif name == 'xz':
            data = lzma.LZMADecompressor().decompress(b[off:])
        else:
            continue
        if data[:4] == b'\x7fELF':
            open(out,'wb').write(data); print(f"OK {name} @0x{off:x} -> ELF {len(data)} bytes"); break
        else:
            print(f"{name}@0x{off:x}: not ELF ({data[:4]!r}, {len(data)})")
    except Exception as e:
        print(f"{name}@0x{off:x}: fail {type(e).__name__}: {str(e)[:60]}")
