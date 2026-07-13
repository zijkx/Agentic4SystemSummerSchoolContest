#!/usr/bin/env python3
"""Deterministic DMA policy derived from the normative virtual-cycle model."""

import json
import sys


REQUIRED_KEYS = {
    "case_id", "direction", "bytes", "alignment", "registered", "concurrency"
}


def valid_integer(value: object, minimum: int, maximum: int | None = None) -> bool:
    return (type(value) is int and value >= minimum and
            (maximum is None or value <= maximum))


def policy(request: object) -> dict[str, object]:
    if not isinstance(request, dict) or set(request) != REQUIRED_KEYS:
        raise ValueError("invalid DMA request fields")
    if not valid_integer(request["case_id"], 0):
        raise ValueError("invalid case_id")
    if request["direction"] not in ("h2d", "d2h"):
        raise ValueError("invalid direction")
    if not valid_integer(request["bytes"], 1):
        raise ValueError("invalid bytes")
    if not valid_integer(request["alignment"], 1):
        raise ValueError("invalid alignment")
    if type(request["registered"]) is not bool:
        raise ValueError("invalid registered flag")
    if not valid_integer(request["concurrency"], 1, 64):
        raise ValueError("invalid concurrency")

    # The model has no large-chunk penalty, and parallelism is capped at two.
    # Registered zero-copy always reduces setup by 55 cycles.
    return {
        "channel": 0 if request["direction"] == "h2d" else 1,
        "chunk_bytes": 1048576,
        "queue_depth": 2 if request["concurrency"] >= 2 else 1,
        "use_zero_copy": request["registered"],
    }


def main() -> int:
    try:
        request = json.load(sys.stdin)
        action = policy(request)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 2
    json.dump(action, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
