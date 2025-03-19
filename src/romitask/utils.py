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
# License along with romitask.  If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

"""ROMI Task Utilities module.

A utility module providing task execution and version management tools for the ROMI (RObotics & Microfarms) project.
This module simplifies the process tracking ROMI component versions.
"""

ROMI_PACKAGES = [
    "romitask",
    "plantdb.commons",
    "plantdb.server",
    "plantdb.client",
    "plant3dvision",
    "plantimager",
    "romicgal",
    "romiseg",
    "dtw",
    "skeleton_refinement",
    "spectral_clustering",
]


def get_version(list_packages="installed"):
    """Retrieves the version information for a predefined list of Python packages.

    This function iterates through a list of package names and tries to fetch their
    respective versions using the `importlib` and `importlib.metadata` libraries. If a
    package is not installed or the version is unavailable, appropriate messages are
    returned for each package.

    Parameters
    ----------
    list_packages : {"all", "installed"}, list of str, optional

    Returns
    -------
    dict
        A dictionary where the keys are package names (str) and the values represent
        one of the following:
        - Version of the package as a string (if available).
        - "Not Installed" if the package is not found.
        - "Undefined" when the version cannot be determined due to an AttributeError.

    Examples
    --------
    >>> # Check versions of ROMI components
    >>> from romitask.utils import get_version
    >>> versions = get_version()
    >>> print(versions)
    {'dtw': '1.0.0', 'plant3dvision': '1.0.0', 'plantdb': '1.0.0', ...}

    """
    import importlib
    from importlib.metadata import version
    from importlib.metadata import PackageNotFoundError

    # Validate input: ensure list_packages is a list of strings if it's a list
    if isinstance(list_packages, list):
        try:
            assert all([isinstance(package, str) for package in list_packages])
        except AssertionError:
            raise ValueError("Input `list_packages` must be a list of strings!")

    # Flag to determine if we should only return installed packages
    only_installed = False
    if list_packages == "installed":
        only_installed = True
        list_packages = ROMI_PACKAGES
    else:
        # Use predefined package list if not "installed" (defaults to "all")
        list_packages = ROMI_PACKAGES

    hash_dict = {}  # Dictionary to store package versions
    # Iterate through packages and get their versions
    for package in list_packages:
        try:
            # Attempt to import the package
            module = importlib.import_module(package)
        except ModuleNotFoundError or PackageNotFoundError:
            package_version = "Not Installed"
        else:
            try:
                # Try to get package version using metadata
                package_version = version(package)
            except AttributeError:
                # Handle cases where version attribute is missing
                package_version = "Undefined"
            except PackageNotFoundError:
                package_version = "Not Installed"

        # Skip uninstalled packages if only_installed is True
        if only_installed and package_version == "Not Installed":
            continue

        # Add package and its version to result dictionary
        hash_dict[package] = package_version

    return hash_dict


def parse_kbdi(kbdi, default='n'):
    """Method to handle keyboard input from user.

    Examples
    --------
    >>> from romitask.utils import parse_kbdi
    >>> response = parse_kbdi(input("Proceed? [y/N] "), default='n')
    >>> print(response)
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if kbdi == '':
        return valid[default]
    else:
        return valid[kbdi]
