from trackmod.xm.spec.ranges import MAX_PATTERNS, MAX_ROWS


def pattern_height(rows: int, *, preferred: int) -> int:
    """The tallest of the preferred height and the shortest one that keeps the order table in range."""
    needed = max(1, -(-max(rows, 1) // MAX_PATTERNS))
    return min(MAX_ROWS, max(preferred, needed))
