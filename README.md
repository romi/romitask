# RomiTask

![](https://anaconda.org/romi-eu/romitask/badges/version.svg)
![](https://anaconda.org/romi-eu/romitask/badges/platforms.svg)
![](https://anaconda.org/romi-eu/romitask/badges/license.svg)

## About

This repository gathers CLI and classes needed to run `luigi` based tasks for the ROMI project.

Alone, this library does not do much...
To run a "meaningful" task you need to install other ROMI libraries like `plantdb` and `plant-3d-vision`
or `plant-imager`.

Note that both `plant-3d-vision` & `plant-imager` ROMI libraries have `romitask` & `plantdb` as git submodules.

## Installation

We strongly advise to create isolated environments to install the ROMI libraries.

We often use `conda` as an environment and python package manager.
If you do not yet have `miniconda3` installed on your system, have a look [here](https://docs.conda.io/en/latest/miniconda.html).

The `romitask` package is available from the `romi-eu` channel.

### Existing conda environment
To install the `romitask` conda package in an existing environment, first activate it, then proceed as follows:
```shell
conda install romitask -c romi-eu
```

### New conda environment
To install the `romitask` conda package in a new environment, here named `romi`, proceed as follows:
```shell
conda create -n romi romitask -c romi-eu
```

### Installation from sources
To install this library, simply clone the repo and use `pip` to install it and the required dependencies.
Again, we strongly advise to create a `conda` environment.

All this can be done as follows:
```shell
git clone https://github.com/romi/romitask.git -b dev  # git clone the 'dev' branch of romitask
cd romitask
conda create -n romi 'python =3.10'
conda activate romi  # do not forget to activate your environment!
python -m pip install -e .  # install the sources
```

Note that the `-e` option is to install the `romitask` sources in "developer mode".
That is, if you make changes to the source code of `romitask` you will not have to `pip install` it again.

You may want to install the `plantdb` sources to perform the `DummyTask` test example below:
```shell
conda activate romi  # do not forget to activate your environment!
python -m pip install git+https://github.com/romi/plantdb.git@dev#egg=plantdb # install the `plantdb` sources from 'dev' branch
```

This will install the required ROMI library `plantdb`, but not in "developer mode".

## Usage

### Create a dummy database
To quickly create a _dummy database_, let's use the temporary folder `/tmp`:
```shell
mkdir -p /tmp/dummy_db/dummy_dataset  # create dummy database and dataset
touch /tmp/dummy_db/romidb  # add the romidb marker (empty file)
export DB_LOCATION='/tmp/dummy_db'  # add database location as an environment variable, 'DB_LOCATION', to current shell
```

### Test the CLI with `DummyTask`
To test the CLI `romi_run_task`:
```shell
romi_run_task DummyTask $DB_LOCATION/dummy_dataset
```

You should get a "Luigi Execution Summary" similar to this:
```
===== Luigi Execution Summary =====

Scheduled 1 tasks of which:
* 1 ran successfully:
    - 1 DummyTask(scan_id=)

This progress looks :) because there were no failed tasks or missing dependencies

===== Luigi Execution Summary =====
```

As no TOML configuration file was provided, you should get a `pipeline.toml` with only a `retcode` and a `version`
sections at the root of the `dummy_dataset/` directory.

The `dummy_database` tree structure should look like this:
```
dummy_database/
├── dummy_dataset/
│   ├── DummyTask__**********/
│   ├── files.json
│   ├── metadata/
│   │   └── DummyTask__**********.json
│   └── pipeline.toml
└── romidb
```


## Developers & contributors

You first have to install the library from sources as explained [here](#installation-from-sources).

### Conda packaging
Start by installing the required `conda-build` & `anaconda-client` conda packages in the `base` environment as follows:
```shell
conda install -n base conda-build anaconda-client
```

#### Build a conda package
To build the `romitask` conda package, from the root directory of the repository and the `base` conda environment, run:
```shell
conda build conda/recipe/ -c conda-forge --user romi-eu
```

If you are struggling with some of the modifications you made to the recipe, 
notably when using environment variables or Jinja2 stuffs, you can always render the recipe with:
```shell
conda render conda/recipe/
```

The official documentation for `conda-render` can be found [here](https://docs.conda.io/projects/conda-build/en/stable/resources/commands/conda-render.html).

#### Upload a conda package
To upload the built packages, you need a valid account (here `romi-eu`) on [anaconda.org](www.anaconda.org) & to log ONCE
with `anaconda login`, then:
```shell
anaconda upload ~/miniconda3/conda-bld/linux-64/romitask*.tar.bz2 --user romi-eu
```

#### Clean builds
To clean the source and build intermediates:
```shell
conda build purge
```

To clean **ALL** the built packages & build environments:
```shell
conda build purge-all
```

### Documentation

We use [`mkdocs`](https://www.mkdocs.org/) to build the documentation with [`mkdocs-material`](https://squidfunk.github.io/mkdocs-material) theme.
The API documentation is generated by [`mkdocstrings`](https://mkdocstrings.github.io/).
Also, we use [`markdown-exec`](https://pawamoy.github.io/markdown-exec) to execute some code snippets to generate output parsed in Markdown.
Finally, you may want to check the [`pymdown-extensions`](https://facelessuser.github.io/pymdown-extensions) documentation.

#### Requirements
To install the requirements for documentation edition, simply run:
```shell
python -m pip install -e .[doc]
```

#### Live edit
You can edit the documentation, `mkdocs.yaml` and the `docs` directory, and see the changes live by using:
```shell
mkdocs serve
```

You should see some logging and this message, indicating where to view it:
```
INFO    -  [14:39:21] Serving on http://127.0.0.1:8000/
```