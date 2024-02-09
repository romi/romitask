# Welcome to RomiTask
![](https://anaconda.org/romi-eu/romitask/badges/version.svg)
![](https://anaconda.org/romi-eu/romitask/badges/platforms.svg)
![](https://anaconda.org/romi-eu/romitask/badges/license.svg)

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