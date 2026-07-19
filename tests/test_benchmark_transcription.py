from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from benchmark_transcription import (  # noqa: E402
    BenchmarkVariant,
    BenchmarkArgs,
    DatasetSample,
    VariantRunResult,
    VariantParseError,
    aggregate_results,
    build_variants,
    compute_cer,
    compute_error_breakdown,
    compute_metrics,
    load_dataset_manifest,
    compute_wer,
    parse_args,
    parse_variant_spec,
    run_benchmark,
)


class ParseVariantSpecTests(unittest.TestCase):
    def test_parses_full_spec(self) -> None:
        variant = parse_variant_spec("model=large-v3-turbo,filter=light,align=on,repeats=3,vad_threshold=0.35")

        self.assertEqual(variant.model, "large-v3-turbo")
        self.assertEqual(variant.filter_preset, "light")
        self.assertTrue(variant.alignment)
        self.assertEqual(variant.repeats, 3)
        self.assertEqual(variant.vad_threshold, 0.35)

    def test_rejects_non_positive_repeats(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("model=small,repeats=0")

    def test_defaults_filter_and_alignment_when_omitted(self) -> None:
        variant = parse_variant_spec("model=small")

        self.assertEqual(variant.model, "small")
        self.assertEqual(variant.filter_preset, "full")
        self.assertFalse(variant.alignment)

    def test_alignment_accepts_various_truthy_falsy_tokens(self) -> None:
        self.assertTrue(parse_variant_spec("model=small,align=true").alignment)
        self.assertTrue(parse_variant_spec("model=small,align=1").alignment)
        self.assertTrue(parse_variant_spec("model=small,align=yes").alignment)
        self.assertFalse(parse_variant_spec("model=small,align=false").alignment)
        self.assertFalse(parse_variant_spec("model=small,align=0").alignment)
        self.assertFalse(parse_variant_spec("model=small,align=no").alignment)

    def test_whitespace_and_case_are_normalized(self) -> None:
        variant = parse_variant_spec(" model = small , filter = NONE , align = ON ")

        self.assertEqual(variant.model, "small")
        self.assertEqual(variant.filter_preset, "none")
        self.assertTrue(variant.alignment)

    def test_missing_model_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("filter=full,align=off")

    def test_empty_spec_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("")
        with self.assertRaises(VariantParseError):
            parse_variant_spec("   ")

    def test_invalid_filter_preset_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("model=small,filter=turbo")

    def test_invalid_alignment_value_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("model=small,align=maybe")

    def test_malformed_fragment_without_equals_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("model=small,filter")

    def test_unknown_field_raises(self) -> None:
        with self.assertRaises(VariantParseError):
            parse_variant_spec("model=small,bogus=1")

    def test_variant_name_is_filesystem_safe(self) -> None:
        variant = parse_variant_spec("model=large-v3-turbo,filter=full,align=on")

        self.assertEqual(variant.name, "large-v3-turbo__full__align-on")
        self.assertNotIn("/", variant.name)
        self.assertNotIn(" ", variant.name)


class BuildVariantsTests(unittest.TestCase):
    def test_builds_list_from_multiple_specs(self) -> None:
        variants = build_variants(
            [
                "model=small,filter=full,align=off",
                "model=large-v3-turbo,filter=light,align=on",
            ]
        )

        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0], BenchmarkVariant("small", "full", False))
        self.assertEqual(variants[1], BenchmarkVariant("large-v3-turbo", "light", True))

    def test_empty_list_yields_empty_variants(self) -> None:
        self.assertEqual(build_variants([]), [])

    def test_duplicate_variant_names_raise(self) -> None:
        with self.assertRaises(VariantParseError):
            build_variants(
                [
                    "model=small,filter=full,align=off",
                    "model=small,filter=full,align=off",
                ]
            )

    def test_propagates_parse_error_from_individual_spec(self) -> None:
        with self.assertRaises(VariantParseError):
            build_variants(["model=small", "filter=full"])


class ParseArgsTests(unittest.TestCase):
    def test_parses_recordings_dir_and_single_variant(self) -> None:
        args = parse_args(
            ["nagrania/", "--variant", "model=small,filter=full,align=off"]
        )

        self.assertEqual(args.recordings_dir, Path("nagrania/"))
        self.assertEqual(len(args.variants), 1)
        self.assertEqual(args.variants[0].model, "small")

    def test_parses_multiple_repeated_variant_flags(self) -> None:
        args = parse_args(
            [
                "nagrania/",
                "--variant",
                "model=small,filter=full,align=off",
                "--variant",
                "model=large-v3-turbo,filter=light,align=on",
            ]
        )

        self.assertEqual(len(args.variants), 2)
        self.assertEqual(args.variants[0].filter_preset, "full")
        self.assertEqual(args.variants[1].filter_preset, "light")
        self.assertTrue(args.variants[1].alignment)

    def test_missing_variant_flag_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["nagrania/"])

    def test_missing_recordings_dir_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--variant", "model=small"])

    def test_invalid_variant_spec_exits(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["nagrania/", "--variant", "filter=full"])

    def test_output_dir_option_is_parsed(self) -> None:
        args = parse_args(
            [
                "nagrania/",
                "--variant",
                "model=small",
                "--output-dir",
                "/tmp/wyniki",
            ]
        )

        self.assertEqual(args.output_dir, Path("/tmp/wyniki"))

    def test_output_dir_defaults_to_none(self) -> None:
        args = parse_args(["nagrania/", "--variant", "model=small"])

        self.assertIsNone(args.output_dir)

    def test_dataset_manifest_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sample.wav").write_bytes(b"audio")
            manifest = root / "dataset.json"
            manifest.write_text('{"samples":[{"audio":"sample.wav","scenario":"noise","reference_text":"test"}]}')
            samples = load_dataset_manifest(manifest, root)

        self.assertEqual(samples[0].scenario, "noise")
        self.assertEqual(samples[0].audio_path.name, "sample.wav")


class ComputeWerTests(unittest.TestCase):
    def test_identical_texts_have_zero_wer(self) -> None:
        self.assertEqual(compute_wer("to jest test", "to jest test"), 0.0)

    def test_completely_different_texts_have_high_wer(self) -> None:
        wer = compute_wer("ala ma kota", "pies goni myszy")
        self.assertEqual(wer, 1.0)

    def test_partial_mismatch_has_fractional_wer(self) -> None:
        wer = compute_wer("ala ma kota", "ala ma psa")
        self.assertAlmostEqual(wer, 1 / 3)

    def test_empty_reference_returns_none(self) -> None:
        self.assertIsNone(compute_wer("", "cokolwiek"))

    def test_is_case_insensitive_and_ignores_punctuation(self) -> None:
        wer = compute_wer("Ala, ma kota!", "ala ma kota")
        self.assertEqual(wer, 0.0)

    def test_cer_and_error_breakdown_are_hand_calculated(self) -> None:
        self.assertEqual(compute_error_breakdown(["ala", "ma"], ["ola", "ma", "kota"]), {
            "substitutions": 1,
            "deletions": 0,
            "insertions": 1,
        })
        self.assertAlmostEqual(compute_cer("abc", "adc"), 1 / 3)

    def test_cer_empty_reference_is_not_zero(self) -> None:
        self.assertIsNone(compute_cer("", "tekst"))


class ExtendedMetricsTests(unittest.TestCase):
    def test_reports_raw_normalized_sdi_and_na_speaker_metrics(self) -> None:
        metrics = compute_metrics(
            reference="Ala, ma kota!",
            hypothesis="Ala ma psa",
            metadata={},
            hypothesis_segments=[],
        )

        self.assertAlmostEqual(metrics["normalized_wer"], 1 / 3)
        self.assertEqual(metrics["errors"], {"substitutions": 1, "deletions": 0, "insertions": 0})
        self.assertIsNone(metrics["speaker"]["der"]["value"])
        self.assertIn("brak", metrics["speaker"]["der"]["reason"].lower())

    def test_silence_and_required_phrase_metrics(self) -> None:
        metrics = compute_metrics(
            reference="",
            hypothesis="fałszywa mowa",
            metadata={"expected_silence": True, "required_phrases": ["fałszywa", "nieobecna"]},
            hypothesis_segments=[],
        )

        self.assertTrue(metrics["false_speech"]["detected"])
        self.assertEqual(metrics["false_speech"]["word_count"], 2)
        self.assertEqual(metrics["required_phrase_recall"], 0.5)

    def test_cpwer_is_invariant_to_speaker_label_permutation(self) -> None:
        metrics = compute_metrics(
            reference="cześć świecie druga osoba",
            hypothesis="cześć świecie druga osoba",
            metadata={
                "reference_segments": [
                    {"speaker": "A", "start": 0.0, "end": 1.0, "text": "cześć świecie"},
                    {"speaker": "B", "start": 1.0, "end": 2.0, "text": "druga osoba"},
                ]
            },
            hypothesis_segments=[
                {"speaker": "Speaker 2", "start": 0.0, "end": 1.0, "text": "cześć świecie"},
                {"speaker": "Speaker 1", "start": 1.0, "end": 2.0, "text": "druga osoba"},
            ],
        )

        self.assertEqual(metrics["speaker"]["cpwer"]["value"], 0.0)
        self.assertEqual(metrics["speaker"]["der"]["value"], 0.0)


class AggregationTests(unittest.TestCase):
    def test_aggregates_global_and_scenario_median_and_p95(self) -> None:
        variant = BenchmarkVariant("small")
        results = [
            VariantRunResult(variant, f"{index}.wav", duration, True, scenario="noise", metrics={"normalized_wer": wer})
            for index, (duration, wer) in enumerate(((1.0, 0.1), (2.0, 0.2), (9.0, 0.3)), start=1)
        ]

        summary = aggregate_results(results)

        self.assertEqual(summary["global"]["duration_seconds"]["median"], 2.0)
        self.assertEqual(summary["global"]["duration_seconds"]["p95"], 9.0)
        self.assertEqual(summary["scenarios"]["noise"]["count"], 3)


class DatasetManifestTests(unittest.TestCase):
    def test_manifest_preserves_scenario_and_reference_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sample.wav").write_bytes(b"audio")
            manifest = root / "dataset.json"
            manifest.write_text(json.dumps({"samples": [{
                "id": "quiet",
                "audio": "sample.wav",
                "scenario": "quiet-speech",
                "reference_text": "szept",
                "required_phrases": ["szept"],
            }]}), encoding="utf-8")

            samples = load_dataset_manifest(manifest, root)

        self.assertIsInstance(samples[0], DatasetSample)
        self.assertEqual(samples[0].sample_id, "quiet")
        self.assertEqual(samples[0].scenario, "quiet-speech")
        self.assertEqual(samples[0].reference_text, "szept")


class BenchmarkRunTests(unittest.TestCase):
    def test_provider_is_built_lazily_for_each_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recordings = root / "recordings"
            recordings.mkdir()
            (recordings / "sample.wav").write_bytes(b"audio")
            variants = [BenchmarkVariant("small"), BenchmarkVariant("medium")]
            args = BenchmarkArgs(recordings, variants, root / "out", run_id="lazy", warmup_runs=0)
            events: list[str] = []

            def fake_build(variant):
                events.append(f"build:{variant.name}")
                return object()

            async def fake_run(variant, sample, provider=None, repeat=1, phase="warmed_inference"):
                self.assertIsNotNone(provider)
                events.append(f"run:{variant.name}")
                return VariantRunResult(
                    variant, sample.audio_path.name, 1.0, True,
                    repeat=repeat, phase=phase, sample_id=sample.sample_id,
                    scenario=sample.scenario, metrics={"normalized_wer": 0.0, "cer": 0.0},
                )

            with (
                patch("benchmark_transcription._build_provider_for_variant", side_effect=fake_build),
                patch("benchmark_transcription._run_variant_on_sample", side_effect=fake_run),
            ):
                asyncio.run(run_benchmark(args))

        self.assertEqual(events, ["build:small__full__align-off", "run:small__full__align-off",
                                  "build:medium__full__align-off", "run:medium__full__align-off"])

    def test_three_repeats_reuse_run_artifacts_and_resume_skips_successes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recordings = root / "recordings"
            recordings.mkdir()
            (recordings / "sample.wav").write_bytes(b"audio")
            variant = BenchmarkVariant("small", repeats=3)
            args = BenchmarkArgs(recordings, [variant], root / "out", run_id="run-1", warmup_runs=1)

            async def fake_run(current_variant, sample, provider=None, repeat=1, phase="warmed_inference"):
                del provider
                return VariantRunResult(
                    current_variant,
                    sample.audio_path.name,
                    1.0,
                    True,
                    repeat=repeat,
                    phase=phase,
                    sample_id=sample.sample_id,
                    scenario=sample.scenario,
                    metrics={"normalized_wer": 0.0, "cer": 0.0},
                )

            with patch("benchmark_transcription._run_variant_on_sample", side_effect=fake_run) as mocked:
                output = asyncio.run(run_benchmark(args))
            self.assertEqual(mocked.call_count, 4)  # warm-up + 3 scored repeats
            self.assertEqual(json.loads((output / "run-manifest.json").read_text())["status"], "completed")

            args.resume = True
            with patch("benchmark_transcription._run_variant_on_sample", side_effect=fake_run) as resumed:
                asyncio.run(run_benchmark(args))
            resumed.assert_not_called()

    def test_resume_retries_failed_result_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recordings = root / "recordings"
            recordings.mkdir()
            (recordings / "sample.wav").write_bytes(b"audio")
            variant = BenchmarkVariant("small", repeats=2)
            args = BenchmarkArgs(recordings, [variant], root / "out", run_id="partial", warmup_runs=0)

            calls = 0
            async def first_run(current_variant, sample, provider=None, repeat=1, phase="warmed_inference"):
                nonlocal calls
                del provider
                calls += 1
                return VariantRunResult(
                    current_variant, sample.audio_path.name, 1.0, repeat != 1,
                    error="boom" if repeat == 1 else None, repeat=repeat, phase=phase,
                    sample_id=sample.sample_id, scenario=sample.scenario,
                    metrics={"normalized_wer": None, "cer": None},
                )

            with patch("benchmark_transcription._run_variant_on_sample", side_effect=first_run):
                asyncio.run(run_benchmark(args))
            self.assertEqual(calls, 2)

            args.resume = True
            with patch("benchmark_transcription._run_variant_on_sample", side_effect=first_run) as resumed:
                asyncio.run(run_benchmark(args))
            self.assertEqual(resumed.call_count, 1)


if __name__ == "__main__":
    unittest.main()
