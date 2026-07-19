from __future__ import annotations

import unittest

from echo_app.schemas import AsrSegment, AsrWord
from echo_app.transcription import AsrResult, WordToken


class AsrResultTests(unittest.TestCase):
    def test_alignment_updates_timestamps_without_changing_segment_text_or_word_count(self) -> None:
        result = AsrResult(
            text="Cześć, świecie!",
            segments=[
                AsrSegment(
                    start=0,
                    end=2,
                    text="Cześć, świecie!",
                    words=[
                        AsrWord(text="Cześć", start=0, end=0.5),
                        AsrWord(text="świecie", start=0.6, end=1.2),
                    ],
                )
            ],
        )

        updated = result.with_aligned_words(
            [
                WordToken(text="Cześć", start=0.1, end=0.4),
                WordToken(text="świecie", start=0.7, end=1.1, aligned=False),
            ]
        )

        self.assertEqual(updated.text, "Cześć, świecie!")
        self.assertEqual(updated.segments[0].text, "Cześć, świecie!")
        self.assertEqual(len(updated.segments[0].words), 2)
        self.assertEqual(updated.segments[0].words[0].start, 0.1)
        self.assertFalse(updated.segments[0].words[1].aligned)


if __name__ == "__main__":
    unittest.main()
