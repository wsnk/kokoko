
import logging
from logging.handlers import RotatingFileHandler


def _format_field_str(val: str) -> str:
    val = val.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{val}"'


class InfluxLineLogHandler(RotatingFileHandler):
    """
    A logging handler that writes logs in InfluxDB line protocol format to a rotating file.
    """
    def __init__(
        self,
        filename: str,
        measurement: str = "log",
        *,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str = None,
        level: int = logging.NOTSET
    ):
        super().__init__(filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)
        self.measurement = measurement
        self.setLevel(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format_influx_line(record)
            self.stream = self._open() if self.stream is None else self.stream
            self.stream.write(line + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

    def format_influx_line(self, record: logging.LogRecord) -> str:
        tags_str = ",".join([
            f"level={record.levelname}",
            f"logger={record.name}"
        ])
        fields_str = ",".join([
            f"message={_format_field_str(record.getMessage())}",
            f"filename={_format_field_str(record.filename)}",
            f"funcName={_format_field_str(record.funcName)}",
            f"lineno={record.lineno}"
        ])

        # Influx expects nanosecond timestamps
        timestamp_ns = int(record.created * 1_000_000_000)
        return f"{self.measurement},{tags_str} {fields_str} {timestamp_ns}"
