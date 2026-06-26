import logging
import os
import datetime
from colorlog import ColoredFormatter

class LogManager:
    _initialized = False

    @classmethod
    def init(cls, level=logging.INFO):
        if cls._initialized:
            return

        # Create logs directory if it doesn't exist
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # Generate timestamp for log file
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(logs_dir, f"{timestamp}.log")

        # File handler for logging to file
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Console handler with colors
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredFormatter(
            "%(log_color)s%(asctime)s %(levelname)-8s %(name)s: %(message)s"
        ))

        root = logging.getLogger()
        root.setLevel(level)
        root.handlers.clear()
        root.addHandler(file_handler)
        root.addHandler(console_handler)

        #logging.getLogger("bluezero.localGATT").setLevel(logging.INFO) # irregardless
        cls._initialized = True


    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)