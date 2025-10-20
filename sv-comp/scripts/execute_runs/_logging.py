"""Logging module for unified logging across scripts."""

import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


LOGGER = logging.getLogger()


def init(level, name="root", logfile=None):
    # pylint: disable=W0603
    global LOGGER
    LOGGER = _create_logger(level, name, logfile)


def _create_logger(level, name, logfile):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    stdout_handler = logging.StreamHandler()
    stdout_formatter = logging.Formatter(
        fmt="%(asctime)s %(name)s:%(levelname)-6s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stdout_handler.setFormatter(stdout_formatter)
    logger.addHandler(stdout_handler)
    if logfile:
        logfile_handler = logging.FileHandler(logfile)
        logfile_formatter = logging.Formatter(
            fmt="%(asctime)s %(name)s:%(levelname)-2s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logfile_handler.setFormatter(logfile_formatter)
        logger.addHandler(logfile_handler)
    return logger


def critical(*args, **kwargs):
    LOGGER.critical(*args, **kwargs)


def error(*args, **kwargs):
    LOGGER.error(*args, **kwargs)


def exception(*args, **kwargs):
    LOGGER.exception(*args, **kwargs)


def warning(*args, **kwargs):
    LOGGER.warning(*args, **kwargs)


def info(*args, **kwargs):
    LOGGER.info(*args, **kwargs)


def debug(*args, **kwargs):
    LOGGER.debug(*args, **kwargs)
