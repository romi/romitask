#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# romitask - Task handling tools for the ROMI project
#
# Copyright (C) 2018-2019 Sony Computer Science Laboratories
# Authors: D. Colliaux, T. Wintz, P. Hanappe
#
# This file is part of romitask.
#
# romitask is free software: you can redistribute it
# and/or modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# romitask is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with romitask.  If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

"""Logging Configuration and Management

A comprehensive logging utility module that provides flexible and configurable logging setup
for Python applications, supporting both console and file-based logging with color formatting options.

Key Features
------------
- Configurable log levels with sensible defaults
- Console logging with optional color formatting
- File-based logging with automatic file handling
- Dummy logger for testing/development
- Centralized logging configuration management
- Custom formatting options for log messages
- Dynamic log filename generation

Usage Examples
--------------
>>> # Basic usage
>>> from romitask.log import get_logger
>>> logger = get_logger(__name__)
>>> logger.info("Application started")
>>> logger.error("An error occurred")

>>> # With custom configuration
>>> logger = get_logger(__name__, log_level="DEBUG", colored=True)
>>> logger.debug("Debugging information")
"""


import logging
import sys
from datetime import datetime

from colorlog import ColoredFormatter

# Define a set of log levels by retrieving all existing log level names from Python's logging module,
# excluding specific levels ("FATAL" and "WARN") which are not standard or redundant.
LOG_LEVELS = set(logging._nameToLevel.keys()) - {"FATAL", "WARN"}

# Set the default logging level to "INFO".
DEFAULT_LOG_LEVEL = 'INFO'

# Define the log message format for non-colored logs.
# Includes the log level name, the logger name, the line number, and the log message itself.
LOG_FMT = "%(levelname)-8s [%(name)s] l.%(lineno)d %(message)s"

# Define the log message format for colored logs.
# The color is dynamically applied using `log_color` and `bg_blue` and reset after styling.
COLOR_LOG_FMT = "%(log_color)s%(levelname)-8s%(reset)s %(bg_blue)s[%(name)s]%(reset)s %(message)s"

# Create a standard logging formatter instance with the non-colored log format.
FORMATTER = logging.Formatter(
    LOG_FMT,
    style="%",
)

# Create a colored logging formatter instance for enhanced log readability in terminal outputs.
# Applies colors for log levels, resets the style after application, and uses the same `{}` style formatting.
COLORED_FORMATTER = ColoredFormatter(
    COLOR_LOG_FMT,
    datefmt=None,  # No date is included in the log format.
    reset=True,  # Automatically reset styles applied to the log after each log message.
    style='%',
)


def get_console_handler():
    """Creates and configures a console handler for logging that outputs to the standard output stream.

    This handler uses a specific formatter for colored log messages.

    Returns
    -------
    logging.StreamHandler
        The configured console logging handler with a colored formatter.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(COLORED_FORMATTER)
    return console_handler


def get_file_handler(log_file):
    """Creates and configures a file handler for logging.

    This function initializes a logging file handler, sets its level, and applies a predefined formatter to it.
    The file handler writes log messages to the specified file in write mode.
    The log level determines the severity of messages that are captured by the handler.

    Parameters
    ----------
    log_file : str or pathlib.Path
        A path to the log file where log messages will be written.

    Returns
    -------
    logging.FileHandler
        The configured logging file handler for capturing log messages.
    """
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(FORMATTER)
    return file_handler


def get_dummy_logger(logger_name, log_level=DEFAULT_LOG_LEVEL):
    """Creates and configures a dummy logger with a console handler.

    This function generates a logger instance associated with the specified name and log level.
    The logger is configured with a console handler to allow output of log statements to the console.
    It is typically used for basic logging setups where no file-based or external configurations are required.

    Parameters
    ----------
    logger_name : str
        A name to use for the logger.
    log_level : int or str, optional
        A logging level to set for the logger. Defaults to ``DEFAULT_LOG_LEVEL``.

    Returns
    -------
    logging.Logger
        The configured logger instance with a console handler attached.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.addHandler(get_console_handler())
    return logger


def get_logger(logger_name, log_file=None, log_level=DEFAULT_LOG_LEVEL):
    """Get a logger with a specific name and log level for console output.

    This function retrieves an existing logger instance with the specified name, or creates a new one if none exists.

    Parameters
    ----------
    name : str
        A name to use for the logger.
        Typically derived from the module or component that generates the logs.
    log_file : str or pathlib.Path, optional
        A path to the file where log messages should be written.
        Defaults to ``None``, in which case no file handler is added.
    log_level : int or str, optional
        A logging level to set for the logger. Defaults to ``DEFAULT_LOG_LEVEL``.

    Returns
    -------
    logging.Logger
        The configured logger instance ready to log messages with the specified settings.
    """
    logger_name = logger_name.split(".")[-1]
    if not logging.getLogger(logger_name).hasHandlers():
        return _get_logger(logger_name, log_file=log_file, log_level=log_level)
    return logging.getLogger(logger_name)


def _get_logger(logger_name, log_file=None, log_level=DEFAULT_LOG_LEVEL):
    """Creates and configures a logger instance with specified settings.

    This function sets up a logger with a given name, associates it with a console
    handler, and optionally with a file handler. It sets the desired log level and
    ensures the logger does not propagate messages to its parent logger. The logger
    is returned to the caller for usage.

    Parameters
    ----------
    logger_name : str
        A name to use for the logger.
    log_file : str or pathlib.Path, optional
        A path to the file where log messages should be written.
        Defaults to ``None``, in which case no file handler is added.
    log_level : int or str, optional
        A logging level to set for the logger. Defaults to ``DEFAULT_LOG_LEVEL``.

    Returns
    -------
    logger : logging.Logger
        The configured logger instance ready to log messages with the specified settings.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.addHandler(get_console_handler())
    if log_file is not None:
        logger.addHandler(get_file_handler(log_file))

    # with this pattern, it's rarely necessary to propagate the error up to parent
    logger.propagate = False

    return logger


def get_log_filename(task, date_fmt="%Y.%m.%d_%Hh%Mm%Ss"):
    """Return a standardised log filename with the date and task name.

    Parameters
    ----------
    task: str
        The task name.
    date_fmt: str
        The date format string. Default is "%Y.%m.%d_%Hh%Mm%Ss".

    Returns
    -------
    str
        The standardised log filename.
    """
    now = datetime.now()
    now_str = now.strftime(date_fmt)
    # Get the log_file name, with the date & task name by default:
    return f'{now_str}_{task.upper()}.log'


DEFAULT_LOG_FILENAME = "romitask.log"
DATE_FMT = "%Y-%m-%d %H:%M:%S"
LOGGING_CFG = """
[loggers]
keys=root

[logger_root]
handlers=console,file
qualname=root
level={log_level}

[handlers]
keys=console,file

[handler_file]
class=logging.FileHandler
formatter=simple
level={log_level}
args=('{logfile_path}','w')

[handler_console]
class=logging.StreamHandler
formatter=color
level={log_level}
stream : ext://sys.stdout

[formatters]
keys=simple,color

[formatter_simple]
class=logging.Formatter
format={simple_fmt}
datefmt={date_fmt}

[formatter_color]
class=colorlog.ColoredFormatter
format={colored_fmt}
datefmt={date_fmt}
"""


def get_logging_config(**kwargs):
    """Return the logging configuration.

    Other Parameters
    ----------------
    log_level : {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        A valid logging level. Defaults to `DEFAULT_LOG_LEVEL`.
    logfile_path : str
        Path to the logging file to write. Defaults to `DEFAULT_LOG_FILENAME`.
    date_fmt : str
        String formatting for dates. Defaults to `DATE_FMT`.
    colored_fmt : str
        String formatting for console log messages. Defaults to `COLORED_FMT`.
    simple_fmt : str
        String formatting for file log messages. Defaults to `SIMPLE_FMT`.

    Returns
    -------
    str
        The logging configuration in configparser format.

    Examples
    --------
    >>> from romitask.log import get_logging_config
    >>> print(get_logging_config())
    """
    kwargs['log_level'] = kwargs.get('log_level', DEFAULT_LOG_LEVEL)
    kwargs['logfile_path'] = kwargs.get('logfile_path', DEFAULT_LOG_FILENAME)
    kwargs['date_fmt'] = kwargs.get('date_fmt', DATE_FMT)
    kwargs['colored_fmt'] = kwargs.get('colored_fmt', COLOR_LOG_FMT)
    kwargs['simple_fmt'] = kwargs.get('simple_fmt', LOG_FMT)
    return LOGGING_CFG.format(**kwargs)
