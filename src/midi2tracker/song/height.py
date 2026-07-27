from midi2tracker.tracker.target import TrackerTarget


def pattern_height(rows: int, *, preferred: int, target: TrackerTarget) -> int:
    """The tallest of the preferred height, the format's own floor, and what keeps the order table in range."""
    needed = max(target.min_rows, -(-max(rows, 1) // target.max_patterns))
    return min(target.max_rows, max(preferred, needed))
