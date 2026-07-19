from __future__ import annotations

import unittest

from echo_app.config import AppSettings
from echo_app.transcription import LocalTranscriptionProvider, SpeakerTurn, WordToken


class SpeakerAssignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = AppSettings()
        self.settings.speaker_overlap_threshold_seconds = 0.1
        self.provider = LocalTranscriptionProvider(self.settings)

    def test_picks_speaker_with_largest_overlap_not_nearest_midpoint(self) -> None:
        word = WordToken(start=1.0, end=2.0, text="hello")
        speaker, overlap = self.provider._pick_speaker_for_word(
            word,
            [SpeakerTurn(start=0.0, end=1.2, speaker="A"), SpeakerTurn(start=1.2, end=2.0, speaker="B")],
        )

        self.assertEqual(speaker, "B")
        self.assertAlmostEqual(overlap, 0.8)

    def test_gap_is_explicitly_unknown(self) -> None:
        speaker, overlap = self.provider._pick_speaker_for_word(
            WordToken(start=2.0, end=2.3, text="cisza"),
            [SpeakerTurn(start=0.0, end=1.0, speaker="A")],
        )

        self.assertEqual(speaker, "UNKNOWN")
        self.assertEqual(overlap, 0.0)

    def test_unknown_does_not_merge_with_previous_speaker(self) -> None:
        segments = self.provider._merge_words_into_segments(
            [WordToken(start=0, end=0.3, text="Ala"), WordToken(start=1, end=1.3, text="ma")],
            [SpeakerTurn(start=0, end=0.4, speaker="raw-a")],
        )

        self.assertEqual([segment.speaker for segment in segments], ["Speaker 1", "UNKNOWN"])

    def test_no_turns_keeps_single_speaker_fallback(self) -> None:
        segments = self.provider._merge_words_into_segments(
            [WordToken(start=0, end=0.3, text="Ala"), WordToken(start=0.4, end=0.7, text="ma")],
            [],
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "Speaker 1")


if __name__ == "__main__":
    unittest.main()
