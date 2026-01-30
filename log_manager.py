import logging
from colorlog import ColoredFormatter

class LogManager:
    _initialized = False

    @classmethod
    def init(cls, level=logging.INFO):
        if cls._initialized:
            return

        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter(
            "%(log_color)s%(asctime)s %(levelname)-8s %(name)s: %(message)s"
        ))

        root = logging.getLogger()
        root.setLevel(level)
        root.handlers.clear()
        root.addHandler(handler)

        cls._initialized = True

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)