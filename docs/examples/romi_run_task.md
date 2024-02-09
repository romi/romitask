# `romi_run_task`

## Create a dummy database
To quickly create a _dummy database_, let's use the temporary folder `/tmp`:
```shell
mkdir -p /tmp/dummy_db/dummy_dataset  # create dummy database and dataset
touch /tmp/dummy_db/romidb  # add the romidb marker (empty file)
export DB_LOCATION='/tmp/dummy_db'  # add database location as an environment variable, 'DB_LOCATION', to current shell
```

## Test the CLI with `DummyTask`
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
