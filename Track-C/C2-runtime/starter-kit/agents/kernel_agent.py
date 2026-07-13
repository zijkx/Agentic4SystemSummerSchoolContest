#!/usr/bin/env python3
"""Select the fastest legal frozen image using only request metadata."""

import json
import sys


REQUEST_KEYS = {
    "case_id", "dtype", "m", "n", "k", "alignment", "workspace", "candidates"
}
CANDIDATE_KEYS = {
    "id", "semantic_kernel_id", "image_id", "variant", "workspace",
    "alignment", "divisibility"
}


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
    if not isinstance(request["dtype"], str) or not request["dtype"]:
        raise ValueError("invalid dtype")
    for key in ("m", "n", "k", "alignment"):
        if not valid_integer(request[key], 1):
            raise ValueError(f"invalid {key}")
    if not valid_integer(request["workspace"], 0):
        raise ValueError("invalid workspace")
    if not isinstance(request["candidates"], list) or not request["candidates"]:
        raise ValueError("missing candidates")

    candidates = [validate_candidate(item) for item in request["candidates"]]
    if len({item["id"] for item in candidates}) != len(candidates):
        raise ValueError("duplicate candidate id")
    legal = [
        item for item in candidates
        if request["alignment"] >= item["alignment"]
        and request["workspace"] >= item["workspace"]
        and request["m"] % item["divisibility"] == 0
        and request["n"] % item["divisibility"] == 0
        and request["k"] % item["divisibility"] == 0
    ]
    if not legal:
        raise ValueError("no legal candidate")

    if all("diagnostic_cycles" in item for item in legal):
        selected = min(legal, key=lambda item: (
            item["diagnostic_cycles"], -item["variant"], item["image_id"],
            item["id"]))
    else:
        # Official image evaluation is monotonic by variant whenever its
        # divisibility/alignment/workspace constraints are satisfied.
        selected = min(legal, key=lambda item: (
            -item["variant"], -item["divisibility"], item["workspace"],
            item["image_id"], item["id"]))
    return {"kernel_id": selected["id"]}


def main() -> int:
    try:
        request = json.load(sys.stdin)
        action = policy(request)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return 2
    json.dump(action, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
