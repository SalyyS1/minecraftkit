from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from extract_api import normalized_constant  # noqa: E402
from java_classfile import (  # noqa: E402
    ClassFormatError,
    decode_modified_utf8,
    descriptor_type,
    method_descriptor,
    parse_class,
)


def u1(value: int) -> bytes:
    return struct.pack(">B", value)


def u2(value: int) -> bytes:
    return struct.pack(">H", value)


def u4(value: int) -> bytes:
    return struct.pack(">I", value)


def utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    return u1(1) + u2(len(raw)) + raw


def fixture_class() -> bytes:
    pool = [
        utf8("Fixture"), u1(7) + u2(1), utf8("java/lang/Object"), u1(7) + u2(3),
        utf8("VALUE"), utf8("Z"), utf8("ConstantValue"), u1(3) + struct.pack(">i", 1),
        utf8("<init>"), utf8("()V"), utf8("greet"),
        utf8("(Ljava/lang/String;)Ljava/lang/String;"), utf8("Exceptions"),
        utf8("java/io/IOException"), u1(7) + u2(14),
    ]
    field = u2(0x0019) + u2(5) + u2(6) + u2(1) + u2(7) + u4(2) + u2(8)
    constructor = u2(0x0001) + u2(9) + u2(10) + u2(0)
    method = u2(0x0001) + u2(11) + u2(12) + u2(1) + u2(13) + u4(4) + u2(1) + u2(15)
    return (
        struct.pack(">IHHH", 0xCAFEBABE, 0, 61, len(pool) + 1)
        + b"".join(pool)
        + u2(0x0021) + u2(2) + u2(4) + u2(0)
        + u2(1) + field + u2(2) + constructor + method + u2(0)
    )


class ClassFileTests(unittest.TestCase):
    def test_parses_declaration_metadata(self) -> None:
        parsed = parse_class(fixture_class())
        self.assertEqual(parsed["name"], "Fixture")
        self.assertEqual(parsed["major"], 61)
        self.assertEqual(parsed["fields"][0]["constant"], 1)
        self.assertEqual(parsed["methods"][1]["exceptions"], ["java.io.IOException"])

    def test_descriptors_are_strict(self) -> None:
        self.assertEqual(descriptor_type("[[Ljava/lang/String;"), ("java.lang.String[][]", 20))
        self.assertEqual(method_descriptor("(ILjava/lang/String;[Z)J"), (["int", "java.lang.String", "boolean[]"], "long"))
        for invalid in ("", "V", "L;", "Ljava.lang.String;", "Iextra", "[V"):
            with self.subTest(invalid=invalid), self.assertRaises(ClassFormatError):
                descriptor_type(invalid)
        for invalid in ("(", "(V)V", "()VI", "not-a-method"):
            with self.subTest(invalid=invalid), self.assertRaises(ClassFormatError):
                method_descriptor(invalid)

    def test_modified_utf8_handles_nul_and_supplementary(self) -> None:
        self.assertEqual(decode_modified_utf8(b"A\xc0\x80B"), "A\x00B")
        self.assertEqual(decode_modified_utf8(b"\xed\xa0\xbd\xed\xb8\x80"), "😀")
        for invalid in (b"\x00", b"\xc1\x81", b"\xf0\x90\x80\x80", b"\xed\xa0\x80"):
            with self.subTest(invalid=invalid), self.assertRaises(ClassFormatError):
                decode_modified_utf8(invalid)

    def test_constants_are_strict_json_safe(self) -> None:
        self.assertIs(normalized_constant(1, "Z"), True)
        self.assertEqual(normalized_constant(float("nan"), "F"), "NaN")
        self.assertEqual(normalized_constant(float("inf"), "D"), "Infinity")
        self.assertEqual(normalized_constant(float("-inf"), "D"), "-Infinity")


if __name__ == "__main__":
    unittest.main()
