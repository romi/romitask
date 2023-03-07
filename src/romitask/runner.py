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

import luigi

from romitask.log import configure_logger

logger = configure_logger(__name__)


class DBRunner(object):
    """Class for running a given (list of) task(s) on a database using luigi.

    Attributes
    ----------
    db : plantdb.db.DB
        Target database.
    task : list of RomiTask
        The list of task to run.
    """

    def __init__(self, db, tasks, config):
        """
        Parameters
        ----------
        db : plantdb.db.DB
            Target database to use to run the task.
        tasks : RomiTask or list of RomiTask
            Task or list of task to run.
        config : dict
            Luigi configuration for tasks.
        """
        if not isinstance(tasks, (list, tuple)):
            tasks = [tasks]
        self.db = db
        self.tasks = tasks
        luigi_config = luigi.configuration.get_config()
        luigi_config.read_dict(config)

    def _run_scan_connected(self, scan):
        db_config = {}
        db_config['worker'] = {
            "no_install_shutdown_handler": True
        }
        db_config['DatabaseConfig'] = {
            'db': self.db,
            'scan_id': scan
        }
        luigi_config = luigi.configuration.get_config()
        luigi_config.read_dict(db_config)
        tasks = [t() for t in self.tasks]
        luigi.build(tasks=tasks,
                    local_scheduler=True)
        return

    def run_scan(self, scan_id):
        """Run the task(s) on a single scan.

        Parameters
        ----------
        scan_id : str
            Id of the scan to process.
        """
        self.db.connect()
        scan = self.db.get_scan(scan_id)
        self._run_scan_connected(scan)
        self.db.disconnect()
        return

    def run(self):
        """Run the task(s) on all scans in the DB."""
        self.db.connect()
        for scan in self.db.get_scans():
            logger.info(f"scan = {scan.id}")
            self._run_scan_connected(scan)
        logger.info("Done")
        self.db.disconnect()
        return
