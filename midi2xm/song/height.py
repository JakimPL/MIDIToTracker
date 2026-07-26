"""How tall the patterns a song is cut into are.

Two ceilings meet here. A pattern's height is bounded by what the format's row field holds, and the number
of patterns by what its order table indexes — so a long piece cut into short patterns runs out of order
positions long before it runs out of music.

The height asked for is therefore a preference rather than a rule: it is honoured wherever the piece fits,
and raised as far as the row ceiling allows when honouring it would need more patterns than the song can
name. A piece longer than both ceilings together is one the format cannot hold at all, which the module's
own bounds report.
"""

from __future__ import annotations

from trackmod.xm.spec.ranges import MAX_PATTERNS, MAX_ROWS


def pattern_height(rows: int, *, preferred: int) -> int:
    """The tallest of the preferred height and the shortest one that keeps the order table in range."""
    needed = max(1, -(-max(rows, 1) // MAX_PATTERNS))
    return min(MAX_ROWS, max(preferred, needed))
