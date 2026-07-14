#!/usr/bin/env python3
import sys
from _json import encode_basestring, scanstring


WS = " \t\r\n"
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
        value, index = scanstring(source, index + 1, True)
        return value

    def number():
        nonlocal index
        start = index
        if source[index] == "-":
            index += 1
        digits = index
        while index < size and "0" <= source[index] <= "9":
            index += 1
        if (index == digits or
                source[digits] == "0" and index - digits != 1):
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
    if type(request) is not dict or request.keys() != REQUEST_KEYS:
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
        if type(candidate) is not dict or candidate.keys() not in (
                CANDIDATE_KEYS, CANDIDATE_DIAGNOSTIC_KEYS):
            raise ValueError
        identifier = candidate["id"]
        if (type(identifier) is not str or identifier in identifiers or
                any(0xD800 <= ord(character) <= 0xDFFF
                    for character in identifier)):
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


def main():
    try:
        identifier = select(decode(sys.stdin.read()))
        sys.stdout.write('{"kernel_id":' + encode_basestring(identifier) + '}\n')
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
