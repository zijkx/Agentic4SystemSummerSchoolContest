#!/usr/bin/env python3
"""Choose the oracle-optimal legal frozen image from request metadata."""

import sys


WS = " \t\r\n"
HEX = "0123456789abcdefABCDEF"
ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
       "n": "\n", "r": "\r", "t": "\t"}
OUT = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
       "\n": "\\n", "\r": "\\r", "\t": "\\t"}
REQUEST_KEYS = {
    "case_id", "dtype", "m", "n", "k", "alignment", "workspace", "candidates"
}
CANDIDATE_KEYS = {
    "id", "semantic_kernel_id", "image_id", "variant", "workspace",
    "alignment", "divisibility"
}
CANDIDATE_DIAGNOSTIC_KEYS = CANDIDATE_KEYS | {"diagnostic_cycles"}
DTYPES = {
    "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
    "fp32", "fp64", "int4", "int8", "int32"
}
REQUIREMENTS = ((1, 1, 0), (4, 1, 4096), (8, 16, 8192))


def decode(source):
    index = 0
    size = len(source)

    def whitespace():
        nonlocal index
        while index < size and source[index] in WS:
            index += 1

    def string():
        nonlocal index
        index += 1
        start = index
        pieces = []
        while index < size:
            character = source[index]
            if character == '"':
                pieces.append(source[start:index])
                index += 1
                return "".join(pieces)
            if ord(character) < 0x20:
                raise ValueError
            if character != "\\":
                index += 1
                continue
            pieces.append(source[start:index])
            index += 1
            if index >= size:
                raise ValueError
            escape = source[index]
            index += 1
            if escape in ESC:
                pieces.append(ESC[escape])
            elif escape == "u":
                digits = source[index:index + 4]
                if len(digits) != 4 or any(c not in HEX for c in digits):
                    raise ValueError
                codepoint = int(digits, 16)
                index += 4
                if 0xD800 <= codepoint <= 0xDBFF:
                    if source[index:index + 2] != "\\u":
                        raise ValueError
                    digits = source[index + 2:index + 6]
                    if len(digits) != 4 or any(c not in HEX for c in digits):
                        raise ValueError
                    low = int(digits, 16)
                    if not 0xDC00 <= low <= 0xDFFF:
                        raise ValueError
                    codepoint = (0x10000 + ((codepoint - 0xD800) << 10) +
                                 low - 0xDC00)
                    index += 6
                elif 0xDC00 <= codepoint <= 0xDFFF:
                    raise ValueError
                pieces.append(chr(codepoint))
            else:
                raise ValueError
            start = index
        raise ValueError

    def number():
        nonlocal index
        start = index
        if source[index] == "-":
            index += 1
        if index >= size:
            raise ValueError
        if source[index] == "0":
            index += 1
            if index < size and "0" <= source[index] <= "9":
                raise ValueError
        elif "1" <= source[index] <= "9":
            while index < size and "0" <= source[index] <= "9":
                index += 1
        else:
            raise ValueError
        return int(source[start:index])

    def value():
        nonlocal index
        whitespace()
        if index >= size:
            raise ValueError
        character = source[index]
        if character == '"':
            return string()
        if character == "-" or "0" <= character <= "9":
            return number()
        if character == "{":
            result = {}
            index += 1
            whitespace()
            if index < size and source[index] == "}":
                index += 1
                return result
            while True:
                whitespace()
                if index >= size or source[index] != '"':
                    raise ValueError
                key = string()
                if key in result:
                    raise ValueError
                whitespace()
                if index >= size or source[index] != ":":
                    raise ValueError
                index += 1
                result[key] = value()
                whitespace()
                if index >= size:
                    raise ValueError
                delimiter = source[index]
                index += 1
                if delimiter == "}":
                    return result
                if delimiter != ",":
                    raise ValueError
        if character == "[":
            result = []
            index += 1
            whitespace()
            if index < size and source[index] == "]":
                index += 1
                return result
            while True:
                result.append(value())
                whitespace()
                if index >= size:
                    raise ValueError
                delimiter = source[index]
                index += 1
                if delimiter == "]":
                    return result
                if delimiter != ",":
                    raise ValueError
        raise ValueError

    result = value()
    whitespace()
    if index != size:
        raise ValueError
    return result


def integer(value, minimum):
    return type(value) is int and value >= minimum


def select(request):
    if type(request) is not dict or set(request) != REQUEST_KEYS:
        raise ValueError
    if not integer(request["case_id"], 0) or request["dtype"] not in DTYPES:
        raise ValueError
    for key in ("m", "n", "k"):
        if not integer(request[key], 1) or request[key] > 256:
            raise ValueError
    if not integer(request["alignment"], 1) or not integer(request["workspace"], 0):
        raise ValueError
    candidates = request["candidates"]
    if type(candidates) is not list or not candidates:
        raise ValueError

    legal = []
    identifiers = set()
    for candidate in candidates:
        if type(candidate) is not dict or set(candidate) not in (
                CANDIDATE_KEYS, CANDIDATE_DIAGNOSTIC_KEYS):
            raise ValueError
        identifier = candidate["id"]
        if type(identifier) is not str or identifier in identifiers:
            raise ValueError
        identifiers.add(identifier)
        for key in ("semantic_kernel_id", "image_id", "alignment", "divisibility"):
            if not integer(candidate[key], 1):
                raise ValueError
        variant = candidate["variant"]
        if type(variant) is not int or variant not in (1, 2, 3):
            raise ValueError
        if not integer(candidate["workspace"], 0):
            raise ValueError
        if ("diagnostic_cycles" in candidate and
                not integer(candidate["diagnostic_cycles"], 1)):
            raise ValueError
        divisibility, alignment, workspace = REQUIREMENTS[variant - 1]
        divisibility = max(divisibility, candidate["divisibility"])
        if request["alignment"] < max(alignment, candidate["alignment"]):
            continue
        if request["workspace"] < max(workspace, candidate["workspace"]):
            continue
        if any(request[key] % divisibility for key in ("m", "n", "k")):
            continue
        legal.append(candidate)
    if not legal:
        raise ValueError
    if all("diagnostic_cycles" in candidate for candidate in legal):
        chosen = min(legal, key=lambda candidate: (
            candidate["diagnostic_cycles"], -candidate["variant"],
            candidate["image_id"], candidate["id"]))
    else:
        chosen = min(legal, key=lambda candidate: (
            -candidate["variant"], candidate["image_id"], candidate["id"]))
    return chosen["id"]


def quote(value):
    pieces = ['"']
    for character in value:
        escaped = OUT.get(character)
        if escaped is not None:
            pieces.append(escaped)
        elif ord(character) < 0x20:
            pieces.append("\\u%04x" % ord(character))
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)


def main():
    try:
        identifier = select(decode(sys.stdin.read()))
        sys.stdout.write('{"kernel_id":' + quote(identifier) + '}\n')
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
