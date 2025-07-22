import logging
import os
from datetime import datetime

from colorlog import ColoredFormatter


def configure(logger: logging.Logger):
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_filename = os.path.join(log_dir, datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.log')

    if not logger.handlers:
        log_format = '%(log_color)s%(asctime)s %(message)s'
        colored_formatter = ColoredFormatter(
            log_format,
            datefmt="[%X]",
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            },
            secondary_log_colors={},
            style='%'
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(colored_formatter)

        file_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="[%X]")
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setFormatter(file_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
