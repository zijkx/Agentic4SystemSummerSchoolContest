#!/usr/bin/env python3
import json
import sys


REQUEST_KEYS = {
    "case_id", "dtype", "m", "n", "k", "alignment", "workspace", "candidates"
}
CANDIDATE_KEYS = {
    "id", "semantic_kernel_id", "image_id", "variant", "workspace",
    "alignment", "divisibility"
}
DTYPES = {
    "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
    "fp32", "fp64", "int4", "int8", "int32"
}
REQUIREMENTS = ((1, 1, 0), (4, 1, 4096), (8, 16, 8192))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def invalid_constant(_value):
    raise ValueError


def decode(source):
    return json.loads(source, object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def integer(value, minimum):
    return type(value) is int and value >= minimum


def select(request):
    if type(request) is not dict or not REQUEST_KEYS.issubset(request):
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
        if type(candidate) is not dict or not CANDIDATE_KEYS.issubset(candidate):
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
        sys.stdout.write(json.dumps(
            {"kernel_id": identifier}, ensure_ascii=True,
            separators=(",", ":")) + "\n")
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
