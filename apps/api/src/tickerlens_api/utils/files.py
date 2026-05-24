from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class TempFileDigest:
    path: str
    sha256: str
    size_bytes: int


def spool_to_temp_and_hash(fileobj, *, chunk_size: int = 1024 * 1024) -> TempFileDigest:
    """
    Reads a file-like object once, writing it to a temp file while computing SHA-256.

    Why: we need a deterministic checksum (dedupe/versioning) *and* we want to upload the exact same bytes to MinIO.
    Spooling to disk keeps memory usage stable for large PDFs.
    """

    hasher = hashlib.sha256()
    size_bytes = 0

    fd, path = tempfile.mkstemp(prefix="tickerlens-upload-", suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = fileobj.read(chunk_size)
                if not chunk:
                    break
                size_bytes += len(chunk)
                hasher.update(chunk)
                f.write(chunk)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    return TempFileDigest(path=path, sha256=hasher.hexdigest(), size_bytes=size_bytes)

