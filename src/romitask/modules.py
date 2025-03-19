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

"""ROMI Task Module Registry

A centralized registry of task modules for the ROMI (RObot for MIcrofarm) project, providing a mapping between task names and their corresponding module paths for plant imaging, reconstruction, and analysis workflows.

Usage Examples
--------------
>>> from romitask.modules import MODULES, TASKS
>>> # Get the module path for a specific task
>>> scanning_module = MODULES["Scan"]
>>> print(scanning_module)
'plantimager.tasks.scan'

>>> # Check if a task requires a dataset
>>> task_name = "Scan"
>>> requires_dataset = task_name not in NO_DATASET_TASK
>>> print(f"{task_name} requires dataset: {requires_dataset}")
'Scan requires dataset: True'
"""

MODULES = {
    # Scanning module:
    "Scan": "plantimager.tasks.scan",
    "ScannerToCenter": "plantimager.tasks.scan",
    "VirtualPlant": "plantimager.tasks.lpy",
    "VirtualScan": "plantimager.tasks.scan",
    "CalibrationScan": "plantimager.tasks.scan",
    "IntrinsicCalibrationScan": "plantimager.tasks.scan",
    # Calibration module:
    "CreateCharucoBoard": "plant3dvision.tasks.calibration",
    "DetectCharuco": "plant3dvision.tasks.calibration",
    "ExtrinsicCalibration": "plant3dvision.tasks.calibration",
    "IntrinsicCalibration": "plant3dvision.tasks.calibration",
    # Geometric reconstruction module:
    "Colmap": "plant3dvision.tasks.colmap",
    "CameraPoseQC": "plant3dvision.tasks.colmap",
    "Undistort": "plant3dvision.tasks.proc2d",
    "Masks": "plant3dvision.tasks.proc2d",
    "Voxels": "plant3dvision.tasks.cl",
    "PointCloud": "plant3dvision.tasks.proc3d",
    "TriangleMesh": "plant3dvision.tasks.proc3d",
    "CurveSkeleton": "plant3dvision.tasks.proc3d",
    # Machine learning reconstruction module:
    "Segmentation2D": "plant3dvision.tasks.proc2d",
    "SegmentedPointCloud": "plant3dvision.tasks.proc3d",
    "ClusteredMesh": "plant3dvision.tasks.proc3d",
    "OrganSegmentation": "plant3dvision.tasks.proc3d",
    # Quantification module:
    "TreeGraph": "plant3dvision.tasks.arabidopsis",
    "AnglesAndInternodes": "plant3dvision.tasks.arabidopsis",
    # Evaluation module:
    "VoxelsGroundTruth": "plant3dvision.tasks.evaluation",
    "VoxelsEvaluation": "plant3dvision.tasks.evaluation",
    "PointCloudGroundTruth": "plant3dvision.tasks.evaluation",
    "PointCloudEvaluation": "plant3dvision.tasks.evaluation",
    "ClusteredMeshGroundTruth": "plant3dvision.tasks.evaluation",
    "SegmentedPointCloudEvaluation": "plant3dvision.tasks.evaluation",
    "Segmentation2DEvaluation": "plant3dvision.tasks.evaluation",
    "AnglesAndInternodesEvaluation": "plant3dvision.tasks.evaluation",
    "CylinderRadiusGroundTruth": "plant3dvision.tasks.evaluation",
    "CylinderRadiusEstimation": "plant3dvision.tasks.evaluation",
    # Visualization module:
    "Visualization": "plant3dvision.tasks.visualization",
    # Database module:
    "DummyTask": "romitask.task",
    "Clean": "romitask.task",
}

TASKS = list(MODULES.keys())

#: List of tasks that create a dataset or that can be used without specifying an existing dataset.
DATA_CREATION_TASK = [
    "Scan",
    "ScannerToCenter",
    "VirtualPlant",
    "CalibrationScan",
    "IntrinsicCalibrationScan",
]
# NOTE: do NOT add 'VirtualScan' here, else it will break workflow heritability for 'VirtualPlant'

#: List of tasks that can work without a dataset.
NO_DATASET_TASK = [
    "DummyTask",
    "ScannerToCenter",
]
