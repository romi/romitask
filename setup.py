#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

opts = dict(
    name="romitask",
    version="0.10.99",
    description="The ROMI task runner, a luigi based task pipeline.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Nabil Ait Taleb",
    author_email="mohamednabil.aittaleb@sony.com",
    maintainer='Jonathan Legrand',
    maintainer_email='jonathan.legrand@ens-lyon.fr',
    url="https://docs.romi-project.eu/Scanner/home/",
    download_url='',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    scripts=[
        'bin/romi_run_task',
        'bin/print_task_info'
    ],
    zip_safe=False,
    python_requires='>=3.7',
    install_requires=[],
    include_package_data=True
)

if __name__ == '__main__':
    setup(**opts)
