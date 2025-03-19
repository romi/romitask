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

"""Database Task Runner

A task execution manager that integrates Luigi task scheduling with database operations in the ROMI project, enabling automated processing of plant scans either individually or in batch mode.

Key Features
------------
- Database-aware task execution system
- Support for single or multiple task execution
- Batch processing capability for all scans in a database
- Automatic database connection management
- Luigi configuration integration
- Flexible task scheduling with local scheduler
- Logging functionality for execution tracking

Usage Examples
--------------
>>> from plantdb.commons.fsdb import FSDB
>>> from romitask.runner import DBRunner
>>> from romitask.task import DummyTask
>>> db = FSDB('path/to/database')
>>> task = DummyTask
>>> config = {'TaskName': {'param1': 'value1'}}
>>> runner = DBRunner(db, task, config)
>>>
>>> # Run on specific scan
>>> runner.run_scan('scan_001')
>>>
>>> # Run on all scans
>>> runner.run()
"""

import luigi

from romitask.log import get_logger

logger = get_logger(__name__)


class DBRunner(object):
    """A class for executing Luigi tasks on a plant database.

    This class provides functionality to run one or more Luigi tasks either on a single scan
    or all scans in a plant database. It handles database connections and Luigi configuration
    management.

    Attributes
    ----------
    db : plantdb.db.DB
        The database instance being used.
    tasks : list of RomiTask
        List of task classes to be executed.

    Examples
    --------
    >>> from plantdb.commons.fsdb import FSDB
    >>> from romitask.runner import DBRunner
    >>> from romitask.task import DummyTask
    >>> db = FSDB('path/to/database')
    >>> task = DummyTask
    >>> config = {'TaskName': {'param1': 'value1'}}
    >>> runner = DBRunner(db, task, config)
    >>>
    >>> # Run on specific scan
    >>> runner.run_scan('scan_001')
    >>>
    >>> # Run on all scans
    >>> runner.run()
    """

    def __init__(self, db, tasks, config):
        """Initialize the runner with a database, tasks, and configuration.

        Parameters
        ----------
        db : plantdb.db.DB
            The target database instance to run tasks on.
        tasks : RomiTask or list of RomiTask
            Single task or list of tasks to execute. Each task must be a Luigi task class
            (not instantiated).
        config : dict
            Luigi configuration dictionary containing task-specific settings.
        """
        if not isinstance(tasks, (list, tuple)):
            tasks = [tasks]
        self.db = db
        self.tasks = tasks
        luigi_config = luigi.configuration.get_config()
        luigi_config.read_dict(config)

    def _run_scan_connected(self, scan):
        """Execute tasks on a single scan in the database.

        Parameters
        ----------
        scan : plantdb.db.Scan
            The scan instance to process.

        Notes
        -----
        This is an internal method that:
        1. Sets up Luigi database configuration
        2. Instantiates task objects
        3. Executes tasks using Luigi's build function

        The method assumes the database is already connected.
        """
        db_config = {}
        db_config['worker'] = {
            "no_install_shutdown_handler": True,
        }
        db_config['DatabaseConfig'] = {
            'db': self.db,
            'scan_id': scan,
        }
        luigi_config = luigi.configuration.get_config()
        luigi_config.read_dict(db_config)
        tasks = [t() for t in self.tasks]
        luigi.build(tasks=tasks,
                    local_scheduler=True)
        return

    def run_scan(self, scan_id):
        """Execute tasks on a single scan in the database.

        Parameters
        ----------
        scan_id : str
            Identifier of the scan to process.

        Notes
        -----
        This method:
        1. Establishes database connection
        2. Retrieves the specified scan
        3. Executes tasks on the scan
        4. Closes the database connection
        """
        self.db.connect()
        scan = self.db.get_scan(scan_id)
        self._run_scan_connected(scan)
        self.db.disconnect()
        return

    def run(self):
        """Execute tasks on all scans in the database.

        This method iterates through all scans in the database and executes
        the configured tasks on each scan sequentially.

        Notes
        -----
        This method:
        1. Establishes database connection
        2. Iterates through all scans
        3. Executes tasks on each scan
        4. Closes the database connection

        The process is logged, with scan IDs printed to the info log level.
        """
        self.db.connect()
        for scan in self.db.get_scans():
            logger.info(f"scan = {scan.id}")
            self._run_scan_connected(scan)
        logger.info("Done")
        self.db.disconnect()
        return
