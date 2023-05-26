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

import time

from plantdb.db import DBBusyError
from watchdog.events import DirCreatedEvent
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from romitask.runner import DBRunner


class FSDBWatcher():
    """Watch changes on a FSDB database and launch a task when it does.

    Attributes
    ----------
    observer : watchdog.observers.Observer
        Watchdog observer for the filesystem.
    """

    def __init__(self, db, tasks, config):
        """Class constructor.

        Parameters
        ----------
        db : plantdb.fsdb.FSDB
            The target database.
        tasks : list of RomiTask
            The list of tasks to do on change.
        config : dict
            Configuration for the task.
        """
        self.observer = Observer()
        handler = FSDBEventHandler(db, tasks, config)
        self.observer.schedule(handler, db.basedir, recursive=False)

    def start(self):
        """Start the observer."""
        self.observer.start()

    def stop(self):
        """Stop the observer."""
        self.observer.stop()

    def join(self):
        """Wait until the observer terminates."""
        self.observer.join()


class FSDBEventHandler(FileSystemEventHandler):
    """Event handler for FSDB.

    Attributes
    ----------
    runner : romitask.runner.DBRunner
        The runner to handle.
    running : bool
        Indicate if the `runner` is running or not.
    """

    def __init__(self, db, tasks, config):
        """Class constructor.

        Parameters
        ----------
        db : plantdb.fsdb.FSDB
            The target database.
        tasks : list of RomiTask
            The list of tasks to do on change.
        config : dict
            Configuration for the task.
        """
        self.runner = DBRunner(db, tasks, config)
        self.running = False

    def on_created(self, event):
        """Run tasks on the database when it becomes available, if a new folder has been created (new scan)."""
        if not isinstance(event, DirCreatedEvent):
            return
        while True:
            try:
                self.runner.run()
                self.running = False
                return
            except DBBusyError:
                print("DB Busy, waiting for it to be available...")
                time.sleep(1)
                continue
