"""Pure-text helpers for figure captions (no model imports)."""

from __future__ import annotations


def caption_is_degenerate(caption: str) -> bool:
    """
    True for a BLIP decoding loop such as
    'the different types of the different types of the different types of ...'.
    A 2+ word phrase repeated 3+ times back to back (or a 3+ word phrase twice)
    never appears in a caption a person wrote.
    """
    words = [w.lower().strip(",.;:") for w in (caption or "").split()]
    for n in range(2, 7):
        for i in range(0, len(words) - 2 * n + 1):
            unit = words[i:i + n]
            reps = 1
            j = i + n
            while words[j:j + n] == unit:
                reps += 1
                j += n
            if reps >= 3 or (n >= 3 and reps >= 2):
                return True
    return False


def collapse_repeated_phrases(words: list[str]) -> list[str]:
    """'x y z x y z x y z x y' -> 'x y z' (drops trailing partial repeat too)."""
    changed = True
    while changed:
        changed = False
        low = [w.lower().strip(",.;:") for w in words]
        for n in range(6, 1, -1):
            for i in range(0, len(words) - 2 * n + 1):
                unit = low[i:i + n]
                if low[i + n:i + 2 * n] != unit:
                    continue
                j = i + n
                while low[j:j + n] == unit:
                    j += n
                # trailing fragment that is just the start of the unit
                k = 0
                while j + k < len(low) and k < n and low[j + k] == unit[k]:
                    k += 1
                if j + k == len(low):
                    j += k
                words = words[:i + n] + words[j:]
                changed = True
                break
            if changed:
                break
    return words
