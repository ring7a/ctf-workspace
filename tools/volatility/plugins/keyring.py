"""Volatility 3 plugin: walk the Linux kernel keyring serial tree (key_serial_tree) and list every
struct key with its type, description and payload.  Targets LUKS2 cases where the volume key lives in a
'logon' key named cryptsetup:<UUID>-d<n>.
Usage: vol -p <this dir> ... keyring.Keyring [--dump]
"""
from typing import List

from volatility3.framework import interfaces, renderers, exceptions
from volatility3.framework.configuration import requirements
from volatility3.framework.renderers import format_hints


class Keyring(interfaces.plugins.PluginInterface):
    """Lists kernel keyring keys (key_serial_tree) and their payloads."""

    _required_framework_version = (2, 0, 0)
    _version = (1, 0, 0)

    @classmethod
    def get_requirements(cls) -> List[interfaces.configuration.RequirementInterface]:
        return [
            requirements.ModuleRequirement(name="kernel", description="Linux kernel",
                                           architectures=["Intel32", "Intel64"]),
            requirements.BooleanRequirement(name="dump", description="Dump key payloads to files",
                                            default=False, optional=True),
        ]

    def _read_cstr(self, layer, addr, maxlen=256):
        if not addr:
            return ""
        try:
            data = layer.read(addr, maxlen, pad=True)
        except exceptions.InvalidAddressException:
            return "<unreadable>"
        return data.split(b"\x00", 1)[0].decode("utf-8", "replace")

    def _generator(self):
        vmlinux = self.context.modules[self.config["kernel"]]
        layer = self.context.layers[vmlinux.layer_name]
        key_type = vmlinux.get_type("key")
        serial_node_off = key_type.relative_child_offset("serial_node")
        root = vmlinux.object_from_symbol("key_serial_tree")
        stack = [int(root.rb_node)]
        seen = set()
        while stack:
            node_addr = stack.pop()
            if not node_addr or node_addr in seen:
                continue
            seen.add(node_addr)
            try:
                node = vmlinux.object(object_type="rb_node", offset=node_addr, absolute=True)
                stack.append(int(node.rb_left))
                stack.append(int(node.rb_right))
                key = vmlinux.object(object_type="key", offset=node_addr - serial_node_off, absolute=True)
                serial = int(key.serial)
                ktype_ptr = int(key.type)
                ktype_name = ""
                if ktype_ptr:
                    ktype = vmlinux.object(object_type="key_type", offset=ktype_ptr, absolute=True)
                    ktype_name = self._read_cstr(layer, int(ktype.name), 64)
                desc = self._read_cstr(layer, int(key.description), 256)
                datalen = int(key.datalen)
                uid = int(key.uid.val) if hasattr(key.uid, "val") else int(key.uid)
                gid = int(key.gid.val) if hasattr(key.gid, "val") else int(key.gid)
                perm = int(key.perm)
                flags = int(key.flags)
                payload_ptr = int(key.payload.data[0])
                payload_hex = ""
                payload_bytes = b""
                if ktype_name in ("user", "logon") and payload_ptr:
                    # struct user_key_payload { struct rcu_head rcu; unsigned short datalen; char data[]; }
                    ukp_t = vmlinux.get_type("user_key_payload")
                    ukp = vmlinux.object(object_type="user_key_payload", offset=payload_ptr, absolute=True)
                    plen = int(ukp.datalen)
                    data_off = ukp_t.relative_child_offset("data")
                    payload_bytes = layer.read(payload_ptr + data_off, plen, pad=True)
                    payload_hex = payload_bytes.hex()
                    if self.config.get("dump") and payload_bytes:
                        fname = "key_%d_%s_%s.bin" % (serial, ktype_name, desc.replace(":", "_").replace("/", "_"))
                        with self.open(fname) as fh:
                            fh.write(payload_bytes)
                yield (0, (format_hints.Hex(key.vol.offset), serial, ktype_name, desc, uid, gid,
                           format_hints.Hex(perm), format_hints.Hex(flags), datalen,
                           format_hints.Hex(payload_ptr), payload_hex or "-"))
            except exceptions.InvalidAddressException as e:
                yield (0, (format_hints.Hex(node_addr), -1, "<invalid>", str(e)[:80], 0, 0,
                           format_hints.Hex(0), format_hints.Hex(0), 0, format_hints.Hex(0), "-"))

    def run(self):
        return renderers.TreeGrid(
            [("Offset", format_hints.Hex), ("Serial", int), ("Type", str), ("Description", str),
             ("UID", int), ("GID", int), ("Perm", format_hints.Hex), ("Flags", format_hints.Hex),
             ("DataLen", int), ("PayloadPtr", format_hints.Hex), ("Payload", str)],
            self._generator(),
        )
