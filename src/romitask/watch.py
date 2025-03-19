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

"""FSDB Watch Module

A monitoring system for plant database operations that automatically executes Luigi tasks when new scans are added.
This module enables real-time processing of plant data by watching file system events.

Key Features
------------
- Monitors filesystem events in a plant database directory
- Automatically triggers task execution when new scans are detected
- Handles database busy states and connection management
- Supports running multiple Luigi tasks sequentially
- Provides event handling for filesystem changes

Usage Examples
--------------
>>> from romitask.watch import FSDBWatch
>>> from plantdb.commons.fsdb import FSDB
>>> from my_tasks import ProcessingTask

>>> # Initialize database and watch
>>> db = FSDB('/path/to/database')
>>> config = {'ProcessingTask': {'param': 'value'}}
>>> watch = FSDBWatch(db, ProcessingTask, config)

>>> # Start monitoring
>>> watch.start()

"""

import time

from plantdb.db import DBBusyError
from watchdog.events import DirCreatedEvent
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from romitask.runner import DBRunner


class FSDBWatcher():
    """File system database watcher that monitors changes and triggers tasks.

    A watcher class that monitors a FSDB (File System Database) for changes and
    executes specified tasks when changes are detected. Uses the watchdog library
    to monitor filesystem events.

    Parameters
    ----------
    db : plantdb.fsdb.FSDB
        The target database instance to monitor for changes.
    tasks : list of RomiTask
        List of tasks to execute when changes are detected in the database.
    config : dict
        Configuration dictionary for the tasks. Contains settings and parameters
        for task execution.

    Attributes
    ----------
    observer : watchdog.observers.Observer
        Watchdog observer instance that monitors the filesystem.

    Notes
    -----
    The watcher only monitors the base directory of the database and does not
    watch subdirectories (recursive=False).

    Examples
    --------
    >>> from plantdb.fsdb import FSDB
    >>> db = FSDB("path/to/database")
    >>> tasks = [MyTask1(), MyTask2()]
    >>> config = {"param1": "value1", "param2": "value2"}
    >>> watcher = FSDBWatcher(db, tasks, config)
    >>> watcher.start()  # Start monitoring
    >>> # ... do some work ...
    >>> watcher.stop()   # Stop monitoring
    >>> watcher.join()   # Wait for the observer to terminate

    See Also
    --------
    FSDBEventHandler : Handles the actual filesystem events
    watchdog.observers.Observer : The underlying observer class
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
        """Start the filesystem observer.

        Begins monitoring the database directory for changes.

        Notes
        -----
        This method is non-blocking. The observer runs in a separate thread.
        """
        self.observer.start()

    def stop(self):
        """Stop the filesystem observer.

        Stops monitoring the database directory for changes.

        Notes
        -----
        This method does not wait for the observer thread to terminate.
        Use `join()` to ensure complete termination.
        """
        self.observer.stop()

    def join(self):
        """Wait for the observer to terminate.

        Blocks until the observer thread has completely terminated.

        Notes
        -----
        This method should be called after `stop()` to ensure proper shutdown.
        """
        self.observer.join()


class FSDBEventHandler(FileSystemEventHandler):
    """File system event handler for monitoring and processing database changes.

    This class extends FileSystemEventHandler to watch for directory creation events
    and trigger processing tasks on a plant database. It manages the execution of
    database tasks while handling database busy states through retries.

    Attributes
    ----------
    runner : romitask.runner.DBRunner
        The database runner instance that executes the processing tasks.
    running : bool
        Flag indicating whether tasks are currently being executed.

    Raises
    ------
    DBBusyError
        When the database is locked or busy during task execution.

    Notes
    -----
    - Only responds to directory creation events, ignoring all other file system events
    - Implements automatic retry mechanism when database is busy
    - Inherits from watchdog.events.FileSystemEventHandler

    Examples
    --------
    >>> from plantdb.fsdb import FSDB
    >>> from romitask.task import DummyTask
    >>>
    >>> # Create database and handler
    >>> db = FSDB("/path/to/db")
    >>> tasks = [DummyTask]
    >>> config = {"DummyTask": {"param": "value"}}
    >>>
    >>> # Initialize handler
    >>> handler = FSDBEventHandler(db, tasks, config)
    >>>
    >>> # Add to watchdog observer
    >>> from watchdog.observers import Observer
    >>> observer = Observer()
    >>> observer.schedule(handler, "/path/to/watch", recursive=False)
    >>> observer.start()

    See Also
    --------
    DBRunner : The task execution engine used by this handler
    FileSystemEventHandler : Base class for file system event handlers
    """

    def __init__(self, db, tasks, config):
        """Initialize the event handler with a database, tasks, and configuration.

        Parameters
        ----------
        db : plantdb.fsdb.FSDB
            The target plant database to monitor and process.
        tasks : list of RomiTask
            List of processing tasks to execute when changes are detected.
        config : dict
            Configuration dictionary for task parameters and settings.
        """
        self.runner = DBRunner(db, tasks, config)
        self.running = False

    def on_created(self, event):
        """Run tasks on the database when a new directory is created.

        This method handles directory creation events by executing database tasks through
        the associated runner. If the database is busy, it implements a retry mechanism
        with a 1-second delay between attempts.

        Parameters
        ----------
        self : FSDBEventHandler
            The instance of the event handler.
        event : watchdog.events.DirCreatedEvent
            The file system event object containing information about the created directory.

        Returns
        -------
        None
            Returns early if the event is not a DirCreatedEvent.

        Raises
        ------
        DBBusyError
            Caught internally when database is locked or busy. Method will retry until successful.

        Notes
        -----
        - Only processes DirCreatedEvent events, all other event types are ignored
        - Implements an infinite retry loop when database is busy
        - Sets self.running to False upon successful completion

        Examples
        --------
        >>> handler = FSDBEventHandler(db, tasks, config)
        >>> event = DirCreatedEvent("/path/to/new/directory")
        >>> handler.on_created(event)  # Will execute tasks or wait if DB is busy

        """
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
