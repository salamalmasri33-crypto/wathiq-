"""Streaming checksum helpers for large artifact files."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ChecksumError(Exception):
    """Base exception for checksum calculation failures."""


class ChecksumFileNotFoundError(ChecksumError, FileNotFoundError):
    """Raised when a checksum target file does not exist."""


class ChecksumFileAccessError(ChecksumError):
    """Raised when a checksum target file cannot be opened or read safely."""


def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA256 digest for a file without loading it fully."""

    file_path = Path(file_path)
    if not file_path.is_file():
        raise ChecksumFileNotFoundError(f"Artifact file does not exist: {file_path}")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")

    hasher = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            while True:
                try:
                    chunk = handle.read(chunk_size)
                except OSError as exc:
                    raise ChecksumFileAccessError(
                        "Unable to read artifact file for SHA256 calculation."
                    ) from exc

                if not chunk:
                    break
                hasher.update(chunk)
    except FileNotFoundError as exc:
        raise ChecksumFileNotFoundError(f"Artifact file does not exist: {file_path}") from exc
    except ChecksumFileAccessError:
        raise
    except OSError as exc:
        raise ChecksumFileAccessError(
            "Unable to access artifact file for SHA256 calculation."
        ) from exc

    return hasher.hexdigest()
