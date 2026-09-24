"""Killable per-upload process isolation supervised by the web worker pool.

The parser uses native libraries plus Poppler and Tesseract subprocesses.
Python threads cannot stop native work after a route timeout, so each web
upload runs in a fresh ``spawn`` child.  On timeout or cancellation the child
and every inherited subprocess are terminated as one POSIX process group.
Batch parsing deliberately does not use this web-only supervisor.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import threading
import time
from collections.abc import Callable
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any

from coa_profiler.errors import COAError, ProcessingTimeoutError

log = logging.getLogger("coa_profiler.web.process_isolation")

_POLL_INTERVAL_S = 0.05
_NORMAL_EXIT_GRACE_S = 0.5
_TERMINATE_GRACE_S = 0.5
_KILL_GRACE_S = 1.0
# Public to the route module so its outer deadline cannot silently drift below
# the supervisor's worst-case default cleanup window.
DEFAULT_UPLOAD_PROCESS_CLEANUP_BUDGET_S = (
    _POLL_INTERVAL_S + _NORMAL_EXIT_GRACE_S + _TERMINATE_GRACE_S + _KILL_GRACE_S
)


class UploadProcessCancelled(RuntimeError):
    """The request or application shutdown cancelled an isolated upload."""


class UploadProcessFailed(RuntimeError):
    """The isolated worker failed without a typed, user-visible error."""


def _all_coa_error_types() -> dict[str, type[COAError]]:
    pending = [COAError]
    by_code: dict[str, type[COAError]] = {}
    while pending:
        error_type = pending.pop()
        by_code[error_type.error_code] = error_type
        pending.extend(error_type.__subclasses__())
    return by_code


_COA_ERRORS_BY_CODE = _all_coa_error_types()


def _establish_private_process_group() -> int | None:
    """Detach before parser code can create Poppler/Tesseract descendants."""
    if os.name != "posix":  # pragma: no cover - production image is Linux
        raise RuntimeError("isolated web uploads require POSIX process-group support")
    os.setsid()
    process_group = os.getpgrp()
    if process_group != os.getpid():
        raise RuntimeError("isolated upload child did not become its process-group leader")
    return process_group


def _child_entry(
    sender: Connection,
    worker: Callable[..., Any],
    args: tuple[Any, ...],
) -> None:
    """Process entry point; only stable protocol data crosses the pipe."""
    try:
        process_group = _establish_private_process_group()
        sender.send(("ready", process_group))
        try:
            result = worker(*args)
        except COAError as exc:
            sender.send(("coa_error", exc.error_code, exc.detail))
        except BaseException as exc:  # noqa: BLE001 - child failures collapse to a private signal
            sender.send(("internal_error", type(exc).__name__))
        else:
            sender.send(("result", result))
    except BaseException as exc:  # noqa: BLE001 - bootstrap/serialization failure
        try:
            sender.send(("bootstrap_error", type(exc).__name__))
        except (BrokenPipeError, EOFError, OSError, ValueError):
            return
    finally:
        sender.close()


def _signal_process_tree(process: multiprocessing.Process, process_group: int | None, sig: int) -> None:
    if os.name == "posix":
        # Before the child's ready handshake, its intended private group ID is
        # still its PID. killpg(PID) is either the new private group or ESRCH;
        # it can never be the parent worker's process group.
        group = process_group if process_group == process.pid else process.pid
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            pass
        except OSError:
            log.exception("could not signal isolated upload process group %s", group)

    if not process.is_alive():
        return
    try:
        if sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass


def _terminate_process_tree(
    process: multiprocessing.Process,
    process_group: int | None,
    *,
    terminate_grace_s: float,
    kill_grace_s: float,
) -> None:
    """TERM, then KILL, without an unbounded join."""
    _signal_process_tree(process, process_group, signal.SIGTERM)
    process.join(max(0.0, terminate_grace_s))

    # Always signal the group with KILL: its leader may have exited on TERM
    # while a Poppler/Tesseract descendant ignored or delayed termination.
    _signal_process_tree(process, process_group, signal.SIGKILL)
    process.join(max(0.0, kill_grace_s))
    if process.is_alive():
        log.critical("isolated upload child pid=%s remained alive after SIGKILL", process.pid)


def _decode_terminal_message(message: tuple[Any, ...]) -> Any:
    kind = message[0]
    if kind == "result":
        return message[1]
    if kind == "coa_error":
        _, error_code, detail = message
        error_type = _COA_ERRORS_BY_CODE.get(error_code, COAError)
        raise error_type(detail)
    if kind in {"internal_error", "bootstrap_error"}:
        error_name = message[1] if len(message) > 1 else "unknown"
        raise UploadProcessFailed(f"isolated upload worker failed ({error_name})")
    raise UploadProcessFailed("isolated upload worker sent an invalid response")


def run_isolated_upload(
    worker: Callable[..., Any],
    *args: Any,
    timeout_seconds: float,
    cancel_event: threading.Event | None = None,
    terminate_grace_s: float = _TERMINATE_GRACE_S,
    kill_grace_s: float = _KILL_GRACE_S,
) -> Any:
    """Run one picklable worker in a spawned child with an absolute deadline."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    cancelled = cancel_event or threading.Event()
    if cancelled.is_set():
        raise UploadProcessCancelled("isolated upload cancelled before start")

    deadline = time.monotonic() + timeout_seconds
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_child_entry,
        args=(sender, worker, args),
        name="coa-upload-child",
        daemon=True,
    )
    process_group: int | None = None
    terminal_message: tuple[Any, ...] | None = None
    termination_attempted = False
    try:
        try:
            process.start()
        except BaseException as exc:
            raise UploadProcessFailed("could not start isolated upload worker") from exc
        finally:
            sender.close()

        ready = False
        while terminal_message is None:
            if cancelled.is_set():
                termination_attempted = True
                _terminate_process_tree(
                    process,
                    process_group,
                    terminate_grace_s=terminate_grace_s,
                    kill_grace_s=kill_grace_s,
                )
                raise UploadProcessCancelled("isolated upload cancelled")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                termination_attempted = True
                _terminate_process_tree(
                    process,
                    process_group,
                    terminate_grace_s=terminate_grace_s,
                    kill_grace_s=kill_grace_s,
                )
                raise ProcessingTimeoutError("Upload pipeline exceeded its processing deadline")

            if receiver.poll(min(_POLL_INTERVAL_S, remaining)):
                try:
                    message = receiver.recv()
                except (EOFError, OSError) as exc:
                    raise UploadProcessFailed("isolated upload worker closed its result pipe") from exc
                if not isinstance(message, tuple) or not message:
                    raise UploadProcessFailed("isolated upload worker sent malformed data")
                if message[0] == "ready":
                    if ready:
                        raise UploadProcessFailed("isolated upload worker sent duplicate readiness")
                    process_group = message[1]
                    if os.name == "posix" and process_group != process.pid:
                        raise UploadProcessFailed("isolated upload worker has an unsafe process group")
                    ready = True
                    continue
                if not ready:
                    raise UploadProcessFailed("isolated upload worker responded before process isolation")
                terminal_message = message
                break

            if not process.is_alive():
                # A final pipe frame can become readable just after the liveness
                # check. Give it one non-blocking opportunity before failing.
                if receiver.poll(0):
                    continue
                process.join(0)
                raise UploadProcessFailed(
                    f"isolated upload worker exited without a result (code {process.exitcode})"
                )

        process.join(_NORMAL_EXIT_GRACE_S)
        if process.is_alive():
            termination_attempted = True
            _terminate_process_tree(
                process,
                process_group,
                terminate_grace_s=terminate_grace_s,
                kill_grace_s=kill_grace_s,
            )
        return _decode_terminal_message(terminal_message)
    finally:
        if process.pid is not None and process.is_alive() and not termination_attempted:
            _terminate_process_tree(
                process,
                process_group,
                terminate_grace_s=terminate_grace_s,
                kill_grace_s=kill_grace_s,
            )
        receiver.close()
        if process.pid is not None and not process.is_alive():
            try:
                process.close()
            except ValueError:
                pass


@dataclass(frozen=True)
class UploadProcessJob:
    """One pool-supervised upload plus its cooperative cancellation signal."""

    future: Future[Any]
    _cancel_event: threading.Event

    def cancel(self) -> None:
        self._cancel_event.set()


class UploadProcessManager:
    """Track isolated uploads submitted to the application's existing pool."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor
        self._condition = threading.Condition()
        self._jobs: dict[Future[Any], threading.Event] = {}
        self._closed = False

    def submit(
        self,
        worker: Callable[..., Any],
        *args: Any,
        timeout_seconds: float,
    ) -> UploadProcessJob:
        cancel_event = threading.Event()
        with self._condition:
            if self._closed:
                raise RuntimeError("upload process manager is shutting down")
            future = self._executor.submit(
                run_isolated_upload,
                worker,
                *args,
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
            )
            self._jobs[future] = cancel_event
        future.add_done_callback(self._job_finished)
        return UploadProcessJob(future=future, _cancel_event=cancel_event)

    def _job_finished(self, future: Future[Any]) -> None:
        with self._condition:
            self._jobs.pop(future, None)
            self._condition.notify_all()

    @property
    def active_count(self) -> int:
        with self._condition:
            return len(self._jobs)

    def cancel_all(self) -> None:
        with self._condition:
            self._closed = True
            events = tuple(self._jobs.values())
        for event in events:
            event.set()

    def wait_for_idle(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._condition:
            while self._jobs:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True
