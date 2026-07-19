# Benchmark pipeline'u transkrypcji

Harness zapisuje wersjonowane artefakty `benchmark-artifact/v1`, rozdziela warm-up od
scorowanych powtórzeń i może bezpiecznie wznowić przerwany run.

## Manifest prywatnego datasetu

Manifest oraz audio trzymaj w `data/` albo `samples/` (oba katalogi są ignorowane przez git):

```json
{
  "samples": [
    {
      "id": "quiet-speech",
      "audio": "quiet.wav",
      "scenario": "quiet-speech",
      "reference_text": "tekst referencyjny",
      "required_phrases": ["ważna wypowiedź"],
      "expected_silence": false,
      "reference_segments": [
        {"speaker": "A", "start": 0.0, "end": 2.4, "text": "tekst referencyjny"}
      ]
    }
  ]
}
```

`reference_segments` są opcjonalne. Bez nich DER/JER/cpWER i błąd timestampów mają
wartość `N/A` wraz z powodem — nigdy sztuczne zero.

## Uruchomienie i wznowienie

```bash
PYTHONPATH=src python3 scripts/benchmark_transcription.py data/benchmark-dataset \
  --dataset-manifest data/benchmark-dataset/dataset.json \
  --run-id control-2026-07-19 \
  --warmup-runs 1 \
  --variant model=large-v3,filter=none,align=off,repeats=3 \
  --variant model=large-v3-turbo,filter=full,align=on,repeats=3

# Po przerwaniu: kompletne sukcesy są pomijane, awarie ponawiane.
PYTHONPATH=src python3 scripts/benchmark_transcription.py data/benchmark-dataset \
  --dataset-manifest data/benchmark-dataset/dataset.json \
  --run-id control-2026-07-19 --resume \
  --variant model=large-v3,filter=none,align=off,repeats=3
```

Każdy wariant ma jedną instancję providera, jeden niescorowany warm-up oraz warmed
inference. `run-manifest.json` pozostaje w stanie `running`, `interrupted` albo
`completed`; JSON-y i podsumowanie są zapisywane atomowo.

## Metryki

- normalized/raw WER, CER oraz substitutions/deletions/insertions;
- false-speech dla `expected_silence` i recall `required_phrases`;
- cpWER, DER, JER oraz średni błąd timestampów przy gold segmentach speakerów;
- mediany i p95 czasu globalnie, per scenariusz i per wariant.

Wynik oparty tylko na pseudo-labelach lub pojedynczym nagraniu służy do smoke testu,
nie do zmiany ustawień domyślnych.
