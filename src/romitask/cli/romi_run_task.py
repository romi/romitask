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

"""
# CLI to execute ROMI Luigi tasks

A lightweight wrapper that launches ROMI‑specific Luigi tasks from the command line (or programmatically).
It loads and merges configuration files, validates dataset directories, prepares logging, sets up environment variables, and finally invokes Luigi with the appropriate module and task.
This makes complex pipeline execution simple, reproducible, and portable.

## Key Features

- **Unified CLI entry point** (`romi_run_task.py`) to run any pre‑defined ROMI task.
- **Automatic configuration handling**: loads backup `scan.toml` / `pipeline.toml`, merges multiple local TOML files, and applies CLI overrides.
- **Dynamic module resolution**: selects the correct Python module for a task, with optional manual override.
- **Dataset validation**: ensures the dataset directory matches the expectations of the selected task (creation vs. processing).
- **Robust logging**: generates per‑task log files, configurable log level, and temporary logging configuration passed to Luigi.
- **Environment preparation**: injects `.env` variables, sets `LUIGI_CONFIG_PATH`, `PYOPENCL_CTX`, and optional DB authentication flags.
- **Dry‑run mode**: prints the full Luigi command without executing it, useful for debugging.
- **Authentication options**: support for DB credentials or a “no‑auth” testing mode.
- **Local scheduler by default**: runs the Luigi scheduler locally unless overridden.
- **Programmatic API**: `run_task()` can be called from Python code for tighter integration.

## Usage Examples

### 1. Command‑line execution
Run a `Scan` task to create a dataset `scan01` located at `/data/ROMI/` with a custom configuration:

```shell
romi_run_task Scan /data/ROMI/scan01 --config /path/to/my/config.toml
```

### 2. Programmatic use from Python
```python
>>> from pathlib import Path
>>> from romitask.cli.romi_run_task import run_task
>>> dataset = Path("/data/scan01")
>>> config_path = "/path/to/config.toml"
>>> run_task(dataset_path=dataset, task="Scan", config=config_path, db_user="my_user", db_password="secret")
```

The call performs the same steps as the CLI, loading configurations, preparing logging, and invoking Luigi.

References
----------
[^1]: https://luigi.readthedocs.io/en/stable/configuration.html#parameters-from-config-ingestion
"""

import copy
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from logging import Logger
from logging import getLogger
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from typing import Literal
from typing import Optional

import click
import tomlkit
from click_option_group import optgroup
from dotenv import dotenv_values

from romitask import PIPE_TOML
from romitask import SCAN_TOML
from romitask.log import LOG_LEVELS
from romitask.log import get_log_filename
from romitask.log import get_logger
from romitask.log import get_logging_config
from romitask.modules import DATA_CREATION_TASK
from romitask.modules import MODULES
from romitask.modules import NO_DATASET_TASK
from romitask.modules import TASKS
from romitask.task_defaults import update_config_with_defaults
from romitask.utils import get_version
from romitask.utils import parse_kbdi

LUIGI_CMD = "luigi"
HELP_URL = "https://docs.romi-project.eu/plant_imager/tutorials/basics/"
LOGGER_NAME = 'romi_run_task'

# Type aliases for readability
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def load_backup_scan_cfg(path: str | Path) -> dict:
    """Try to load a ``SCAN_TOML`` configuration from the given path.

    Parameters
    ----------
    path : str or pathlib.Path
        Where the ``SCAN_TOML`` configuration file should be.

    Returns
    -------
    dict
        The configuration dictionary, if loaded from a backup file.
    """
    scan_last_cfg = os.path.join(path, SCAN_TOML)
    bak_scan_config = {}
    with open(scan_last_cfg, "r", encoding="utf-8") as f:
        bak_scan_config = tomlkit.load(f)

    return bak_scan_config


def load_backup_pipe_cfg(dataset_path: Path, task: str, logger: Logger) -> dict:
    """Try to load a ``PIPE_TOML`` configuration from the given path.

    Parameters
    ----------
    dataset_path : pathlib.Path
        Where the ``PIPE_TOML`` configuration file should be.
    task : str
        Name of the task to perform.
    logger : logging.Logger
        The logger to use with this method.

    Returns
    -------
    dict
        The configuration dictionary, if loaded from a backup file.
    """
    bak_pipe_path = dataset_path / PIPE_TOML
    bak_pipe_config = {}
    if os.path.isfile(bak_pipe_path):
        # Raise an IOError when task 'Scan' is required in a folder with a backup of a processing pipeline
        # This probably means that you are trying to use a dataset that is NOT EMPTY!
        if "Scan" in task:
            logger.critical(f"Task '{task}' was called with dataset '{dataset_path}'!")
            logger.critical(f"It contains a processing pipeline configuration backup file!")
            sys.exit(f"Requested {task} task in non-empty folder, clean it up or change location!")
        with open(bak_pipe_path, "r", encoding="utf-8") as f:
            bak_pipe_config = tomlkit.load(f)

    return bak_pipe_config


def load_config_from_directory(path: str | Path, logger: Logger) -> dict:
    """Load the TOML & JSON configuration files from the given path.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to where the configuration file(s) should be.
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
            with open(f, "r", encoding="utf-8") as fp:
                c = tomlkit.load(fp)
            config.update(c)  # update the config with the new one
        except:
            logger.warning(f"Could not process TOML config file: {f}")
        else:
            logger.info(f"Loaded TOML configuration file: {f}")

    return config


def load_config_from_file(path: str | Path, logger: Logger) -> dict:
    """Load the TOML configuration file from the given path.

    Parameters
    ----------
    path : str or pathlib.Path
        The path to the configuration file to load.
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
        with open(path, "r", encoding="utf-8") as f:
            config = tomlkit.load(f)
    except:
        if not path.suffix == ".toml":
            logger.critical(f"Could not load TOML configuration file '{path}'!")
        else:
            logger.critical(f"Unsupported configuration file format, should be a TOML file, got '{path.name}'!")
    else:
        logger.info(f"Loaded TOML configuration file: {path}")

    return config


def get_task_module(task: str, logger: Logger, module: Optional[str] = None) -> str:
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


def create_backup_cfg(path: str | Path, cfgname: str, config: dict[str, dict[str, Any]]) -> str:
    """Create the backup configuration file used by luigi.

    Parameters
    ----------
    path : str or pathlib.Path
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
        # Number of times a task can fail within `disable_window` before the scheduler will automatically disable it.
        "retry_delay": 1,  # Number of seconds to wait after a task failure to mark it pending again.
        "disable_window": 3600,
        # Number of seconds during which `retry_count` failures must occur in order for an automatic disable by the scheduler.
    }

    # The following return codes are the recommended exit codes for Luigi.
    # They are in increasing level of severity (for most applications).
    # https://luigi.readthedocs.io/en/stable/configuration.html#retcode
    config["retcode"] = {"already_running": 10, "missing_data": 20,
                         "not_run": 25, "task_failed": 30,
                         "scheduling_error": 35, "unhandled_exception": 40}

    # Save the version number for each ROMI library:
    config["version"] = get_version()

    compat_cfg = copy.copy(config)
    for task_name, task_params in compat_cfg.items():
        # Convert any list or dict task parameter value to a string for compatibility:
        compat_cfg[task_name] = {param_name: str(param) if isinstance(param, (list, dict)) else param for param_name, param in task_params.items()}
        # Exclude `None` from the config
        compat_cfg[task_name] = {param_name: param for param_name, param in task_params.items() if param is not None}

    with open(file_path, 'w') as f:
        tomlkit.dump(compat_cfg, f)

    return file_path


def check_dataset_directory(path: Path, task: str, logger: Logger) -> str:
    """Check the dataset directory is correctly defined depending on the `task` to execute.

    Parameters
    ----------
    path : pathlib.Path
        The path to the dataset to check.
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
    If a "Scan" like task is required, a directory should be created to receive the created fileset.
    Else, the dataset directory should exist as an existing fileset will be processed.
    """
    if task == "ScannerToCenter":
        cfgname = SCAN_TOML
    elif task in DATA_CREATION_TASK:
        try:
            assert not path.is_dir()
        except AssertionError:
            logger.critical(f"Given dataset directory '{path}' exists and is not empty!")
            delete = parse_kbdi(input("Do you want ro remove the previous dataset? [y/N]"))
            if delete:
                shutil.rmtree(path)
            else:
                sys.exit("Non-empty dataset directory for data creation task.")
        cfgname = SCAN_TOML
    else:
        try:
            assert path.is_dir()
        except AssertionError:
            logger.critical(f"Could not find dataset directory '{path}'!")
            sys.exit("Non-existing dataset directory for processing task.")
        cfgname = PIPE_TOML
    return cfgname


def update_config(config: dict, update: dict) -> dict:
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
    for task_name, task_params in update.items():
        for tp_name, tp_value in task_params.items():
            try:
                if not config.get(task_name):
                    config[task_name] = {}
                config[task_name][tp_name] = tp_value
            except TypeError:
                print(f"Could not update '{task_name}.{tp_name}': {tp_value}")
                print(f"{config[task_name][tp_name]=}")
                raise
    return config


def run_task(dataset_path: str | Path,
             task: str,
             config: str | Path | dict,
             cfg_override: dict[str, Any] | None = None,
             **kwargs: Any) -> CompletedProcess[bytes]:
    """Load the configuration to use and call the luigi command to run the selected task.

    Parameters
    ----------
    dataset_path : pathlib.Path or str
        The path to the dataset directory.
    task : str
        The name of the task to execute by luigi.
    config : pathlib.Path or str or dict
        The configuration path or dictionary.
    cfg_override : dict, optional
        A configuration dictionary that defines tasks and parameters that override the values from `config`.

    Other Parameters
    ----------------
    logger : logging.Logger
        A logger to use with this method, default to the global logger named `LOGGER_NAME`.
    log_fname : str
        The log file name to use.
        Defaults to use the standardized log filename with the date and task name from `get_log_filename`.
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
    no_auth : bool
        Use a database with automatic 'admin' user login, for testing purposes only.
    db_user : str
        Username for FSDB login.
    db_password : str
        Password for FSDB login.

    See Also
    --------
    romitask.log.get_logging_config
    romitask.log.get_log_filename

    Examples
    --------
    >>> from pathlib import Path
    >>> from romitask.cli.romi_run_task import run_task
    >>> geom_pipe_real_conf = Path("configs/test_geom_pipe_real.toml").resolve()
    >>> real_plant_data = Path("tests/testdata/real_plant/").resolve()
    >>> process = run_task(real_plant_data, 'Clean', geom_pipe_real_conf, no_auth=True)
    >>> process = run_task(real_plant_data, 'PointCloud', geom_pipe_real_conf, no_auth=True)
    """
    logger = kwargs.get("logger", getLogger(LOGGER_NAME))
    log_level = kwargs.get("log_level", "INFO")
    luigicmd = kwargs.get("luigicmd", LUIGI_CMD)

    dataset_path = Path(dataset_path)
    # - Try to load PIPELINE backup TOML configuration:
    bak_pipe_config = load_backup_pipe_cfg(dataset_path, task, logger=logger)

    # - Process given PIPELINE configuration directory OR file, if any:
    if isinstance(config, dict):
        # Use directly the given config dictionary:
        logger.info("Loading configuration from dictionary.")
    elif os.path.isdir(config):
        # Load all config files from the given directory, if any, to a single config dictionary:
        config = load_config_from_directory(config, logger=logger)
    elif os.path.isfile(config):
        # Load config file to a config dictionary:
        config = load_config_from_file(config, logger=logger)
    elif config != "":
        logger.critical(f"Could not understand `config` option '{config}'!")
        sys.exit("Error with configuration file!")
    else:
        if not bak_pipe_config:
            config = {}
            logger.warning("Using full default configuration!")
        else:
            config = bak_pipe_config
            logger.info("Using a PREVIOUS pipeline configuration!")

    # Update the loaded config undefined task values with default task values from classes implementation
    config = update_config_with_defaults(config, MODULES)

    # - Look for "local" PIPELINE configuration file(s) to load:
    local_path = copy.copy(dataset_path)
    local_toml = sorted(local_path.glob('*.toml'), reverse=True)  # maintain resolution order, priority goes from first to last in alphabetical order
    local_toml = [f for f in local_toml if f.name != SCAN_TOML]  # exclude SCAN backup TOML config
    local_toml = [f for f in local_toml if f.name != PIPE_TOML]  # exclude PIPELINE backup TOML config
    # - Load the local configuration from detected file(s):
    if len(local_toml) > 0:
        local_config = {}
        logger.info(f"Found {len(local_toml)} local TOML configuration file{'s' if len(local_toml) > 1 else ''}!")
        for f in local_toml:
            local_config = update_config(local_config, load_config_from_file(str(f), logger=logger))
        if local_config != {}:
            logger.info(f"Got local definitions for: {list(local_config.keys())}")
            logger.debug(f"{local_config=}")
            # Update the given PIPELINE configuration with the local configuration:
            config = update_config(config, local_config)
            logger.info("Updated given configuration with local definitions!")

    # Apply CLI override (manual definition of parameters)
    if cfg_override:
        for task_override, param_override in cfg_override.items():
            config[task_override] = {**config.get(task_override, {}), **param_override}

    # - Set the name of the module to be loaded for the selected task:
    module = get_task_module(task, logger=logger, module=kwargs.get("module", None))
    # - Check the dataset directory is OK to use:
    cfgname = check_dataset_directory(dataset_path, task, logger=logger)

    with tempfile.TemporaryDirectory() as tmpd:
        # Get the log_file name, with the date & task name by default:
        log_fname = kwargs.get('log_fname', get_log_filename(task))
        logfile_path = os.path.join(tmpd, log_fname)
        # - Get logging configuration string for luigi, specifying the log file name :
        logging_config = get_logging_config(log_level=log_level, logfile_path=logfile_path)
        # - Create a "logging.cfg" file to be used by `luigi`:
        logging_file_path = os.path.join(tmpd, "logging.cfg")
        with open(logging_file_path, 'w') as f:
            f.write(logging_config)
        # - Create the "scan.toml" OR "pipeline.toml" (backup) config file used by luigi:
        cfg_file_path = create_backup_cfg(tmpd, cfgname, config)

        # - Define a custom environment variables dictionary
        # Get any value defined :
        env = dotenv_values(dataset_path / ".env")
        # Set the logging TOML file path to `luigi`:
        env.update({"LUIGI_CONFIG_PARSER": "toml",
                    "LUIGI_CONFIG_PATH": cfg_file_path,
                    "MPLBACKEND": "Agg"})
        # Set the default choice for PyOpenCL context:
        env.update({'PYOPENCL_CTX': '0'})
        # Set the database in "no authentication" mode
        if kwargs.get('no_auth'):
            # Enable the "no authentication" session manager if not forbidden
            # 1. by a 'ROMI_DB_NOAUTH' defined in as environment variable
            # 2. by a 'ROMI_DB_NOAUTH' defined in the dotenv file at the root of the DB
            env['ROMI_DB_NOAUTH'] = (os.getenv('ROMI_DB_NOAUTH') or env.get('ROMI_DB_NOAUTH', None)) or "1"
            if env['ROMI_DB_NOAUTH'] == "0":
                logger.error(f"Disabling authentication on this database if forbidden.")
                logger.info(f"Use `--db-user` and `--db-password` to pass your credentials to the CLI.")
                raise ValueError("Credentials required")
        # Add database credentials to environment if provided
        if kwargs.get('db_user') and kwargs.get('db_password'):
            env['ROMI_DB_USER'] = kwargs['db_user']
            env['ROMI_DB_PASSWORD'] = kwargs['db_password']

        # - Define the luigi command to run:
        # "--ScanConfiguration-scan args.dataset_path" set the value of `scan` for the `ScanConfiguration` Config class
        # https://luigi.readthedocs.io/en/stable/parameters.html#setting-parameter-value-for-other-classes
        cmd = [luigicmd, "--logging-conf-file", logging_file_path,
               "--module", module, task,
               "--ScanConfiguration-scan", dataset_path]
        if kwargs.get('local_scheduler', True):
            cmd.append("--local-scheduler")

        # - Print or Start the configured pipeline:
        if kwargs.get('dry_run', False):
            logger.info(f"Luigi command to call is:\n{' '.join(list(map(str, cmd)))}")
        else:
            t_start = time.time()
            logger.info(f"Running luigi command:\n{' '.join(list(map(str, cmd)))}")
            logger.debug(f"Using locally defined varenv: {env}")
            logger.debug(f"Using globally defined varenv: {os.environ}")

            # System‑wide variables (`os.environ`) overwrite any duplicate keys from the custom `env` dict
            # Use `check=False` to avoid raising on non‑zero exit; we will handle failures manually.
            p = subprocess.run(cmd, env={**env, **os.environ}, check=False)

            delta = timedelta(seconds=time.time() - t_start)
            delta = str(delta).split('.')[0]  # to get HH:MM:SS

            if p.returncode == 0:
                logger.info(f"Done in {delta}s!")
                # Move the temporary logging configuration and backup TOML file
                # to the actual dataset directory after the task has created it.
                # This must happen **after** the subprocess call because the
                # dataset directory is created by the task itself.
                try:
                    # Move logging.cfg
                    shutil.move(logfile_path, Path(dataset_path) / log_fname)
                    # Move the backup configuration file (scan.toml or pipeline.toml)
                    # Ensure the destination file is overwritten if it already exists.
                    dest_cfg_path = Path(dataset_path) / Path(cfg_file_path).name
                    if dest_cfg_path.exists():
                        try:
                            dest_cfg_path.unlink()  # Remove the existing file first
                        except Exception as e_unlink:
                            logger.error(f"Could not remove existing config file '{dest_cfg_path}': {e_unlink}")
                            raise
                    shutil.move(cfg_file_path, dest_cfg_path)
                except Exception as move_err:
                    logger.error(f"Failed to move temporary config files: {move_err}")
            else:
                logger.info(f"Failed after {delta}s!")
                failed_tmp_workdir = tmpd + "_failed"
                shutil.copytree(tmpd, failed_tmp_workdir, copy_function=shutil.copy2)
                logger.info(f"Moved failed temporary working directory to: {failed_tmp_workdir}")

    return p


@click.command(
    context_settings=dict(help_option_names=['-h', '--help']),
    help=f"Run a ROMI task on selected dataset.\n\n"
         f"The list of pre-defined tasks is: {', '.join(TASKS)}.\n\n"
         f"See {HELP_URL} for a detailed help with CLI."
)
@click.argument('task', type=str)
@click.argument('dataset_path', nargs=-1, type=str)
@click.option(
    '--config',
    default="",
    help="Pipeline configuration file (TOML) or directory. "
         "If a file, read the configuration from it. "
         "If a directory, read & concatenate all TOML configuration files in it. "
         "By default, search a 'pipeline.toml' file in the selected dataset directory."
)
@click.option(
    '--cfg',
    'cfg_override',
    default="",
    help="Override configuration file using specific parameters, e.g. \"Clean.keep_task='Masks'\"."
)
@click.option(
    '--module',
    default=None,
    help="Library and module of the task. "
         "Use it if not available or different than defined in `romitask.modules.MODULES`."
)
@click.option(
    '--log-level',
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    default='INFO',
    help="Level of message logging, defaults to 'INFO'."
)
@click.option(
    '--dry-run',
    is_flag=True,
    help="Use this to test the command-line by doing everything except calling the task(s)."
)
@optgroup.group('Authentication options')
@optgroup.option(
    '-u', '--user',
    'db_user',
    default=None,
    help="Username for FSDB login."
)
@optgroup.option(
    '-p', '--password',
    'db_password',
    default=None,
    help="Password for FSDB login."
)
@optgroup.option(
    '--no-auth',
    is_flag=True,
    help="Use a database with automatic 'admin' user log in, for testing purposes only."
)
@optgroup.group('Luigi options')
@optgroup.option(
    '--luigicmd',
    default=LUIGI_CMD,
    help=f"Luigi command, defaults to `{LUIGI_CMD}`."
)
@optgroup.option(
    '--local-scheduler',
    'local_scheduler',
    is_flag=True,
    default=True,
    help="Use the local luigi scheduler, defaults to `True`."
)
def main(
        task: str,
        dataset_path: tuple[str, ...],
        config: str,
        cfg_override: str,
        module: Optional[str],
        log_level: LogLevel,
        dry_run: bool,
        db_user: Optional[str],
        db_password: Optional[str],
        no_auth: bool,
        luigicmd: str,
        local_scheduler: bool
):
    """Main CLI entry point."""
    # - Configure a logger from this application:
    global logger
    logger = get_logger(LOGGER_NAME, log_level=log_level)

    # Convert dataset_path tuple to appropriate format
    if len(dataset_path) == 0:
        dataset_path = ''
    elif len(dataset_path) == 1:
        dataset_path = dataset_path[0]
    else:
        dataset_path = list(dataset_path)

    if task in DATA_CREATION_TASK:
        # These are "data creation modules", we thus require a single path to dataset...
        try:
            assert isinstance(dataset_path, str)
        except AssertionError:
            logger.critical(f"Task '{task}' requires the `dataset_path` to be a string.")
            logger.critical(f"Got '{dataset_path}'!")
            sys.exit(f"Error with input dataset path for '{task}' module!")
        else:
            folders = dataset_path
    else:
        # Other modules are "data processing modules", they can accept multiple path to dataset...
        if isinstance(dataset_path, str):
            # Process the input string `dataset_path` with ``glob``:
            #   - check existence of path:
            #   - may contain UNIX matching symbols (like '*' or '?'):
            folders = glob.glob(dataset_path)
            # Resolve path (make it absolute & normalize):
            folders = [Path(path).resolve() for path in folders]
            # Check that globed paths are directory (and exist, implied):
            folders = sorted([path for path in folders if path.is_dir()])
        elif isinstance(dataset_path, list):
            # Resolve path (make it absolute & normalize):
            folders = [Path(path).resolve() for path in dataset_path]
            # Check that listed paths are directory (and exist, implied):
            folders = sorted([path for path in folders if path.is_dir()])
        else:
            logger.critical(f"Can not understand input dataset path: '{dataset_path}'")
            sys.exit(f"Error with input dataset path for '{task}' module!")
        # If only one element in list, make it a plain str:
        if len(folders) == 1:
            folders = folders[0]

    def _dataset_path_error(dataset_path):
        logger.critical(f"Could not obtain a valid path from input dataset path: '{dataset_path}'!")
        sys.exit(f"Error with input dataset path for '{task}' module!")

    # Some tasks may accept to work without a dataset:
    if task not in NO_DATASET_TASK:
        # If a pathlib.Path instance, it should exist:
        if isinstance(folders, Path) and not folders.exists():
            _dataset_path_error(dataset_path)
        # If a list instance, it should not be empty:
        if isinstance(folders, list) and len(folders) == 0:
            _dataset_path_error(dataset_path)

    # Try to parse the cfg_override string or default to `None`
    if cfg_override:
        try:
            cfg_override = tomlkit.loads(cfg_override)
        except Exception as e:
            logger.critical(f"Could not parse a TOML config from '{cfg_override}': {e}")
            cfg_override = None
    else:
        cfg_override = None

    # Finally, we can call the main `run_task` method:
    if isinstance(folders, list):
        ## For each folder:
        dataset = [folder.name for folder in folders]
        logger.info(f"Got a list of {len(folders)} scan dataset to analyze: {', '.join(dataset)}")
        for dataset_path_item in folders:
            print("\n")  # to facilitate the search in the console by separating the datasets
            logger.info(f"Processing dataset '{Path(dataset_path_item).name}'.")
            try:
                run_task(dataset_path_item, task, config, cfg_override,
                         log_level=log_level, luigicmd=luigicmd, module=module,
                         local_scheduler=local_scheduler, dry_run=dry_run,
                         no_auth=no_auth, db_user=db_user, db_password=db_password)
            except Exception as e:
                print(e)
    else:
        ## For the folder:
        run_task(folders, task, config, cfg_override,
                 log_level=log_level, luigicmd=luigicmd, module=module,
                 local_scheduler=local_scheduler, dry_run=dry_run,
                 no_auth=no_auth, db_user=db_user, db_password=db_password)


if __name__ == '__main__':
    main()
