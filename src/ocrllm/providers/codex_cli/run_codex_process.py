"""Drain JSON events while one accepted CLI finishes; retain no private stream."""
import subprocess
import tempfile
from threading import Thread
from ...errors import OutputError


def run_codex_process(argv, *, timeout_seconds, attempt):
    """Return exit and bounded stderr; persist usage as each JSON line arrives.

    Stop signals only gate the caller's next spawn. Timeout still bounds this
    process as before. A usage disk failure is surfaced after draining this
    accepted process and prevents retries.
    """
    errors = []
    with tempfile.TemporaryFile(mode="w+b") as stderr:
        process = subprocess.Popen(
            argv, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
            stderr=stderr, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        attempt.spawned = True
        attempt.common["cli_pid"] = getattr(process, "pid", None)

        def drain():
            try:
                for line in process.stdout:
                    try:
                        attempt.consume_line(line)
                    except Exception as error:
                        if not errors:
                            errors.append(error)
            except Exception as error:
                errors.append(error)
            finally:
                process.stdout.close()

        reader = Thread(target=drain, name="ocrllm-codex-usage", daemon=True)
        reader.start()
        timed_out = False
        try:
            process.wait(timeout=max(0.001, timeout_seconds))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                raise OutputError("The timed-out Codex process did not exit; no retry was admitted.",
                    details={"reason": "codex_process_cleanup_failed", "provider_client_closed": False}) from None
        reader.join(timeout=5.0)
        if reader.is_alive():
            # Tools are disabled, but a malformed CLI may leave a pipe open.
            # Do not claim complete capture or wait without a bound.
            attempt.stream_complete = False
            raise OutputError("The Codex usage stream did not close; capture remains incomplete.",
                              details={"reason": "codex_usage_stream_incomplete", "provider_calls_attempted": 1})
        if errors:
            raise errors[0]
        stderr.seek(0, 2)
        stderr.seek(max(0, stderr.tell() - 8192))
        detail = stderr.read().decode("utf-8", errors="replace")
        attempt.record_diagnostic("stderr_tail", detail)
        return process.returncode, detail, timed_out
