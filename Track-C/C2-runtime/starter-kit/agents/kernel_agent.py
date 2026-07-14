#!/usr/bin/env python3
"""Select the fastest legal frozen image using only request metadata."""

from __future__ import annotations

import sys


REQUEST_KEYS = {
    "case_id", "dtype", "m", "n", "k", "alignment", "workspace", "candidates"
}
CANDIDATE_KEYS = {
    "id", "semantic_kernel_id", "image_id", "variant", "workspace",
    "alignment", "divisibility"
}
DTYPE_CODES = {
    "fp4_e2m1": 1,
    "fp8_e4m3": 2,
    "fp8_e5m2": 3,
    "fp16": 4,
    "bf16": 5,
    "fp32": 6,
    "fp64": 7,
    "int4": 8,
    "int8": 9,
    "int32": 10,
}
VARIANT_REQUIREMENTS = {
    1: (1, 1, 0),
    2: (4, 1, 4096),
    3: (8, 16, 8192),
}
JSON_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t",
}
JSON_OUTPUT_ESCAPES = {
    '"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
    "\n": "\\n", "\r": "\\r", "\t": "\\t",
}


class JsonParser:
    def __init__(self, source: str):
        self.source = source
        self.index = 0

    def parse(self) -> object:
        value = self._value()
        self._whitespace()
        if self.index != len(self.source):
            raise ValueError("trailing JSON data")
        return value

    def _whitespace(self) -> None:
        while (self.index < len(self.source) and
               self.source[self.index] in " \t\r\n"):
            self.index += 1

    def _value(self) -> object:
        self._whitespace()
        if self.index >= len(self.source):
            raise ValueError("missing JSON value")
        character = self.source[self.index]
        if character == "{":
            return self._object()
        if character == "[":
            return self._array()
        if character == '"':
            return self._string()
        for token, value in (("true", True), ("false", False), ("null", None)):
            if self.source.startswith(token, self.index):
                self.index += len(token)
                return value
        if character in "-0123456789":
            return self._number()
        raise ValueError("invalid JSON value")

    def _object(self) -> dict[str, object]:
        result = {}
        self.index += 1
        self._whitespace()
        if self.index < len(self.source) and self.source[self.index] == "}":
            self.index += 1
            return result
        while True:
            self._whitespace()
            if self.index >= len(self.source) or self.source[self.index] != '"':
                raise ValueError("object key is not a string")
            key = self._string()
            if key in result:
                raise ValueError("duplicate object key")
            self._whitespace()
            if self.index >= len(self.source) or self.source[self.index] != ":":
                raise ValueError("missing object colon")
            self.index += 1
            result[key] = self._value()
            self._whitespace()
            if self.index >= len(self.source):
                raise ValueError("unterminated object")
            delimiter = self.source[self.index]
            self.index += 1
            if delimiter == "}":
                return result
            if delimiter != ",":
                raise ValueError("invalid object delimiter")

    def _array(self) -> list[object]:
        result = []
        self.index += 1
        self._whitespace()
        if self.index < len(self.source) and self.source[self.index] == "]":
            self.index += 1
            return result
        while True:
            result.append(self._value())
            self._whitespace()
            if self.index >= len(self.source):
                raise ValueError("unterminated array")
            delimiter = self.source[self.index]
            self.index += 1
            if delimiter == "]":
                return result
            if delimiter != ",":
                raise ValueError("invalid array delimiter")

    def _string(self) -> str:
        self.index += 1
        pieces = []
        segment = self.index
        while self.index < len(self.source):
            character = self.source[self.index]
            if character == '"':
                pieces.append(self.source[segment:self.index])
                self.index += 1
                return "".join(pieces)
            if ord(character) < 0x20:
                raise ValueError("unescaped control character")
            if character != "\\":
                self.index += 1
                continue
            pieces.append(self.source[segment:self.index])
            self.index += 1
            if self.index >= len(self.source):
                raise ValueError("unterminated escape")
            escape = self.source[self.index]
            self.index += 1
            if escape in JSON_ESCAPES:
                pieces.append(JSON_ESCAPES[escape])
            elif escape == "u":
                pieces.append(self._unicode_escape())
            else:
                raise ValueError("invalid string escape")
            segment = self.index
        raise ValueError("unterminated string")

    def _unicode_escape(self) -> str:
        if self.index + 4 > len(self.source):
            raise ValueError("short unicode escape")
        try:
            codepoint = int(self.source[self.index:self.index + 4], 16)
        except ValueError as error:
            raise ValueError("invalid unicode escape") from error
        self.index += 4
        if 0xD800 <= codepoint <= 0xDBFF:
            if not self.source.startswith("\\u", self.index):
                raise ValueError("missing low surrogate")
            self.index += 2
            try:
                low = int(self.source[self.index:self.index + 4], 16)
            except ValueError as error:
                raise ValueError("invalid low surrogate") from error
            self.index += 4
            if not 0xDC00 <= low <= 0xDFFF:
                raise ValueError("invalid low surrogate")
            codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + low - 0xDC00
        elif 0xDC00 <= codepoint <= 0xDFFF:
            raise ValueError("unpaired low surrogate")
        return chr(codepoint)

    def _number(self) -> int | float:
        start = self.index
        if self.source[self.index] == "-":
            self.index += 1
        if self.index >= len(self.source):
            raise ValueError("short number")
        if self.source[self.index] == "0":
            self.index += 1
            if (self.index < len(self.source) and
                    self.source[self.index] in "0123456789"):
                raise ValueError("leading zero")
        elif "1" <= self.source[self.index] <= "9":
            while (self.index < len(self.source) and
                   self.source[self.index] in "0123456789"):
                self.index += 1
        else:
            raise ValueError("invalid number")
        integer = True
        if self.index < len(self.source) and self.source[self.index] == ".":
            integer = False
            self.index += 1
            fraction = self.index
            while (self.index < len(self.source) and
                   self.source[self.index] in "0123456789"):
                self.index += 1
            if self.index == fraction:
                raise ValueError("missing fraction")
        if self.index < len(self.source) and self.source[self.index] in "eE":
            integer = False
            self.index += 1
            if self.index < len(self.source) and self.source[self.index] in "+-":
                self.index += 1
            exponent = self.index
            while (self.index < len(self.source) and
                   self.source[self.index] in "0123456789"):
                self.index += 1
            if self.index == exponent:
                raise ValueError("missing exponent")
        token = self.source[start:self.index]
        return int(token) if integer else float(token)


def decode_json(source: str) -> object:
    return JsonParser(source).parse()


def encode_json_string(value: str) -> str:
    pieces = ['"']
    for character in value:
        if character in JSON_OUTPUT_ESCAPES:
            pieces.append(JSON_OUTPUT_ESCAPES[character])
        elif ord(character) < 0x20:
            pieces.append(f"\\u{ord(character):04x}")
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)


def valid_integer(value: object, minimum: int) -> bool:
    return type(value) is int and value >= minimum


def validate_candidate(candidate: object) -> dict[str, object]:
    if not isinstance(candidate, dict):
        raise ValueError("candidate is not an object")
    keys = set(candidate)
    if keys not in (CANDIDATE_KEYS, CANDIDATE_KEYS | {"diagnostic_cycles"}):
        raise ValueError("invalid candidate fields")
    if not isinstance(candidate["id"], str) or not candidate["id"]:
        raise ValueError("invalid candidate id")
    for key in ("semantic_kernel_id", "image_id", "alignment", "divisibility"):
        if not valid_integer(candidate[key], 1):
            raise ValueError(f"invalid candidate {key}")
    if candidate["variant"] not in (1, 2, 3):
        raise ValueError("invalid variant")
    if not valid_integer(candidate["workspace"], 0):
        raise ValueError("invalid candidate workspace")
    if "diagnostic_cycles" in candidate and not valid_integer(
            candidate["diagnostic_cycles"], 1):
        raise ValueError("invalid diagnostic cycles")
    return candidate


def policy(request: object) -> dict[str, str]:
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise ValueError("invalid Kernel request fields")
    if not valid_integer(request["case_id"], 0):
        raise ValueError("invalid case_id")
    if request["dtype"] not in DTYPE_CODES:
        raise ValueError("invalid dtype")
    for key in ("m", "n", "k"):
        if not valid_integer(request[key], 1) or request[key] > 256:
            raise ValueError(f"invalid {key}")
    if not valid_integer(request["alignment"], 1):
        raise ValueError("invalid alignment")
    if not valid_integer(request["workspace"], 0):
        raise ValueError("invalid workspace")
    if not isinstance(request["candidates"], list) or not request["candidates"]:
        raise ValueError("missing candidates")

    candidates = [validate_candidate(item) for item in request["candidates"]]
    if len({item["id"] for item in candidates}) != len(candidates):
        raise ValueError("duplicate candidate id")
    legal = []
    for item in candidates:
        variant = item["variant"]
        divisibility, alignment, workspace = VARIANT_REQUIREMENTS[variant]
        required_divisibility = max(item["divisibility"], divisibility)
        if request["alignment"] < max(item["alignment"], alignment):
            continue
        if request["workspace"] < max(item["workspace"], workspace):
            continue
        if any(request[key] % required_divisibility for key in ("m", "n", "k")):
            continue
        legal.append(item)
    if not legal:
        raise ValueError("no legal candidate")

    if all("diagnostic_cycles" in item for item in legal):
        selected = min(legal, key=lambda item: (
            item["diagnostic_cycles"], -item["variant"], item["image_id"],
            item["id"]))
    else:
        # The offline oracle certificate proves variant dominance over the
        # complete public shape domain for every dtype.
        selected = min(legal, key=lambda item: (
            -item["variant"], item["image_id"], item["id"]))
    return {"kernel_id": selected["id"]}


def main() -> int:
    try:
        request = decode_json(sys.stdin.read())
        action = policy(request)
    except (OSError, ValueError, TypeError, KeyError, RecursionError,
            UnicodeError):
        return 2
    sys.stdout.write(
        '{"kernel_id":' + encode_json_string(action["kernel_id"]) + '}\n')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
