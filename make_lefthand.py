#!/usr/bin/env python3
"""Make a left-hand copy of an FFXII weapon .dae.phyre, using the same transform
as the FF12 Dual Wield mod's w9xxx models (reverse-engineered from w2104->w9012,
w2105->w9013, w4130->w9034):

    position' = R @ position + T      normal'/tangent' = R @ v
    R = [[0,0,1],[0,-1,0],[1,0,0]]  (180 deg turn)     T = (0.0854, 0, -0.0133)

Vertex arrays are found by scanning for runs of unit-length float3 vectors
(normals/tangents). A run of N non-unit float3s directly before a unit run of
N rows is that mesh's positions.

usage: make_lefthand.py src.dae.phyre dst.dae.phyre OLDNAME NEWNAME
"""
import struct
import sys
import numpy as np

R = np.array([[0, 0, 1], [0, -1, 0], [1, 0, 0]], np.float64)
T = np.array([0.0854057009, 0.0000051642, -0.0133286270])
MIN_RUN = 4


def rows_at(buf, start, n):
    return np.frombuffer(bytes(buf[start:start + 12 * n]), '<f4').reshape(n, 3).astype(np.float64)


def unit_runs(buf):
    """Maximal runs of unit float3 rows, at any byte alignment."""
    runs = []
    size = len(buf)
    for al in range(4):
        n = (size - al) // 4
        f = np.frombuffer(bytes(buf[al:al + 4 * n]), '<f4').astype(np.float64)
        with np.errstate(all='ignore'):
            for ph in range(3):
                m = (len(f) - ph) // 3
                v = f[ph:ph + 3 * m].reshape(m, 3)
                ln = np.sqrt((v * v).sum(1))
                ok = np.isfinite(ln) & (np.abs(ln - 1) < 2e-3)
                i = 0
                while i < m:
                    if ok[i]:
                        j = i
                        while j < m and ok[j]:
                            j += 1
                        if j - i >= MIN_RUN:
                            runs.append((al + 4 * (ph + 3 * i), j - i))
                        i = j
                    else:
                        i += 1
    runs.sort()
    return runs


def is_plausible_positions(p):
    return np.all(np.isfinite(p)) and np.all(np.abs(p) < 20) and np.mean(np.abs(np.sqrt((p * p).sum(1)) - 1) < 2e-3) < 0.5


def convert(src, dst, old, new):
    buf = bytearray(open(src, 'rb').read())
    runs = unit_runs(buf)
    unit_at = {}
    for s, n in runs:
        unit_at.setdefault(s, max(n, unit_at.get(s, 0)))
    pos_blocks, unit_blocks = [], []
    claimed = []

    def free(a, n):
        return all(a + 12 * n <= c0 or a >= c1 for c0, c1 in claimed)

    for s, m in sorted(runs, key=lambda r: -r[1]):
        # mesh = positions(N) + normals(N) contiguous, then tangents(2N) later.
        # Runs may be 1-2 rows long when neighbouring data happens to look like unit vectors.
        for n in (m, m - 1, m - 2):
            ps = s - 12 * n
            if ps < 0 or n < 6 or not free(ps, 2 * n):
                continue
            if not is_plausible_positions(rows_at(buf, ps, n)):
                continue
            tang = [(t, k) for t, k in runs if 2 * n <= k <= 2 * n + 2 and t > s and free(t, 2 * n)]
            if not tang:
                continue
            pos_blocks.append((ps, n)); unit_blocks.append((s, n)); unit_blocks.append((tang[0][0], 2 * n))
            claimed.append((ps, s + 12 * n)); claimed.append((tang[0][0], tang[0][0] + 24 * n))
            break
    for s, n in unit_blocks:
        v = rows_at(buf, s, n) @ R.T
        buf[s:s + 12 * n] = v.astype('<f4').tobytes()
    allpts = []
    for s, n in pos_blocks:
        p = rows_at(buf, s, n)
        allpts.append(p)
        buf[s:s + 12 * n] = (p @ R.T + T).astype('<f4').tobytes()
    # bounding box right after "LODNODE_0": min xyz, 0x00, max xyz (generous union)
    k = buf.find(b'\xff\xff\xff\xff\x00LODNODE_0')
    k = k + 5 if k >= 0 else -1
    if k >= 0:
        # bounding box after "LODNODE_0": min xyz (3 floats), 0x00, size xyz (3 floats)
        b0 = k + len(b'LODNODE_0') + 5
        mn = np.array(struct.unpack_from('<3f', buf, b0)); sz = np.array(struct.unpack_from('<3f', buf, b0 + 13))
        corners = np.array([[x, y, z] for x in (mn[0], mn[0] + sz[0]) for y in (mn[1], mn[1] + sz[1]) for z in (mn[2], mn[2] + sz[2])])
        moved = corners @ R.T + T
        lo = np.minimum(corners.min(0), moved.min(0)); hi = np.maximum(corners.max(0), moved.max(0))
        struct.pack_into('<3f', buf, b0, *lo); struct.pack_into('<3f', buf, b0 + 13, *(hi - lo))
    out = bytes(buf).replace(old.encode(), new.encode())
    open(dst, 'wb').write(out)
    return pos_blocks, unit_blocks


if __name__ == '__main__':
    pb, ub = convert(*sys.argv[1:5])
    print('positions', [(hex(s), n) for s, n in pb])
    print('unit arrays', [(hex(s), n) for s, n in ub])
