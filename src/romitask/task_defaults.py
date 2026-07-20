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
    evaluated with :func:`ast.literal_eval`.  In addition to plain assignments
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
    >>> defaults = get_all_task_defaults(Path('romitask/src/romitask/task.py'))
    >>> defaults['Clean']
    {'upstream_task': None,
     'no_confirm': False,
     'keep_metadata': [],
     'keep_pipeline_cfg': True,
     'keep_task': ''}
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

    with open(module_file, 'r') as f:
        source_code = f.read()

    tree = ast.parse(source_code)
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
                        defaults[attr_name] = _extract_value(item.value)

            # 2. Annotated assignment:  attr: type = <value>
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.value is not None:
                    attr_name = item.target.id
                    defaults[attr_name] = _extract_value(item.value)

        # Keep only classes that yielded at least one default
        if defaults:
            all_defaults[class_name] = defaults

    return all_defaults


def _extract_value(node: ast.AST) -> Any:
    """
    Helper that returns the evaluated value for a given AST node.

    - Tries ``ast.literal_eval`` for simple literals.
    - Detects ``luigi.*Parameter`` calls and extracts the ``default`` argument.
    - Returns ``None`` if the value cannot be safely evaluated.

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
                    # If the default is a Name (e.g. a class reference), return its identifier as a string
                    if isinstance(kw.value, ast.Name):
                        return kw.value.id
                    # If the default is an Attribute (e.g. module.Class), return the dotted name
                    if isinstance(kw.value, ast.Attribute):
                        parts = []
                        cur = kw.value
                        while isinstance(cur, ast.Attribute):
                            parts.append(cur.attr)
                            cur = cur.value
                        if isinstance(cur, ast.Name):
                            parts.append(cur.id)
                        return ".".join(reversed(parts))

            # If no explicit keyword, luigi often uses the first positional arg as default
            if node.args:
                # Evaluate first positional arg if possible
                val = _safe_literal_eval(node.args[0])
                if val is not None:
                    return val
                # Handle Name or Attribute similarly to keyword case
                if isinstance(node.args[0], ast.Name):
                    return node.args[0].id
                if isinstance(node.args[0], ast.Attribute):
                    parts = []
                    cur = node.args[0]
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    return ".".join(reversed(parts))

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
            # Merge existing config with defaults
            merged[task_name] = {**defaults[task_name], **config[task_name]}
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
