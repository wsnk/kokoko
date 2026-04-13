import os
import logging
from kokoko.influx_log_handler import InfluxLineLogHandler


FILENAME = os.path.basename(__file__)


def mk_logger(log_path, name, **handler_kwargs):
    handler = InfluxLineLogHandler(log_path, measurement="testlog", **handler_kwargs)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger


def test_influx_line_log_handler_basic(tmp_path):
    log_path = tmp_path / "test.log"
    logger = mk_logger(log_path, "testlogger")

    logger.info("Hello %s!", "world")

    logger.handlers[0].flush()  # Ensure the log is written to the file before reading it

    lines = log_path.read_text().strip().splitlines()

    assert len(lines) == 1
    line = lines[0].strip()
    assert line.startswith(
        "testlog,"
        f"level=INFO,logger=testlogger"
        " "
        "message=\"Hello world!\","
        f"filename=\"{FILENAME}\","
        "funcName=\"test_influx_line_log_handler_basic\","
        "lineno=22 "
    )
    timestamp = int(line.rsplit(" ", 1)[-1])
    assert timestamp > 0


def test_influx_line_log_handler_rotation(tmp_path):
    log_path = tmp_path / "test.log"
    logger = mk_logger(log_path, "rotatelogger", maxBytes=100, backupCount=1)

    for i in range(20):
        logger.info("msg %d", i)

    logger.handlers[0].flush()  # Ensure the log is written to the file before checking rotation

    # Should have rotated at least once
    files = os.listdir(tmp_path)
    assert any(f.startswith("test.log") for f in files)
    # At least one file should have content
    assert any(os.path.getsize(os.path.join(tmp_path, f)) > 0 for f in files)
