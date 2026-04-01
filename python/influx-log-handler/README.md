# Influx Log Handler

This package provides a Python logging handler that writes logs in InfluxDB line protocol format to a file.

## Usage

```
from influx_log_handler.influx_handler import InfluxLineLogHandler
import logging

handler = InfluxLineLogHandler("logs.influx", measurement="log")
logging.basicConfig(handlers=[handler], level=logging.INFO)

logger = logging.getLogger("mylogger")
logger.info("Hello world!")
```

This will append lines in InfluxDB line protocol format to `logs.influx`.

## Format

Each log entry is written as a line in the following format:

```
log,level=INFO,logger=mylogger message="Hello world!",filename="main.py",funcName="<function>",lineno=42 1640995200000000000
```

- `measurement` (default: `log`)
- tags: `level`, `logger`
- fields: `message`, `filename`, `funcName`, `lineno`
- timestamp: nanoseconds since epoch
