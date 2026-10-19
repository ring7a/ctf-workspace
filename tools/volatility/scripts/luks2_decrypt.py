"""luks2_decrypt.py - verify a recovered LUKS2 volume key against the header digest and decrypt the data
segment (aes-xts-plain64) without cryptsetup.  Pure Python (cryptography).  Windows friendly.
usage: luks2_decrypt.py <vault.img> <volume_key.bin> <out_plain.img>
"""
import sys, json, struct, hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

img_path, key_path, out_path = sys.argv[1:4]
img = open(img_path, 'rb')
hdr = img.read(4096)
assert hdr[:6] == b'LUKS\xba\xbe', hdr[:6]
version = struct.unpack('>H', hdr[6:8])[0]
hdr_size = struct.unpack('>Q', hdr[8:16])[0]
uuid = hdr[0xa8:0xa8 + 40].split(b'\0')[0].decode()
img.seek(4096)
js = img.read(hdr_size - 4096).split(b'\0', 1)[0].decode()
meta = json.loads(js)
print('LUKS2 version', version, 'hdr_size', hdr_size, 'uuid', uuid)
seg = meta['segments']['0']
dig = meta['digests']['0']
ks = meta['keyslots']['0']
print('segment:', seg)
print('digest :', {k: dig[k] for k in dig if k not in ('salt', 'digest')})
print('keyslot0 kdf:', ks.get('kdf'), 'key_size', ks.get('key_size'), 'af', ks.get('af'))

key = open(key_path, 'rb').read()
print('volume key', len(key), 'bytes:', key.hex())

# 1) verify key against digest (pbkdf2-sha256 of the volume key with header salt)
assert dig['type'] == 'pbkdf2' and dig['hash'] == 'sha256'
salt = base64.b64decode(dig['salt'])
expect = base64.b64decode(dig['digest'])
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=len(expect), salt=salt, iterations=int(dig['iterations']))
got = kdf.derive(key)
print('digest expected', expect.hex())
print('digest computed', got.hex())
if got != expect:
    print('!! KEY DOES NOT MATCH HEADER DIGEST'); sys.exit(2)
print('OK: recovered key matches LUKS2 digest -> this is the genuine volume key')

# 2) decrypt the segment
assert seg['encryption'] == 'aes-xts-plain64', seg['encryption']
sector = int(seg['sector_size'])
offset = int(seg['offset'])
img.seek(0, 2); total = img.tell()
size = total - offset if seg['size'] == 'dynamic' else int(seg['size'])
print('data offset', offset, 'size', size, 'sector', sector)
# dm-crypt plain64: IV = little-endian 64-bit *512-byte* sector number, zero padded to 16 bytes.
# dm-crypt only shifts to sector_size units when the 'iv_large_sectors' flag is set (not set here).
# Verified empirically: with the 4096-index the GDT block decrypts to garbage, with the 512-index
# group descriptor 0 reads block_bitmap=3, inode_bitmap=19, inode_table=35.
img.seek(offset)
out = open(out_path, 'wb')
n = size // sector
iv_step = sector // 512
for i in range(n):
    ct = img.read(sector)
    tweak = struct.pack('<Q', i * iv_step) + b'\0' * 8
    dec = Cipher(algorithms.AES(key), modes.XTS(tweak)).decryptor()
    out.write(dec.update(ct) + dec.finalize())
out.close()
# 3) sanity: ext4 superblock magic at 0x438
pl = open(out_path, 'rb').read(4096)
magic = struct.unpack('<H', pl[0x438:0x43a])[0]
print('plaintext first 16 bytes:', pl[:16].hex(), ' ext4 magic @0x438 = 0x%04x (%s)' % (magic, 'EXT4 OK' if magic == 0xEF53 else 'not ext4'))
if magic == 0xEF53:
    import uuid as _u
    print('ext4 UUID', _u.UUID(bytes=pl[0x468:0x478]), 'volume name', pl[0x478:0x488].split(b'\0')[0])
