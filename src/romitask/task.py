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

"""Task Management System for ROMI Project

A comprehensive task management framework that provides base classes and utilities for defining, executing, and managing data processing tasks in the ROMI (RObot for MIcrofarm) project.
This module implements a dependency-aware task system with database integration for managing plant imaging and analysis workflows.

Key Features
------------
- Task dependency management through upstream task declarations
- File and dataset existence verification
- Database-integrated file management system
- Parameter handling with serialization support
- Task hierarchy support with base classes for:
    * Generic tasks (RomiTask)
    * File processing tasks (FileByFileTask)
    * Dataset verification tasks
    * File existence checking
- Clean-up utilities for managing task outputs
- Virtual plant object handling
- Error handling and failure management

Usage Examples
--------------
>>> # Creating a simple task
>>> class MyProcessingTask(RomiTask):
...     upstream_task = "PreviousTask"
...
...     def requires(self):
...         return {"previous": self.upstream_task()}
...
...     def run(self):
...         # Task implementation
...         pass

>>> # Using the file management system
>>> class MyFileTask(FileByFileTask):
...     query = "SELECT * FROM files"
...     type = "process"
...
...     def f(self, file):
...         # Process individual file
...         return processed_data
"""

import glob
import json
import os.path
from json import JSONDecodeError
from pathlib import Path
from shutil import rmtree

import luigi
from tqdm import tqdm

from romitask.log import get_logger

logger = get_logger(__name__)
db = None


class ScanParameter(luigi.Parameter):
    """Register a ``luigi.Parameter`` object to access `plantdb.fsdb.Scan` class.

    Override the default implementation methods ``parse`` & ``serialize``.

    Notes
    -----
    The ``parse`` method connect to the given path to a ``plantdb.fsdb.FSDB`` database.
    """

    def parse(self, scan_path):
        """Convert the scan path to a ``plantdb.fsdb.Scan`` object.

        Override the default implementation method for specialized parsing.

        Parameters
        ----------
        scan_path : str
            The value to parse, here the path to an ``plantdb.fsdb.Scan`` dataset.

        Returns
        -------
        plantdb.fsdb.Scan
            The object corresponding to given path.

        Notes
        -----
        Uses given path, e.g. ``/db/root/path/scan_id``, to defines:
          - the database root dir with ``/db/root/path``
          - the scan dataset id with ``scan_id``

        If the given scan dataset id does not exist, it is created.
        """
        from plantdb import FSDB
        global db
        path = scan_path.rstrip('/')
        path = path.split('/')
        # Defines the database root dir
        db_path = '/'.join(path[:-1])
        # Defines the scan dataset id
        scan_id = path[-1]
        # create & connect to `db` if not defined:
        if db is None:  # TODO: cannot change DB during run...
            db = FSDB(db_path)
            db.connect()
        # Get the scan dataset object or create one & return it
        scan = db.get_scan(scan_id)
        if scan is None:
            scan = db.create_scan(scan_id)
        return scan

    def serialize(self, scan):
        """Converts ``plantdb.fsdb.Scan`` in its path.

        Opposite of ``parse()``.

        Parameters
        ----------
        scan : plantdb.fsdb.Scan
            The value to serialize, here a ``plantdb.fsdb.Scan`` object.

        Returns
        -------
        str
            The path to the corresponding ``plantdb.fsdb.Scan`` object.
        """
        db_path = scan.db.basedir
        scan_id = scan.id
        return str(db_path / scan_id)


class DatabaseConfig(luigi.Config):
    """Configuration for a ``plantdb.FSBD`` database.

    Attributes
    ----------
    scan : plantdb.fsdb.Scan
        The scan dataset to use for configuration.

    Examples
    --------
    >>> from romitask.task import DatabaseConfig
    >>> from plantdb import FSDB
    >>> from plantdb.fsdb import dummy_db
    >>> # - First, let's create a dummy FSDB database to play with:
    >>> db = dummy_db()
    >>> db.connect()
    >>> scan = db.create_scan("007")  # Add a `Scan` named `007` to the `FSDB` instance
    >>> db_cfg = DatabaseConfig(scan=scan)

    """
    scan = ScanParameter()


class FilesetTarget(luigi.Target):
    """Subclass ``luigi.Target`` for ``Fileset`` as defined in romitask ``plantdb.fsdb.FSDB`` API.

    A ``FilesetTarget`` is used by ``luigi.Task`` (or subclass) methods:
     * ``requires`` to assert the existence of the ``Fileset`` prior to starting the task;
     * ``output`` to create a ``Fileset`` after running a task.

    Attributes
    ----------
    db : plantdb.fsdb.FSDB
        An ``FSDB`` database instance.
    scan : plantdb.fsdb.Scan
        A ``Scan`` dataset instance within ``db``.
    fileset_id : str
        Name of the target ``Fileset`` instance within ``scan``.

    Notes
    -----
    A luigi ``Target`` subclass requires to implement the ``exists`` method.

    Examples
    --------
    >>> from romitask.task import FilesetTarget
    >>> from plantdb import FSDB
    >>> from plantdb.fsdb import dummy_db
    >>> # - First, let's create a dummy FSDB database to play with:
    >>> db = dummy_db()
    >>> db.connect()
    >>> scan = db.create_scan("007")  # Add a `Scan` named `007` to the `FSDB` instance
    >>> fs = scan.create_fileset("required_fs")  # Add a `Fileset` named `required_fs` to the `Scan` instance

    >>> # - Now let's use `FilesetTarget` to check if a given `Fileset` exists in the FSDB (as used in Tasks `require` methods):
    >>> fst = FilesetTarget(scan, "required_fs")
    >>> fst.exists()  # `Fileset` exist but is empty
    False

    >>> # - Add a dummy test file to the `Fileset`:
    >>> fs.create_file('dummy_test_file')
    >>> fst.exists()  # `Fileset` exist and is not empty
    True

    >>> # - Now let's use `FilesetTarget` to create a new `Fileset` (as used in Tasks `output` methods):
    >>> out_fst = FilesetTarget(scan, "output_fs")
    >>> out_fs = out_fst.create()
    >>> type(out_fs)
    plantdb.fsdb.Fileset
    >>> print(out_fs.id)
    'output_fs'

    """

    def __init__(self, scan, fileset_id):
        """FilesetTarget constructor.

        Parameters
        ----------
        scan : plantdb.fsdb.Scan
            The ``Scan`` dataset instance where to find/create the ``Fileset``.
        fileset_id : str
            Name of the target ``Fileset``.

        """
        self.db = scan.db
        self.scan = scan
        self.fileset_id = fileset_id

    def create(self):
        """Creates a ``Fileset`` using the ``plantdb`` FSDB API.

        The name of the created ``Fileset`` is given by ``self.fileset_id``.

        Returns
        -------
        plantdb.fsdb.Fileset
            The created `Fileset` instance.
        """
        return self.scan.create_fileset(self.fileset_id)

    def exists(self):
        """Assert the target ``Fileset`` exists.

        A target exists if the associated fileset exists and is not empty.

        Returns
        -------
        bool
            ``True`` if the target exists, else ``False``.
        """
        fs = self.scan.get_fileset(self.fileset_id)
        return fs is not None and len(fs.get_files()) > 0

    def get(self, create=True):
        """Returns the target ``Fileset`` instance, can be created.

        Parameters
        ----------
        create : bool, optional
            If ``True`` (default), create the fileset if it does not exist in the database.

        Returns
        -------
        plantdb.fsdb.Fileset
            The fetched/created ``Fileset`` instance.
        """
        return self.scan.get_fileset(self.fileset_id, create=create)


class RomiTask(luigi.Task):
    """ROMI implementation of a ``luigi.Task``, working with the ``plantdb.db.DB`` API.

    Attributes
    ----------
    upstream_task : luigi.TaskParameter
        The upstream task.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) to use to get, or create, the ``FilesetTarget``.
        If unspecified (default), the current active scan will be used.

    Notes
    -----
    The task parameters are exported automatically as fileset metadata.

    The task name is also exported automatically as fileset metadata, under a 'task_name' entry.
    """
    upstream_task = luigi.TaskParameter()
    scan_id = luigi.Parameter(default="")

    def requires(self):
        """Specify dependencies to other Task object.

        This method will be overridden by the classes inheriting ``RomiTask``.

        Returns
        -------
        luigi.TaskParameter
            The upstream task.
        """
        return self.upstream_task()

    def output(self):
        """Defines the returned ``Target``, for a ``RomiTask`` it is a ``FileSetTarget``.

        The fileset ID being the task ID.

        Returns
        -------
        FilesetTarget
            A set of file(s) in the ???

        Notes
        -----
        The task parameters are exported automatically as fileset metadata, under a 'task_params' entry.

        The task name is also exported automatically as fileset metadata, under a 'task_name' entry.
        """
        # Get the `Fileset` id from the `task_id` attribute generated by `luigi.Task`
        # Can be overriding in inheriting class as for the `Visualization` task
        # This will be used as DIRECTORY NAME!
        fileset_id = self.task_id
        if self.scan_id == "":
            t = FilesetTarget(DatabaseConfig().scan, fileset_id)
        else:
            t = FilesetTarget(db.get_scan(self.scan_id), fileset_id)
        fs = t.get()  # get the fileset
        # Export all the task parameters as a dictionary:
        params = dict(self.to_str_params(only_significant=False, only_public=False))
        # Try to fix empty "scan_id":
        if params["scan_id"] == "":
            params["scan_id"] = fs.get_scan().get_id()
        # Check if it needs JSON parsing:
        for k in params.keys():
            try:
                params[k] = json.loads(params[k])
            except KeyError:
                continue
            except JSONDecodeError:
                continue
        # Save the task parameter as fileset metadata under "task_params":
        fs.set_metadata("task_params", params)
        # Save the task name as fileset metadata under "task_name":
        fs.set_metadata("task_name", self.get_task_name())
        return t

    def input_file(self, file_id=None, suffix=None):
        """Helper method to get a file from the input fileset.

        Parameters
        ----------
        file_id : str, optional
            Name of the input file. Defaults to ``None``.
        suffix : str, optional
            A suffix of the input file name. Defaults to ``None``.

        Returns
        -------
        plantdb.db.File
            The input file.
        """
        return self.pose_task().output_file(file_id, suffix=suffix, create=False)

    def output_file(self, file_id=None, suffix=None, create=True):
        """Helper method to create & get a file from the output fileset.

        Parameters
        ----------
        file_id : str, optional
            Name of the output file. Defaults to ``None``.
        suffix : str, optional
            Add a suffix to the output file name. Defaults to ``None``.
        create : bool, optional
            Define if the output file should be created. Defaults to ``True``

        Returns
        -------
        plantdb.db.File
            The (created) output file.
        """
        if file_id is None:
            file_id = self.get_task_name()
        if suffix is not None:
            file_id += suffix
        return self.output().get().get_file(file_id, create)

    def get_task_name(self):
        """Helper method to get the name of the current task.

        Returns
        -------
        str
            The name of the current task.
        """
        return self.get_task_family().split('.')[-1]


class DatasetExists(RomiTask):
    """A task that require a given dataset id (scan name) to exist.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter
        The dataset id (scan name) that should exist.

    See Also
    --------
    romitask.task.RomiTask
    """
    upstream_task = None  # override default attribute from ``RomiTask``
    scan_id = luigi.Parameter()

    def requires(self):
        """Require nothing."""
        return []

    def output(self):
        """Returns nothing."""
        return None

    def complete(self):
        """Indicate the task as complete."""
        return False  # there is no output

    def run(self):
        """Check the dataset exist.

        Raises
        ------
        OSError
            If the `scan_id` does not exist.
        """
        db = DatabaseConfig().scan.db
        if db.get_scan(self.scan_id) is None:
            raise OSError(f"Scan {self.scan_id} does not exist!")
        return


class FilesetExists(RomiTask):
    """A task that require a given fileset id to exist.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) where to get the ``Fileset``.
    fileset_id : luigi.Parameter
        The name of the fileset that should exist.

    See Also
    --------
    romitask.task.RomiTask
    """
    upstream_task = None  # override default attribute from ``RomiTask``
    fileset_id = luigi.Parameter()

    def requires(self):
        """Require nothing."""
        return []

    def output(self):
        """The output of the task is the fileset."""
        self.task_id = self.fileset_id  # name the task using the fileset
        return super().output()

    def run(self):
        """Check the fileset exist.

        Raises
        ------
        OSError
            If the `fileset_id` does not exist.
        """
        if self.output().get() is None:
            raise OSError(f"Fileset {self.fileset_id} does not exist!")
        return


class ImagesFilesetExists(FilesetExists):
    """Task to assert the presence of a fileset containing the *images*.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) where to get the ``Fileset``.
    fileset_id : luigi.Parameter
        Name of the fileset containing the images.
        Defaults to `'images'`.
    """
    fileset_id = luigi.Parameter(default="images")


class ModelFilesetExists(FilesetExists):
    """Task to assert the presence of a fileset containing the *trained weight model* for CNN prediction.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) where to get the ``Fileset``.
    fileset_id : luigi.Parameter
        Name of the fileset containing the trained weight model.
        Defaults to `'models'`.
    """
    fileset_id = luigi.Parameter(default="models")


class Segmentation2DGroundTruthFilesetExists(FilesetExists):
    """Task to assert the presence of a fileset containing the *ground-truth images* for CNN training.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) where to get the ``Fileset``.
    fileset_id : luigi.Parameter
        Name of the fileset containing the ground-truth images.
        Defaults to `'Segmentation2DGroundTruth'`.
    """
    fileset_id = luigi.Parameter(default="Segmentation2DGroundTruth")


class FileExists(RomiTask):
    """A task that require a given file id to exist.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The dataset id (scan name) where to get the ``Fileset``.
    fileset_id : luigi.Parameter
        Name of the fileset where to find the file.
    file_id : luigi.Parameter
        Name of the file that should exist.

    See Also
    --------
    romitask.task.RomiTask
    """
    upstream_task = None  # override default attribute from ``RomiTask``
    fileset_id = luigi.Parameter()
    file_id = luigi.Parameter()

    def requires(self):
        """Require nothing."""
        return []

    def output(self):
        """The output of the task is the fileset."""
        self.task_id = self.fileset_id  # name the task using the fileset
        return super().output()

    def output_file(self, file_id=None, create=False):
        """The output file should exist."""
        if file_id is None:
            file_id = self.file_id
        return super().output_file(file_id, create=False)

    def run(self):
        """Check the fileset and files exist.

        Raises
        ------
        OSError
            If the `fileset_id` does not exist.
        OSError
            If the `file_id` does not exist.
        """
        if self.output().get() is None:
            raise OSError(f"Fileset {self.fileset_id} does not exist")
        if self.output().get().get_file(self.file_id) is None:
            raise OSError(f"File {self.fileset_id}/{self.file_id} does not exist")
        return


class VirtualPlantObj(FileExists):
    """The VirtualPlantObj task returns a 3D plant model file.

    The 3D model should be stored as '.obj' and '.mtl' files.

    Use as follows, using ``VirtualScan`` as an example:

    .. code-block::

        [VirtualScan]
        obj_fileset = "VirtualPlantObj"

    This example will seek for the default file with ID VirtualPlant in the fileset
    VirtualPlant in the active scan directory.

    These default values can be overriden as follows:

    .. code-block::

        [VirtualPlantObj]
        scan_id = "AnotherScan"
        fileset_id = "AnotherFileset"
        fileset_id_prefix = "AnotherFilesetPrefix"
        file_id = "FileID"

        [VirtualScan]
        obj_fileset = "VirtualPlantObj"

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id: luigi.Parameter, optional
        The scan id where to look for the fileset.
        If unspecified (default), the current active scan will be used.
    fileset_id: luigi.Parameter, optional
        The ID of the fileset to use.
        Defaults to "VirtualPlant".
    fileset_id_prefix: luigi.Parameter, optional
        If the ID of the fileset cannot be provided, a prefix can be an alternative to search for a fileset id.
        Defaults to "VirtualPlant".
    file_id : luigi.Parameter, optional
        The ID of the file to use.
        Defaults to "VirtualPlant".

    """
    scan_id = luigi.Parameter(default="")
    fileset_id = luigi.Parameter(default="VirtualPlant")
    fileset_id_prefix = luigi.Parameter(default="VirtualPlant")
    file_id = luigi.Parameter(default="VirtualPlant")

    def output(self):
        """Return the fileset containing the model files."""
        if self.scan_id == "":
            scan = DatabaseConfig().scan
        else:
            scan = db.get_scan(self.scan_id)

        t = FilesetTarget(scan, self.fileset_id)
        if not t.exists():  # backup solution : search for a fileset id beginning with a specific prefix
            filesets_with_prefix = [f for f in scan.get_filesets() if f.id.startswith(self.fileset_id_prefix)]
            if len(filesets_with_prefix) == 0:
                raise FileNotFoundError(f"Fileset with {self.fileset_id_prefix} prefix does not exist")
            elif len(filesets_with_prefix) > 1:
                raise ValueError(f"Two or more Filesets with {self.fileset_id_prefix} prefix found")
            else:
                self.fileset_id = filesets_with_prefix[0].id
                t = FilesetTarget(scan, self.fileset_id)

        fs = t.get()

        params = dict(self.to_str_params(only_significant=False, only_public=False))
        for k in params.keys():
            try:
                params[k] = json.loads(params[k])
            except KeyError:
                continue
            except JSONDecodeError:
                continue
        fs.set_metadata("task_params", params)

        self.task_id = self.fileset_id
        return t


class FileByFileTask(RomiTask):
    """Abstract task to sequentially apply a function to each ``File`` of a ``Fileset``.

    Attributes
    ----------
    upstream_task : luigi.TaskParameter
        The upstream task.
    scan_id : luigi.Parameter, optional
        The scan id to use to get or create the ``FilesetTarget``.
        If unspecified (default), the current active scan will be used.
    query : luigi.DictParameter, optional
        A filtering dictionary to apply on input ```Fileset`` metadata.
        Key(s) and value(s) must be found in metadata to select the ``File``.
        By default, no filtering is performed, all inputs are used.
    type : None
        ???
    reader : None
        ???
    writer : None
        ???

    Notes
    -----
    Input `File`s metadata are copied to the target/output `File`s metadata.

    """
    query = luigi.DictParameter(default={})
    type = None  # ???
    reader = None  # ???
    writer = None  # ???

    def f(self, f, outfs):
        """Function applied to every file in the fileset must return a file object.

        Parameters
        ----------
        f: plantdb.fsdb.FSDB.File
            Input file.
        outfs: plantdb.fsdb.FSDB.Fileset
            Output fileset.

        Returns
        -------
        plantdb.fsdb.FSDB.File
            Tis file must be created in `outfs`.
        """
        raise NotImplementedError

    def run(self):
        """Run the task on every `File`s from a `Fileset` that fulfill the ``query``."""
        input_fileset = self.input().get()
        output_fileset = self.output().get()

        in_files = input_fileset.get_files(query=self.query)
        logger.debug(f"Got {len(in_files)} input files:")
        logger.debug(f"{', '.join([f.id for f in in_files])}")
        logger.debug(f"Got a filtering query: '{self.query}'.")

        for fi in tqdm(in_files, unit="file"):
            outfi = self.f(fi, output_fileset)
            if outfi is not None:
                m = fi.get_metadata()
                outm = outfi.get_metadata()
                outfi.set_metadata({**m, **outm})
        return


@RomiTask.event_handler(luigi.Event.FAILURE)
def mourn_failure(task, exception):
    """In the case of failure of a task, remove the corresponding fileset from the database.

    Parameters
    ----------
    task : RomiTask
        The task which has failed.
    exception : Exception
        The exception raised by the failure.
    """
    # Log the failure:
    logger.critical(exception)
    # Delete the task fileset:
    # output_fileset = task.output().get()
    # scan = task.output().get().scan
    # scan.delete_fileset(output_fileset.id)


class DummyTask(RomiTask):
    """A dummy task.

    Does nothing and requires nothing.

    Attributes
    ----------
    upstream_task : None
        No upstream task is required.
    scan_id : luigi.Parameter, optional
        The scan id to use to get or create the ``FilesetTarget``.

    See Also
    --------
    romitask.task.RomiTask
    """
    upstream_task = None  # override from RomiTask

    def requires(self):
        """Require nothing."""
        return []

    def run(self):
        """Do nothing."""
        return


#: List of original image metadata (to keep in Clean task):
#: * "pose" is added by the PlantImager or VirtualPlantImager
#: * "approximate_pose" is added by the PlantImager
#: * "channel" is added by the PlantImager or VirtualPlantImager
#: * "shot_id" is added by the PlantImager or VirtualPlantImager
#: * "camera" is added by the VirtualPlantImager and is used by `Voxels`
IMAGES_MD = ["pose", "approximate_pose", "channel", "shot_id", "camera"]


class Clean(RomiTask):
    """Cleanup a scan, keeping only the "images" fileset and removing all computed pipelines.

    Attributes
    ----------
    upstream_task : luigi.TaskParameter
        The upstream task.
    scan_id : luigi.Parameter, optional
        The scan id to use to get or create the ``FilesetTarget``.
    no_confirm : luigi.BoolParameter
        Do not ask for confirmation of the cleaning in the command prompt.
        Default to ``False``.
    keep_metadata : luigi.ListParameter
        List of metadata to keep (retain) in the `images` fileset metadata.
        Default to ``IMAGES_MD``.

    See Also
    --------
    romitask.task.RomiTask
    romitask.task.IMAGES_MD
    """
    upstream_task = None  # override default attribute from ``RomiTask``
    pose_task = None
    no_confirm = luigi.BoolParameter(default=False)
    keep_metadata = luigi.ListParameter(default=[])

    def requires(self):
        """No requirements here."""
        return []

    def output(self):
        """Override inherited method to avoid ``FilesetTarget``."""
        return None  # we do not want the cleaning task to add a Fileset!

    def complete(self):
        """Indicate the task as complete."""
        return False  # there is no output

    @staticmethod
    def confirm(c, default='n'):
        """Handle keyboard input from user."""
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
        if c == '':
            return valid[default]
        else:
            return valid[c]

    def run(self):
        """Run the task."""
        scan = DatabaseConfig().scan
        logger.info(f"Cleaning task got a scan named '{scan.id}'...")

        # - Create the list of metadata to keep (retain) to a set and add the ones defined in `IMAGES_MD`
        keep_metadata = list(set(self.keep_metadata) | set(IMAGES_MD))

        # - Handle the necessity to confirm prior to dataset & metadata cleaning.
        if not self.no_confirm:
            del_msg = "This will delete all filesets and metadata except for the `images` & 'VirtualPlant' filesets."
            confirm_msg = "Confirm? [y/N]"
            logger.warning(del_msg)
            logger.warning(confirm_msg)
            clean = self.confirm(input().lower())
        else:
            clean = True

        # - If cleaning not required, abort:
        if not clean:
            logger.info("Did not validate dataset cleaning!")
            return

        # - Perform the dataset & metadata cleaning:
        # List all filesets in dataset (excluding 'images'):
        fs_ids = [fs.id for fs in scan.get_filesets() if fs.id != "images"]
        # Also exclude the dataset associated to VirtualPlant:
        fs_ids = [fs for fs in fs_ids if not fs.startswith("VirtualPlant")]
        logger.info(f"Found {len(fs_ids)} filesets to cleanup (excluding 'images' & 'VirtualPlant')...")

        # Cleanup all Filesets except 'images' & VirtualPlant*:
        if len(fs_ids) != 0:
            for fs in tqdm(fs_ids, unit='fileset'):
                logger.info(f"Deleting '{fs}' fileset...")
                scan.delete_fileset(fs)

        # Cleanup 'images' Filesets metadata:
        img_fs = scan.get_fileset('images')
        if img_fs is None:
            logger.critical(f"Could not get the 'image' fileset for '{scan.id}'!")
        else:
            logger.info("Cleaning 'images' Fileset metadata...")
            for f in tqdm(img_fs.get_files(), unit='file'):
                md = f.get_metadata()
                clean_md = {k: v for k, v in md.items() if k in keep_metadata}
                f.metadata = {}  # need to clear all metadata before setting the clean ones
                f.set_metadata(clean_md)

        # - Cleanup metadata folder:
        metadata_path = Path.resolve(Path(scan.path()) / 'metadata')
        # Clean orphan metadata JSON files
        fs_metadata = glob.glob(str(metadata_path) + '/*.json')
        fs_metadata = [f for f in fs_metadata if f.split('/')[-1] != 'images.json']
        if len(fs_metadata) != 0:
            logger.info(f"Found {len(fs_metadata)} orphan metadata JSON files!")
        for f in fs_metadata:
            try:
                Path(f).unlink(missing_ok=False)
                logger.warning(f"Deleted file: {f}")
            except FileNotFoundError:
                logger.error(f"Could not delete file '{f}'!")
        # Clean orphan metadata directories
        fs_dir = set([d for d in os.listdir(metadata_path) if Path(d).is_dir()]) - {'images'}
        if len(fs_dir) != 0:
            logger.info(f"Found {len(fs_dir)} orphan metadata directories!")
        for md_dir in fs_dir:
            try:
                rmtree(metadata_path / md_dir, ignore_errors=True)
                logger.info(f"Deleted directory: {md_dir}")
            except FileNotFoundError:
                logger.error(f"Could not delete directory '{md_dir}'!")

        # Try to remove 'pipeline.toml' backup, if any:
        pipe_toml = Path.resolve(Path(scan.path()) / 'pipeline.toml')
        if pipe_toml.is_file():
            try:
                pipe_toml.unlink()
            except FileNotFoundError:
                logger.warning(f"Could not delete backup pipeline config: '{pipe_toml}'")
            else:
                logger.info(f"Deleted backup pipeline config: '{pipe_toml}'")
        else:
            logger.info("No backup pipeline config found!")

        return
