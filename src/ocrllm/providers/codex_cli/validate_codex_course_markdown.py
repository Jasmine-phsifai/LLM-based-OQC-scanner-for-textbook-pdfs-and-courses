"""Opt-in course-frame validation for Codex; no body rewriting or model audit."""

from __future__ import annotations

import re
import unicodedata

from ...errors import ConfigError, ProviderError
from ...image_group_limits import MAX_IMAGE_GROUP_COUNT

_FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
_DIRECT_PREFIX = re.compile(r"meta\s*:\s*frame\s+id\s*=\s*", re.IGNORECASE)
_RAW_CODE = re.compile(r"<(pre|code|script|style|svg)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_RAW_CODE_TO_END = re.compile(r"<(pre|code|script|style|svg)\b[^>]*>.*?(?:</\1\s*>|\Z)", re.IGNORECASE | re.DOTALL)
_MAX_MARKER_CHARACTERS = 512


def validate_codex_course_markdown(
    markdown: str,
    expected_names: tuple[str, ...],
    *,
    adjacent_repeat_limit: int | None = None,
) -> str:
    """Match every real frame comment once, normalizing only matched spans.

    Exact identities and same-name jpg omissions bind before fuzzy matching.
    Fuzzy candidates need a unique nearest expected marker and strictly less
    than 30 percent insertion/deletion cost over the full expected string.
    An already identified duplicate cannot impersonate another missing frame.
    Extra comments and unambiguous reversed frame order do not cause rejection.

    The separate optional repetition guard checks exact adjacent long prose
    lines within each frame only. It is not an inherited local OCR threshold.
    """
    if (type(expected_names) is not tuple or not expected_names
            or len(expected_names) > MAX_IMAGE_GROUP_COUNT
            or any(type(name) is not str or not name for name in expected_names)
            or len(set(expected_names)) != len(expected_names)):
        raise ConfigError("Course validation requires distinct original image names.",
                          code="CONFIG_INVALID", details={"provider_calls_attempted": 0})
    if (adjacent_repeat_limit is not None
            and (type(adjacent_repeat_limit) is not int or adjacent_repeat_limit < 3)):
        raise ConfigError("adjacent_repeat_limit must be None or an integer of at least 3.",
                          code="CONFIG_INVALID", details={"provider_calls_attempted": 0})
    expected = tuple(f"<!-- meta:frame id={name} -->" for name in expected_names)
    if any(len(marker) > _MAX_MARKER_CHARACTERS for marker in expected):
        raise ConfigError("A course frame marker exceeds the supported bounded length.",
                          code="CONFIG_INVALID", details={"provider_calls_attempted": 0})
    if type(markdown) is not str:
        _reject("invalid_unicode")
    try:
        markdown.encode("utf-8")
    except UnicodeEncodeError:
        _reject("invalid_unicode")
    if "\ufffd" in markdown:
        _reject("invalid_unicode")

    protected = _code_spans(markdown)
    candidates = _frame_comments(markdown, protected, max(map(len, expected)))
    assignments: dict[int, int] = {}
    identified: set[int] = set()
    # Exact complete markers outrank aliases (e.g. a source literally named x).
    for index, (_, _, comment) in enumerate(candidates):
        if comment in expected:
            assignments[index] = expected.index(comment)
            continue
        name = _direct_name(comment)
        exact = [i for i, value in enumerate(expected_names) if name == value]
        aliases = [i for i, value in enumerate(expected_names)
                   if value.endswith(".jpg") and name in (value[:-4], value[:-3])]
        matches = exact or aliases
        if len(matches) == 1:
            identity = matches[0]
            identified.add(index)
            # The filename binds identity, but does not waive the format budget.
            # Only the explicitly approved jpg omission is free of edit cost.
            comparison = expected[identity] if exact else f"<!-- meta:frame id={name} -->"
            if _insertion_deletion_distance(comment, comparison) * 10 < len(expected[identity]) * 3:
                assignments[index] = identity

    for index, (_, _, comment) in enumerate(candidates):
        if index in assignments or index in identified:
            continue
        distances = [
            _insertion_deletion_distance(comment, marker)
            if abs(len(comment) - len(marker)) * 10 < len(marker) * 3
            else len(comment) + len(marker)
            for marker in expected
        ]
        best = min(distances)
        matches = [i for i, cost in enumerate(distances)
                   if cost == best and cost * 10 < len(expected[i]) * 3]
        # Compare against every expected identity, including already covered
        # ones. Otherwise an A duplicate could silently fill a missing B.
        if len(matches) == 1:
            assignments[index] = matches[0]

    covered = set(assignments.values())
    if len(covered) != len(expected):
        _reject("course_frame_markers_invalid", expected_count=len(expected),
                matched_count=len(covered))
    matched = [(start, end, assignments[i]) for i, (start, end, _) in enumerate(candidates)
               if i in assignments]
    if adjacent_repeat_limit is not None:
        for index, (_, end, _) in enumerate(matched):
            following = matched[index + 1][0] if index + 1 < len(matched) else len(markdown)
            if _adjacent_prose_repetition(markdown[end:following], adjacent_repeat_limit):
                _reject("adjacent_repetition", consecutive_lines=adjacent_repeat_limit)
    pieces = []
    position = 0
    for start, end, identity in matched:
        pieces.extend((markdown[position:start], expected[identity]))
        position = end
    pieces.append(markdown[position:])
    return "".join(pieces)


def _reject(reason: str, **details: int) -> None:
    raise ProviderError(
        "The Codex course response did not satisfy its configured validation.",
        code="PROVIDER_RESPONSE_INVALID", details={"reason": reason, **details},
    ) from None


def _direct_name(comment: str) -> str | None:
    inner = comment[4:-3].strip()
    prefix = _DIRECT_PREFIX.match(inner)
    if prefix is None:
        return None
    value = inner[prefix.end():].strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _frame_comments(text: str, protected: list[tuple[int, int]], maximum: int):
    candidates = []
    position = protected_index = 0
    while True:
        start = text.find("<!--", position)
        if start < 0:
            break
        end = text.find("-->", start + 4)
        if end < 0:
            break
        end += 3
        position = end
        while protected_index < len(protected) and protected[protected_index][1] <= start:
            protected_index += 1
        if (protected_index < len(protected)
                and protected[protected_index][0] < end):
            continue
        if end - start > max(_MAX_MARKER_CHARACTERS, maximum * 1.3):
            continue  # Bound candidates while retaining direct same-name aliases.
        comment = text[start:end]
        # Candidate location must not require an already exact marker prefix:
        # small mistakes in meta/frame/id are part of the full-string distance.
        # Ordinary comments still need the same strict distance and unique
        # identity before they can contribute any frame coverage.
        candidates.append((start, end, comment))
    return candidates


def _insertion_deletion_distance(left: str, right: str) -> int:
    """A substitution is two edits, matching the approved local marker rule."""
    row = list(range(len(right) + 1))
    for index, character in enumerate(left, 1):
        following = [index]
        for other_index, other in enumerate(right, 1):
            following.append(row[other_index - 1] if character == other
                             else min(row[other_index] + 1, following[-1] + 1))
        row = following
    return row[-1]


def _code_spans(text: str, *, include_unclosed_html: bool = False) -> list[tuple[int, int]]:
    """Locate code containers only; never parse or judge their content."""
    raw_code = _RAW_CODE_TO_END if include_unclosed_html else _RAW_CODE
    spans = [(match.start(), match.end()) for match in raw_code.finditer(text)]
    offset = 0
    fence = None
    leading_blank = True
    for line in text.splitlines(keepends=True):
        opening = _FENCE.match(line)
        if fence is not None:
            if (opening is not None and opening[1][0] == fence[0]
                    and len(opening[1]) >= fence[1] and not line[opening.end():].strip()):
                spans.append((fence[2], offset + len(line)))
                fence = None
        elif opening is not None:
            fence = (opening[1][0], len(opening[1]), offset)
        elif (line.startswith(("    ", "\t"))
              and not (leading_blank and line.lstrip().startswith("<!--"))):
            spans.append((offset, offset + len(line)))
        else:
            runs = list(re.finditer(r"`+", line))
            index = 0
            while index < len(runs):
                closing = next((j for j in range(index + 1, len(runs))
                                if runs[j][0] == runs[index][0]), None)
                if closing is None:
                    index += 1
                else:
                    spans.append((offset + runs[index].start(), offset + runs[closing].end()))
                    index = closing + 1
        offset += len(line)
        if line.strip():
            leading_blank = False
    if fence is not None:
        spans.append((fence[2], len(text)))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _adjacent_prose_repetition(text: str, limit: int) -> bool:
    protected = _code_spans(text, include_unclosed_html=True)
    position = code_index = count = 0
    previous = None
    for line in text.splitlines(keepends=True):
        end = position + len(line)
        while code_index < len(protected) and protected[code_index][1] <= position:
            code_index += 1
        in_code = code_index < len(protected) and protected[code_index][0] < end
        position = end
        value = line.strip()
        if not value:
            continue
        if (in_code or len(value) < 40 or value[-1] not in ".!?。！？"
                or value.startswith(("#", ">", "- "))
                or any(c in value for c in "\\/$<>{}|=+_*^[]`")
                or sum(unicodedata.category(c).startswith("L") for c in value) < 20):
            previous, count = None, 0
            continue
        count = count + 1 if value == previous else 1
        if count >= limit:
            return True
        previous = value
    return False
