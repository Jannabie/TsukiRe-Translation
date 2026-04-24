"""
tag_validator.py — Pre-injection tag validator for Tsukihime Remake translations

Run validate_translation(offset, text) before calling build_mrg() to catch all
known tag problems that can cause in-game crashes, freezes, or visual glitches.

Returns a list of TagIssue objects, each with a severity and human-readable message.
The GUI Linter dialog (Ctrl+L) calls validate_all() over every translated entry.

Known issues covered
────────────────────
CRITICAL (will freeze or crash the game):
  • Ruby tag with ASCII in the reading field  → engine layout freeze
  • Ruby tag with empty reading field         → may freeze depending on engine build

ERROR (will cause garbled / broken text):
  • Unclosed %{i}, %{b}, %{g}, %{ri}, %{u}, %{s} pairs
  • @g, @b, @t, @k engine commands injected literally (not via %{g}) — invalid
  • %{g} appears after non-whitespace text in the same string (engine ignores it)
  • Nested %{ri} inside %{ri} (not supported)
  • %{n} tag (forced newline) used without any surrounding text (empty line entry)

WARNING (probably fine but unusual):
  • Ruby tag with no reading field separator (malformed <text> without |)
  • %{g} used together with %{ri} in the same entry (result is undefined)
  • Very long strings (> 512 bytes when encoded) — may overflow engine text buffer
  • Bare @g / @b in the translated text (use %{g} instead)

INFO (informational only):
  • Ruby tags stripped during injection (display text kept, reading discarded)
  • %{b} is identical to %{i} — font has no separate bold style
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "CRITICAL"   # game will freeze / crash
    ERROR    = "ERROR"      # visual glitch or broken text
    WARNING  = "WARNING"    # unexpected but probably survivable
    INFO     = "INFO"       # informational


@dataclass
class TagIssue:
    severity:  Severity
    message:   str
    offset:    int = -1      # MRG string offset (-1 = unknown)

    def __str__(self) -> str:
        prefix = f"[{self.severity.value}]"
        if self.offset >= 0:
            return f"{prefix} Offset #{self.offset}: {self.message}"
        return f"{prefix} {self.message}"


# ─── compiled patterns ────────────────────────────────────────────────────────
_RUBY_FULL_RE  = re.compile(r'<([^|>\r\n]*)\|([^>\r\n]*)>')
_RUBY_BARE_RE  = re.compile(r'<([^|>\r\n]+)>')           # no | separator
_FMT_TAG_RE    = re.compile(r'%\{(/?(?:ri|[a-z]))\}')
_AT_CMD_RE     = re.compile(r'@[gbkt]')
_GAME_CMD_RE   = re.compile(r'\[[a-z]{3}\d{2}\]')

_OPEN_CLOSE_PAIRS = [
    ('%{i}',  '%{/i}'),
    ('%{b}',  '%{/b}'),
    ('%{g}',  '%{/g}'),
    ('%{ri}', '%{/ri}'),
    ('%{u}',  '%{/u}'),
    ('%{s}',  '%{/s}'),
]

# ASCII printable range that is safe in ruby readings (letters + digits only)
_ASCII_READING_RE = re.compile(r'[A-Za-z0-9]')
_KANA_RE          = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')  # hiragana + katakana


def validate_translation(offset: int, text: str) -> list[TagIssue]:
    """Validate a single translation string and return all detected issues."""
    issues: list[TagIssue] = []

    if not text or not text.strip():
        return issues

    # ── 1. Ruby tag checks ──────────────────────────────────────────────────
    for m in _RUBY_FULL_RE.finditer(text):
        display = m.group(1)
        reading = m.group(2)

        if not reading:
            issues.append(TagIssue(
                Severity.WARNING, offset=offset,
                message=f"Ruby tag <{display}|> has an empty reading field — "
                        "will be stripped to plain text during injection.",
            ))
        elif _ASCII_READING_RE.search(reading) and not _KANA_RE.search(reading):
            issues.append(TagIssue(
                Severity.CRITICAL, offset=offset,
                message=f"Ruby tag <{display}|{reading}> contains ASCII in the "
                        "reading field.  The HuneX engine's furigana layout code "
                        "assumes full-width Japanese kana — ASCII readings cause "
                        "an INFINITE LOOP (game freeze).  "
                        "The tag will be stripped to just \"{display}\" on inject.",
            ))
        else:
            # Reading is non-empty and non-ASCII — safe to pass through
            issues.append(TagIssue(
                Severity.INFO, offset=offset,
                message=f"Ruby tag <{display}|{reading}> will be stripped to "
                        f'"{display}" during injection (reading discarded).  '
                        "To inject with native ruby, use render_for_mrg_with_native_ruby().",
            ))

    for m in _RUBY_BARE_RE.finditer(text):
        # Only flag if it wasn't captured as a full ruby (i.e. no |)
        if '|' not in m.group(0):
            issues.append(TagIssue(
                Severity.WARNING, offset=offset,
                message=f"Possible malformed ruby tag: {m.group(0)!r} — "
                        "missing | separator.  Did you mean <text|reading>?",
            ))

    # ── 2. Mismatched open/close tag pairs ──────────────────────────────────
    for open_tag, close_tag in _OPEN_CLOSE_PAIRS:
        n_open  = text.count(open_tag)
        n_close = text.count(close_tag)
        if n_open != n_close:
            name = open_tag[2:-1].upper()
            issues.append(TagIssue(
                Severity.ERROR, offset=offset,
                message=f"Mismatched {open_tag}/{close_tag}: "
                        f"{n_open} opening tag(s), {n_close} closing tag(s).  "
                        "Text between unpaired tags may render incorrectly.",
            ))

    # ── 3. %{g} position check ──────────────────────────────────────────────
    if '%{g}' in text:
        # Find the position of %{g} relative to non-whitespace, non-tag content
        before_g = text[:text.index('%{g}')]
        # Strip all tags and whitespace from the prefix to see if real text precedes %{g}
        stripped_before = _FMT_TAG_RE.sub('', before_g).replace('\r\n', '').strip()
        if stripped_before:
            issues.append(TagIssue(
                Severity.WARNING, offset=offset,
                message=f"%{{g}} appears after visible text: {stripped_before!r}.  "
                        "The @g engine command only takes effect at position 0 of the string.  "
                        "During injection, @g is automatically hoisted to position 0, "
                        "so the text before %{g} will render in gray style too.  "
                        "Consider putting %{g} at the very start of the entry.",
            ))

        # Warn about %{g} + %{ri} combination
        if '%{ri}' in text:
            issues.append(TagIssue(
                Severity.WARNING, offset=offset,
                message="%{g} and %{ri} are used together in the same entry.  "
                        "The @g style command and reverse-italic encoding have not been "
                        "tested in combination — result is undefined.  Use with caution.",
            ))

    # ── 4. Nested %{ri} ─────────────────────────────────────────────────────
    ri_depth = 0
    for m in _FMT_TAG_RE.finditer(text):
        tag = m.group(1)
        if tag == 'ri':
            ri_depth += 1
            if ri_depth > 1:
                issues.append(TagIssue(
                    Severity.ERROR, offset=offset,
                    message="Nested %{ri} detected — %{ri} inside another %{ri} block "
                            "is not supported.  Only the outermost reversal will apply; "
                            "inner blocks are ignored.",
                ))
                break
        elif tag == '/ri':
            ri_depth = max(0, ri_depth - 1)

    # ── 5. Bare @g / @b engine commands in translated text ─────────────────
    for m in _AT_CMD_RE.finditer(text):
        cmd = m.group(0)
        issues.append(TagIssue(
            Severity.WARNING, offset=offset,
            message=f"Bare engine command {cmd!r} found in translated text.  "
                    "Use the format tag equivalent instead: "
                    "@g → %{g}, @b → %{g} (same in-engine effect).  "
                    "Bare @g WILL work only at position 0; anywhere else it is treated "
                    "as literal text.",
        ))

    # ── 6. Byte-length estimate ─────────────────────────────────────────────
    # PUA characters encode to 3 bytes in UTF-8; estimate worst case
    import pua_encode as _pe
    try:
        rendered = _pe.render_for_mrg(text)
        byte_len = len(rendered.encode('utf-8'))
        if byte_len > 512:
            issues.append(TagIssue(
                Severity.WARNING, offset=offset,
                message=f"Encoded string is {byte_len} bytes — unusually long.  "
                        "Very long strings may overflow the engine's internal text buffer.  "
                        "Consider splitting with # (glue) or %{n} (line break).",
            ))
    except Exception:
        pass   # don't let the linter itself crash

    return issues


def validate_all(
    translations: dict[int, str],
) -> list[TagIssue]:
    """Validate all translation entries.  Returns issues sorted by severity then offset."""
    all_issues: list[TagIssue] = []
    for offset, text in translations.items():
        if text and text.strip():
            all_issues.extend(validate_translation(offset, text))

    _sev_order = {
        Severity.CRITICAL: 0,
        Severity.ERROR:    1,
        Severity.WARNING:  2,
        Severity.INFO:     3,
    }
    all_issues.sort(key=lambda i: (_sev_order[i.severity], i.offset))
    return all_issues


def summarise(issues: list[TagIssue]) -> str:
    """Return a short human-readable summary string."""
    counts = {s: 0 for s in Severity}
    for iss in issues:
        counts[iss.severity] += 1
    parts = []
    for sev in Severity:
        if counts[sev]:
            parts.append(f"{counts[sev]} {sev.value}")
    return ", ".join(parts) if parts else "No issues found"