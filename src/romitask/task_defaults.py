#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
# Task Default Values

Utility functions for introspecting Python task classes, extracting their default attribute values, and synchronizing those defaults with TOML‑based configuration files.
This module makes it easy to keep configuration files up‑to‑date without manually copying defaults, and works safely by analyzing source code rather than executing it.

## Key Features

- **Static extraction of class defaults**: Parses a module’s source with the `ast` library to retrieve default values for class‑level attributes and luigi parameters.
- **Support for plain, annotated, and luigi parameter assignments**: Handles `attr = 10`, `attr: int = 5`, and calls such as `luigi.BoolParameter(default=False)`.
- **Bulk processing**: `get_all_task_defaults` scans an entire module and returns a mapping of every class to its defaults.
- **Configuration merging**: `merge_config_with_defaults` combines a user‑provided dictionary (e.g., loaded from TOML) with the discovered defaults, preserving user overrides.
- **TOML update helper**: `update_toml_with_defaults` reads a TOML file, merges in defaults, and writes the result back to disk (in‑place or to a new file).
- **Module‑level constant handling and import mapping**: map top‑level constants defined in the inspected file and map imported symbols (both `import module` and `from module import name`).
  These maps are used to resolve references such as `COLMAP_EXE` or imported constants, ensuring that default values referencing other modules or constants are correctly evaluated.

## Usage Examples

```python
>>> from pathlib import Path
>>> from romitask.task_defaults import get_task_defaults
>>> from romitask.task_defaults import merge_config_with_defaults
>>> from romitask.task_defaults import update_toml_with_defaults
>>>
>>> module_path = 'romitask.task'
>>> # 1. Extract defaults from a task module
>>> defaults = get_task_defaults("Clean", module_path)
>>> print(defaults)
{'upstream_task': None, 'no_confirm': False, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
>>>
>>> # 2. Merge with an existing configuration (e.g., loaded from a TOML file)
>>> config = {"Clean": {"no_confirm": True, "undefined_param": None}}  # user‑provided overrides
>>> merged = merge_config_with_defaults(config["Clean"], defaults)
>>> print(merged)  # Note the absence on the undefined parameter 'undefined_param'
{'upstream_task': None, 'no_confirm': True, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
>>>
>>> # 3. Update the configuration from a TOML file
>>> pipe_cfg = update_toml_with_defaults(Path('../configs/geom_pipe_real.toml'))
>>> print(pipe_cfg['Clean'])
{'upstream_task': None, 'no_confirm': True, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
```

"""

import importlib.util
from pathlib import Path
from typing import Any

import tomlkit
from luigi.task_register import Register

from romitask.modules import MODULES


def get_task_defaults(task_name: str, module_path: Path | str) -> dict[str, Any]:
    """
    Extract default parameter values from a task class in a specified module.

    This function dynamically imports a module, retrieves a task class by name,
    and extracts its default parameter values.

    Parameters
    ----------
    task_name : str
        The name of the task class to retrieve from the module. This should be
        an exact match to the class name as defined in the module.
    module_path : Path or str
        The import path to the module containing the task class. Can be provided
        as a string (e.g., 'package.subpackage.module') or as a Path object.
        Must be a valid Python module path.

    Returns
    -------
    dict[str, Any]
        A dictionary mapping parameter names to their default values.

    Raises
    ------
    ModuleNotFoundError
        If the specified module_path does not exist or cannot be imported.
    AttributeError
        If the task_name does not exist as an attribute in the specified module.
    TypeError
        If the task class is not a ``luigi.task_register.Register`` instance.

    Notes
    -----
    The 'scan_id' parameter is explicitly excluded from the results.
    Special handling is applied to different parameter types:

    - dictionaries and lists are converted to strings,
    - type objects are converted to their string names,

    Examples
    --------
    >>> from pathlib import Path
    >>> from romitask.task_defaults import get_task_defaults
    >>> defaults = get_task_defaults('Undistort', 'plant3dvision.tasks.proc2d')
    >>> print(defaults)
    {'query': '{}', 'upstream_task': 'ImagesFilesetExists', 'camera_model_src': 'Colmap', 'camera_model': 'SIMPLE_RADIAL', 'intrinsic_calib_scan_id': '', 'extrinsic_calib_scan_id': '', 'n_workers': -1, 'parallel': True}
    >>> defaults = get_task_defaults('Clean', 'romitask.task')
    >>> print(defaults)
    {'query': '{}', 'upstream_task': 'ImagesFilesetExists', 'camera_model_src': 'Colmap', 'camera_model': 'SIMPLE_RADIAL', 'intrinsic_calib_scan_id': '', 'extrinsic_calib_scan_id': '', 'n_workers': -1, 'parallel': True}
    """
    # Accept both import‑style strings (e.g. "package.module") and filesystem paths.
    if isinstance(module_path, Path):
        module_path = str(module_path)
    # If the string looks like a filesystem path to a .py file, load it via spec.
    path_obj = Path(module_path)
    if path_obj.is_file() and path_obj.suffix == ".py":
        # Use the stem of the file as a temporary module name.
        module_name = path_obj.stem
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ModuleNotFoundError(f"Cannot load module from path: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    else:
        # Dynamically import the module using its import path.
        module = importlib.import_module(module_path)

    task = getattr(module, task_name)

    if not isinstance(task, Register):
        raise TypeError(f"Class '{task_name}' is not a Luigi task.'")

    # Extract the default parameter values:
    defaults = [(p_name, p._default) for p_name, p in task.get_params() if p_name != 'scan_id']

    # Convert default parameter values to desired types:
    task_defaults = {}
    for (p_name, p_value) in defaults:
        if isinstance(p_value, (dict, list)):
            # Convert dictionaries and lists to strings:
            task_defaults[p_name] = str(p_value)
        elif isinstance(p_value, type):
            # convert type objects to their string names:
            task_defaults[p_name] = p_value.__name__
        else:
            task_defaults[p_name] = p_value

    # Force 'upstream_task' definition:
    if 'upstream_task' not in task_defaults:
        task_defaults['upstream_task'] = None

    # Return the dictionary with 'upstream_task' key in first position
    return {'upstream_task': task_defaults.pop('upstream_task'), **task_defaults}


def merge_config_with_defaults(
        task_config: dict[str, Any],
        task_defaults: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge a user‑provided task configuration dictionary with default task values.


    Parameters
    ----------
    task_config : dict[str, Any]
        Existing task configuration dictionary, typically loaded from a TOML file.
    task_defaults : dict[str, Any]
        Mapping of task names to their default attribute dictionaries as
        produced by `get_all_task_defaults`.

    Returns
    -------
    dict[str, Any]
        A new configuration dictionary containing the merged values.

    Examples
    --------
    >>> from romitask.task_defaults import merge_config_with_defaults
    >>> config = {"TaskA": {"param": 1}, "ExtraTask": {"value": 42}}
    >>> task_defaults = {"param": 0, "threshold": 0.5}  # "TaskA" defaults
    >>> merged = merge_config_with_defaults(config["TaskA"], task_defaults)
    >>> merged
    {'param': 1, 'threshold': 0.5}
    """
    # Merge existing config with defaults, replacing default values with config
    # eliminating non-existent params from the config if not found in the default
    return {param_name: task_config.get(param_name, param_value) for param_name, param_value in task_defaults.items()}


def update_config_with_defaults(
        config: dict[str, dict[str, Any]],
        module_mapping: dict[str, str] = MODULES,
) -> dict[str, dict[str, Any]]:
    """
    Update a TOML configuration file with default values from task classes.

    Parameters
    ----------
    config : dict[str, dict[str, Any]]
        Configuration dictionary to update.
    module_mapping : dict[str, str]
        Mapping of task names to their module names.
        Defaults to ``romitask.modules.MODULES``.

    Returns
    -------
    dict
        The merged configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If ``toml_path`` does not point to an existing file.
    toml.TomlDecodeError
        If the input TOML file cannot be parsed.

    See Also
    --------
    romitask.modules.MODULES: the default mapping of task names to their module names.

    Notes
    -----
    * The operation is shallow; nested dictionaries are not merged recursively.

    Examples
    --------
    >>> import tomlkit
    >>> from pathlib import Path
    >>> from romitask.task_defaults import update_config_with_defaults
    >>> with open('../configs/geom_pipe_real.toml') as f: config = tomlkit.load(f)
    >>> print(config['Clean'])
    {'no_confirm': True}
    >>> updated_config = update_config_with_defaults(config)
    >>> print(updated_config['Clean'])
    {'upstream_task': None, 'no_confirm': True, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
    """
    merged_config: dict[str, Any] = {}
    for task_name, task_config in config.items():
        module_path = module_mapping.get(task_name, None)
        if not module_path:
            continue
        # Get defaults from module
        task_defaults = get_task_defaults(task_name, module_path)
        # Merge config with defaults
        merged_config[task_name] = merge_config_with_defaults(task_config, task_defaults)

    return merged_config


def update_toml_with_defaults(
        toml_path: Path,
        module_mapping: dict[str, str] = MODULES,
) -> dict[str, dict[str, Any]]:
    """
    Update a TOML configuration file with default values from task classes.

    Parameters
    ----------
    toml_path : pathlib.Path
        Path to the input TOML configuration file to be read.
    module_mapping : dict[str, str]
        Mapping of task names to their module names.
        Defaults to ``romitask.modules.MODULES``.

    Returns
    -------
    dict
        The merged configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If ``toml_path`` does not point to an existing file.
    toml.TomlDecodeError
        If the input TOML file cannot be parsed.

    See Also
    --------
    romitask.modules.MODULES: the default mapping of task names to their module names.

    Notes
    -----
    * The operation is shallow; nested dictionaries are not merged recursively.

    Examples
    --------
    >>> from pathlib import Path
    >>> from romitask.task_defaults import update_toml_with_defaults
    >>> pipe_cfg = update_toml_with_defaults(Path('configs/geom_pipe_real.toml'))
    >>> print(pipe_cfg['Clean'])
    """
    # Load existing config
    with open(toml_path, 'r') as f:
        config = tomlkit.load(f)

    return update_config_with_defaults(config, module_mapping)
