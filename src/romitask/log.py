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
import logging
from datetime import datetime
from pathlib import Path

from colorlog import ColoredFormatter

SIMPLE_FMT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
COLORED_FMT = "%(log_color)s%(levelname)-8s%(reset)s %(bg_blue)s[%(name)s]%(reset)s %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"
LOGLEV = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_LOG_LEVEL = LOGLEV[1]
DEFAULT_LOG_FILENAME = "romitask.log"
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
    kwargs['colored_fmt'] = kwargs.get('colored_fmt', COLORED_FMT)
    kwargs['simple_fmt'] = kwargs.get('simple_fmt', SIMPLE_FMT)
    return LOGGING_CFG.format(**kwargs)


def configure_logger(name, log_path="", log_level='INFO'):
    """Return a configured logger.

    Parameters
    ----------
    name : str
        The name of the logger.
    log_path : str
        A file path to save the log.
        Defaults to `''`.
    log_level : {'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'}
        A valid logging level.
        Defaults to `'INFO'`.
    """
    # Create a logger:
    logger = logging.getLogger(name)
    # Create a colored formatter for the console handler:
    colored_formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(bg_blue)s[%(name)s]%(reset)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S", reset=True, style='%'
    )
    # Create a console handler & set the colored formatter:
    console = logging.StreamHandler()
    console.setFormatter(colored_formatter)
    # Add it to the logger:
    logger.addHandler(console)
    logger.setLevel(getattr(logging, log_level))

    # If a '' is specified, we add a file handler with a simple formatter:
    if log_path is not None and log_path != "":
        # Create a simple formatter for the file handler:
        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S", style='%'
        )
        # Create a file handler & set the simple formatter:
        fh = logging.FileHandler(Path(log_path) / f'{name}.log', mode='w')
        fh.setFormatter(simple_formatter)
        # Add it to the logger:
        logger.addHandler(fh)

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
