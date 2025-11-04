"""
File hashing utilities for data lineage tracking.

Provides SHA256 hashing of CSV files to detect data drift and changes.
"""

import hashlib
from pathlib import Path
from typing import Union


def compute_sha256(file_path: Union[str, Path]) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file to hash

    Returns:
        Hexadecimal SHA256 hash string (64 characters)

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
        IOError: If file read fails

    Example:
        >>> hash_val = compute_sha256("data/inputs/substrates.csv")
        >>> len(hash_val)
        64
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files efficiently
    chunk_size = 8192
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
    except PermissionError as e:
        raise PermissionError(f"Cannot read file (permission denied): {file_path}") from e
    except IOError as e:
        raise IOError(f"Failed to read file: {file_path}") from e

    return sha256_hash.hexdigest()


def compute_multiple_hashes(file_paths: list[Union[str, Path]]) -> dict[str, str]:
    """
    Compute SHA256 hashes for multiple files.

    Args:
        file_paths: List of file paths to hash

    Returns:
        Dictionary mapping filename (not full path) to SHA256 hash

    Raises:
        FileNotFoundError: If any file does not exist
        PermissionError: If any file cannot be read
        IOError: If any file read fails

    Example:
        >>> paths = ["data/inputs/substrates.csv", "data/inputs/chemicals.csv"]
        >>> hashes = compute_multiple_hashes(paths)
        >>> "substrates.csv" in hashes
        True
    """
    results = {}
    for file_path in file_paths:
        path_obj = Path(file_path)
        filename = path_obj.name
        hash_value = compute_sha256(path_obj)
        results[filename] = hash_value

    return results


def verify_file_unchanged(file_path: Union[str, Path], expected_hash: str) -> bool:
    """
    Verify that a file's hash matches an expected value.

    Args:
        file_path: Path to file to verify
        expected_hash: Expected SHA256 hash (64 hex characters)

    Returns:
        True if hash matches, False otherwise

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If expected_hash is invalid format

    Example:
        >>> hash_val = compute_sha256("data.csv")
        >>> verify_file_unchanged("data.csv", hash_val)
        True
    """
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError(
            f"Invalid expected_hash format. Must be 64 hex characters, got: {expected_hash}"
        )

    try:
        int(expected_hash, 16)
    except ValueError as e:
        raise ValueError(f"expected_hash must be hexadecimal string: {expected_hash}") from e

    actual_hash = compute_sha256(file_path)
    return actual_hash == expected_hash
