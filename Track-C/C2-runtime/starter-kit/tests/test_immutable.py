#!/usr/bin/env python3
"""Verify that every C2 immutable contract still matches the release bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


INITIAL_COMMIT = "abcaa940b107c153514d3cb162108090631cfdf6"
IMMUTABLE_DIRECTORIES = (
    "include",
    "docs",
    "kernels",
    "grader",
    "cases",
    "golden",
    "schemas",
)
IMMUTABLE_FILES = ("lib/libaec_device.so",)
TRACKED_CONTRACTS = (*IMMUTABLE_DIRECTORIES, "RELEASE_MANIFEST.json")
EXPECTED_IMAGE_COUNT = 34


def is_transient(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    parser.add_argument("--initial-commit", default=INITIAL_COMMIT)
    args = parser.parse_args()
    root = args.submission.resolve()

    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    assert isinstance(files, dict) and files, "manifest has no file hash map"

    directory_names = set(IMMUTABLE_DIRECTORIES)
    expected = {
        PurePosixPath(name).as_posix(): digest
        for name, digest in files.items()
        if PurePosixPath(name).parts[0] in directory_names
        or name in IMMUTABLE_FILES
    }
    assert set(IMMUTABLE_FILES) <= expected.keys(), "device library absent from manifest"

    actual: set[str] = set()
    for directory in IMMUTABLE_DIRECTORIES:
        contract_root = root / directory
        assert contract_root.is_dir(), f"missing immutable directory: {directory}"
        actual.update(
            path.relative_to(root).as_posix()
            for path in contract_root.rglob("*")
            if path.is_file() and not is_transient(path)
        )
    for name in IMMUTABLE_FILES:
        path = root / name
        if path.is_file():
            actual.add(name)

    missing = sorted(set(expected) - actual)
    extra = sorted(actual - set(expected))
    assert not missing, f"missing immutable files: {missing}"
    assert not extra, f"extra immutable files: {extra}"

    mismatches = [
        name for name, digest in sorted(expected.items())
        if sha256(root / name) != digest
    ]
    assert not mismatches, f"immutable hash mismatches: {mismatches}"

    expected_images = {
        name for name in expected
        if name.startswith("kernels/images/") and name.endswith(".aecbin")
    }
    actual_images = {
        name for name in actual
        if name.startswith("kernels/images/") and name.endswith(".aecbin")
    }
    assert len(expected_images) == EXPECTED_IMAGE_COUNT
    assert actual_images == expected_images

    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=root,
        text=True, capture_output=True, check=True,
    )
    git_root = Path(git_root_result.stdout.strip()).resolve()
    starter_prefix = root.relative_to(git_root)
    pathspecs = [str(starter_prefix / path) for path in TRACKED_CONTRACTS]
    diff = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--name-status",
         args.initial_commit, "--", *pathspecs],
        cwd=git_root, text=True, capture_output=True, check=False,
    )
    assert diff.returncode == 0, diff.stderr
    assert not diff.stdout, (
        "tracked immutable contracts differ from initial commit:\n" + diff.stdout
    )

    print(
        f"PASS immutable audit: {len(expected)} manifest files, "
        f"{len(actual_images)} fixed images, tracked diff clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
