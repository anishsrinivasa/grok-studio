#!/usr/bin/env python3
"""decode_capture.py - turn capture_pixels.luau's "GSPIX ..." result into a PNG (stdlib only).

    python3 decode_capture.py <tool-result.txt> <out.png>
"""
import base64
import re
import struct
import sys
import zlib


def main(src, dst):
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    m = re.search(r"GSPIX (\d+) (\d+) (\d+) (\d+) ([A-Za-z0-9+/=]+)", text)
    if not m:
        raise SystemExit("no GSPIX payload in %s" % src)
    w, h = int(m.group(3)), int(m.group(4))
    raw = base64.b64decode(m.group(5))
    if len(raw) < w * h * 3:
        raise SystemExit("payload truncated: %d bytes, need %d (lower OUT_W)" % (len(raw), w * h * 3))
    rows = b"".join(b"\x00" + raw[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(dst, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    print("%s: %dx%d (screen %sx%s)" % (dst, w, h, m.group(1), m.group(2)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
