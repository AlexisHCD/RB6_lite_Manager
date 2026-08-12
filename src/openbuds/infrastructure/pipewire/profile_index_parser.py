"""Pure parsers for runtime WirePlumber profile listings."""

from __future__ import annotations

import re

# Compact form seen in some pw-cli versions: `index:0 id:0 name:off`.
_COMPACT_LINE = re.compile(r"\bindex:(\d+)\b.*?\bname:(\S+)")
# Tree form used by pw-cli 1.0.x: one `Object: ... Param:Profile` block per
# profile with `Int <n>` after Profile:index and `String "<name>"` after
# Profile:name.
_PROFILE_BLOCK = re.compile(r"Object:.*?Param:Profile.*?(?=\n\s*Object:|\Z)", re.DOTALL)
_BLOCK_INDEX = re.compile(r"Profile:index.*?Int\s+(\d+)", re.DOTALL)
_BLOCK_NAME = re.compile(r'Profile:name.*?String\s+"([^"]+)"', re.DOTALL)


def _profile_entries(output: str) -> list[tuple[int, str]]:
    """Parse profile index/name pairs while preserving output order."""
    entries: list[tuple[int, str]] = []
    for block in _PROFILE_BLOCK.finditer(output):
        index_match = _BLOCK_INDEX.search(block.group(0))
        name_match = _BLOCK_NAME.search(block.group(0))
        if index_match is not None and name_match is not None:
            entries.append((int(index_match.group(1)), name_match.group(1)))
    if entries:
        return entries
    for line in output.splitlines():
        match = _COMPACT_LINE.search(line)
        if match is not None:
            entries.append((int(match.group(1)), match.group(2)))
    return entries


def parse_profile_index(output: str, profile_name: str) -> int | None:
    """Return the index for an offered profile name, if present."""
    for index, name in _profile_entries(output):
        if name == profile_name:
            return index
    return None


def parse_profile_names(output: str) -> tuple[str, ...]:
    """Return offered profile names in the order reported by ``pw-cli``."""
    return tuple(name for _, name in _profile_entries(output))
