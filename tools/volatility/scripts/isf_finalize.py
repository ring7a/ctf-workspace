"""isf_finalize.py - make a BTF-derived Volatility 3 ISF usable by the linux.* plugins.

Kernel BTF carries almost no types for *global variables* (only per-CPU data), and recent kernels
renamed/retyped a few struct members that Volatility still addresses by the old name.  This script
is idempotent: run it on the JSON produced by btf2isf.py (or on any ISF) as many times as you like.

  1. gives well-known globals a type (init_task, init_mm, modules, mount_hashtable, key_serial_tree,
     prb, taint_flags, socket_file_ops, ...)  -> fixes "Symbol X has no associated type"
  2. kernel >= 6.12 : page.index was renamed __folio_index   -> add alias field
  3. kernel >= 6.18 : page.flags / folio.flags became memdesc_flags_t (struct) -> unsigned long

usage: isf_finalize.py <isf.json> [NR_CPUS]      (NR_CPUS from CONFIG_NR_CPUS, default 64)
Add more globals to GLOBALS when a plugin dies with "Symbol <name> has no associated type".
"""
import json
import sys


def st(n):
    return {'kind': 'struct', 'name': n}


def un(n):
    return {'kind': 'union', 'name': n}


def ptr(t):
    return {'kind': 'pointer', 'base': 'pointer', 'subtype': t}


def arr(n, t):
    return {'kind': 'array', 'count': n, 'subtype': t}


def base(n):
    return {'kind': 'base', 'name': n}


def globals_table(nr_cpus, U):
    pgd = st('pgd_t') if 'pgd_t' in U else base('unsigned long')
    return {
        # core / processes / memory
        'init_task': st('task_struct'), 'init_mm': st('mm_struct'), 'init_thread_union': un('thread_union'),
        'init_cred': st('cred'), 'init_files': st('files_struct'), 'init_signals': st('signal_struct'),
        'init_fs': st('fs_struct'), 'init_nsproxy': st('nsproxy'), 'init_pid_ns': st('pid_namespace'),
        'init_user_ns': st('user_namespace'), 'init_uts_ns': st('uts_namespace'), 'init_ipc_ns': st('ipc_namespace'),
        'init_net': st('net'), 'init_cgroup_ns': st('cgroup_namespace'), 'cgrp_dfl_root': st('cgroup_root'),
        'kthreadd_task': ptr(st('task_struct')), 'root_task_group': st('task_group'), 'root_user': st('user_struct'),
        'init_top_pgt': arr(512, pgd), 'swapper_pg_dir': arr(512, base('unsigned long')),
        'page_offset_base': base('unsigned long'), 'vmalloc_base': base('unsigned long'),
        'vmemmap_base': base('unsigned long'), 'mem_section': ptr(ptr(st('mem_section'))),
        'max_pfn': base('unsigned long'), 'high_memory': ptr(base('void')), 'mmap_min_addr': base('unsigned long'),
        'vmap_nodes': ptr(st('vmap_node')), 'nr_vmap_nodes': base('unsigned int'), 'vmlist': ptr(st('vm_struct')),
        'iomem_resource': st('resource'), 'boot_cpu_data': st('cpuinfo_x86'), 'nr_cpu_ids': base('unsigned int'),
        '__per_cpu_offset': arr(nr_cpus, base('unsigned long')), 'runqueues': st('rq'),
        '__cpu_online_mask': st('cpumask'), '__cpu_possible_mask': st('cpumask'), '__cpu_present_mask': st('cpumask'),
        'cpu_bit_bitmap': arr(65, arr(4, base('unsigned long'))), 'kernel_cpustat': st('kernel_cpustat'),
        'jiffies': base('unsigned long'), 'jiffies_64': base('unsigned long long'), 'system_state': base('int'),
        'tk_core': st('tk_core'), 'timekeeper': st('timekeeper'), 'tick_cpu_device': st('tick_device'),
        # modules / taint / printk
        'modules': st('list_head'), 'module_kset': ptr(st('kset')), 'module_addr_min': base('unsigned long'),
        'module_addr_max': base('unsigned long'), 'taint_flags': arr(18, st('taint_flag')),
        'tainted_mask': base('unsigned long'), 'prb': ptr(st('printk_ringbuffer')),
        'printk_rb_static': st('printk_ringbuffer'), 'log_buf': ptr(base('char')), 'log_buf_len': base('unsigned int'),
        'clear_seq': st('latched_seq'), 'syslog_seq': base('unsigned long long'), 'kallsyms_num_syms': base('unsigned int'),
        # vfs / mounts / proc / sysctl
        'super_blocks': st('list_head'), 'mount_hashtable': ptr(st('hlist_head')), 'mount_lock': st('seqlock_t'),
        'dentry_hashtable': ptr(st('hlist_bl_head')), 'file_systems': ptr(st('file_system_type')),
        'proc_root': st('proc_dir_entry'), 'sysctl_table_root': st('ctl_table_root'),
        # tty / input
        'tty_drivers': st('list_head'), 'tty_ldiscs': arr(30, ptr(st('tty_ldisc_ops'))),
        'keyboard_notifier_list': st('blocking_notifier_head'),
        # network
        'net_namespace_list': st('list_head'), 'inet_protos': arr(256, ptr(st('net_protocol'))),
        'tcp_hashinfo': st('inet_hashinfo'), 'ptype_all': st('list_head'), 'ptype_base': arr(16, st('list_head')),
        'unix_socket_table': arr(512, st('hlist_head')), 'inetsw': arr(11, st('list_head')), 'proto_list': st('list_head'),
        'nf_hooks_ingress': st('list_head'), 'socket_file_ops': st('file_operations'),
        'sockfs_dentry_operations': st('dentry_operations'), 'sockfs_inode_ops': st('inode_operations'),
        'sock_fs_type': st('file_system_type'), 'unix_dgram_ops': st('proto_ops'), 'unix_stream_ops': st('proto_ops'),
        'inet_stream_ops': st('proto_ops'), 'inet_dgram_ops': st('proto_ops'), 'inet6_stream_ops': st('proto_ops'),
        'inet6_dgram_ops': st('proto_ops'), 'packet_ops': st('proto_ops'), 'netlink_ops': st('proto_ops'),
        'tcp_prot': st('proto'), 'udp_prot': st('proto'), 'unix_proto': st('proto'),
        # keys / dm (for LUKS, dm-crypt cases)
        'key_serial_tree': st('rb_root'), 'key_user_tree': st('rb_root'), 'key_types_list': st('list_head'),
        'key_type_logon': st('key_type'), 'key_type_user': st('key_type'), 'key_type_keyring': st('key_type'),
        '_name_buckets': ptr(st('list_head')), '_uuid_buckets': ptr(st('list_head')),
    }


def type_exists(t, U):
    if t['kind'] in ('struct', 'union'):
        return t['name'] in U
    if t['kind'] in ('pointer', 'array'):
        return type_exists(t['subtype'], U) or t['subtype']['kind'] == 'base'
    return True


def main():
    path = sys.argv[1]
    nr_cpus = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    isf = json.load(open(path, encoding='utf-8'))
    S, U = isf['symbols'], isf['user_types']
    added = skipped = 0
    for name, t in globals_table(nr_cpus, U).items():
        if name in S and 'type' not in S[name]:
            if type_exists(t, U):
                S[name]['type'] = t
                added += 1
            else:
                skipped += 1
    # kernel >= 6.12: struct page.index -> __folio_index
    for sname in ('page', 'folio'):
        f = U.get(sname, {}).get('fields', {})
        if 'index' not in f and '__folio_index' in f:
            f['index'] = dict(f['__folio_index'])
            print(f'{sname}.index aliased to __folio_index @ {f["index"]["offset"]}')
        # kernel >= 6.18: flags became memdesc_flags_t (a struct) -> plugins do `page.flags & mask`
        fl = f.get('flags')
        if fl and fl['type'].get('kind') != 'base':
            fl['type'] = base('unsigned long')
            print(f'{sname}.flags retyped to unsigned long')
    json.dump(isf, open(path, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f'typed {added} globals ({skipped} skipped: struct not in this kernel BTF)')


if __name__ == '__main__':
    main()
