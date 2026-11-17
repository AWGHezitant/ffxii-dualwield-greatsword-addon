#!/usr/bin/env python3
"""Extend ff12-dualwield v47.1's off-hand model table with extra (item, model) pairs.

The DLL copies a 0xEB0-byte payload from RVA 0xE430 into the game. Its off-hand
lookup table (u16 item id, u16 model id; 0-terminated) sits at payload+0xE10 and
fills the payload to the end. We append a new section holding a copy of the
payload with a longer table, and point the copy at it:
    0x12E5  lea rdx, [rip+disp32]   -> new section
    0x12EC  mov r8d, 0xEB0          -> new size (must stay <= 0x1000, one page)
usage: patch_dualwield.py in.dll out.dll ITEM=MODEL [ITEM=MODEL ...]   (hex)
"""
import struct
import sys

import pefile

PAYLOAD_RVA, PAYLOAD_SIZE, TABLE_OFF = 0xE430, 0xEB0, 0xE10
LEA_RVA, MOV_RVA = 0x12E5, 0x12EC


def main():
    src, dst, *pairs = sys.argv[1:]
    pe = pefile.PE(src)
    data = bytearray(open(src, 'rb').read())
    off = pe.get_offset_from_rva

    # sanity: the instructions we patch are what we expect
    lea = data[off(LEA_RVA):off(LEA_RVA) + 7]
    mov = data[off(MOV_RVA):off(MOV_RVA) + 6]
    disp = struct.unpack_from('<i', lea, 3)[0]
    assert lea[:3] == b'\x48\x8d\x15' and LEA_RVA + 7 + disp == PAYLOAD_RVA, 'unexpected DLL version'
    assert mov == b'\x41\xb8' + struct.pack('<I', PAYLOAD_SIZE), 'unexpected DLL version'

    payload = bytes(data[off(PAYLOAD_RVA):off(PAYLOAD_RVA) + PAYLOAD_SIZE])
    table = []
    p = TABLE_OFF
    while True:
        item, model = struct.unpack_from('<HH', payload, p)
        if item == 0:
            break
        table.append((item, model)); p += 4
    existing = {i for i, _ in table}
    for pr in pairs:
        i, m = (int(x, 16) for x in pr.split('='))
        if i in existing:
            sys.exit('item 0x%x already in table' % i)
        table.append((i, m))
    new_payload = payload[:TABLE_OFF] + b''.join(struct.pack('<HH', i, m) for i, m in table) + b'\0' * 8
    assert len(new_payload) <= 0x1000, 'payload no longer fits in one page'

    # append a new read-only section
    fa, sa = pe.OPTIONAL_HEADER.FileAlignment, pe.OPTIONAL_HEADER.SectionAlignment
    last = pe.sections[-1]
    new_rva = (last.VirtualAddress + last.Misc_VirtualSize + sa - 1) // sa * sa
    raw_off = (len(data) + fa - 1) // fa * fa
    raw_size = (len(new_payload) + fa - 1) // fa * fa
    hdr_off = pe.sections[-1].get_file_offset() + 40
    first_raw = min(s.PointerToRawData for s in pe.sections)
    assert hdr_off + 40 <= first_raw, 'no room for a new section header'
    assert data[hdr_off:hdr_off + 40] == b'\0' * 40, 'section header slot not empty'
    hdr = struct.pack('<8sIIIIIIHHI', b'.dwgs\0\0\0', len(new_payload), new_rva, raw_size, raw_off,
                      0, 0, 0, 0, 0x40000040)  # initialized data, readable
    data[hdr_off:hdr_off + 40] = hdr
    data += b'\0' * (raw_off - len(data))
    data += new_payload + b'\0' * (raw_size - len(new_payload))
    # headers: section count, image size, clear checksum
    fh = pe.FILE_HEADER.get_file_offset()
    struct.pack_into('<H', data, fh + 2, pe.FILE_HEADER.NumberOfSections + 1)
    oh = pe.OPTIONAL_HEADER.get_file_offset()
    struct.pack_into('<I', data, oh + 56, (new_rva + len(new_payload) + sa - 1) // sa * sa)  # SizeOfImage
    struct.pack_into('<I', data, oh + 64, 0)  # CheckSum
    # redirect the copy
    struct.pack_into('<i', data, off(LEA_RVA) + 3, new_rva - (LEA_RVA + 7))
    struct.pack_into('<I', data, off(MOV_RVA) + 2, len(new_payload))
    open(dst, 'wb').write(data)
    print('table entries: %d (was %d), payload 0x%x bytes at RVA 0x%x' % (len(table), len(existing), len(new_payload), new_rva))


if __name__ == '__main__':
    main()
