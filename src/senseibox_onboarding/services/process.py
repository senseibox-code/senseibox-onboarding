from __future__ import annotations

import asyncio
from dataclasses import dataclass
from subprocess import DEVNULL
from typing import Callable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandTimeout(RuntimeError):
    pass


class CommandRunner:
    """Tiny async process wrapper.

    Commands are passed as argv lists, never shell strings. Callers decide what
    is safe to log so credentials do not leak into logs.
    """

    def __init__(
        self,
        on_output: Callable[[str], None] | None = None,
        on_running: Callable[[bool], None] | None = None,
    ) -> None:
        self.on_output = on_output
        self.on_running = on_running

    async def run(
        self,
        argv: list[str],
        *,
        timeout_s: int,
        input_text: str | None = None,
    ) -> CommandResult:
        self._emit("$ " + " ".join(self._redact_argv(argv)))
        self._set_running(True)
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE if input_text is not None else DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            self._set_running(False)
            self._emit(f"{argv[0]} was not found")
            return CommandResult(
                returncode=127,
                stdout="",
                stderr=f"{argv[0]} was not found",
            )
        except PermissionError:
            self._set_running(False)
            self._emit(f"{argv[0]} could not be executed")
            return CommandResult(
                returncode=126,
                stdout="",
                stderr=f"{argv[0]} could not be executed",
            )
        except Exception:
            self._set_running(False)
            raise
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(
                    input_text.encode("utf-8") if input_text is not None else None
                ),
                timeout=timeout_s,
            )
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            self._set_running(False)
            self._emit("command timed out")
            raise CommandTimeout("command timed out") from exc
        result = CommandResult(
            returncode=proc.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )
        self._set_running(False)
        self._emit_result(result)
        return result

    def _redact_argv(self, argv: list[str]) -> list[str]:
        redacted: list[str] = []
        redact_next = False
        for value in argv:
            if redact_next:
                redacted.append("******")
                redact_next = False
                continue
            redacted.append(value)
            if value.lower() in {"password", "passwd", "--password"}:
                redact_next = True
        return redacted

    def _emit_result(self, result: CommandResult) -> None:
        output_lines = [
            line
            for stream in (result.stdout, result.stderr)
            for line in stream.splitlines()
            if line.strip()
        ]
        if output_lines:
            for line in output_lines[:4]:
                self._emit(line)
            if len(output_lines) > 4:
                self._emit(f"... {len(output_lines) - 4} more lines")
        self._emit(f"exit {result.returncode}")

    def _emit(self, line: str) -> None:
        if self.on_output:
            self.on_output(line)

    def _set_running(self, running: bool) -> None:
        if self.on_running:
            self.on_running(running)
