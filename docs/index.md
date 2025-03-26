# Welcome to RomiTask

[![Licence](https://img.shields.io/github/license/romi/romitask?color=lightgray)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fromi%2Fromitask%2Frefs%2Fheads%2Fdev%2Fpyproject.toml&logo=python&logoColor=white)]()
[![PyPI - Version](https://img.shields.io/pypi/v/romitask?logo=pypi&logoColor=white)](https://pypi.org/project/romitask/)
[![Conda - Version](https://img.shields.io/conda/vn/romi-eu/romitask?logo=anaconda&logoColor=white&label=romi-eu&color=%2344A833)](https://anaconda.org/romi-eu/romitask)
[![GitHub branch check runs](https://img.shields.io/github/check-runs/romi/romitask/dev)](https://github.com/romi/romitask)

![ROMI_ICON2_greenB.png](assets/images/ROMI_ICON2_greenB.png)

For full documentation of the ROMI project visit [docs.romi-project.eu](https://docs.romi-project.eu/).

## About

This repository gathers CLI and classes needed to run `luigi` based tasks for the ROMI project.

Alone, this library does not do much...
To run a "meaningful" task you need to install other ROMI libraries like `plantdb` and `plant-3d-vision`
or `plant-imager`.

Note that both `plant-3d-vision` & `plant-imager` ROMI libraries have `romitask` & `plantdb` as git submodules.


## Getting started

To install the `romitask` conda package in an existing environment, first activate it, then proceed as follows:
```shell
conda install romitask -c romi-eu
```