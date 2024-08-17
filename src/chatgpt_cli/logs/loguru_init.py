from loguru import logger
import sys
import warnings
import contextlib

# Remove default logger
logger.remove()

# Add a rotating file handler with colorful logs
logger.add(
    "file.log",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>",
    level="DEBUG",
    rotation="10 MB",
    compression="zip",
)

# Add a handler for stdout
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>",
    level="WARNING",
)


# Capture standard stdout, stderr, and warnings
class StreamToLogger:
    """
    A class to redirect standard output and error to the logger.
    """

    def __init__(self, level: str = "INFO") -> None:
        """
        Initializes the StreamToLogger object.

        Args:
            level: The logging level to use.
        """
        self._level = level

    def write(self, buffer: str) -> None:
        """
        Writes the buffer to the logger.

        Args:
            buffer: The buffer to write.
        """
        for line in buffer.rstrip().splitlines():
            logger.opt(depth=1).log(self._level, line.rstrip())

    def flush(self) -> None:
        """
        Flushes the buffer.
        """
        pass


stream = StreamToLogger()
with contextlib.redirect_stdout(stream):
    with contextlib.redirect_stderr(stream):
        print("Standard output is sent to added handlers.")
        sys.stderr.write("Standard error is sent to added handlers.\n")

showwarning_ = warnings.showwarning


def showwarning(message: str, *args, **kwargs) -> None:
    """
    Logs warnings to the logger.

    Args:
        message: The warning message.
        *args: Additional arguments.
        **kwargs: Additional keyword arguments.
    """
    logger.warning(message)
    showwarning_(message, *args, **kwargs)


warnings.showwarning = showwarning
