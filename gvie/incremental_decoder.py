"""Helpers for merging incremental transcript updates."""

from difflib import SequenceMatcher


def normalize_transcript(text: str) -> str:
    """Collapse whitespace and trim transcript text."""
    return " ".join(text.split()).strip()


def merge_transcript_chunks(previous: str, current: str) -> str:
    """Merge a new transcript candidate with the previous one."""

    previous = normalize_transcript(previous)
    current = normalize_transcript(current)

    if not previous:
        return current
    if not current:
        return previous
    if current == previous:
        return current
    if current.startswith(previous):
        return current
    if previous.startswith(current):
        return current

    previous_words = previous.split()
    current_words = current.split()
    max_overlap = min(len(previous_words), len(current_words))

    for overlap in range(max_overlap, 0, -1):
        if previous_words[-overlap:] == current_words[:overlap]:
            return " ".join(previous_words + current_words[overlap:])

    SequenceMatcher(None, previous, current).ratio()
    return current

