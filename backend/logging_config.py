"""
Production logging setup.
- Console  : coloured, human-readable (INFO+)
- File     : rotating JSON lines  logs/app.jsonl  (DEBUG+, 10 MB × 5)

Call setup() once at process start before anything else imports logging.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    """One JSON object per line — ingestible by any log aggregator."""

    _EXTRA = (
        "request_id", "ticker", "accession", "duration_ms",
        "status_code", "chunks", "reasoning_tokens", "output_tokens",
        "total_tokens", "chars", "method", "path",
    )

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level":  record.levelname,
            "logger": record.name,
            "module": f"{record.module}:{record.lineno}",
            "msg":    record.getMessage(),
        }
        for k in self._EXTRA:
            v = record.__dict__.get(k)
            if v is not None:
                entry[k] = v
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _ConsoleFormatter(logging.Formatter):
    """Coloured, aligned, human-readable console lines."""

    _LEVEL_COLOR = {
        "DEBUG":    "\033[36m",    # cyan
        "INFO":     "\033[32m",    # green
        "WARNING":  "\033[33m",    # yellow
        "ERROR":    "\033[31m",    # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    _RESET = "\033[0m"
    _DIM   = "\033[90m"

    def format(self, record: logging.LogRecord) -> str:
        now   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color = self._LEVEL_COLOR.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{self._RESET}"
        name  = f"{self._DIM}{record.name:<26}{self._RESET}"
        msg   = record.getMessage()
        line  = f"{now}  {level}  {name}  {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup(log_dir: str = "logs", console_level: int = logging.INFO) -> None:
    """
    Configure root logger with a console handler and a rotating JSON file handler.
    Call this before uvicorn starts so all loggers inherit the config.
    """
    Path(log_dir).mkdir(exist_ok=True)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ConsoleFormatter())
    console.setLevel(console_level)

    file_h = logging.handlers.RotatingFileHandler(
        Path(log_dir) / "app.jsonl",
        maxBytes=10 * 1024 * 1024,   # 10 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_h.setFormatter(_JsonFormatter())
    file_h.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_h)

    # Suppress noisy third-party chatter
    for lib in (
        "httpx", "httpcore", "hpack", "multipart",
        "sentence_transformers", "huggingface_hub", "transformers",
        "filelock", "PIL", "torch",
    ):
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
    logging.getLogger("uvicorn").setLevel(logging.DEBUG)
    logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)

    logging.getLogger(__name__).info(
        "Logging initialised — console=%s  file=%s/app.jsonl",
        logging.getLevelName(console_level), log_dir,
    )
