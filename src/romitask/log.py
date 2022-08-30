#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from os import path

from colorlog import ColoredFormatter


def configure_logger(name, log_path="", log_level='INFO'):
    colored_formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(bg_blue)s[%(name)s]%(reset)s %(message)s",
        datefmt=None,
        reset=True,
        style='%'
    )
    simple_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    # create console handler:
    console = logging.StreamHandler()
    console.setFormatter(colored_formatter)

    if 'logger' not in globals():
        logger = logging.getLogger(name)
        logger.addHandler(console)
        logger.setLevel(getattr(logging, log_level))

        if log_path is not None and log_path != "":
            # create file handler:
            fh = logging.FileHandler(path.join(log_path, f'{name}.log'), mode='w')
            fh.setFormatter(simple_formatter)
            logger.addHandler(fh)

    return logger


logger = configure_logger('romitask')

