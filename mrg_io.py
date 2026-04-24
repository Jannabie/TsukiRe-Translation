"""
mrg_io.py — MRG / MZP binary parser and packer for Tsukihime Remake

The script_text.mrg file is an MZP archive (magic "mrgd00") containing 10
sections.  Sections 0 and 1 are the offset table and string table respectively.

Offset table format:
  Each 4-byte big-endian unsigned integer gives the byte offset of the
  corresponding string in the string table.  The table ends with two entries
  equal to the string-table length followed by 0xFFFFFFFF.

Bug fixed vs. original _build_mrg (pre-v2):
  Every offset 0..max_offset now always gets an OT entry even if the string is
  empty, keeping the table aligned with allscr.mrg references.

See also: tag_validator.py — run validate_all(translations) before build_mrg()
to catch tag issues that could cause in-game freezes or visual glitches.
"""

import io, struct
from pua_encode import render_for_mrg


# ════════════════════════════════════════════════════════════════════════════════
#  MZP CONTAINER
# ════════════════════════════════════════════════════════════════════════════════

class _Mzp:
    MAGIC = b"mrgd00"
    SEC   = 0x800          # sector size (2048 bytes)
    FMT   = "<HHHH"        # (sector-offset, byte-offset, sector-count, byte-count)

    def __init__(self, path: str):
        raw = open(path, "rb").read()
        magic, n = struct.unpack_from("<6sH", raw, 0)
        if magic != self.MAGIC:
            raise ValueError(f"Not a valid MRG archive (magic={magic!r})")
        hdrs = [struct.unpack_from(self.FMT, raw, 8 + 8*i) for i in range(n)]
        base = 8 + 8*n
        self.data: list[bytes] = []
        for so, bo, ss, sb in hdrs:
            start = base + so * self.SEC + bo
            size  = (ss * self.SEC & ~0xFFFF) | sb
            self.data.append(raw[start:start + size])

    @classmethod
    def pack(cls, sections: list[bytes]) -> bytes:
        hdr  = io.BytesIO()
        body = io.BytesIO()
        hdr.write(struct.pack("<6sH", cls.MAGIC, len(sections)))
        for s in sections:
            # Align body to 16-byte boundary
            while body.tell() % 16:
                body.write(b"\xff")
            p  = body.tell()
            so = p // cls.SEC
            bo = p %  cls.SEC
            ss = len(s) // cls.SEC + (1 if len(s) % cls.SEC else 0)
            sb = len(s) & 0xFFFF
            hdr.write(struct.pack(cls.FMT, so, bo, ss, sb))
            body.write(s)
        # Final padding to 8-byte alignment
        while (hdr.tell() + body.tell()) % 8:
            body.write(b"\xff")
        body.seek(0)
        hdr.write(body.read())
        hdr.seek(0)
        return hdr.read()


# ════════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════════════════

def parse_strings(path: str) -> dict[int, str]:
    """Read script_text.mrg and return {offset_index: utf8_string}."""
    mzp = _Mzp(path)
    ot, st = mzp.data[0], mzp.data[1]
    out: dict[int, str] = {}
    for i in range(len(ot) // 4 - 1):
        ds, = struct.unpack(">I", ot[i*4 : i*4+4])
        de_raw = ot[(i+1)*4 : (i+1)*4+4]
        if len(de_raw) < 4:
            break
        de, = struct.unpack(">I", de_raw)
        if ds == de or de == 0xFFFFFFFF:
            break
        out[i] = st[ds:de].decode("utf-8", errors="replace")
    return out


def build_mrg(
    originals:    dict[int, str],
    translations: dict[int, str],
    max_offset:   int,
) -> bytes:
    """Pack translated strings back into MRG binary format.

    For each index 0..max_offset:
      - If a translation exists, it is rendered through render_for_mrg()
        which:
          • converts %{i}/%{b}/%{n} tags to PUA / newlines
          • converts %{g} to @g, hoisted to string position 0
          • strips ruby <text|reading> to plain display text
            (prevents the HuneX engine ruby-layout freeze)
          • strips %{u}/%{s} (unsupported by engine)
      - Otherwise the original string is used verbatim.
      - An OT entry is always written so the table stays aligned.

    The six padding sections (newline / fullwidth-space tables) are rebuilt
    from scratch in the same format as the original file.

    IMPORTANT: Run tag_validator.validate_all(translations) before calling
    this function.  CRITICAL issues (e.g. ASCII ruby readings) can cause
    in-game freezes even though build_mrg itself will not raise an error.
    """
    ot_buf = io.BytesIO()
    st_buf = io.BytesIO()

    for o in range(max_offset + 1):
        raw = translations.get(o) or originals.get(o, "")
        ot_buf.write(struct.pack(">I", st_buf.tell()))
        if raw:
            encoded = render_for_mrg(raw)
            st_buf.write(encoded.encode("utf-8"))

    ep = st_buf.tell()
    ot_buf.write(struct.pack(">I", ep))   # end sentinel ×2
    ot_buf.write(struct.pack(">I", ep))
    ot_buf.write(struct.pack(">I", 0xFFFFFFFF))

    ot = ot_buf.getvalue()
    st = st_buf.getvalue()

    # Rebuild the six auxiliary sections (newline / space tables)
    ec = max_offset + 1

    def _pad_section(payload: bytes) -> tuple[bytes, bytes]:
        po = io.BytesIO()
        ps = io.BytesIO()
        for _ in range(ec):
            po.write(struct.pack(">I", ps.tell()))
            ps.write(payload)
        end = ps.tell()
        po.write(struct.pack(">I", end))
        po.write(struct.pack(">I", end))
        po.write(struct.pack(">I", 0xFFFFFFFF))
        return po.getvalue(), ps.getvalue()

    nl_o, nl_s = _pad_section(b"  \r\n")
    sp_o, sp_s = _pad_section("\u3000\r\n".encode("utf-8"))

    return _Mzp.pack([
        ot, st,
        nl_o, nl_s,
        sp_o, sp_s,
        sp_o, sp_s,
        sp_o, sp_s,
    ])