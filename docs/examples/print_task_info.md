# `print_task_info`

## Get an example dataset

To get an example dataset you may use the `shared_fsdb` CLI from `plantdb` to get the `real_plant_analyzed` processed dataset as follows:
```shell
export ROMI_DB="/tmp/ROMI_DB"
shared_fsdb $ROMI_DB --dataset real_plant_analyzed 
```

!!! note
    Obviously this requires to install the `plantdb` library available [here](https://github.com/romi/plantdb).

## Print a summary

After running a task, _e.g._ `PointCloud`, on a dataset, _e.g._ `real_plant_analyzed`, print a summary as follows:
```shell
export ROMI_DB="/tmp/ROMI_DB"
print_task_info PointCloud $ROMI_DB/real_plant_analyzed
```

This should yield something like this:
```
# -- Summary of task PointCloud:
# - Used TOML configuration:
{'upstream_task': 'Voxels', 'level_set_value': 1.0}

# - Generated metadata:
Found a JSON metadata file associated to task 'PointCloud' in dataset '/tmp/ROMI_DB/real_plant_analyzed'!
PointCloud_1_0_1_0_10_0_7ee836e5a9 task recorded the following parameters metadata:
{
  "task_name": "PointCloud",
  "task_params": {
    "background_prior": 1.0,
    "level_set_value": 1.0,
    "min_contrast": 10.0,
    "min_score": 0.2,
    "scan_id": "real_plant_analyzed",
    "upstream_task": "Voxels"
  }
}

# - Task outputs:
Found PLY file for task 'PointCloud_1_0_1_0_10_0_7ee836e5a9':
 - 57890 points
 - pointcloud dimensions (x, y, z): [ 79.17346065  58.64248768 275.51855581]
```