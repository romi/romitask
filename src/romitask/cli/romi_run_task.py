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
# License along with romitask.  If not, see
# <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

"""ROMI tasks CLI.

It is intended to be used as the main program to run the various tasks defined in ``MODULES``.

It uses ``luigi`` paradigm with ``Task``, ``Target`` & ``Parameters`` defined
for each ``RomiTask`` in their module.

The program uses two config files stored in the root scan dataset folder:

  - ``scan.toml``: the last configuration used with the 'Scan' module;
  - ``pipeline.toml``: the last configuration used with any other module.


They define tasks parameters that will override the default tasks parameters
using luigi's "config ingestion" [^1] and ROMI configuration classes.

The tasks "CalibrationScan", "IntrinsicCalibrationScan", "Scan" & "VirtualScan"
requires a non-existent or empty dataset directory.
The other tasks requires a dataset directory populated by images from one of
the previously named task.

References
----------
[^1]: https://luigi.readthedocs.io/en/stable/configuration.html#parameters-from-config-ingestion

"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from logging import getLogger
from pathlib import Path

import toml

from romitask import PIPE_TOML
from romitask import SCAN_TOML
from romitask.log import LOG_LEVELS
from romitask.log import get_logger
from romitask.log import get_log_filename
from romitask.log import get_logging_config
from romitask.modules import DATA_CREATION_TASK
from romitask.modules import MODULES
from romitask.modules import NO_DATASET_TASK
from romitask.modules import TASKS
from romitask.utils import get_version
from romitask.utils import parse_kbdi

LUIGI_CMD = "luigi"
HELP_URL = "https://docs.romi-project.eu/plant_imager/tutorials/basics/"
LOGGER_NAME = 'romi_run_task'


def parsing():
    parser = argparse.ArgumentParser(
        description="Run a ROMI task on selected dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"The list of pre-defined tasks is: {', '.join(TASKS)}.\n" + \
               f"See {HELP_URL} for a detailed help with CLI.")

    # Positional arguments:
    parser.add_argument('task', metavar='task', type=str,
                        help=f"Name of the ROMI task to run. See the list of pre-defined tasks below.")
    parser.add_argument('dataset_path', type=str, default='', nargs='*',
                        help="""Path to the dataset to process (directory).
                        You may use Unix pattern matching with "*" and "?" to select a list of dataset.""")

    # Optional arguments:
    parser.add_argument('--config', dest='config', type=str, default="",
                        help="""Pipeline configuration file (TOML) or directory.
                        If a file, read the configuration from it.
                        If a directory, read & concatenate all configuration files in it.
                        By default, search a 'pipeline.toml' file in the selected dataset directory.""")
    parser.add_argument('--module', dest='module', type=str, default=None,
                        help="""Library and module of the task.
                        Use it if not available or different than defined in `romitask.modules.MODULES`.""")
    parser.add_argument('--log-level', dest='log_level', type=str, default='INFO', choices=LOG_LEVELS,
                        help="Level of message logging, defaults to 'INFO'.")
    parser.add_argument('--dry-run', dest='dry_run', action="store_true",
                        help="Use this to test the command-line by doing everything except calling the task(s).")

    # Luigi related arguments:
    luigi = parser.add_argument_group("luigi options")
    luigi.add_argument('--luigicmd', dest='luigicmd', type=str, default=LUIGI_CMD,
                       help=f"Luigi command, defaults to `{LUIGI_CMD}`.")
    luigi.add_argument('--local-scheduler', dest='ls', action="store_true", default=True,
                       help="Use the local luigi scheduler, defaults to `True`.")
    return parser


def load_backup_scan_cfg(path):
    """Try to load ``SCAN_TOML`` configuration from path.

    Parameters
    ----------
    path : str
        Where the ``SCAN_TOML`` configuration file should be.

    Returns
    -------
    dict
        The configuration dictionary, if loaded from backup file.
    """
    scan_last_cfg = os.path.join(path, SCAN_TOML)
    bak_scan_config = {}
    if os.path.isfile(scan_last_cfg):
        bak_scan_config = toml.load(scan_last_cfg)

    return bak_scan_config


def load_backup_pipe_cfg(path, task, logger):
    """Try to load ``PIPE_TOML`` configuration from path.

    Parameters
    ----------
    path : str
        Where the ``PIPE_TOML`` configuration file should be.
    task : str
        Name of the task to perform.
    logger : logging.Logger
        The logger to use with this method.

    Returns
    -------
    dict
        The configuration dictionary, if loaded from backup file.
    """
    bak_pipe_path = os.path.join(path, PIPE_TOML)
    bak_pipe_config = {}
    if os.path.isfile(bak_pipe_path):
        # Raise an IOError when task 'Scan' is required in a folder with a backup of a processing pipeline
        # This probably means that you are trying to use a dataset that is NOT EMPTY!
        if "Scan" in task:
            logger.critical(f"Task '{task}' was called with dataset '{path}'!")
            logger.critical(f"It contains a processing pipeline configuration backup file!")
            sys.exit(f"Requested {task} task in non-empty folder, clean it up or change location!")
        bak_pipe_config = toml.load(bak_pipe_path)

    return bak_pipe_config


def load_config_from_directory(path, logger):
    """Load TOML & JSON configuration files from path.

    Parameters
    ----------
    path : str
        Path to where the configuration file(s) should be.
    logger : logging.Logger
        The logger to use with this method.

    Returns
    -------
    dict
        The configuration dictionary, if loaded from the files.

    Notes
    -----
    We exclude the backup files ``SCAN_TOML`` & ``PIPE_TOML`` from the list of loadable files.

    """
    # List TOML config files:
    toml_list = glob.glob(os.path.join(path, "*.toml"))

    # Exclude BACKUP configuration files from TOML config files list:
    toml_list = [Path(cfg) for cfg in toml_list if cfg.split("/")[-1] not in (SCAN_TOML, PIPE_TOML)]
    # Make sure we got at least one TOML or JSON config file:
    if len(toml_list) == 0:
        logger.critical(f"Could not find any TOML configuration file in '{path}'!")
        sys.exit("Configuration file missing!")

    config = {}
    # Read TOML configs
    for f in toml_list:
        try:
            c = toml.load(f)
            config.update(c)  # update the config with the new one
        except:
            logger.warning(f"Could not process TOML config file: {f}")
        else:
            logger.info(f"Loaded TOML configuration file: {f}")

    return config


def load_config_from_file(path, logger):
    """Load TOML configuration file from path.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the configuration file to load.
    logger : logging.Logger
        The logger to use with this method.

    Returns
    -------
    dict
        The configuration dictionary.
    """
    config = {}
    if isinstance(path, str):
        path = Path(path)
    # Check that the given configuration file exists:
    if not path.is_file():
        logger.critical(f"Could not configuration find file: '{path.absolute()}'")
    # Try to load the TOML configuration file:
    try:
        config = toml.load(path)
    except:
        if not path.suffix == ".toml":
            logger.critical(f"Could not load TOML configuration file '{path}'!")
        else:
            logger.critical(f"Unsupported configuration file format, should be a TOML file, got '{path.name}'!")
    else:
        logger.info(f"Loaded TOML configuration file: {path}")

    return config


def get_task_module(task, logger, module=None):
    """Set the name of the `module` to be loaded for the selected `task`.

    Parameters
    ----------
    task : str
        Get the name of the `module` for selected `task`.
        If `module` is not ``None``, check it exists.
    logger : logging.Logger
        The logger to use with this method.
    module : str, optional
        A manually defined module name.

    Returns
    -------
    str
        The name of the `module` to use with `task`.
    """
    import importlib
    if module is not None:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            logger.warning(f"Could not load manually defined module: '{module}'.")
            module = get_task_predefined_module(task, logger=logger)
        else:
            logger.info(f"Got a manually defined module: '{module}'.")
    else:
        module = get_task_predefined_module(task, logger=logger)
    return module


def get_task_predefined_module(task: str, logger) -> str:
    """Try to get the task from the pre-defined ``MODULES`` dictionary."""
    try:
        module = MODULES[task]
    except KeyError:
        logger.critical(f"Could not find pre-defined module for selected task '{task}'!")
        logger.critical(f"The list of pre-defined tasks is: {', '.join(sorted(TASKS))}.")
        logger.critical(f"Use `--module` to manually define the Python module corresponding to the selected task.")
        sys.exit("Error with module definition!")
    else:
        logger.info(f"Found pre-defined module '{module}' for task '{task}'.")
    return module


def create_backup_cfg(path, cfgname, config):
    """Create the backup configuration file used by luigi.

    Parameters
    ----------
    path : str
        Where to save the backup configuration file used by luigi.
    cfgname : str
        Name of the backup configuration file.
    config : dict
        Task(s) configuration dictionary.

    Returns
    -------
    str
        Path to the configuration file to use by luigi.

    Notes
    -----
    We append "return codes" and "library versioning" to the given configuration dictionary.

    """
    file_path = os.path.join(path, cfgname)

    # The following parameters control Luigi worker behavior.
    # https://luigi.readthedocs.io/en/stable/configuration.html#worker
    config["worker"] = {
        "keep_alive": True,
        "max_keep_alive_idle_duration": 10,  # in seconds
    }

    # The following parameters control Luigi scheduler behavior.
    # https://luigi.readthedocs.io/en/stable/configuration.html#scheduler
    config["scheduler"] = {
        "retry_count": 1,
        "retry_delay": 1,
    }

    # The following return codes are the recommended exit codes for Luigi.
    # They are in increasing level of severity (for most applications).
    # https://luigi.readthedocs.io/en/stable/configuration.html#retcode
    config["retcode"] = {"already_running": 10, "missing_data": 20,
                         "not_run": 25, "task_failed": 30,
                         "scheduling_error": 35, "unhandled_exception": 40}

    # Save the libraries version:
    config["version"] = get_version()

    with open(file_path, 'w') as f:
        toml.dump(config, f)
    return file_path


def check_dataset_directory(path, task, logger):
    """Check the dataset directory is correctly defined depending on the `task` to execute.

    Parameters
    ----------
    path : pathlib.Path
        Path to the dataset to check.
    task : str
        Name of the task to execute by luigi.
    logger : logging.Logger
        The logger to use with this method.

    Returns
    -------
    str
        The name of the (backup) configuration file to use by luigi.

    Notes
    -----
    If a "Scan" like tasks is required, a directory should be created to receive the created fileset.
    Else, the dataset directory should exist as an existing fileset will be processed.
    """
    if task == "ScannerToCenter":
        cfgname = SCAN_TOML
    elif task in DATA_CREATION_TASK:
        try:
            path.mkdir(exist_ok=False)
        except FileExistsError:
            if not list(path.iterdir()) == []:
                logger.critical(f"Given dataset directory '{path}' exists and is not empty!")
                delete = parse_kbdi(input("Do you want ro remove the previous dataset? [y/N]"))
                if delete:
                    shutil.rmtree(path)
                    path.mkdir(exist_ok=False)
                else:
                    sys.exit("Non-empty dataset directory for data creation task.")
            else:
                logger.info(f"Using existing empty dataset directory: {path}")
        cfgname = SCAN_TOML
    else:
        try:
            assert path.is_dir()
        except AssertionError:
            logger.critical(f"Could not find dataset directory '{path}'!")
            sys.exit("Non-existing dataset directory for processing task.")
        cfgname = PIPE_TOML
    return cfgname


def update_config(config, update):
    """Update a configuration dictionary.

    Parameters
    ----------
    config : dict
        The configuration dictionary to update.
    update : dict
        The update dictionary.

    Returns
    -------
    dict
        Updated configuration dictionary.

    Notes
    -----
    We update only the values from the update dictionary without removing any existing keys.

    """
    from collections.abc import Mapping
    for k, v in update.items():
        if isinstance(v, Mapping):
            config[k] = update_config(config.get(k, {}), v)
        else:
            config[k] = v
    return config


def run_task(dataset_path, task, config, **kwargs):
    """Load the configuration to use and call the luigi command to run the selected task.

    Parameters
    ----------
    dataset_path : pathlib.Path or str
        The path to the dataset directory.
    task : str
        The name of the task to execute by luigi.
    config : pathlib.Path or str or dict
        The configuration path or dictionary.

    Other Parameters
    ----------------
    logger : logging.Logger
        A logger to use with this method, default to the global logger named `LOGGER_NAME`.
    log_fname : str
        The log file name to use.
        Defaults to use the standardised log filename with the date and task name from `get_log_filename`.
    log_level : {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        The logging level to use, defaults to 'INFO'.
    luigicmd : str
        The luigi command to use, defaults to 'LUIGI_CMD'.
    module : str
        The module name to load the task from. Default to `None`, search in the module dictionary.
    local_scheduler : bool
        Whether to run the task locally. Defaults to `True`.
    dry_run : bool
        Whether to make it a dry run, returning the command but not calling it. Defaults to `False`.

    See Also
    --------
    romitask.log.get_logging_config
    romitask.log.get_log_filename
    """
    logger = kwargs.get("logger", getLogger(LOGGER_NAME))
    log_level = kwargs.get("log_level", "INFO")
    luigicmd = kwargs.get("luigicmd", LUIGI_CMD)

    # - Try to load PIPELINE backup TOML configuration:
    bak_pipe_config = load_backup_pipe_cfg(dataset_path, task, logger=logger)

    # - Process given PIPELINE configuration directory OR file, if any:
    if isinstance(config, dict):
        logger.info("Loading configuration from dictionary.")
    elif os.path.isdir(config):
        config = load_config_from_directory(config, logger=logger)
    elif os.path.isfile(config):
        config = load_config_from_file(config, logger=logger)
    elif config != "":
        logger.critical(f"Could not understand `config` option '{config}'!")
        sys.exit("Error with configuration file!")
    else:
        if bak_pipe_config is None:
            logger.info("Using NO configuration!")
        else:
            config = bak_pipe_config
            logger.info("Using a PREVIOUS pipeline configuration!")

    # - Look for "local" PIPELINE configuration file(s) to load:
    local_path = Path(dataset_path)
    local_toml = list(local_path.glob('*.toml'))
    local_toml = [f for f in local_toml if f.name != SCAN_TOML]  # exclude SCAN backup TOML config
    local_toml = [f for f in local_toml if f.name != PIPE_TOML]  # exclude PIPELINE backup TOML config
    # - Load the local configuration from detected file(s):
    local_config = {}
    if len(local_toml) > 0:
        logger.info(f"Found {len(local_toml)} local TOML configuration file{'s' if len(local_toml) > 1 else ''}!")
        for f in local_toml:
            local_config.update(load_config_from_file(str(f), logger=logger))
        if local_config != {}:
            logger.info(f"Got local definitions for: {list(local_config.keys())}")
            # Update the given PIPELINE configuration with the local configuration:
            update_config(config, local_config)
            logger.info("Updated given configuration with local definitions!")
        else:
            logger.error(f"Failed to load local TOML configuration file{'s' if len(local_toml) > 1 else ''}!")

    # - Set the name of the module to be loaded for the selected task:
    module = get_task_module(task, logger=logger, module=kwargs.get("module", None))
    # - Check the dataset directory is OK to use:
    cfgname = check_dataset_directory(dataset_path, task, logger=logger)
    # - Create the "scan.toml" OR "pipeline.toml" (backup) config file used by luigi:
    file_path = create_backup_cfg(dataset_path, cfgname, config)

    # Get the log_file name, with the date & task name by default:
    log_fname = kwargs.get('log_fname', get_log_filename(task))
    # - Get logging configuration string for luigi, specifying the log file name :
    logging_config = get_logging_config(log_level=log_level, logfile_path=str(local_path / log_fname))

    with tempfile.TemporaryDirectory() as tmpd:
        # - Create a "logging.cfg" file to be used by `luigi`:
        logging_file_path = os.path.join(tmpd, "logging.cfg")
        with open(logging_file_path, 'w') as f:
            f.write(logging_config)

        # - Define environment variables to provide the logging TOML file path to `luigi`:
        env = {"LUIGI_CONFIG_PARSER": "toml", "LUIGI_CONFIG_PATH": file_path}
        env.update({'PYOPENCL_CTX': '0'})  # default choice
        # - Define the luigi command to run:
        # "--DatabaseConfig-scan args.dataset_path" set the value of `scan` for the `DatabaseConfig` Config class
        # https://luigi.readthedocs.io/en/stable/parameters.html#setting-parameter-value-for-other-classes
        cmd = [luigicmd, "--logging-conf-file", logging_file_path,
               "--module", module, task,
               "--DatabaseConfig-scan", dataset_path]
        if kwargs.get('local_scheduler', False):
            cmd.append("--local-scheduler")

        if kwargs.get('dry_run', False):
            logger.info(f"Luigi command to call is:\n{cmd}")
        else:
            t_start = time.time()
            # - Start the configured pipeline:
            p = subprocess.run(cmd, env={**os.environ, **env}, check=True)
            delta = timedelta(seconds=time.time() - t_start)
            delta = str(delta).split('.')[0]  # to get HH:MM:SS
            if p.returncode == 0:
                logger.info(f"Done in {delta}s!")
            else:
                logger.info(f"Failed after {delta}s!")

    return


def main():
    # - Parse the input arguments to variables:
    parser = parsing()
    args = parser.parse_args()

    # - Configure a logger from this application:
    global logger
    logger = get_logger(LOGGER_NAME)

    # - If only one path in the list, get the first one:
    if len(args.dataset_path) == 1:
        args.dataset_path = args.dataset_path[0]

    if args.task in DATA_CREATION_TASK:
        # These are "data creation modules", we thus require a single path to dataset...
        try:
            assert isinstance(args.dataset_path, str)
        except AssertionError:
            logger.critical(f"Task '{args.task}' requires the `dataset_path` to be a string.")
            logger.critical(f"Got '{args.dataset_path}'!")
            sys.exit(f"Error with input dataset path for '{args.task}' module!")
        else:
            folders = args.dataset_path
    else:
        # Other modules are "data processing modules", they can accept multiple path to dataset...
        if isinstance(args.dataset_path, str):
            # Process the input string `args.dataset_path` with ``glob``:
            #   - check existence of path:
            #   - may contain UNIX matching symbols (like '*' or '?'):
            folders = glob.glob(args.dataset_path)
            # Resolve path (make it absolute & normalize):
            folders = [Path(path).resolve() for path in folders]
            # Check that globed paths are directory (and exist, implied):
            folders = sorted([path for path in folders if path.is_dir()])
        elif isinstance(args.dataset_path, list):
            # Resolve path (make it absolute & normalize):
            folders = [Path(path).resolve() for path in args.dataset_path]
            # Check that listed paths are directory (and exist, implied):
            folders = sorted([path for path in folders if path.is_dir()])
        else:
            logger.critical(f"Can not understand input dataset path: '{args.dataset_path}'")
            sys.exit(f"Error with input dataset path for '{args.task}' module!")
        # If only one element in list, make it a plain str:
        if len(folders) == 1:
            folders = folders[0]

    def _dataset_path_error(args):
        logger.critical(f"Could not obtain a valid path from input dataset path: '{args.dataset_path}'!")
        sys.exit(f"Error with input dataset path for '{args.task}' module!")

    # Some tasks may accept to work without a dataset:
    if args.task not in NO_DATASET_TASK:
        # If a pathlib.Path instance, it should exist:
        if isinstance(folders, Path) and not folders.exists():
            _dataset_path_error(args)
        # If a list instance, it should not be empty:
        if isinstance(folders, list) and len(folders) == 0:
            _dataset_path_error(args)

    # Finally, we can call the main `run_task` method:
    if isinstance(folders, list):
        ## For each folder:
        dataset = [folder.name for folder in folders]
        logger.info(f"Got a list of {len(folders)} scan dataset to analyze: {', '.join(dataset)}")
        for dataset_path in folders:
            print("\n")  # to facilitate the search in the console by separating the datasets
            logger.info(f"Processing dataset '{Path(dataset_path).name}'.")
            try:
                run_task(dataset_path, args.task, args.config,
                         log_level=args.log_level, luigicmd=args.luigicmd, module=args.module,
                         local_scheduler=args.ls, dry_run=args.dry_run)
            except Exception as e:
                print(e)
    else:
        ## For the folder:
        run_task(folders, args.task, args.config,
                 log_level=args.log_level, luigicmd=args.luigicmd, module=args.module,
                 local_scheduler=args.ls, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
