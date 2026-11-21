"""QR code (ISO/IEC 18004) encoder, byte mode, error correction level M, versions 1-40 -> SVG. Stdlib only.
Follows the structure of Project Nayuki's reference implementation (MIT). Verified with zbarimg in the build checks."""
from __future__ import annotations

import html

ECC_M = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28,
         28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28]
BLOCKS_M = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26,
            28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49]
FORMAT_M = 0


def _raw_modules(ver: int) -> int:
    r = (16 * ver + 128) * ver + 64
    if ver >= 2:
        na = ver // 7 + 2
        r -= (25 * na - 10) * na - 55
        if ver >= 7:
            r -= 36
    return r


def _data_codewords(ver: int) -> int:
    return _raw_modules(ver) // 8 - ECC_M[ver] * BLOCKS_M[ver]


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


class QR:
    def __init__(self, data: bytes):
        for ver in range(1, 41):
            ccbits = 8 if ver < 10 else 16
            if 4 + ccbits + 8 * len(data) <= _data_codewords(ver) * 8:
                break
        else:
            raise ValueError("data too long for a QR code")
        self.ver = ver
        self.size = ver * 4 + 17
        n = self.size
        self.mod = [[False] * n for _ in range(n)]
        self.fn = [[False] * n for _ in range(n)]
        bits: list[int] = []

        def put(val: int, length: int) -> None:
            bits.extend((val >> i) & 1 for i in reversed(range(length)))
        put(4, 4)
        put(len(data), ccbits)
        for b in data:
            put(b, 8)
        cap = _data_codewords(ver) * 8
        put(0, min(4, cap - len(bits)))
        put(0, (8 - len(bits) % 8) % 8)
        pad = 0xEC
        while len(bits) < cap:
            put(pad, 8)
            pad ^= 0xEC ^ 0x11
        words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
        self._draw_function_patterns()
        self._draw_codewords(self._add_ecc(words))
        best, best_pen = 0, None
        for mask in range(8):
            self._apply_mask(mask)
            self._draw_format(mask)
            pen = self._penalty()
            if best_pen is None or pen < best_pen:
                best, best_pen = mask, pen
            self._apply_mask(mask)
        self._apply_mask(best)
        self._draw_format(best)

    def _set(self, x: int, y: int, dark: bool) -> None:
        self.mod[y][x] = dark
        self.fn[y][x] = True

    def _draw_function_patterns(self) -> None:
        n = self.size
        for i in range(n):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for (cx, cy) in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = self._align_positions()
        last = len(pos) - 1
        for i, a in enumerate(pos):
            for j, b in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format(0)
        if self.ver >= 7:
            rem = self.ver
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            v = self.ver << 12 | rem
            for i in range(18):
                bit = bool((v >> i) & 1)
                a, b = n - 11 + i % 3, i // 3
                self._set(a, b, bit)
                self._set(b, a, bit)

    def _align_positions(self) -> list[int]:
        if self.ver == 1:
            return []
        na = self.ver // 7 + 2
        step = (self.ver * 8 + na * 3 + 5) // (na * 4 - 4) * 2
        res = [6]
        p = self.size - 7
        while len(res) < na:
            res.insert(1, p)
            p -= step
        return res

    def _draw_format(self, mask: int) -> None:
        data = FORMAT_M << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        g = lambda i: bool((bits >> i) & 1)  # noqa: E731
        n = self.size
        for i in range(6):
            self._set(8, i, g(i))
        self._set(8, 7, g(6))
        self._set(8, 8, g(7))
        self._set(7, 8, g(8))
        for i in range(9, 15):
            self._set(14 - i, 8, g(i))
        for i in range(8):
            self._set(n - 1 - i, 8, g(i))
        for i in range(8, 15):
            self._set(8, n - 15 + i, g(i))
        self._set(8, n - 8, True)

    def _add_ecc(self, data: list[int]) -> list[int]:
        nb, ecc = BLOCKS_M[self.ver], ECC_M[self.ver]
        raw = _raw_modules(self.ver) // 8
        nshort = nb - raw % nb
        short_len = raw // nb
        div = _rs_divisor(ecc)
        blocks, k = [], 0
        for i in range(nb):
            dat = data[k:k + short_len - ecc + (0 if i < nshort else 1)]
            k += len(dat)
            e = _rs_remainder(dat, div)
            if i < nshort:
                dat = dat + [0]
            blocks.append(dat + e)
        out = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                if i != short_len - ecc or j >= nshort:
                    out.append(blk[i])
        return out

    def _draw_codewords(self, words: list[int]) -> None:
        n = self.size
        i = 0
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.fn[y][x] and i < len(words) * 8:
                        self.mod[y][x] = bool((words[i >> 3] >> (7 - (i & 7))) & 1)
                        i += 1
            right -= 2

    def _apply_mask(self, mask: int) -> None:
        f = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
             lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
             lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
             lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0][mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.fn[y][x] and f(x, y):
                    self.mod[y][x] = not self.mod[y][x]

    def _penalty(self) -> int:
        n, m, pen = self.size, self.mod, 0
        for grid in (m, [list(c) for c in zip(*m)]):
            for row in grid:
                run, prev = 0, None
                for c in row:
                    if c == prev:
                        run += 1
                    else:
                        if run >= 5:
                            pen += run - 2
                        run, prev = 1, c
                if run >= 5:
                    pen += run - 2
        for y in range(n - 1):
            for x in range(n - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    pen += 3
        dark = sum(sum(r) for r in m)
        total = n * n
        pen += (abs(dark * 20 - total * 10) + total - 1) // total * 10
        return pen

    def svg(self, label: str, border: int = 4, size_px: int = 180) -> str:
        n = self.size + 2 * border
        d = []
        for y in range(self.size):
            for x in range(self.size):
                if self.mod[y][x]:
                    d.append(f"M{x + border} {y + border}h1v1h-1z")
        return (f'<svg class="qr" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{size_px}" '
                f'height="{size_px}" role="img" aria-label="{html.escape(label)}" shape-rendering="crispEdges">'
                f'<title>{html.escape(label)}</title><rect width="{n}" height="{n}" fill="#fff"/>'
                f'<path fill="#000" d="{"".join(d)}"/></svg>')


def qr_svg(text: str, label: str, size_px: int = 180) -> str:
    return QR(text.encode("utf-8")).svg(label, size_px=size_px)
