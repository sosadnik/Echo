from __future__ import annotations

import logging
from pathlib import Path

from .transcription import WordToken

logger = logging.getLogger(__name__)


class AlignmentError(RuntimeError):
    pass


class ForcedAligner:
    """Wyrównuje słowa Whispera przez wav2vec2 (WhisperX `align()`).

    Przy braku zależności `whisperx` albo błędzie alignmentu loguje ostrzeżenie
    i zwraca surowe słowa Whispera — pipeline transkrypcji nie może się wywalić
    przez alignment.
    """

    def __init__(self, device: str = "cpu", language: str | None = None, max_words_per_chunk: int = 120) -> None:
        self.device = device
        self.language = language
        self.max_words_per_chunk = max(1, int(max_words_per_chunk))
        self._model = None
        self._metadata = None
        self.warnings: list[str] = []

    def align(
        self,
        words: list[WordToken],
        audio_path: Path,
        source_name: str,
    ) -> list[WordToken]:
        if not words:
            return words
        self.warnings = []
        aligned: list[WordToken] = []
        for chunk_start in range(0, len(words), self.max_words_per_chunk):
            chunk = words[chunk_start : chunk_start + self.max_words_per_chunk]
            try:
                corrected = self._align_with_whisperx(chunk, audio_path)
                aligned.extend(self._merge_aligned_chunk(chunk, corrected))
            except Exception as exc:
                self.warnings.append(f"chunk {chunk_start // self.max_words_per_chunk}: {exc}")
                logger.warning(
                    "Alignment nie powiodl sie dla `%s` (chunk %s), uzywam surowych timestampow: %s",
                    source_name,
                    chunk_start // self.max_words_per_chunk,
                    exc,
                )
                aligned.extend(chunk)
        return aligned

    def _merge_aligned_chunk(self, original: list[WordToken], corrected: list[WordToken]) -> list[WordToken]:
        """Nie gubi tokenów, gdy WhisperX zwróci tylko część słów chunku."""
        output: list[WordToken] = []
        corrected_index = 0
        for raw in original:
            if corrected_index < len(corrected) and corrected[corrected_index].text.strip() == raw.text.strip():
                output.append(corrected[corrected_index])
                corrected_index += 1
            else:
                output.append(raw)
        return output

    def _align_with_whisperx(self, words: list[WordToken], audio_path: Path) -> list[WordToken]:
        import whisperx

        model_a, metadata = self._load_model(whisperx)
        segment = {
            "start": words[0].start,
            "end": words[-1].end,
            "text": " ".join(word.text for word in words),
            "words": [
                {"word": word.text, "start": word.start, "end": word.end}
                for word in words
            ],
        }
        audio = whisperx.load_audio(str(audio_path))
        result = whisperx.align(
            [segment],
            model_a,
            metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        aligned_words: list[WordToken] = []
        for aligned_segment in result.get("segments", []):
            for word in aligned_segment.get("words", []):
                start = word.get("start")
                end = word.get("end")
                text = str(word.get("word") or word.get("text") or "").strip()
                if start is None or end is None or not text:
                    continue
                aligned_words.append(WordToken(start=float(start), end=float(end), text=text))

        if not aligned_words:
            raise AlignmentError("Aligner zwrocil pusty wynik.")
        return aligned_words

    def _load_model(self, whisperx_module):
        if self._model is not None:
            return self._model, self._metadata
        self._model, self._metadata = whisperx_module.load_align_model(
            language_code=self.language or "pl",
            device=self.device,
        )
        return self._model, self._metadata
