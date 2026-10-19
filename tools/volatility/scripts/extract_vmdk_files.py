"""extract_vmdk_files.py - pull files out of a VMDK / raw disk image's ext2/3/4 partitions, read-only,
without mounting (pure Python: dissect.hypervisor + dissect.volume + dissect.extfs).

usage:
  extract_vmdk_files.py <image.vmdk|image.raw> <outdir> <path> [<path> ...]
     <path>  absolute path inside *any* ext partition, e.g. /boot/vmlinuz-virt  /etc/fstab
             a trailing '/*' saves every regular file in that directory, e.g. /boot/*
  extract_vmdk_files.py <image> --ls <dir>          list a directory on every ext partition

Saved names flatten the path: /root/.ash_history -> root__.ash_history
Typical first call for a Linux memory case (kernel + System.map + config for ISF building):
  extract_vmdk_files.py disk.vmdk out /boot/*
"""
import os
import stat
import sys

from dissect.extfs import ExtFS
from dissect.volume import disk as vdisk


def open_image(path):
    fh = open(path, 'rb')
    head = fh.read(4)
    fh.seek(0)
    if head in (b'KDMV', b'# Di') or path.lower().endswith('.vmdk'):
        from dissect.hypervisor.disk import vmdk
        return vmdk.VMDK(fh)
    return fh


def ext_partitions(img):
    d = vdisk.Disk(img)
    for i, p in enumerate(d.partitions):
        try:
            yield i, p, ExtFS(p.open())
        except Exception:
            continue


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    img = open_image(sys.argv[1])
    parts = list(ext_partitions(img))
    print(f'ext partitions: {[(i, p.offset, p.size) for i, p, _ in parts]}')
    if sys.argv[2] == '--ls':
        for i, p, fs in parts:
            try:
                names = [e.filename for e in fs.get(sys.argv[3]).iterdir()]
                print(f'part{i} {sys.argv[3]}: {names}')
            except Exception as e:
                print(f'part{i}: {e}')
        return
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    for want in sys.argv[3:]:
        found = False
        for i, p, fs in parts:
            try:
                if want.endswith('/*'):
                    d = fs.get(want[:-2] or '/')
                    for e in d.iterdir():
                        if e.filetype == stat.S_IFREG:
                            data = e.open().read()
                            name = (want[:-2].strip('/') + '/' + e.filename).replace('/', '__')
                            open(os.path.join(outdir, name), 'wb').write(data)
                            print(f'part{i} {want[:-2]}/{e.filename} -> {name} ({len(data)} B)')
                    found = True
                else:
                    e = fs.get(want)
                    data = e.open().read()
                    name = want.strip('/').replace('/', '__')
                    open(os.path.join(outdir, name), 'wb').write(data)
                    print(f'part{i} {want} -> {name} ({len(data)} B)')
                    found = True
            except Exception:
                continue
        if not found:
            print(f'MISSING {want}')


if __name__ == '__main__':
    main()
