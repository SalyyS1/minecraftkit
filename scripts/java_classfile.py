"""Small, dependency-free Java class-file reader for API inventory generation."""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any


BASE_ACCESS_NAMES = ((0x0001, "public"), (0x0002, "private"), (0x0004, "protected"), (0x0008, "static"), (0x0010, "final"))


class ClassFormatError(ValueError):
    """Raised when a class file is truncated or structurally invalid."""


class Reader:
    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)

    def take(self, size: int) -> bytes:
        value = self.stream.read(size)
        if len(value) != size:
            raise ClassFormatError("Unexpected end of class file")
        return value

    def u1(self) -> int:
        return self.take(1)[0]

    def u2(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def u4(self) -> int:
        return struct.unpack(">I", self.take(4))[0]


def decode_modified_utf8(raw: bytes) -> str:
    """Decode the JVM's strict modified UTF-8 format from CONSTANT_Utf8_info."""
    units: list[int] = []
    index = 0
    while index < len(raw):
        first = raw[index]
        if 0x01 <= first <= 0x7F:
            units.append(first)
            index += 1
            continue
        if 0xC0 <= first <= 0xDF:
            if index + 1 >= len(raw) or raw[index + 1] & 0xC0 != 0x80:
                raise ClassFormatError("Invalid modified UTF-8 two-byte sequence")
            value = ((first & 0x1F) << 6) | (raw[index + 1] & 0x3F)
            if value == 0:
                if first != 0xC0 or raw[index + 1] != 0x80:
                    raise ClassFormatError("Invalid modified UTF-8 NUL sequence")
            elif value < 0x80:
                raise ClassFormatError("Overlong modified UTF-8 sequence")
            units.append(value)
            index += 2
            continue
        if 0xE0 <= first <= 0xEF:
            if index + 2 >= len(raw) or raw[index + 1] & 0xC0 != 0x80 or raw[index + 2] & 0xC0 != 0x80:
                raise ClassFormatError("Invalid modified UTF-8 three-byte sequence")
            value = ((first & 0x0F) << 12) | ((raw[index + 1] & 0x3F) << 6) | (raw[index + 2] & 0x3F)
            if value < 0x800:
                raise ClassFormatError("Overlong modified UTF-8 sequence")
            units.append(value)
            index += 3
            continue
        raise ClassFormatError("Invalid modified UTF-8 leading byte")

    result: list[str] = []
    index = 0
    while index < len(units):
        value = units[index]
        if 0xD800 <= value <= 0xDBFF:
            if index + 1 >= len(units) or not 0xDC00 <= units[index + 1] <= 0xDFFF:
                raise ClassFormatError("Unpaired high surrogate in modified UTF-8")
            codepoint = 0x10000 + ((value - 0xD800) << 10) + (units[index + 1] - 0xDC00)
            result.append(chr(codepoint))
            index += 2
            continue
        if 0xDC00 <= value <= 0xDFFF:
            raise ClassFormatError("Unpaired low surrogate in modified UTF-8")
        result.append(chr(value))
        index += 1
    return "".join(result)


@dataclass
class ConstantPool:
    values: list[Any]

    def item(self, index: int) -> Any:
        if index <= 0 or index >= len(self.values):
            raise ClassFormatError(f"Invalid constant-pool index {index}")
        return self.values[index]

    def utf8(self, index: int) -> str:
        value = self.item(index)
        if not isinstance(value, tuple) or value[0] != "utf8":
            raise ClassFormatError(f"Constant {index} is not UTF-8")
        return value[1]

    def class_name(self, index: int) -> str | None:
        if index == 0:
            return None
        value = self.item(index)
        if not isinstance(value, tuple) or value[0] != "class":
            raise ClassFormatError(f"Constant {index} is not a class")
        return self.utf8(value[1]).replace("/", ".")

    def literal(self, index: int) -> Any:
        value = self.item(index)
        if not isinstance(value, tuple):
            return None
        if value[0] in {"integer", "float", "long", "double"}:
            return value[1]
        if value[0] == "string":
            return self.utf8(value[1])
        return None


def _constant_pool(reader: Reader) -> ConstantPool:
    count = reader.u2()
    values: list[Any] = [None] * count
    index = 1
    while index < count:
        tag = reader.u1()
        if tag == 1:
            raw = reader.take(reader.u2())
            values[index] = ("utf8", decode_modified_utf8(raw))
        elif tag == 3:
            values[index] = ("integer", struct.unpack(">i", reader.take(4))[0])
        elif tag == 4:
            values[index] = ("float", struct.unpack(">f", reader.take(4))[0])
        elif tag == 5:
            values[index] = ("long", struct.unpack(">q", reader.take(8))[0])
            index += 1
        elif tag == 6:
            values[index] = ("double", struct.unpack(">d", reader.take(8))[0])
            index += 1
        elif tag == 7:
            values[index] = ("class", reader.u2())
        elif tag == 8:
            values[index] = ("string", reader.u2())
        elif tag in {9, 10, 11}:
            values[index] = ("ref", reader.u2(), reader.u2())
        elif tag == 12:
            values[index] = ("name_type", reader.u2(), reader.u2())
        elif tag == 15:
            values[index] = ("method_handle", reader.u1(), reader.u2())
        elif tag in {16, 19, 20}:
            values[index] = ("index", reader.u2())
        elif tag in {17, 18}:
            values[index] = ("dynamic", reader.u2(), reader.u2())
        else:
            raise ClassFormatError(f"Unsupported constant-pool tag {tag}")
        index += 1
    return ConstantPool(values)


def _attributes(reader: Reader, pool: ConstantPool) -> dict[str, list[bytes]]:
    result: dict[str, list[bytes]] = {}
    for _ in range(reader.u2()):
        name = pool.utf8(reader.u2())
        result.setdefault(name, []).append(reader.take(reader.u4()))
    return result


def _attribute_u2(data: bytes) -> int | None:
    return struct.unpack(">H", data)[0] if len(data) >= 2 else None


def _member(reader: Reader, pool: ConstantPool) -> dict[str, Any]:
    access = reader.u2()
    name = pool.utf8(reader.u2())
    descriptor = pool.utf8(reader.u2())
    attrs = _attributes(reader, pool)
    signature_index = _attribute_u2(attrs.get("Signature", [b""])[0])
    constant_index = _attribute_u2(attrs.get("ConstantValue", [b""])[0])
    exceptions: list[str] = []
    if attrs.get("Exceptions"):
        values = Reader(attrs["Exceptions"][0])
        exceptions = [pool.class_name(values.u2()) or "" for _ in range(values.u2())]
    return {
        "access": access,
        "name": name,
        "descriptor": descriptor,
        "signature": pool.utf8(signature_index) if signature_index else None,
        "constant": pool.literal(constant_index) if constant_index else None,
        "exceptions": exceptions,
        "deprecated": "Deprecated" in attrs,
    }


def parse_class(data: bytes) -> dict[str, Any]:
    """Parse the declaration-level API metadata of one JVM class file."""
    reader = Reader(data)
    if reader.u4() != 0xCAFEBABE:
        raise ClassFormatError("Invalid class magic")
    minor, major = reader.u2(), reader.u2()
    pool = _constant_pool(reader)
    access = reader.u2()
    class_index, super_index = reader.u2(), reader.u2()
    class_name = pool.class_name(class_index)
    if not class_name:
        raise ClassFormatError("Missing class name")
    interfaces = [pool.class_name(reader.u2()) for _ in range(reader.u2())]
    fields = [_member(reader, pool) for _ in range(reader.u2())]
    methods = [_member(reader, pool) for _ in range(reader.u2())]
    attrs = _attributes(reader, pool)
    signature_index = _attribute_u2(attrs.get("Signature", [b""])[0])
    effective_access = access
    for payload in attrs.get("InnerClasses", []):
        nested = Reader(payload)
        for _ in range(nested.u2()):
            inner_index = nested.u2()
            nested.u2()  # outer class
            nested.u2()  # inner simple name
            inner_access = nested.u2()
            if inner_index and pool.class_name(inner_index) == class_name:
                effective_access = inner_access
    return {
        "name": class_name,
        "major": major,
        "minor": minor,
        "access": effective_access,
        "super": pool.class_name(super_index),
        "interfaces": [value for value in interfaces if value],
        "signature": pool.utf8(signature_index) if signature_index else None,
        "fields": fields,
        "methods": methods,
        "deprecated": "Deprecated" in attrs,
        "record": "Record" in attrs,
    }


def modifiers(access: int, *, member_kind: str = "class") -> list[str]:
    extra = {
        "class": ((0x0200, "interface"), (0x0400, "abstract"), (0x1000, "synthetic"), (0x2000, "annotation"), (0x4000, "enum")),
        "field": ((0x0040, "volatile"), (0x0080, "transient"), (0x1000, "synthetic"), (0x4000, "enum")),
        "method": ((0x0020, "synchronized"), (0x0040, "bridge"), (0x0080, "varargs"), (0x0100, "native"), (0x0400, "abstract"), (0x0800, "strict"), (0x1000, "synthetic")),
        "constructor": ((0x0080, "varargs"), (0x1000, "synthetic")),
    }.get(member_kind, ())
    return [name for bit, name in (*BASE_ACCESS_NAMES, *extra) if access & bit]


def visibility(access: int) -> str:
    if access & 0x0001:
        return "public"
    if access & 0x0004:
        return "protected"
    if access & 0x0002:
        return "private"
    return "package"


def _descriptor_type(descriptor: str, offset: int, *, allow_void: bool) -> tuple[str, int]:
    if offset < 0 or offset >= len(descriptor):
        raise ClassFormatError(f"Truncated descriptor {descriptor!r}")
    arrays = 0
    while offset < len(descriptor) and descriptor[offset] == "[":
        arrays += 1
        if arrays > 255:
            raise ClassFormatError("Descriptor exceeds 255 array dimensions")
        offset += 1
    if offset >= len(descriptor):
        raise ClassFormatError(f"Truncated descriptor {descriptor!r}")
    code = descriptor[offset]
    primitives = {"B": "byte", "C": "char", "D": "double", "F": "float", "I": "int", "J": "long", "S": "short", "Z": "boolean", "V": "void"}
    if code == "L":
        end = descriptor.find(";", offset + 1)
        binary_name = descriptor[offset + 1 : end] if end >= 0 else ""
        if end < 0 or not binary_name or any(char in binary_name for char in ".[;"):
            raise ClassFormatError(f"Invalid object descriptor {descriptor!r}")
        value, offset = binary_name.replace("/", "."), end + 1
    elif code in primitives:
        if code == "V" and (not allow_void or arrays):
            raise ClassFormatError(f"Void is not valid here in descriptor {descriptor!r}")
        value, offset = primitives[code], offset + 1
    else:
        raise ClassFormatError(f"Unknown descriptor type {code!r} in {descriptor!r}")
    return value + "[]" * arrays, offset


def descriptor_type(descriptor: str, offset: int = 0) -> tuple[str, int]:
    """Parse one non-void field descriptor and require full consumption at offset zero."""
    value, end = _descriptor_type(descriptor, offset, allow_void=False)
    if offset == 0 and end != len(descriptor):
        raise ClassFormatError(f"Trailing data in descriptor {descriptor!r}")
    return value, end


def method_descriptor(descriptor: str) -> tuple[list[str], str]:
    if not descriptor.startswith("("):
        raise ClassFormatError(f"Invalid method descriptor {descriptor!r}")
    offset, parameters = 1, []
    while offset < len(descriptor) and descriptor[offset] != ")":
        value, offset = _descriptor_type(descriptor, offset, allow_void=False)
        parameters.append(value)
    if offset >= len(descriptor) or descriptor[offset] != ")":
        raise ClassFormatError(f"Unterminated method descriptor {descriptor!r}")
    return_type, end = _descriptor_type(descriptor, offset + 1, allow_void=True)
    if end != len(descriptor):
        raise ClassFormatError(f"Trailing data in method descriptor {descriptor!r}")
    return parameters, return_type
