# RomiTask

## About

This repository gathers scripts and classes needed to run `luigi` based tasks for the ROMI project.

Alone, this library does not do much...
To run a "meaningful" task you need to install other ROMI libraries like `plantdb` and `plant-3d-vision`
or `plant-imager`.

Note that both `plant-3d-vision` & `plant-imager` ROMI libraries have `romitask` & `plantdb` as git submodules.

## Installation

### Conda environment

We strongly advise to create a `conda` environment, here named `romitask`:

```shell
conda create -n romitask 'python>=3.7'
```

If you do not yet have `miniconda3` on your system, have a look [here](https://docs.conda.io/en/latest/miniconda.html).

### Installation from sources

To install this library, simply clone the repo and use `pip` to install it and the required dependencies:

```shell
git clone https://github.com/romi/romitask.git -b dev  # git clone the 'dev' branch of romitask
cd romitask
conda activate romitask  # do not forget to activate your environment!
python -m pip install -r requirements.txt  # install the dependencies
python -m pip install -e .  # install the sources
```

Note that the `-e` option is to install the `romitask` sources in "developer mode".
That is, if you make changes to the source code of `romitask` you will not have to `pip install` it again.

You may want to install the `plantdb` sources to perform the `DummyTask` test example below:

```shell
conda activate romitask  # do not forget to activate your environment!
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
romi_run_task DummyTask $DB_LOCATION/dummy_dataset --module romitask.task
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