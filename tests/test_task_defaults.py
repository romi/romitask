#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Unit tests for the task_defaults module.

This test suite validates all functions in the task_defaults module, including:
- Static extraction of class defaults from Python source code
- Luigi parameter handling
- Module-level constant resolution
- Import mapping and resolution
- Configuration merging and TOML file operations
"""

import sys
import tempfile
import unittest
from pathlib import Path
from shutil import rmtree
from textwrap import dedent

# Import the module under test
from romitask import task_defaults


class TestGetTaskDefaults(unittest.TestCase):
    """Tests for the get_task_defaults function."""

    def setUp(self):
        """Create a temporary package with a test module and patch Register."""
        # Create a temporary directory that will act as a package root
        self.temp_dir = tempfile.mkdtemp()
        self.pkg_path = Path(self.temp_dir) / "tmp_pkg"
        self.pkg_path.mkdir()
        # Ensure the package is importable
        (self.pkg_path / "__init__.py").write_text("")
        # Insert the temporary directory at the front of sys.path
        self.original_sys_path = list(sys.path)
        sys.path.insert(0, self.temp_dir)
        # Helper to write a module file within the temporary package
        self.module_file = self.pkg_path / "test_mod.py"

    def tearDown(self):
        """Clean up the temporary package and restore patched objects."""
        # Remove the temporary package from sys.path
        sys.path = self.original_sys_path
        # Delete temporary files and directories
        if self.module_file.exists():
            self.module_file.unlink()
        if (self.pkg_path / "__init__.py").exists():
            (self.pkg_path / "__init__.py").unlink()
        if self.pkg_path.exists():
            rmtree(self.pkg_path)
        if Path(self.temp_dir).exists():
            rmtree(Path(self.temp_dir))

    def _write_module(self, source: str):
        """Write the provided source code to the temporary test module."""
        self.module_file.write_text(source)

    def test_simple_attribute_extraction(self):
        """Extract defaults from a plain class with simple attributes."""
        source = """
import luigi
class DummyTask(luigi.Task):
    param1 = luigi.IntParameter(10)
    param2 = luigi.Parameter("test")

    @classmethod
    def get_params(cls):
        class Param:
            def __init__(self, default):
                self._default = default
        return [("param1", Param(10)), ("param2", Param("test"))]
"""
        self._write_module(source)

        # Import the module via its package name
        defaults = task_defaults.get_task_defaults("DummyTask", self.module_file)

        # Expected defaults (upstream_task is always added)
        expected = {
            "upstream_task": None,
            "param1": 10,
            "param2": "test",
        }
        self.assertEqual(defaults, expected)

    def test_module_constant_resolution(self):
        """Ensure that module‑level constants are correctly resolved."""
        source = """
import luigi
GLOBAL_CONST = 100

class DummyTask(luigi.Task):
    value = luigi.IntParameter(GLOBAL_CONST)

    @classmethod
    def get_params(cls):
        class Param:
            def __init__(self, default):
                self._default = default
        return [("value", Param(GLOBAL_CONST))]
"""
        self._write_module(source)

        defaults = task_defaults.get_task_defaults("DummyTask", self.module_file)
        expected = {
            "upstream_task": None,
            "value": 100,
        }
        self.assertEqual(defaults, expected)

    def test_luigi_like_parameter_keyword_default(self):
        """Simulate a Luigi BoolParameter with a keyword default."""
        source = """
import luigi
class DummyTask(luigi.Task):
    enabled = None  # placeholder, not used directly

    @classmethod
    def get_params(cls):
        class Param:
            def __init__(self, default):
                self._default = default
        return [("enabled", Param(False))]
"""
        self._write_module(source)

        defaults = task_defaults.get_task_defaults("DummyTask", self.module_file)
        expected = {
            "upstream_task": None,
            "enabled": False,
        }
        self.assertEqual(defaults, expected)

    def test_luigi_like_parameter_positional_default(self):
        """Simulate a Luigi Parameter where the default is the first positional arg."""
        source = """
import luigi
class DummyTask(luigi.Task):
    name = None  # placeholder

    @classmethod
    def get_params(cls):
        class Param:
            def __init__(self, default):
                self._default = default
        return [("name", Param("default_name"))]
"""
        self._write_module(source)

        defaults = task_defaults.get_task_defaults("DummyTask", self.module_file)
        expected = {
            "upstream_task": None,
            "name": "default_name",
        }
        self.assertEqual(defaults, expected)

    def test_class_without_params(self):
        """A task class with no parameters should still return upstream_task."""
        source = """
import luigi
class DummyTask(luigi.Task):
    @classmethod
    def get_params(cls):
        return []
"""
        self._write_module(source)

        defaults = task_defaults.get_task_defaults("DummyTask", self.module_file)
        expected = {"upstream_task": None}
        self.assertEqual(defaults, expected)


class TestMergeConfigWithDefaults(unittest.TestCase):
    """Tests for the merge_config_with_defaults function."""

    def test_merge_with_override(self):
        """Test that user config values override defaults."""
        # Define config with override
        config = {"TaskA": {"param": 1}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config['TaskA'], defaults['TaskA'])

        # User value should override default
        self.assertEqual(result["param"], 1)
        # Default value should be added
        self.assertEqual(result["threshold"], 0.5)

    def test_merge_adds_missing_defaults(self):
        """Test that missing parameters are added from defaults."""
        # Define config with partial params
        config = {"TaskA": {"param": 1}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5, "enabled": True}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config['TaskA'], defaults['TaskA'])

        # All default params should be present
        expected = {"param": 1, "threshold": 0.5, "enabled": True}
        self.assertEqual(result, expected)

    def test_undefined_param_in_config_removed(self):
        """Test that parameters in config but not in defaults are removed."""
        # Define config with an undefined parameter
        config = {"TaskA": {"param": 1, "undefined_param": None}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config['TaskA'], defaults['TaskA'])

        # undefined_param should not be in the result
        self.assertNotIn("undefined_param", result)
        # Only valid params should be present
        expected = {"param": 1, "threshold": 0.5}
        self.assertEqual(result, expected)

    def test_empty_config(self):
        """Test merging with an empty config dictionary."""
        # Define empty config
        defaults = {"TaskA": {"param": 0}}

        # Merge empty config with defaults
        result = task_defaults.merge_config_with_defaults({}, defaults['TaskA'])

        # Result should be empty
        self.assertEqual(result, {"param": 0})

    def test_empty_defaults(self):
        """Test merging with empty defaults dictionary."""
        # Define config with empty defaults
        config = {"TaskA": {"param": 1}}

        # Merge config with empty defaults
        result = task_defaults.merge_config_with_defaults(config['TaskA'], {})

        # Config should be retained as-is
        self.assertEqual(result, {})


class TestUpdateConfigWithDefaults(unittest.TestCase):
    """Tests for the update_config_with_defaults function."""

    def setUp(self):
        """Create temporary module files for testing."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.module_a_file = Path(self.temp_dir) / "module_a.py"
        self.module_b_file = Path(self.temp_dir) / "module_b.py"

    def tearDown(self):
        """Clean up temporary files."""
        # Remove temporary files and directory
        if self.module_a_file.exists():
            self.module_a_file.unlink()
        if self.module_b_file.exists():
            self.module_b_file.unlink()
        if Path(self.temp_dir).exists():
            rmtree(self.temp_dir)

    def test_update_with_module_mapping(self):
        """Test updating config with a custom module mapping."""
        # Write module A with TaskA
        source_a = dedent("""
        import luigi
        class TaskA(luigi.Task):
            param1 = luigi.IntParameter(10)
            param2 = luigi.Parameter("default")
        """)
        self.module_a_file.write_text(source_a)

        # Write module B with TaskB
        source_b = dedent("""
        import luigi
        class TaskB(luigi.Task):
            enabled = luigi.BoolParameter(False)
        """)
        self.module_b_file.write_text(source_b)

        # Define config and module mapping
        config = {
            "TaskA": {"param1": 20},
            "TaskB": {"enabled": True}
        }
        module_mapping = {
            "TaskA": self.module_a_file,
            "TaskB": self.module_b_file
        }

        # Update config with defaults
        result = task_defaults.update_config_with_defaults(config, module_mapping)

        # Check TaskA merged correctly
        self.assertEqual(result["TaskA"]["param1"], 20)  # overridden
        self.assertEqual(result["TaskA"]["param2"], "default")  # added from defaults

        # Check TaskB merged correctly
        self.assertEqual(result["TaskB"]["enabled"], True)  # overridden

    def test_task_not_in_mapping(self):
        """Test that tasks not in module mapping are skipped."""
        # Define config with a task not in mapping
        config = {"TaskA": {"param": 1}, "UnknownTask": {"value": 2}}
        module_mapping = {}  # Empty mapping

        # Update config with defaults
        result = task_defaults.update_config_with_defaults(config, module_mapping)

        # Result should be empty (no tasks in mapping)
        self.assertEqual(result, {})


class TestUpdateTomlWithDefaults(unittest.TestCase):
    """Tests for the update_toml_with_defaults function."""

    def setUp(self):
        """Create temporary TOML file and module for testing."""
        # Create temporary directory and files
        self.temp_dir = tempfile.mkdtemp()
        self.toml_file = Path(self.temp_dir) / "config.toml"
        self.module_file = Path(self.temp_dir) / "test_module.py"

    def tearDown(self):
        """Clean up temporary files."""
        # Remove temporary files and directory
        if self.toml_file.exists():
            self.toml_file.unlink()
        if self.module_file.exists():
            self.module_file.unlink()
        if Path(self.temp_dir).exists():
            rmtree(self.temp_dir)

    def test_update_toml_file(self):
        """Test updating a TOML file with defaults from a module."""
        # Write a module with a task
        source = dedent("""
        import luigi
        class TaskA(luigi.Task):
            param1 = luigi.IntParameter(10)
            param2 = luigi.Parameter("default")
        """)
        self.module_file.write_text(source)

        # Write a TOML config file
        import tomlkit
        config = {"TaskA": {"param1": 20}}
        with open(self.toml_file, "w") as f:
            tomlkit.dump(config, f)

        # Define module mapping
        module_mapping = {"TaskA": self.module_file}

        # Update TOML with defaults
        result = task_defaults.update_toml_with_defaults(self.toml_file, module_mapping)

        # Check merged result
        self.assertEqual(result["TaskA"]["param1"], 20)  # overridden
        self.assertEqual(result["TaskA"]["param2"], "default")  # added from defaults

    def test_nonexistent_toml_file_raises(self):
        """Test that a non-existent TOML file raises FileNotFoundError."""
        # Use a path that doesn't exist
        nonexistent_toml = Path("/nonexistent/path/config.toml")

        # Should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            task_defaults.update_toml_with_defaults(nonexistent_toml)

    def test_invalid_toml_syntax(self):
        """Test that invalid TOML syntax raises TomlDecodeError."""
        from tomlkit.exceptions import ParseError

        # Write invalid TOML content
        self.toml_file.write_text("[[invalid toml")

        # Should raise TomlDecodeError
        with self.assertRaises(ParseError):
            task_defaults.update_toml_with_defaults(self.toml_file)


if __name__ == "__main__":
    unittest.main()
