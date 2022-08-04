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

MODULES = {
    # Scanning modules:
    "Scan": "plantimager.tasks.scan",
    "VirtualPlant": "plantimager.tasks.lpy",
    "VirtualScan": "plantimager.tasks.scan",
    "CalibrationScan": "plantimager.tasks.scan",
    "IntrinsicCalibrationScan": "plantimager.tasks.scan",
    # Intrinsic Calibration modules:
    "CreateCharucoBoard" : "plant3dvision.tasks.proc2d",
    "DetectCharuco" : "plant3dvision.tasks.proc2d",
    "IntrinsicCalibration" : "plant3dvision.tasks.proc2d",
    # Geometric reconstruction modules:
    "Colmap": "plant3dvision.tasks.colmap",
    "Undistorted": "plant3dvision.tasks.proc2d",
    "Masks": "plant3dvision.tasks.proc2d",
    "Voxels": "plant3dvision.tasks.cl",
    "PointCloud": "plant3dvision.tasks.proc3d",
    "TriangleMesh": "plant3dvision.tasks.proc3d",
    "CurveSkeleton": "plant3dvision.tasks.proc3d",
    # Machine learning reconstruction modules:
    "Segmentation2D": "plant3dvision.tasks.proc2d",
    "SegmentedPointCloud": "plant3dvision.tasks.proc3d",
    "ClusteredMesh": "plant3dvision.tasks.proc3d",
    "OrganSegmentation": "plant3dvision.tasks.proc3d",
    # Quantification modules:
    "TreeGraph": "plant3dvision.tasks.arabidopsis",
    "AnglesAndInternodes": "plant3dvision.tasks.arabidopsis",
    # Evaluation modules:
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
    # Visu modules:
    "Visualization": "plant3dvision.tasks.visualization",
    # Database modules:
    "Clean": "romitask.task"
}

TASKS = list(MODULES.keys())
