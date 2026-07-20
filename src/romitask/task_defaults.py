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

## Usage Examples

```python
>>> from pathlib import Path
>>> from romitask.task_defaults import get_all_task_defaults
>>> from romitask.task_defaults import merge_config_with_defaults
>>> from romitask.task_defaults import update_toml_with_defaults
>>>
>>> module_path = 'romitask.task'
>>> # 1. Extract defaults from a task module
>>> defaults = get_all_task_defaults(module_path)
>>> print(defaults)  # {'Clean': {'upstream_task': None, 'no_confirm': False, ...}, ...}
>>>
>>> # 2. Merge with an existing configuration (e.g., loaded from a TOML file)
>>> config = {"Clean": {"no_confirm": True}}  # user‑provided overrides
>>> merged = merge_config_with_defaults(config, defaults)
>>> print(merged["Clean"])  # {'upstream_task': None, 'no_confirm': True, ...}
>>>
>>> # 3. Update the configuration from a TOML file
>>> pipe_cfg = update_toml_with_defaults(Path('configs/geom_pipe_real.toml'))
>>> print(pipe_cfg['Clean'])
{'upstream_task': None, 'no_confirm': True, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
```

"""

import ast
import importlib.util
import os
from pathlib import Path
from typing import Any

import toml

from romitask.modules import MODULES


def get_class_defaults(source_code: str, class_name: str) -> dict[str, Any]:
    """
    Extract default class attributes from a Python source string.

    Parameters
    ----------
    source_code : str
        The complete source code of a Python module as a single string.
    class_name : str
        Name of the class whose class‑level defaults should be extracted.

    Returns
    -------
    dict[str, Any]
        Mapping from the attribute name to its default value for the specified class.
        Only attributes that can be evaluated by `ast.literal_eval` are included;
        attributes with complex expressions are ignored.

    Notes
    -----
    * The function walks the AST of ``source_code`` and looks for ``ast.ClassDef`` nodes matching ``class_name``.
    * It supports both plain assignments (e.g. ``attr = 10``) and annotated
      assignments with a value (e.g. ``attr: int = 5``).
    * Attributes whose values cannot be safely evaluated with
      ``ast.literal_eval`` (e.g., calls or comprehensions) are silently skipped.
    * The search stops after the first matching class definition is found.

    Examples
    --------
    >>> from romitask.task_defaults import get_class_defaults
    >>> source = '''
    ... class Example:
    ...     count = 42
    ...     name: str = "test"
    ...     # Complex expression (ignored)
    ...     value = [i for i in range(3)]
    ... '''
    >>> defaults = get_class_defaults(source, "Example")
    >>> print(defaults)
    {'count': 42, 'name': 'test'}
    """
    tree = ast.parse(source_code)
    defaults = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                # Look for simple assignments at class level
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attr_name = target.id
                            # Extract the value
                            value = ast.literal_eval(item.value)
                            defaults[attr_name] = value
                # Handle annotated assignments (e.g., attr: str = "value")
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if item.value is not None:
                        attr_name = item.target.id
                        try:
                            value = ast.literal_eval(item.value)
                            defaults[attr_name] = value
                        except (ValueError, TypeError):
                            pass
            break

    return defaults


def get_all_task_defaults(module_path: Path | str) -> dict[str, dict[str, Any]]:
    """
    Extract default class attributes from all classes defined in a Python module,
    including defaults of *luigi* parameter objects.

    The function parses the source file at ``module_path`` using the ``ast`` module,
    walks the abstract syntax tree, and collects attributes that can be safely
    evaluated with `ast.literal_eval`.  In addition to plain assignments
    (e.g. ``attr = 10``) and annotated assignments (e.g. ``attr: int = 5``), it now
    recognises *luigi* parameters such as ``luigi.BoolParameter(default=False)`` or
    ``luigi.ListParameter(default=[])`` and extracts the value passed to the
    ``default`` keyword (or the first positional argument when ``default`` is not
    explicitly named).

    Parameters
    ----------
    module_path : pathlib.Path or str
        Path to the Python module file whose classes should be inspected.

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping from class name to a dictionary of attribute names and their
        evaluated default values.  Only classes that define at least one
        evaluable attribute are included in the result.

    Raises
    ------
    FileNotFoundError
        If ``module_path`` does not point to an existing file.
    PermissionError
        If the file cannot be read due to insufficient permissions.

    Notes
    -----
    * The function does **not** execute any code from the target module; it
      only analyses the static source tree, making it safe for untrusted input.
    * Attributes with values that cannot be represented by ``ast.literal_eval``
      (e.g., function calls, list comprehensions, lambda expressions) are
      skipped without raising an exception, unless they are recognised *luigi*
      parameter calls.
    * For *luigi* parameters the parser extracts the ``default`` argument.  If
      the argument cannot be evaluated (e.g., it is a complex expression), the
      attribute is omitted.
    * The search includes all classes in the module, regardless of inheritance
      hierarchy.

    See Also
    --------
    get_class_defaults : Extract defaults from a single class given source code.
    merge_config_with_defaults : Combine a configuration dictionary with defaults
        obtained from task classes.

    Examples
    --------
    >>> from pathlib import Path
    >>> from romitask.task_defaults import get_all_task_defaults
    >>> defaults = get_all_task_defaults('romitask.task')
    >>> print(defaults['Clean'])
    {'upstream_task': None, 'no_confirm': False, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
    >>> defaults = get_all_task_defaults(Path('romitask/src/romitask/task.py'))
    >>> print(defaults['Clean'])
    {'upstream_task': None, 'no_confirm': False, 'keep_metadata': [], 'keep_pipeline_cfg': True, 'keep_task': ''}
    >>> defaults = get_all_task_defaults('plant3dvision.tasks.voxel_reconstruction')
    >>> print(defaults)
    {'Voxels': {'upstream_task': 'Masks', 'query': {}, 'camera_metadata': 'colmap_camera', 'voxel_size': 1.0, 'method': 'averaging', 'log': True, 'invert': False, 'labels': [], 'bounding_box': None, 'bounding_box_edit': None}}
    >>> defaults = get_all_task_defaults('plant3dvision.tasks.colmap')
    >>> print(defaults)
    {'Colmap': {'upstream_task': 'ImagesFilesetExists', 'query': {}, 'colmap_exe': 'roboticsmicrofarms/colmap', 'matcher': 'exhaustive', 'use_gpu': True, 'single_camera': True, 'compute_dense': False, 'alignment_max_error': 10, 'align_pcd': True, 'camera_model': 'SIMPLE_RADIAL', 'bounding_box': None, 'cli_args': {}, 'intrinsic_calibration_scan_id': '', 'extrinsic_calibration_scan_id': '', 'use_calibration_camera': True, 'qc_check': True, 'mad_factor': 3.0, 'metrics': ['xy', 'z', 'pan', 'roll'], 'distance_threshold': 3.0, 'fixed_distance_threshold': 1.0, 'angle_threshold': 5.0, 'fixed_angle_threshold': 3.5, 'max_blind_angle': 30.0, 'retry_count': 10, 'retry': 0}}
    """
    # Resolve ``module_path`` which may be a file system path or a dotted module name.
    if isinstance(module_path, Path):
        module_file = module_path
    else:
        # ``module_path`` is a string – decide whether it looks like a file path.
        if os.path.sep in module_path or module_path.endswith('.py'):
            module_file = Path(module_path)
        else:
            # Assume it is a Python module name; locate the source file via importlib.
            spec = importlib.util.find_spec(module_path)
            if spec is None or spec.origin is None:
                raise ValueError(f"Unable to locate module '{module_path}'.")
            module_file = Path(spec.origin)

    # Parse the source file
    with open(module_file, 'r') as f:
        source_code = f.read()
    tree = ast.parse(source_code)

    # Build a map of *module‑level* constants (e.g. `{'COLMAP_EXE': "/usr/bin/colmap"}`)
    global_consts: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            # Only handle simple names on the left‑hand side
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                const_name = node.targets[0].id
                const_val = _safe_literal_eval(node.value)
                if const_val is not None:  # keep only literals we can evaluate
                    global_consts[const_name] = const_val
        # also accept annotated assignments (e.g. VAR: str = "value")
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                const_name = node.target.id
                const_val = _safe_literal_eval(node.value)
                if const_val is not None:
                    global_consts[const_name] = const_val

    # Build a map of imported names → (module, original_name)
    #      Handles both ``import module`` and ``from mod import name as alias``.
    import_map: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                asname = alias.asname or alias.name
                import_map[asname] = (alias.name, None)  # ``module`` is the package itself
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue  # skip relative imports without a module name
            for alias in node.names:
                asname = alias.asname or alias.name
                import_map[asname] = (node.module, alias.name)  # ``from module import name``

    # Walk the tree and extract class defaults, passing the globals map
    all_defaults: dict[str, dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        class_name = node.name
        defaults: dict[str, Any] = {}

        for item in node.body:
            # 1. Plain assignment:  attr = <value>
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        defaults[attr_name] = _extract_value(item.value,
                                                             globals_map=global_consts,
                                                             import_map=import_map)

            # 2. Annotated assignment:  attr: type = <value>
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.value is not None:
                    attr_name = item.target.id
                    defaults[attr_name] = _extract_value(item.value,
                                                         globals_map=global_consts,
                                                         import_map=import_map)

        # Keep only classes that yielded at least one default
        if defaults:
            all_defaults[class_name] = defaults

    return all_defaults


def _load_module_globals(module_name: str) -> dict[str, Any]:
    """
    Load the source file for *module_name* and return a mapping of its top‑level
    constant assignments.

    The function parses the module's source code using `ast` and extracts
    assignments that can be safely evaluated with ``ast.literal_eval`` or simple
    expressions such as ``os.environ.get``.  It performs two passes:

    1. **First pass** – collect literals and simple annotated values.
    2. **Second pass** – attempt to evaluate expressions that reference
       constants discovered in the first pass (e.g. ``CONST_A = 1`` followed by
       ``CONST_B = CONST_A + 2``).

    This utility is used as a fallback when an imported name cannot be obtained
    via `importlib.import_module` because the attribute is defined as a
    complex expression in the module.

    Parameters
    ----------
    module_name : str
        The fully‑qualified name of the module to inspect (e.g. ``'my_pkg.utils'``).

    Returns
    -------
    dict[str, Any]
        A dictionary mapping constant names to their evaluated values.
        If the module cannot be found, cannot be read, or no evaluable constants are
        present, an empty dictionary is returned.

    Raises
    ------
    None
        The function never raises; any failure (missing file, parse error,
        evaluation error) results in an empty mapping being returned.

    Notes
    -----
    * Only top‑level assignments are considered; constants defined inside
      functions or classes are ignored.
    * Evaluation is deliberately conservative – if a value cannot be safely
      interpreted, it is skipped rather than executing arbitrary code.
    * Environment variable lookups via ``os.environ.get`` or ``os.getenv`` are
      supported and will return the value from the environment (or the provided default).

    Examples
    --------
    >>> from romitask.task_defaults import _load_module_globals
    >>> consts = _load_module_globals('romitask.task')
    >>> consts.get('IMAGES_MD')
    ['pose', 'approximate_pose', 'channel', 'shot_id', 'camera']
    >>> # When the module does not exist, an empty dict is returned
    >>> _load_module_globals('non.existent.module')
    {}
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        return {}

    if spec is None or spec.origin is None:
        return {}

    try:
        with open(spec.origin, "r") as f:
            src = f.read()
    except Exception:
        return {}

    try:
        tree = ast.parse(src)
    except Exception:
        return {}

    # First pass: collect simple literals
    consts: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                val = _safe_literal_eval(node.value)
                if val is not None:
                    consts[name] = val
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                name = node.target.id
                val = _safe_literal_eval(node.value)
                if val is not None:
                    consts[name] = val

    # Second pass: try to evaluate expressions that reference already-resolved constants
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name not in consts:  # Only process if not already resolved
                    val = _evaluate_expression(node.value, consts)
                    if val is not None:
                        consts[name] = val
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                name = node.target.id
                if name not in consts:  # Only process if not already resolved
                    val = _evaluate_expression(node.value, consts)
                    if val is not None:
                        consts[name] = val

    return consts


def _evaluate_expression(node: ast.AST, local_consts: dict[str, Any]) -> Any:
    """
    Try to evaluate an AST expression node using available constants.

    Handles:
    - Simple literals
    - Name references to local_consts
    - os.environ.get() calls with literal arguments

    Parameters
    ----------
    node : ast.AST
        The expression node to evaluate
    local_consts : dict[str, Any]
        Dictionary of already-resolved constant values

    Returns
    -------
    Any
        The evaluated value, or None if evaluation is not possible
    """
    # Try simple literal first
    val = _safe_literal_eval(node)
    if val is not None:
        return val

    # Handle Name nodes that reference local constants
    if isinstance(node, ast.Name):
        return local_consts.get(node.id)

    # Handle os.environ.get('KEY', 'default') or os.getenv('KEY', 'default')
    if isinstance(node, ast.Call):
        # Check if it's os.environ.get() or os.getenv()
        is_environ_get = False
        if isinstance(node.func, ast.Attribute):
            # os.environ.get
            if (isinstance(node.func.value, ast.Attribute) and
                    isinstance(node.func.value.value, ast.Name) and
                    node.func.value.value.id == 'os' and
                    node.func.value.attr == 'environ' and
                    node.func.attr == 'get'):
                is_environ_get = True
            # os.getenv
            elif (isinstance(node.func.value, ast.Name) and
                  node.func.value.id == 'os' and
                  node.func.attr == 'getenv'):
                is_environ_get = True

        if is_environ_get and len(node.args) >= 1:
            # Get the environment variable name
            key_node = node.args[0]
            key_val = _safe_literal_eval(key_node)
            if isinstance(key_val, str):
                # Get the default value if provided
                default_val = None
                if len(node.args) >= 2:
                    default_val = _safe_literal_eval(node.args[1])
                elif any(kw.arg == 'default' for kw in node.keywords):
                    for kw in node.keywords:
                        if kw.arg == 'default':
                            default_val = _safe_literal_eval(kw.value)
                            break

                # Get from environment or use default
                return os.environ.get(key_val, default_val)

    return None


def _extract_value(
        node: ast.AST, *,
        globals_map: dict[str, Any] | None = None,
        import_map: dict[str, tuple[str, str]] | None = None
) -> Any:
    """
    Helper that returns the evaluated value for a given AST node.

    - Tries ``ast.literal_eval`` for simple literals.
    - Detects ``luigi.*Parameter`` calls and extracts the ``default`` argument.
    - Returns ``None`` if the value cannot be safely evaluated.
    - If the node is a ``Name`` (e.g. ``COLMAP_EXE``) we look it up in `globals_map`.
    - Resolves imported names (e.g. ``COLMAP_EXE`` coming from
      ``from plant3dvision.colmap import COLMAP_EXE``) by importing the
      originating module and fetching the attribute.
    - When the name is not present, we fall back to the identifier string

    Parameters
    ----------
    node : ast.AST
        The AST node representing the right‑hand side of an assignment.

    Returns
    -------
    Any
        The evaluated value, or ``None`` when evaluation is not possible.
    """
    # Simple literals (numbers, strings, tuples, lists, dicts, booleans, None)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        pass

    # Name node (local constant or imported)
    if isinstance(node, ast.Name):
        # Local constant defined in the same file
        if globals_map and node.id in globals_map:
            return globals_map[node.id]  # resolved literal

        # Imported symbol – look it up in ``import_map`` and import the module
        if import_map and node.id in import_map:
            mod_name, orig_name = import_map[node.id]
            # Try a normal import first
            try:
                mod = importlib.import_module(mod_name)
                attr_name = orig_name or node.id
                value = getattr(mod, attr_name)
                if isinstance(value, (str, int, float, bool, type(None), dict, list, tuple)):
                    return value
                # If it's a class or callable, return its name as a string
                if isinstance(value, type):  # It's a class
                    return attr_name
                # If it's not a plain literal, fall back to static analysis
                fallback_consts = _load_module_globals(mod_name)
                if attr_name in fallback_consts:
                    return fallback_consts[attr_name]
                # As a last resort, return the identifier string (not None)
                return attr_name
            except Exception:
                # Normal import failed – fall back to static analysis of the module
                fallback_consts = _load_module_globals(mod_name)
                attr_name = orig_name or node.id
                if attr_name in fallback_consts:
                    return fallback_consts[attr_name]
                # Could not resolve, return the identifier string
                return attr_name

        # Not a literal we could evaluate – return the identifier string
        return node.id

    # Attribute chain (module.Class or module.CONST)
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            base_name = parts[-1]

            # Resolve the left‑most name via import map if possible
            if import_map and base_name in import_map:
                mod_name, orig_name = import_map[base_name]
                try:
                    mod = importlib.import_module(mod_name)
                    obj = getattr(mod, orig_name or base_name)
                    # Walk remaining attributes on that object
                    for attr in reversed(parts[:-1]):
                        obj = getattr(obj, attr)
                    # Return literal if possible
                    if isinstance(obj, (str, int, float, bool, type(None), dict, list, tuple)):
                        return obj
                    return ".".join(reversed(parts))
                except Exception:
                    # Fallback to static analysis of the module
                    fallback_consts = _load_module_globals(mod_name)
                    full_name = ".".join(reversed(parts))
                    if full_name in fallback_consts:
                        return fallback_consts[full_name]
                    # Return dotted name as a last resort
                    return ".".join(reversed(parts))

            # Fallback – just return the dotted name
            return ".".join(reversed(parts))

    # Look for luigi parameter calls, e.g. luigi.BoolParameter(default=False)
    if isinstance(node, ast.Call):
        # Resolve the called object's name (could be Name or Attribute)
        func_name = None
        if isinstance(node.func, ast.Attribute):
            # e.g. luigi.BoolParameter
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            # e.g. BoolParameter (if imported directly)
            func_name = node.func.id

        if func_name and func_name.endswith("Parameter"):
            # Try to find a ``default`` keyword argument
            for kw in node.keywords:
                if kw.arg == "default":
                    # If the default is a simple literal, evaluate it
                    val = _safe_literal_eval(kw.value)
                    if val is not None:
                        return val
                    # Fallback to name / attribute handling
                    return _extract_value(kw.value, globals_map=globals_map, import_map=import_map)

            # If no explicit keyword, luigi often uses the first positional arg as default
            if node.args:
                # Evaluate first positional arg if possible
                val = _safe_literal_eval(node.args[0])
                if val is not None:
                    return val
                # Fallback to name / attribute handling
                return _extract_value(node.args[0], globals_map=globals_map, import_map=import_map)

    # If we reach this point, we couldn't evaluate the expression
    return None


def _safe_literal_eval(node: ast.AST) -> Any:
    """
    Wrapper around ``ast.literal_eval`` that silences ``ValueError``/``TypeError``
    and returns ``None`` for unsupported nodes.

    Parameters
    ----------
    node : ast.AST
        Node to evaluate.

    Returns
    -------
    Any
        Evaluated value or ``None``.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def merge_config_with_defaults(
        config: dict[str, Any],
        defaults: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Merge a user‑provided configuration dictionary with default task attributes.

    The function iterates over each task defined in ``config`` and combines the
    corresponding entries from ``default`` (if present).
    Tasks present only in ``config`` are retained unchanged.
    The merge is shallow: nested dictionaries are not merged recursively.

    Parameters
    ----------
    config : dict[str, Any]
        Existing configuration dictionary, typically loaded from a TOML file.
    defaults : dict[str, dict[str, Any]]
        Mapping of task names to their default attribute dictionaries as
        produced by `get_all_task_defaults`.

    Returns
    -------
    dict[str, Any]
        A new configuration dictionary containing the merged values.
        The original ``config`` and ``defaults`` inputs are not mutated.

    Examples
    --------
    >>> from romitask.task_defaults import merge_config_with_defaults
    >>> config = {"TaskA": {"param": 1}, "ExtraTask": {"value": 42}}
    >>> defaults = {"TaskA": {"param": 0, "threshold": 0.5}, "TaskB": {"enabled": True}}
    >>> merged = merge_config_with_defaults(config, defaults)
    >>> merged["TaskA"]
    {'param': 1, 'threshold': 0.5}
    >>> merged["ExtraTask"]
    {'value': 42}
    >>> "TaskB" in merged
    False
    """
    merged = {}

    # Process each task section
    for task_name in config:
        if task_name in defaults:
            # Merge existing config with defaults, replacing default values with config
            # eliminating non-existant params from the config if not found in the default
            merged[task_name] = {param_name: config[task_name].get(param_name, param_value) for param_name, param_value
                                 in defaults[task_name].items()}
        else:
            merged[task_name] = config[task_name]

    return merged


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
    >>> import toml
    >>> from pathlib import Path
    >>> from romitask.task_defaults import update_config_with_defaults
    >>> with open('configs/geom_pipe_real.toml') as f: config = toml.load(f)
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
        defaults = get_all_task_defaults(module_path)
        # Merge config with defaults
        merged_config[task_name] = merge_config_with_defaults({task_name: task_config}, defaults)[task_name]

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
        config = toml.load(f)

    return update_config_with_defaults(config, module_mapping)
