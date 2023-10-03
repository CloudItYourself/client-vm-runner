import logging
from typing import Final

LOGGING_FORMAT: Final[str] = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"


def initialize_logger(logger_name: str):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logger.addHandler(handler)
