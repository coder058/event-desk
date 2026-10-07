"""Identified, bounded SEC reads with one shared durable project pacing gate.

The transport does not supply a guessed identity, bypass a block, follow redirects
or turn filing dates into acceptance times. Collection is separate from the
competition worker. Other applications on the same IP are outside this gate.
"""
from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx
from sqlalchemy import Float, Integer, String, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, mapped_column

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.sec_submissions import MAX_SUBMISSIONS_BYTES, FilingReference, normalize_cik
from eventdesk.store import Base, Store

# GUESS: five-per-second maximum project admission, stricter than SEC's ten/second ceiling.
# UNCALIBRATED GUESS: actual throughput need/server behavior must be measured.
MIN_INTERVAL_SECONDS = 0.2
# GUESS: whole HTTP phase budget and fallback block cooldown; not latency targets. # UNCALIBRATED GUESS
HTTP_BUDGET_SECONDS = 20
DEFAULT_BLOCK_SECONDS = 300
# SOURCE: one lock identity for all SEC hosts/readers in this project's PostgreSQL database.
LOCK_NAME = "eventdesk:sec-http"


class SecBudget(Base):
    __tablename__ = "sec_http_budget"
    name: Mapped[str] = mapped_column(String, primary_key=True)
    not_before: Mapped[float] = mapped_column(Float)


class SecRead(Base):
    __tablename__ = "sec_http_reads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String)
    started_at: Mapped[float] = mapped_column(Float)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SecDeferred(Exception):
    """No network request was made; a busy/recorded cooldown gate is not bypassed."""


class SecFetchFailed(Exception):
    """Safe status only, never an error body or administrator contact."""


class Permit(Protocol):
    def finish(self, state: str, status: int | None, size: int | None, cooldown: float) -> None: ...


class Gate(Protocol):
    def acquire(self, url: str) -> Permit: ...


def unlock(connection: Connection) -> None:
    try:
        connection.rollback()
        connection.execute(text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": LOCK_NAME})
        connection.commit()
    except Exception:
        # An invalidated physical connection releases its session lock; never return a locked socket to the pool.
        connection.invalidate()
        raise
    finally:
        connection.close()


class PostgresPermit:
    def __init__(self, connection: Connection, read_id: int, clock: Callable[[], float]) -> None:
        self.connection, self.read_id, self.clock = connection, read_id, clock

    def finish(self, state: str, status: int | None, size: int | None, cooldown: float) -> None:
        try:
            completed = self.clock()
            if not math.isfinite(completed) or not math.isfinite(cooldown) or cooldown < 0:
                raise ValueError("Invalid SEC completion time/cooldown")
            previous = self.connection.scalar(select(SecBudget.not_before).where(SecBudget.name == LOCK_NAME))
            self.connection.execute(update(SecBudget).where(SecBudget.name == LOCK_NAME).values(
                not_before=max(float(previous or 0), completed+max(MIN_INTERVAL_SECONDS, cooldown))))
            self.connection.execute(update(SecRead).where(SecRead.id == self.read_id).values(
                completed_at=completed, state=state, http_status=status, content_bytes=size))
            self.connection.commit()
        finally:
            unlock(self.connection)


class PostgresSecGate:
    def __init__(self, store: Store, clock: Callable[[], float] = time.time) -> None:
        if store.engine.dialect.name != "postgresql":
            raise ValueError("SEC collection requires the shared PostgreSQL gate")
        self.store, self.clock = store, clock

    def acquire(self, url: str) -> PostgresPermit:
        connection = self.store.engine.connect()
        acquired = False
        try:
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(hashtext(:name))"),
                                               {"name": LOCK_NAME}))
            connection.commit()
            if not acquired:
                raise SecDeferred("sec_reader_busy")
            started = self.clock()
            if not math.isfinite(started) or started < 0:
                raise ValueError("Invalid SEC admission time")
            previous = connection.scalar(select(SecBudget.not_before).where(SecBudget.name == LOCK_NAME))
            if previous is not None and previous > started:
                raise SecDeferred("sec_pacing_or_cooldown")
            if previous is None:
                connection.execute(insert(SecBudget).values(name=LOCK_NAME, not_before=started+MIN_INTERVAL_SECONDS))
            else:
                connection.execute(update(SecBudget).where(SecBudget.name == LOCK_NAME).values(
                    not_before=started+MIN_INTERVAL_SECONDS))
            read_id = connection.scalar(insert(SecRead).values(source_url=url, started_at=started,
                state="reserved").returning(SecRead.id))
            if read_id is None:
                raise RuntimeError("SEC request reservation missing")
            # Persist admission before network I/O. An interrupted process does not reset the pacing clock.
            connection.commit()
            return PostgresPermit(connection, read_id, self.clock)
        except BaseException:
            if acquired:
                unlock(connection)
            else:
                connection.close()
            raise


def user_agent(value: str) -> str:
    value = value.strip()
    # SOURCE: httpx text header values are ASCII; reject controls/non-ASCII before its exception could quote a contact.
    if (not value or any(ord(character) < 32 or ord(character) > 126 for character in value)
            or re.search(r"\S+@[^\s@]+\.[^\s@]+", value) is None):
        raise ValueError("SEC_USER_AGENT requires a declared organization/admin contact")
    return value


def retry_after(value: str | None, now: float) -> float:
    if value is None:
        return 0
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    except ValueError:
        pass
    try:
        stamp = parsedate_to_datetime(value)
        if stamp.tzinfo is not None:
            return max(0, stamp.timestamp()-now)
    except (ValueError, TypeError, OverflowError):
        pass
    return 0


class SecTransport:
    def __init__(self, *, contact: str, gate: Gate, objects: RawObjects, http: httpx.AsyncClient | None = None) -> None:
        self.contact = user_agent(contact)  # Fails before any gate/database/network access.
        self.gate, self.objects = gate, objects
        self.http = http if http is not None else httpx.AsyncClient(trust_env=False, follow_redirects=False)
        self.owns_http = http is None

    async def __aenter__(self) -> SecTransport:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self.owns_http:
            await self.http.aclose()

    async def submissions(self, cik: str) -> CapturedDocument:
        return await self._fetch("https://data.sec.gov/submissions/CIK"+normalize_cik(cik)+".json", None, None, None)

    async def filing(self, reference: FilingReference) -> CapturedDocument:
        # Revalidate model_copy/constructed objects before opening a network permit.
        reference = FilingReference.model_validate_json(reference.model_dump_json())
        return await self._fetch(reference.source_url, reference.accepted_at, reference.form, reference.accession)

    async def _fetch(self, url: str, accepted: datetime | None, form: str | None,
                     accession: str | None) -> CapturedDocument:
        permit = self.gate.acquire(url)
        state, status, size, cooldown = "interrupted", None, None, 0.0
        try:
            # Standard TLS/hostname verification is the client's default. Production callers must use
            # trust_env=False; injected fixture clients use a MockTransport, never a validation bypass.
            async with asyncio.timeout(HTTP_BUDGET_SECONDS):
                async with self.http.stream("GET", url, headers={"User-Agent": self.contact,
                    "Accept-Encoding": "gzip, deflate"}, follow_redirects=False,
                    timeout=HTTP_BUDGET_SECONDS) as response:
                    status = response.status_code
                    # SOURCE: HTTP success/block/rate-limit/unavailable status codes (RFC 9110/6585).
                    if status != 200:
                        state = "http_"+str(status)
                        if status in (403, 429, 503):
                            cooldown = max(DEFAULT_BLOCK_SECONDS, retry_after(response.headers.get("retry-after"), time.time()))
                        raise SecFetchFailed(state)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body)+len(chunk) > MAX_SUBMISSIONS_BYTES:
                            state = "body_too_large"
                            raise SecFetchFailed(state)
                        body.extend(chunk)
                    size = len(body)
            if not body:
                state = "empty_body"
                raise SecFetchFailed(state)
            seen = datetime.now(UTC)
            raw = bytes(body)
            state = "capture_failed"
            document = CapturedDocument(source="sec", source_url=url, content_sha256=self.objects.put(raw),
                content_bytes=len(raw), accepted_at=accepted, first_seen_at=seen, form=form, accession=accession)
            state = "captured"
            return document
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            state = "transport_"+type(error).__name__
            raise SecFetchFailed(state) from None
        finally:
            # No response error body, administrator contact, request headers or secrets are retained here.
            permit.finish(state, status, size, cooldown)
