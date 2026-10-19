"""btf2isf.py - build a Volatility 3 ISF (schema 6.2.0) from a kernel .BTF blob + System.map
(+ optional vmlinux ELF for linux_banner constant_data).
usage: btf2isf.py <btf.bin> <System.map> <out.json> [vmlinux.elf]
"""
import sys, struct, json, hashlib, base64

BTF_KIND = {1: 'INT', 2: 'PTR', 3: 'ARRAY', 4: 'STRUCT', 5: 'UNION', 6: 'ENUM', 7: 'FWD', 8: 'TYPEDEF',
            9: 'VOLATILE', 10: 'CONST', 11: 'RESTRICT', 12: 'FUNC', 13: 'FUNC_PROTO', 14: 'VAR',
            15: 'DATASEC', 16: 'FLOAT', 17: 'DECL_TAG', 18: 'TYPE_TAG', 19: 'ENUM64'}


def parse_btf(b):
    magic, ver, flags, hdr_len, type_off, type_len, str_off, str_len = struct.unpack_from('<HBBIIIII', b, 0)
    assert magic == 0xeb9f, hex(magic)
    types_b = b[hdr_len + type_off: hdr_len + type_off + type_len]
    strs = b[hdr_len + str_off: hdr_len + str_off + str_len]

    def s(off):
        e = strs.index(b'\0', off)
        return strs[off:e].decode('utf-8', 'replace')

    types = [None]  # id 0 = void
    p = 0
    while p < len(types_b):
        name_off, info, size_type = struct.unpack_from('<III', types_b, p)
        p += 12
        vlen = info & 0xffff
        kind = (info >> 24) & 0x1f
        kflag = (info >> 31) & 1
        t = {'kind': BTF_KIND.get(kind, kind), 'name': s(name_off), 'vlen': vlen, 'kflag': kflag,
             'size': size_type, 'type': size_type}
        k = t['kind']
        if k == 'INT':
            (enc,) = struct.unpack_from('<I', types_b, p)
            p += 4
            t['bits'] = enc & 0xff
            t['bit_off'] = (enc >> 16) & 0xff
            t['enc'] = (enc >> 24) & 0xf
        elif k == 'ARRAY':
            t['elem'], t['index'], t['nelems'] = struct.unpack_from('<III', types_b, p)
            p += 12
        elif k in ('STRUCT', 'UNION'):
            m = []
            for _ in range(vlen):
                n, ty, off = struct.unpack_from('<III', types_b, p)
                p += 12
                if kflag:
                    m.append((s(n), ty, off & 0xffffff, off >> 24))
                else:
                    m.append((s(n), ty, off, 0))
            t['members'] = m
        elif k == 'ENUM':
            e = []
            for _ in range(vlen):
                n, v = struct.unpack_from('<Ii', types_b, p)
                p += 8
                e.append((s(n), v if kflag else v & 0xffffffff))
            t['enum'] = e
        elif k == 'ENUM64':
            e = []
            for _ in range(vlen):
                n, lo, hi = struct.unpack_from('<III', types_b, p)
                p += 12
                v = (hi << 32) | lo
                if kflag and v & (1 << 63):
                    v -= 1 << 64
                e.append((s(n), v))
            t['enum'] = e
        elif k == 'FUNC_PROTO':
            prm = []
            for _ in range(vlen):
                n, ty = struct.unpack_from('<II', types_b, p)
                p += 8
                prm.append((s(n), ty))
            t['params'] = prm
        elif k == 'VAR':
            (t['linkage'],) = struct.unpack_from('<I', types_b, p)
            p += 4
        elif k == 'DATASEC':
            sec = []
            for _ in range(vlen):
                ty, off, sz = struct.unpack_from('<III', types_b, p)
                p += 12
                sec.append((ty, off, sz))
            t['secinfo'] = sec
        elif k == 'DECL_TAG':
            (t['comp_idx'],) = struct.unpack_from('<I', types_b, p)
            p += 4
        types.append(t)
    return types


def main():
    btf_path, smap_path, out_path = sys.argv[1:4]
    elf_path = sys.argv[4] if len(sys.argv) > 4 else None
    btf = open(btf_path, 'rb').read()
    T = parse_btf(btf)
    print('BTF types:', len(T) - 1)

    base_types = {
        'void': {'size': 0, 'signed': False, 'kind': 'void', 'endian': 'little'},
        'pointer': {'size': 8, 'signed': False, 'kind': 'int', 'endian': 'little'},
    }
    user_types, enums, symbols = {}, {}, {}
    anon_names = {}

    def strip(tid):
        while tid and T[tid]['kind'] in ('CONST', 'VOLATILE', 'RESTRICT', 'TYPE_TAG'):
            tid = T[tid]['type']
        return tid

    def tname(tid):
        t = T[tid]
        if t['name']:
            return t['name']
        if tid not in anon_names:
            anon_names[tid] = 'unnamed_%d' % tid
        return anon_names[tid]

    # typedef of anonymous struct/union/enum -> name the anonymous type after the typedef (dwarf2json behaviour)
    for tid in range(1, len(T)):
        t = T[tid]
        if t['kind'] == 'TYPEDEF':
            tgt = strip(t['type'])
            if tgt and T[tgt]['kind'] in ('STRUCT', 'UNION', 'ENUM', 'ENUM64') and not T[tgt]['name'] and tgt not in anon_names:
                anon_names[tgt] = t['name']

    def base_name_for_int(t):
        n = t['name']
        if n not in base_types:
            kind = 'int'
            if t['enc'] & 4:
                kind = 'bool'
            elif t['enc'] & 2 or 'char' in n:
                kind = 'char'
            base_types[n] = {'size': t['size'], 'signed': bool(t['enc'] & 1), 'kind': kind, 'endian': 'little'}
        return n

    def desc(tid):
        tid = strip(tid)
        if tid == 0:
            return {'kind': 'base', 'name': 'void'}
        t = T[tid]
        k = t['kind']
        if k == 'INT':
            return {'kind': 'base', 'name': base_name_for_int(t)}
        if k == 'FLOAT':
            n = t['name']
            base_types.setdefault(n, {'size': t['size'], 'signed': True, 'kind': 'float', 'endian': 'little'})
            return {'kind': 'base', 'name': n}
        if k == 'PTR':
            return {'kind': 'pointer', 'base': 'pointer', 'subtype': desc(t['type'])}
        if k == 'ARRAY':
            return {'kind': 'array', 'count': t['nelems'], 'subtype': desc(t['elem'])}
        if k == 'STRUCT':
            return {'kind': 'struct', 'name': tname(tid)}
        if k == 'UNION':
            return {'kind': 'union', 'name': tname(tid)}
        if k in ('ENUM', 'ENUM64'):
            return {'kind': 'enum', 'name': tname(tid)}
        if k == 'FWD':
            return {'kind': 'union' if t['kflag'] else 'struct', 'name': t['name']}
        if k == 'TYPEDEF':
            tgt = strip(t['type'])
            if tgt == 0:
                return {'kind': 'base', 'name': 'void'}
            if T[tgt]['kind'] == 'INT':
                bt = T[tgt]
                base_name_for_int(bt)
                base_types.setdefault(t['name'], dict(base_types[bt['name']]))
            return desc(tgt)
        if k in ('FUNC_PROTO', 'FUNC'):
            return {'kind': 'function'}
        if k in ('VAR', 'DATASEC', 'DECL_TAG'):
            return {'kind': 'base', 'name': 'void'}
        raise ValueError(k)

    def add_fields(fields, tid, base_bits):
        """flatten anonymous struct/union members (dwarf2json behaviour)"""
        t = T[tid]
        for (mname, mty, boff, bsz) in t['members']:
            boff += base_bits
            s_ty = strip(mty)
            if not mname and s_ty and T[s_ty]['kind'] in ('STRUCT', 'UNION'):
                add_fields(fields, s_ty, boff)
                continue
            if not mname:
                mname = 'unnamed_field_%x' % (boff // 8)
            bits = bsz
            if not bits and s_ty and T[s_ty]['kind'] == 'INT' and T[s_ty]['bits'] and T[s_ty]['bits'] != T[s_ty]['size'] * 8:
                bits = T[s_ty]['bits']
                boff += T[s_ty]['bit_off']
            if bits:
                d = desc(mty)
                if d['kind'] not in ('base', 'enum'):
                    d = {'kind': 'base', 'name': 'int'}
                if d['kind'] == 'base':
                    sz = base_types[d['name']]['size'] or 4
                else:
                    sz = enums.get(d['name'], {}).get('size', 4) or 4
                byte_off = (boff // (sz * 8)) * sz
                fields[mname] = {'type': {'kind': 'bitfield', 'bit_position': boff - byte_off * 8,
                                          'bit_length': bits, 'type': d}, 'offset': byte_off}
            else:
                fields[mname] = {'type': desc(mty), 'offset': boff // 8}

    for tid in range(1, len(T)):
        t = T[tid]
        if t['kind'] in ('ENUM', 'ENUM64'):
            n = tname(tid)
            if n in enums:
                continue
            signed = bool(t['kflag'])
            base = {4: 'int' if signed else 'unsigned int', 8: 'long long' if signed else 'unsigned long long',
                    1: 'char', 2: 'short'}.get(t['size'], 'int')
            base_types.setdefault(base, {'size': t['size'], 'signed': signed, 'kind': 'int', 'endian': 'little'})
            enums[n] = {'size': t['size'], 'base': base, 'constants': {k: v for k, v in t['enum']}}
    for tid in range(1, len(T)):
        t = T[tid]
        if t['kind'] in ('STRUCT', 'UNION'):
            n = tname(tid)
            if n in user_types:
                continue
            fields = {}
            add_fields(fields, tid, 0)
            user_types[n] = {'size': t['size'], 'kind': 'struct' if t['kind'] == 'STRUCT' else 'union', 'fields': fields}

    alias = {'long': 'long int', 'unsigned long': 'long unsigned int', 'long long': 'long long int',
             'unsigned long long': 'long long unsigned int', 'short': 'short int', 'unsigned short': 'short unsigned int',
             'long int': 'long', 'long unsigned int': 'unsigned long', 'long long int': 'long long',
             'long long unsigned int': 'unsigned long long', 'short int': 'short', 'short unsigned int': 'unsigned short'}
    for a, b in alias.items():
        if a not in base_types and b in base_types:
            base_types[a] = dict(base_types[b])
    for n, sz, sg, kd in [('char', 1, True, 'char'), ('unsigned char', 1, False, 'char'), ('int', 4, True, 'int'),
                          ('unsigned int', 4, False, 'int'), ('long', 8, True, 'int'), ('unsigned long', 8, False, 'int'),
                          ('long long', 8, True, 'int'), ('unsigned long long', 8, False, 'int'), ('short', 2, True, 'int'),
                          ('unsigned short', 2, False, 'int'), ('_Bool', 1, False, 'bool')]:
        base_types.setdefault(n, {'size': sz, 'signed': sg, 'kind': kd, 'endian': 'little'})

    var_types = {}
    for tid in range(1, len(T)):
        t = T[tid]
        if t['kind'] == 'VAR' and t['name'] not in var_types:
            try:
                var_types[t['name']] = desc(t['type'])
            except Exception:
                pass

    smap = open(smap_path, 'rb').read()
    for line in smap.decode('utf-8', 'replace').splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        addr, typ, name = int(parts[0], 16), parts[1], parts[2]
        if name in symbols:
            continue
        e = {'address': addr}
        if name in var_types:
            e['type'] = var_types[name]
        symbols[name] = e

    if elf_path and 'linux_banner' in symbols:
        from elftools.elf.elffile import ELFFile
        f = ELFFile(open(elf_path, 'rb'))
        rod = f.get_section_by_name('.rodata')
        data = rod.data()
        off = symbols['linux_banner']['address'] - rod['sh_addr']
        s = data[off: data.index(b'\0', off) + 1]
        symbols['linux_banner']['constant_data'] = base64.b64encode(s).decode()
        symbols['linux_banner']['type'] = {'kind': 'array', 'count': len(s), 'subtype': {'kind': 'base', 'name': 'char'}}
        print('linux_banner:', s)

    isf = {
        'metadata': {
            'format': '6.2.0',
            'producer': {'name': 'btf2isf.py', 'version': '0.1', 'datetime': '2026-10-18T00:00:00'},
            'linux': {
                'symbols': [{'kind': 'system-map', 'name': smap_path.replace('\\', '/').split('/')[-1],
                             'hash_type': 'sha256', 'hash_value': hashlib.sha256(smap).hexdigest()}],
                'types': [{'kind': 'dwarf', 'name': 'vmlinux.btf', 'hash_type': 'sha256',
                           'hash_value': hashlib.sha256(btf).hexdigest()}],
            },
        },
        'base_types': base_types, 'user_types': user_types, 'enums': enums, 'symbols': symbols,
    }
    json.dump(isf, open(out_path, 'w'), separators=(',', ':'))
    print('base_types=%d user_types=%d enums=%d symbols=%d typed_symbols=%d' % (
        len(base_types), len(user_types), len(enums), len(symbols), sum(1 for s in symbols.values() if 'type' in s)))
    ts = user_types.get('task_struct', {})
    print('task_struct size', ts.get('size'), 'fields', len(ts.get('fields', {})),
          'pid@', ts.get('fields', {}).get('pid'), 'comm@', ts.get('fields', {}).get('comm'))


main()
