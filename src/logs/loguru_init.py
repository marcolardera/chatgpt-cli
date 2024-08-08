from loguru import logger
import sys
import warnings
import contextlib

# Remove default logger
logger.remove()

# Add a rotating file handler with colorful logs
logger.add(
    "logs/chatgpt_{time}.log",
    rotation="1 week",  # Rotate logs every week
    retention="1 month",  # Keep logs for 1 month
    compression="zip",  # Compress logs
    colorize=True,  # Enable colorful logs
    level="INFO",
    format="{time}<blue>{file}</blue><red>{module}</red><level>{message}</level> <cyan>{name}</cyan>:<cyan>{line}</cyan><yellow>{process}</yellow><green>{thread}</green><magenta>{elapsed}</magenta><red>{exception}</red><green>{function}</green>",
)

# Add a handler for stdout
logger.add(
    sys.stdout,
    colorize=True,
    format="{time}<blue>{file}</blue><red>{module}</red><level>{message}</level> <cyan>{name}</cyan>:<cyan>{line}</cyan><yellow>{process}</yellow><green>{thread}</green><magenta>{elapsed}</magenta><red>{exception}</red><green>{function}</green>",
    level="INFO",
)


# Capture standard stdout, stderr, and warnings
class StreamToLogger:
    def __init__(self, level="INFO"):
        self._level = level

    def write(self, buffer):
        for line in buffer.rstrip().splitlines():
            logger.opt(depth=1).log(self._level, line.rstrip())

    def flush(self):
        pass


stream = StreamToLogger()
with contextlib.redirect_stdout(stream):
    with contextlib.redirect_stderr(stream):
        print("Standard output is sent to added handlers.")
        sys.stderr.write("Standard error is sent to added handlers.\n")

showwarning_ = warnings.showwarning


def showwarning(message, *args, **kwargs):
    logger.warning(message)
    showwarning_(message, *args, **kwargs)


warnings.showwarning = showwarning
