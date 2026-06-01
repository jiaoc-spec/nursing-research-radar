from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class DigestLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.digest = load_module("daily_literature_digest", "scripts/daily_literature_digest.py")

    def test_common_locale_mapping(self):
        cases = {
            "de_DE": "de",
            "de-DE": "de",
            "en_US": "en",
            "en-GB": "en",
            "zh_CN": "zh-CN",
            "zh-Hans": "zh-CN",
            "zh-Hant": "zh-TW",
            "fr_FR": "fr",
            "ja_JP": "ja",
        }
        for locale_name, expected in cases.items():
            with self.subTest(locale_name=locale_name):
                self.assertEqual(self.digest.language_from_locale(locale_name), expected)

    def test_explicit_language_does_not_auto_detect(self):
        with mock.patch.object(self.digest, "detect_os_locale", return_value="de_DE"):
            self.assertEqual(self.digest.resolve_language("en"), ("explicit", "", "en"))
            self.assertEqual(self.digest.resolve_language("zh-CN"), ("explicit", "", "zh-CN"))
            self.assertEqual(self.digest.resolve_language("de"), ("explicit", "", "de"))

    def test_auto_uses_detected_locale(self):
        with mock.patch.object(self.digest, "detect_os_locale", return_value="de_DE"):
            self.assertEqual(self.digest.resolve_language("auto"), ("auto", "de_DE", "de"))

    def test_auto_detection_failure_falls_back_to_english(self):
        with mock.patch.object(self.digest, "detect_os_locale", return_value=""):
            self.assertEqual(self.digest.resolve_language("auto"), ("auto", "", "en"))


class EmailLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.email = load_module("nursing_literature_digest_email", "email-scripts/nursing-literature-digest-email.py")

    def test_email_language_normalization(self):
        cases = {
            "de_DE": "de",
            "en-GB": "en",
            "zh_CN": "zh-CN",
            "zh-Hans": "zh-CN",
            "zh-Hant": "zh-TW",
            "fr_FR": "fr",
            "ja_JP": "ja",
            "unsupported": "en",
            "": "en",
        }
        for language, expected in cases.items():
            with self.subTest(language=language):
                self.assertEqual(self.email.normalize_language(language), expected)


if __name__ == "__main__":
    unittest.main()
