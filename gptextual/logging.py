import logging
import logging.config
from logging.config import DictConfigurator as _dictConfig
import datetime as dt
import json
import queue
from pathlib import Path
import atexit
import os

import yaml


_logger = None


LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JSONFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        fmt_keys: dict[str, str] | None = None,
    ):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


class DictConfigurator(_dictConfig):
    def configure(self) -> None:
        super().configure()
        return self.config


class QueueHandler(logging.handlers.QueueHandler):
    def __init__(self, handlers):
        # Initialize the queue
        self.log_queue = queue.Queue(-1)  # No limit on queue size
        super().__init__(self.log_queue)

        # Initialize the handlers
        self.handlers = handlers

    def _initialize_listener(self, handlers):
        # Create and start the listener
        handlers = [handlers[h] for h in self.handlers]
        self.listener = logging.handlers.QueueListener(
            self.log_queue, *handlers, respect_handler_level=True
        )
        self.listener.start()

        # Register the stop method to be called at exit
        atexit.register(self.stop_listener)

    def stop_listener(self):
        """Stop the QueueListener."""
        self.listener.stop()


log_path = Path.home() / ".gptextual" / "logging"


def default_config(log_level: str = "INFO"):
    return f"""
  version: 1
  disable_existing_loggers: False
  formatters:
    simple:
      format: '%(asctime)s - %(levelname)s - %(pathname)s(%(lineno)d)::%(funcName)s - %(message)s'
    json:
      (): gptextual.logging.JSONFormatter
      fmt_keys:
        level: levelname
        message: message
        timestamp: timestamp
        logger: name
        module: module
        function: funcName
        line: lineno
        thread_name: threadName

  handlers:
    file_handler:
      class: logging.handlers.RotatingFileHandler
      level: DEBUG
      formatter: json 
      filename: {log_path / 'gptextual.jsonl'}
      maxBytes: 3485760 # 3MB
      backupCount: 1
      encoding: utf8
    queue_handler:
      (): gptextual.logging.QueueHandler
      handlers:
        - file_handler

  loggers:
    root:
      level: {log_level}  
      handlers:
        - queue_handler
  
  
  """


def setup_logging(log_level: str = "INFO"):
    global _logger
    os.makedirs(name=log_path, exist_ok=True)
    config = yaml.safe_load(default_config(log_level))
    configurator = DictConfigurator(config)
    config = configurator.configure()
    queue_handler = config["handlers"]["queue_handler"]
    queue_handler._initialize_listener(config["handlers"])
    _logger = logging.getLogger("gptextual")


def logger():
    return _logger
