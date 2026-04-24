"""
pua_encode.py — PUA (Private Use Area) encoding/decoding for Tsukihimates font

The Tsukihimates patch ships a custom font where italic glyph variants are mapped
into the Unicode Private Use Area block U+E000–U+E07E.

Encoding rule:
  italic char c (printable ASCII 0x20–0x7E)
       → U+E000 + ord(c)
  e.g. italic 'P' (0x50) → U+E050  ✓  (confirmed from script_text.mrg inspection)

NOTE: The original source (tsuki_trans.py v1) used PUA_ITALIC_OFFSET = 0x80,
putting italic 'P' at U+E0D0.  The game's actual data shows offset = 0 (zero).
That wrong offset is the root cause of "reversed / garbled" italic text in-game.

%{n} tag:
  Mapped to \r\n (the engine's native line-break sequence) during MRG render.

Bold (%{b}):
  The Tsukihimates font currently provides only ONE PUA style range (0=italic).
  %{b} is therefore encoded identically to %{i}.  Bold is NOT exposed in the
  GUI toolbar because it produces no visual difference from italic in-game.

Gray / inner-monologue (%{g}...%{/g}):
  Maps to the game engine's @g rendering mode (gray / inner-monologue style).
  During MRG render the opening %{g} inserts @g at that position; the closing
  %{/g} is stripped (the engine has no "end-gray" command — gray persists for
  the rest of the string / display unit).
  Write: %{g}Or wer't thy sire...%{/g}
  MRG:   @gOr wer't thy sire...

Ruby / furigana (<text|reading>):
  Passed through to MRG as-is.  The game engine renders the furigana natively.
  It is safe to OMIT the ruby reading in translated text (write plain text).
  To USE ruby, write: <word|reading>  e.g. <Arcueid|Arc>

Reverse-Italic (%{ri}...%{/ri}):
  Special effect tag.  The text between %{ri} and %{/ri} is:
    1. Reversed character-by-character
    2. Encoded as PUA italic (same as %{i})
  Used in scenes where text appears backwards in-game (mirror / vision effects).
  Write the text NORMALLY — the encoder handles the reversal automatically.
  Example:  %{ri}I want to tear her into a thousand pieces.%{/ri}
  → MRG contains italic PUA of ".seceip dnasuoht a otni reh raet ot tnaw I"
"""

import re

# ─── configurable offsets (Edit > PUA Settings in the GUI) ────────────────────
PUA_ITALIC_OFFSET: int = 0x000
PUA_BOLD_OFFSET:   int = 0x000   # same range — font has one PUA style

_PUA_ASCII_LO = 0x20
_PUA_ASCII_HI = 0x7E

# Handles: i, /i, b, /b, g, /g, n, ri, /ri
_TAG_RE = re.compile(r'%\{(/?(?:ri|[gibn]))\}')


def render_for_mrg(text: str) -> str:
    """Convert translation format tags to PUA glyph sequences for MRG injection."""
    text = re.sub(r'%\{/?[us]\}', '', text)   # strip unsupported underline/strike
    text = text.replace('#', '')              # strip glue markers
    # Ruby/furigana <text|reading> is passed through as-is — the game engine
    # renders it natively.  Do NOT strip it here.

    result  = []
    italic  = False
    bold    = False
    ri_mode = False
    ri_buf: list[str] = []
    pos     = 0

    for m in _TAG_RE.finditer(text):
        chunk = text[pos:m.start()]
        if chunk:
            if ri_mode:
                ri_buf.append(chunk)
            else:
                result.append(_encode_chunk(chunk, italic, bold))

        tag = m.group(1)
        if   tag == 'i':   italic  = True
        elif tag == '/i':  italic  = False
        elif tag == 'b':   bold    = True
        elif tag == '/b':  bold    = False
        elif tag == 'g':
            # %{g} → inject the game-engine @g gray-mode marker at this position.
            # Must be outside any ri_buf because @g is a game command, not a char.
            (ri_buf if ri_mode else result).append('@g')
        elif tag == '/g':
            pass   # no "end gray" command in the engine — simply discard
        elif tag == 'n':
            (ri_buf if ri_mode else result).append('\r\n')
        elif tag == 'ri':
            ri_mode = True
            ri_buf  = []
        elif tag == '/ri':
            ri_mode = False
            buffered = ''.join(ri_buf)
            result.append(_encode_chunk(buffered[::-1], italic=True, bold=False))
            ri_buf = []

        pos = m.end()

    tail = text[pos:]
    if tail:
        if ri_mode:
            ri_buf.append(tail)
            result.append(_encode_chunk(''.join(ri_buf)[::-1], italic=True, bold=False))
        else:
            result.append(_encode_chunk(tail, italic, bold))

    return ''.join(result)


def _encode_chunk(chunk: str, italic: bool, bold: bool) -> str:
    if not (italic or bold):
        return chunk
    offset = PUA_ITALIC_OFFSET if italic else PUA_BOLD_OFFSET
    out = []
    for c in chunk:
        cp = ord(c)
        if _PUA_ASCII_LO <= cp <= _PUA_ASCII_HI:
            out.append(chr(0xE000 + offset + cp))
        else:
            out.append(c)
    return ''.join(out)


def decode_pua_orig(text: str) -> str:
    return ''.join(
        chr(ord(c) - 0xE000) if 0xE000 <= ord(c) <= 0xE07E else c
        for c in text
    )


def pua_to_fmt_tags(text: str) -> str:
    result = []
    i = 0
    n = len(text)

    while i < n:
        cp = ord(text[i])

        if 0xE020 <= cp <= 0xE07E:
            rel = cp - 0xE000
            if PUA_ITALIC_OFFSET <= rel <= PUA_ITALIC_OFFSET + _PUA_ASCII_HI:
                result.append('%{i}')
                while i < n:
                    cp2 = ord(text[i])
                    rel2 = cp2 - 0xE000
                    if 0xE020 <= cp2 <= 0xE07E and \
                       PUA_ITALIC_OFFSET <= rel2 <= PUA_ITALIC_OFFSET + _PUA_ASCII_HI:
                        result.append(chr(cp2 - 0xE000 - PUA_ITALIC_OFFSET))
                        i += 1
                    else:
                        break
                result.append('%{/i}')
                continue

            if PUA_ITALIC_OFFSET != PUA_BOLD_OFFSET and \
               PUA_BOLD_OFFSET <= rel <= PUA_BOLD_OFFSET + _PUA_ASCII_HI:
                result.append('%{b}')
                while i < n:
                    cp2 = ord(text[i])
                    rel2 = cp2 - 0xE000
                    if 0xE020 <= cp2 <= 0xE07E and \
                       PUA_BOLD_OFFSET <= rel2 <= PUA_BOLD_OFFSET + _PUA_ASCII_HI:
                        result.append(chr(cp2 - 0xE000 - PUA_BOLD_OFFSET))
                        i += 1
                    else:
                        break
                result.append('%{/b}')
                continue

        result.append(text[i])
        i += 1

    return ''.join(result)


def has_pua_italic(text: str) -> bool:
    return any(0xE020 <= ord(c) <= 0xE07E for c in text)
