"""Immutable source bytes and explicit point-in-time evidence boundaries."""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapturedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["sec", "defense_contracts"]
    source_url: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_bytes: int = Field(ge=0)
    accepted_at: datetime | None
    first_seen_at: datetime
    form: str | None = None
    accession: str | None = None

    @model_validator(mode="after")
    def provenance(self) -> CapturedDocument:
        if self.first_seen_at.tzinfo is None or (self.accepted_at is not None and self.accepted_at.tzinfo is None):
            raise ValueError("Evidence times require a timezone")
        if self.accepted_at is not None and self.accepted_at > self.first_seen_at:
            raise ValueError("Official acceptance cannot follow this recorded capture")
        parsed = urlsplit(self.source_url)
        hosts = {"sec": {"www.sec.gov", "data.sec.gov"}, "defense_contracts": {"www.defense.gov"}}
        # SOURCE: standard HTTPS port, exact official hosts; no source-provided redirects/query credentials.
        if (parsed.scheme != "https" or parsed.hostname not in hosts[self.source]
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError("Evidence source must be an approved official URL")
        return self

    def usable_before(self, cutoff: datetime) -> bool:
        if cutoff.tzinfo is None:
            raise ValueError("Cutoff requires timezone")
        # Conservative policy: later retrieval of an old URL is not proof that these exact bytes existed earlier.
        return (self.accepted_at is not None and self.accepted_at <= cutoff and self.first_seen_at <= cutoff)


class RawObjects:
    """Write verified bytes once; concurrent identical writes cannot replace an object."""
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("Evidence root cannot be a symlink")

    def put(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        # SOURCE: SHA-256 hex is path-safe; the first byte gives a bounded fanout for object directories.
        directory = self.root/digest[:2]
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Evidence shard cannot be a symlink")
        target = directory/digest
        descriptor, temporary = tempfile.mkstemp(prefix=".capture-", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Atomic creation without overwrite. Permission is inherited from the private temporary object.
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
            if os.name == "posix":
                # SOURCE: file fsync alone does not persist the new directory entry on POSIX.
                # SOURCE: zero is the neutral flags value when a platform lacks O_DIRECTORY.
                directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            if target.is_symlink() or self.read(digest) != raw:
                raise ValueError("Existing evidence object is corrupt or unsafe")
        finally:
            Path(temporary).unlink(missing_ok=True)
        return digest

    def read(self, digest: str) -> bytes:
        # Validate before constructing a path; callers cannot traverse by supplying an arbitrary identifier.
        import re
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Expected content SHA-256")
        path = self.root/digest[:2]/digest
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("Evidence object cannot be a symlink")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Evidence object failed content verification")
        return raw


class QuotedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str = Field(min_length=1)

    def verify(self, document: CapturedDocument, text: str, objects: RawObjects) -> None:
        raw = objects.read(document.content_sha256)
        # Initial scope is exact UTF-8 source text, not a claimed HTML/PDF normalization pipeline.
        if len(raw) != document.content_bytes or raw.decode("utf-8") != text:
            raise ValueError("Text must come from the retained source bytes")
        if (document.content_sha256 != self.document_sha256
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != self.text_sha256
                or self.end <= self.start or text[self.start:self.end] != self.quote):
            raise ValueError("Quote/provenance does not match retained text")
