from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from benchmark_transcription import (  # noqa: E402
    BenchmarkVariant,
    VariantParseError,
    build_variants,
    compute_wer,
    parse_args,
    parse_variant_spec,
)


class ParseVariantSpecTests(unittest.TestCase):
    def test_parses_full_spec(self) -> None:
        variant = parse_variant_spec("model=large-v3-turbo,filter=light,align=on")

        self.assertEqual(variant.model, "large-v3-turbo")
        self.assertEqual(variant.filter_preset, "light")
        self.assertTrue(variant.alignment)

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


if __name__ == "__main__":
    unittest.main()
