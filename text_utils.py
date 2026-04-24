"""
text_utils.py — Tag registry, validation, search normalisation, grid helpers

All tag types found in script_text.mrg and the Tsukihimates translation format:

  GAME-ENGINE TAGS (in original JP text)
  @g        gray / inner-monologue style
  @b        bold style (always combined with @g)
  @t        tab / column alignment
  @k        pause / wait marker
  [ber00]   beep / screech sound-FX placeholder
  [zap00]   zap sound-FX placeholder
  ^         column-separator / emphasis marker (dual-choice display)
  ■ U+25A0  censored / intentionally-blank text

  TRANSLATION FORMAT TAGS (written by the translator)
  %{i}…%{/i}    italic   → PUA U+E021+ord(c) in final MRG
                           (space 0x20 is NOT PUA-encoded — kept as plain space)
  %{g}…%{/g}    gray / inner-monologue → injects @g game-engine marker at pos 0
                           (%{/g} is stripped — no "end gray" command exists)
                           ⚠ Always place %{g} at the START of the entry.
  %{ri}…%{/ri}  reverse-italic → text reversed then PUA-italic encoded
                               (write text NORMALLY; encoder reverses for you)
                               (space is kept as regular space, not PUA-encoded)
  %{b}…%{/b}    bold (NOT in toolbar — font has only one PUA style range,
                       identical to italic; kept for legacy compatibility only)
  %{u}…%{/u}    underline   (stripped — engine has no underline support)
  %{s}…%{/s}    strikethrough (stripped — engine has no strikethrough support)
  %{n}          forced line-break → \\r\\n in final MRG
  #             line-glue marker (two consecutive MRG entries treated as one)
  <text|ruby>   furigana / ruby annotation — ⚠ STRIPPED during MRG injection.
                Reading field with ASCII causes HuneX engine ruby-layout FREEZE.
                Only the display text is kept in the final MRG.
                The game engine renders native ruby only for JP kana readings.
"""

import re
from pua_encode import decode_pua_orig, pua_to_fmt_tags, has_pua_italic

# ── compiled regexes ──────────────────────────────────────────────────────────
AT_TAG_RE    = re.compile(r'@[gbkt]')
GAME_CMD_RE  = re.compile(r'\[[a-z]{3}\d{2}\]')
CARET_RE     = re.compile(r'\^')
# Multi-char tags: ri must come before [a-z] to take priority
FMT_TAG_RE   = re.compile(r'%\{/?(?:ri|[a-z])\}')
HASH_RE      = re.compile(r'#')
RUBY_RE      = re.compile(r'<([^|>]+)\|[^>]*>')

# Matched pairs for validation
FMT_PAIRS: dict[str, str] = {
    '%{i}':  '%{/i}',
    '%{b}':  '%{/b}',
    '%{g}':  '%{/g}',
    '%{ri}': '%{/ri}',
    '%{u}':  '%{/u}',
    '%{s}':  '%{/s}',
}

SYMBOL_CHARS: frozenset[str] = frozenset('@%#^[]<>|')


# ════════════════════════════════════════════════════════════════════════════════
#  STRIPPING / VALIDATION
# ════════════════════════════════════════════════════════════════════════════════

def strip_all_tags(text: str) -> str:
    """Strip every inline tag category, leaving only readable content."""
    text = RUBY_RE.sub(r'\1', text)
    text = AT_TAG_RE.sub('', text)
    text = GAME_CMD_RE.sub('', text)
    text = CARET_RE.sub('', text)
    text = FMT_TAG_RE.sub('', text)
    text = HASH_RE.sub('', text)
    return text


def validate_format_tags(text: str) -> list[str]:
    """Return human-readable warnings for every mismatched %{x}…%{/x} pair."""
    warnings = []
    for open_tag, close_tag in FMT_PAIRS.items():
        n_open  = len(re.findall(re.escape(open_tag),  text))
        n_close = len(re.findall(re.escape(close_tag), text))
        if n_open != n_close:
            name = open_tag[2:-1].upper()
            warnings.append(f'%{{{name}}}: {n_open} opening, {n_close} closing')
    return warnings


def validate_for_injection(offset: int, text: str) -> list[str]:
    """Extended pre-injection validation.  Returns plain-string warnings.

    Includes all validate_format_tags checks PLUS:
      • Ruby with ASCII reading (CRITICAL — engine freeze)
      • %{g} not at string start (WARNING — @g hoisted but may surprise)
      • Nested %{ri} (ERROR — only outermost applies)
    """
    from tag_validator import validate_translation, Severity
    issues = validate_translation(offset, text)
    out = []
    for iss in issues:
        if iss.severity == Severity.INFO:
            continue   # skip pure info in the lightweight validator
        label = iss.severity.value
        out.append(f"[{label}] {iss.message}")
    return out


# ════════════════════════════════════════════════════════════════════════════════
#  SEARCH NORMALISATION
# ════════════════════════════════════════════════════════════════════════════════

def normalize_for_search(text: str) -> str:
    text = decode_pua_orig(text)
    text = strip_all_tags(text)
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    text = text.replace('\u3000', ' ')
    text = re.sub(r' {2,}', ' ', text)
    return text.lower()


def raw_for_search(text: str) -> str:
    text = decode_pua_orig(text)
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    text = text.replace('\u3000', ' ')
    text = re.sub(r' {2,}', ' ', text)
    return text.lower()


# ════════════════════════════════════════════════════════════════════════════════
#  GRID DISPLAY
# ════════════════════════════════════════════════════════════════════════════════

def grid_fmt(text: str, maxlen: int = 130) -> str:
    text = pua_to_fmt_tags(text)
    text = text.replace('\r\n', ' · ').replace('\n', ' · ').replace('\r', '')
    return text.strip()[:maxlen]


def tags_badge(orig: str, trans: str = '') -> str:
    parts: list[str] = []
    if has_pua_italic(orig):                        parts.append('ital')
    if '@b' in orig:                                parts.append('gb')
    elif '@g' in orig:                              parts.append('g')
    if GAME_CMD_RE.search(orig):                    parts.append('fx')
    if '■' in orig:                                 parts.append('■')
    if re.search(r'<[^|>]+\|[^>]*>', orig):        parts.append('«»')
    if trans:
        if '%{g}'  in trans or '%{/g}'  in trans:  parts.append('%g')
        if '%{ri}' in trans or '%{/ri}' in trans:  parts.append('%ri')
        if '%{i}'  in trans or '%{/i}'  in trans:  parts.append('%i')
        if '%{b}'  in trans or '%{/b}'  in trans:  parts.append('%b')
        if re.search(r'<[^|>]+\|[^>]*>', trans):  parts.append('‹›⚠')  # ⚠ = stripped
        if '#' in trans:                            parts.append('#')
    return ' '.join(parts)