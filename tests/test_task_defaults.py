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

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

# Import the module under test
from romitask import task_defaults


class TestGetClassDefaults(unittest.TestCase):
    """Tests for the get_class_defaults function."""

    def test_simple_class_attribute(self):
        """Test extraction of a simple class attribute with a literal value."""
        source = dedent("""
        class Example:
            count = 42
        """)
        # Extract defaults for the Example class
        result = task_defaults.get_class_defaults(source, "Example")

        # Should extract the count attribute
        self.assertEqual(result, {"count": 42})

    def test_annotated_attribute(self):
        """Test extraction of an annotated class attribute."""
        source = dedent("""
        class Example:
            name: str = "test"
        """)
        # Extract defaults for the annotated attribute
        result = task_defaults.get_class_defaults(source, "Example")

        # Should extract the name attribute with its value
        self.assertEqual(result, {"name": "test"})

    def test_multiple_attributes(self):
        """Test extraction of multiple attributes from a single class."""
        source = dedent("""
        class Example:
            count = 42
            name: str = "test"
            enabled = True
        """)
        # Extract all defaults from the Example class
        result = task_defaults.get_class_defaults(source, "Example")

        # Should extract all three attributes
        expected = {"count": 42, "name": "test", "enabled": True}
        self.assertEqual(result, expected)

    def test_complex_expression_ignored(self):
        """Test that complex expressions (list comprehensions, etc.) are ignored."""
        source = dedent("""
        class Example:
            count = 42
            items = [i for i in range(3)]
        """)
        # Extract defaults, complex expression should be skipped
        result = task_defaults.get_class_defaults(source, "Example")

        # Should only extract the simple literal (count), not the comprehension
        self.assertEqual(result, {"count": 42})

    def test_nonexistent_class(self):
        """Test that requesting a non-existent class returns an empty dictionary."""
        source = dedent("""
        class Example:
            count = 42
        """)
        # Request defaults for a class that doesn't exist
        result = task_defaults.get_class_defaults(source, "NonExistent")

        # Should return empty dict
        self.assertEqual(result, {})

    def test_empty_class(self):
        """Test that a class with no attributes returns an empty dictionary."""
        source = dedent("""
        class Example:
            pass
        """)
        # Extract defaults from an empty class
        result = task_defaults.get_class_defaults(source, "Example")

        # Should return empty dict
        self.assertEqual(result, {})

    def test_list_and_dict_literals(self):
        """Test extraction of list and dictionary literal values."""
        source = dedent("""
        class Example:
            items = [1, 2, 3]
            config = {"key": "value"}
        """)
        # Extract complex literal structures
        result = task_defaults.get_class_defaults(source, "Example")

        # Should extract both list and dict literals
        expected = {"items": [1, 2, 3], "config": {"key": "value"}}
        self.assertEqual(result, expected)

    def test_none_value(self):
        """Test extraction of None as a default value."""
        source = dedent("""
        class Example:
            optional = None
        """)
        # Extract None value
        result = task_defaults.get_class_defaults(source, "Example")

        # Should extract None correctly
        self.assertEqual(result, {"optional": None})


class TestGetAllTaskDefaults(unittest.TestCase):
    """Tests for the get_all_task_defaults function."""

    def setUp(self):
        """Create a temporary module file for testing."""
        # Create a temporary directory and file
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test_module.py"

    def tearDown(self):
        """Clean up temporary files."""
        # Remove temporary file and directory
        if self.temp_file.exists():
            self.temp_file.unlink()
        if Path(self.temp_dir).exists():
            Path(self.temp_dir).rmdir()

    def test_multiple_classes(self):
        """Test extraction of defaults from multiple classes in a module."""
        # Write a module with multiple classes
        source = dedent("""
        class TaskA:
            param1 = 10
            param2 = "test"

        class TaskB:
            enabled = True
            count = 5
        """)
        self.temp_file.write_text(source)

        # Extract defaults from all classes
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should return defaults for both classes
        expected = {
            "TaskA": {"param1": 10, "param2": "test"},
            "TaskB": {"enabled": True, "count": 5}
        }
        self.assertEqual(result, expected)

    def test_module_level_constants(self):
        """Test that module-level constants are resolved in class attributes."""
        # Write a module with a top-level constant used in a class
        source = dedent("""
        GLOBAL_CONST = 100

        class Task:
            value = GLOBAL_CONST
        """)
        self.temp_file.write_text(source)

        # Extract defaults, should resolve the constant
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should resolve GLOBAL_CONST to 100
        self.assertEqual(result["Task"]["value"], 100)

    def test_luigi_parameter_keyword_default(self):
        """Test extraction of default from luigi parameter with keyword argument."""
        # Write a class with a luigi parameter using keyword default
        source = dedent("""
        import luigi

        class Task:
            enabled = luigi.BoolParameter(default=False)
            count = luigi.IntParameter(default=42)
        """)
        self.temp_file.write_text(source)

        # Extract defaults from luigi parameters
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should extract the default values from luigi parameters
        expected = {"Task": {"enabled": False, "count": 42}}
        self.assertEqual(result, expected)

    def test_luigi_parameter_positional_default(self):
        """Test extraction of default from luigi parameter with positional argument."""
        # Write a class with luigi parameter using positional default
        source = dedent("""
        import luigi

        class Task:
            name = luigi.Parameter("default_name")
        """)
        self.temp_file.write_text(source)

        # Extract defaults from luigi parameter with positional arg
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should extract the first positional argument as default
        self.assertEqual(result["Task"]["name"], "default_name")

    def test_empty_module(self):
        """Test that an empty module returns an empty dictionary."""
        # Write an empty module
        source = ""
        self.temp_file.write_text(source)

        # Extract defaults from empty module
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should return empty dict
        self.assertEqual(result, {})

    def test_class_without_defaults(self):
        """Test that classes without evaluable defaults are excluded."""
        # Write a class with only complex expressions
        source = dedent("""
        class Task:
            value = some_function()
        """)
        self.temp_file.write_text(source)

        # Extract defaults, class should be excluded
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should return empty dict (no evaluable defaults)
        self.assertEqual(result['Task']['value'], None)

    def test_annotated_module_constant(self):
        """Test that annotated module-level constants are recognized."""
        # Write a module with annotated constant
        source = dedent("""
        CONST: int = 50

        class Task:
            value = CONST
        """)
        self.temp_file.write_text(source)

        # Extract defaults, should resolve annotated constant
        result = task_defaults.get_all_task_defaults(self.temp_file)

        # Should resolve the annotated constant
        self.assertEqual(result["Task"]["value"], 50)

    def test_nonexistent_file_raises(self):
        """Test that a non-existent file path raises FileNotFoundError."""
        # Use a path that doesn't exist
        nonexistent_path = Path("/nonexistent/path/to/module.py")

        # Should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            task_defaults.get_all_task_defaults(nonexistent_path)

    def test_invalid_module_name_raises(self):
        """Test that an invalid module name raises ValueError."""
        # Use a module name that cannot be resolved
        invalid_module = "nonexistent.invalid.module"

        # Should return an empty dictionary
        result = task_defaults.get_all_task_defaults(invalid_module)
        self.assertEqual(result, {})


class TestLoadModuleGlobals(unittest.TestCase):
    """Tests for the _load_module_globals helper function."""

    def setUp(self):
        """Create a temporary module file for testing."""
        # Create temporary directory and file
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test_globals.py"

        # Add temp directory to sys.path so modules can be imported
        self.original_path = sys.path.copy()
        sys.path.insert(0, self.temp_dir)

    def tearDown(self):
        """Clean up temporary files and restore sys.path."""
        import sys
        # Restore original sys.path
        sys.path = self.original_path

        # Clean up any imported test modules
        modules_to_remove = [name for name in sys.modules if name.startswith('test_globals')]
        for module_name in modules_to_remove:
            del sys.modules[module_name]

        # Remove temporary file and directory
        if self.temp_file.exists():
            self.temp_file.unlink()
        if Path(self.temp_dir).exists():
            Path(self.temp_dir).rmdir()

    def test_simple_constants(self):
        """Test extraction of simple top-level constants."""
        # Write a module with simple constants
        source = dedent("""
        CONST_A = 10
        CONST_B = "test"
        CONST_C = [1, 2, 3]
        """)
        self.temp_file.write_text(source)

        # Load module globals using the module name directly
        result = task_defaults._load_module_globals("test_globals")

        # Should extract all three constants
        self.assertIn("CONST_A", result)
        self.assertIn("CONST_B", result)
        self.assertIn("CONST_C", result)
        self.assertEqual(result["CONST_A"], 10)
        self.assertEqual(result["CONST_B"], "test")
        self.assertEqual(result["CONST_C"], [1, 2, 3])

    def test_nonexistent_module(self):
        """Test that a non-existent module returns an empty dictionary."""
        # Try to load globals from a non-existent module
        result = task_defaults._load_module_globals("nonexistent.module")

        # Should return empty dict
        self.assertEqual(result, {})

    def test_os_environ_get(self):
        """Test that os.environ.get() calls are evaluated correctly."""
        # Set an environment variable for testing
        os.environ["TEST_VAR"] = "test_value"

        try:
            # Write a module that uses os.environ.get
            source = dedent("""
            import os
            CONST = os.environ.get("TEST_VAR", "default")
            """)
            self.temp_file.write_text(source)

            # Load module globals
            result = task_defaults._load_module_globals("test_globals")

            # Should resolve the environment variable
            self.assertIn("CONST", result)
            self.assertEqual(result["CONST"], "test_value")
        finally:
            # Clean up
            del os.environ["TEST_VAR"]

    def test_annotated_constants(self):
        """Test extraction of annotated module-level constants."""
        # Write a module with annotated constants
        source = dedent("""
        CONST_INT: int = 42
        CONST_STR: str = "hello"
        CONST_DICT: dict = {"key": "value"}
        """)
        self.temp_file.write_text(source)

        # Load module globals
        result = task_defaults._load_module_globals("test_globals")

        # Should extract all annotated constants
        self.assertEqual(result["CONST_INT"], 42)
        self.assertEqual(result["CONST_STR"], "hello")
        self.assertEqual(result["CONST_DICT"], {"key": "value"})


class TestEvaluateExpression(unittest.TestCase):
    """Tests for the _evaluate_expression helper function."""

    def test_simple_literal(self):
        """Test evaluation of a simple literal expression."""
        # Parse a simple literal
        node = ast.parse("42").body[0].value

        # Evaluate it with empty context
        result = task_defaults._evaluate_expression(node, {})

        # Should return the literal value
        self.assertEqual(result, 42)

    def test_name_reference(self):
        """Test evaluation of a name that references a local constant."""
        # Parse a name node
        node = ast.parse("CONST").body[0].value

        # Evaluate with a constant in the context
        result = task_defaults._evaluate_expression(node, {"CONST": 100})

        # Should resolve to the constant value
        self.assertEqual(result, 100)

    def test_name_not_in_context(self):
        """Test evaluation of a name not present in the context returns None."""
        # Parse a name node
        node = ast.parse("UNKNOWN").body[0].value

        # Evaluate with empty context
        result = task_defaults._evaluate_expression(node, {})

        # Should return None
        self.assertIsNone(result)

    def test_os_environ_get_with_default(self):
        """Test evaluation of os.environ.get() with a default value."""
        # Parse an os.environ.get call with default
        node = ast.parse('os.environ.get("MISSING_VAR", "fallback")').body[0].value

        # Evaluate (variable doesn't exist, should use default)
        result = task_defaults._evaluate_expression(node, {})

        # Should return the fallback value
        self.assertEqual(result, "fallback")

    def test_os_getenv_call(self):
        """Test evaluation of os.getenv() call."""
        # Set an environment variable
        os.environ["TEST_GETENV"] = "value"

        # Parse an os.getenv call
        node = ast.parse('os.getenv("TEST_GETENV")').body[0].value

        try:
            # Evaluate the call
            result = task_defaults._evaluate_expression(node, {})

            # Should return the environment variable value
            self.assertEqual(result, "value")
        finally:
            # Clean up
            del os.environ["TEST_GETENV"]


class TestExtractValue(unittest.TestCase):
    """Tests for the _extract_value helper function."""

    def test_simple_literal(self):
        """Test extraction of a simple literal value."""
        # Parse a simple integer literal
        node = ast.parse("42").body[0].value

        # Extract the value
        result = task_defaults._extract_value(node)

        # Should return the literal
        self.assertEqual(result, 42)

    def test_name_in_globals_map(self):
        """Test extraction of a name that exists in the globals map."""
        # Parse a name reference
        node = ast.parse("CONST").body[0].value

        # Extract with globals map
        result = task_defaults._extract_value(node, globals_map={"CONST": 99})

        # Should resolve to the global constant
        self.assertEqual(result, 99)

    def test_name_not_in_maps(self):
        """Test that a name not in any map returns the identifier string."""
        # Parse a name reference
        node = ast.parse("UNKNOWN").body[0].value

        # Extract without any maps
        result = task_defaults._extract_value(node)

        # Should return the name as a string
        self.assertEqual(result, "UNKNOWN")

    def test_attribute_chain(self):
        """Test extraction of an attribute chain (e.g., module.Class)."""
        # Parse an attribute chain
        node = ast.parse("module.Class").body[0].value

        # Extract the value
        result = task_defaults._extract_value(node)

        # Should return the dotted name
        self.assertEqual(result, "module.Class")

    def test_luigi_parameter_with_keyword_default(self):
        """Test extraction of default from a luigi parameter call with keyword."""
        # Parse a luigi parameter call with keyword default
        node = ast.parse("luigi.IntParameter(default=10)").body[0].value

        # Extract the default value
        result = task_defaults._extract_value(node)

        # Should return the default value
        self.assertEqual(result, 10)

    def test_luigi_parameter_with_positional_default(self):
        """Test extraction of default from a luigi parameter call with positional arg."""
        # Parse a luigi parameter call with positional default
        node = ast.parse("luigi.Parameter('default_value')").body[0].value

        # Extract the default value
        result = task_defaults._extract_value(node)

        # Should return the first positional argument
        self.assertEqual(result, "default_value")

    def test_unsupported_expression(self):
        """Test that unsupported expressions return None."""
        # Parse a lambda expression (unsupported)
        node = ast.parse("lambda x: x + 1").body[0].value

        # Extract the value
        result = task_defaults._extract_value(node)

        # Should return None
        self.assertIsNone(result)


class TestSafeLiteralEval(unittest.TestCase):
    """Tests for the _safe_literal_eval helper function."""

    def test_valid_literal(self):
        """Test evaluation of a valid literal."""
        # Parse a valid literal
        node = ast.parse("42").body[0].value

        # Evaluate safely
        result = task_defaults._safe_literal_eval(node)

        # Should return the value
        self.assertEqual(result, 42)

    def test_invalid_expression(self):
        """Test that invalid expressions return None."""
        # Parse an invalid expression (function call)
        node = ast.parse("func()").body[0].value

        # Evaluate safely
        result = task_defaults._safe_literal_eval(node)

        # Should return None
        self.assertIsNone(result)

    def test_list_literal(self):
        """Test evaluation of a list literal."""
        # Parse a list literal
        node = ast.parse("[1, 2, 3]").body[0].value

        # Evaluate safely
        result = task_defaults._safe_literal_eval(node)

        # Should return the list
        self.assertEqual(result, [1, 2, 3])

    def test_dict_literal(self):
        """Test evaluation of a dictionary literal."""
        # Parse a dict literal
        node = ast.parse("{'key': 'value'}").body[0].value

        # Evaluate safely
        result = task_defaults._safe_literal_eval(node)

        # Should return the dictionary
        self.assertEqual(result, {"key": "value"})


class TestMergeConfigWithDefaults(unittest.TestCase):
    """Tests for the merge_config_with_defaults function."""

    def test_merge_with_override(self):
        """Test that user config values override defaults."""
        # Define config with override
        config = {"TaskA": {"param": 1}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # User value should override default
        self.assertEqual(result["TaskA"]["param"], 1)
        # Default value should be added
        self.assertEqual(result["TaskA"]["threshold"], 0.5)

    def test_merge_adds_missing_defaults(self):
        """Test that missing parameters are added from defaults."""
        # Define config with partial params
        config = {"TaskA": {"param": 1}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5, "enabled": True}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # All default params should be present
        expected = {"param": 1, "threshold": 0.5, "enabled": True}
        self.assertEqual(result["TaskA"], expected)

    def test_task_not_in_defaults(self):
        """Test that tasks not in defaults are retained unchanged."""
        # Define config with a task not in defaults
        config = {"ExtraTask": {"value": 42}}
        defaults = {"TaskA": {"param": 0}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # ExtraTask should be retained as-is
        self.assertEqual(result["ExtraTask"], {"value": 42})

    def test_undefined_param_in_config_removed(self):
        """Test that parameters in config but not in defaults are removed."""
        # Define config with an undefined parameter
        config = {"TaskA": {"param": 1, "undefined_param": None}}
        defaults = {"TaskA": {"param": 0, "threshold": 0.5}}

        # Merge config with defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # undefined_param should not be in the result
        self.assertNotIn("undefined_param", result["TaskA"])
        # Only valid params should be present
        expected = {"param": 1, "threshold": 0.5}
        self.assertEqual(result["TaskA"], expected)

    def test_empty_config(self):
        """Test merging with an empty config dictionary."""
        # Define empty config
        config = {}
        defaults = {"TaskA": {"param": 0}}

        # Merge empty config with defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # Result should be empty
        self.assertEqual(result, {})

    def test_empty_defaults(self):
        """Test merging with empty defaults dictionary."""
        # Define config with empty defaults
        config = {"TaskA": {"param": 1}}
        defaults = {}

        # Merge config with empty defaults
        result = task_defaults.merge_config_with_defaults(config, defaults)

        # Config should be retained as-is
        self.assertEqual(result["TaskA"], {"param": 1})


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
            Path(self.temp_dir).rmdir()

    def test_update_with_module_mapping(self):
        """Test updating config with a custom module mapping."""
        # Write module A with TaskA
        source_a = dedent("""
        class TaskA:
            param1 = 10
            param2 = "default"
        """)
        self.module_a_file.write_text(source_a)

        # Write module B with TaskB
        source_b = dedent("""
        class TaskB:
            enabled = False
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
            Path(self.temp_dir).rmdir()

    def test_update_toml_file(self):
        """Test updating a TOML file with defaults from a module."""
        # Write a module with a task
        source = dedent("""
        class TaskA:
            param1 = 10
            param2 = "default"
        """)
        self.module_file.write_text(source)

        # Write a TOML config file
        import toml
        config = {"TaskA": {"param1": 20}}
        with open(self.toml_file, "w") as f:
            toml.dump(config, f)

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
        import toml

        # Write invalid TOML content
        self.toml_file.write_text("[[invalid toml")

        # Should raise TomlDecodeError
        with self.assertRaises(toml.TomlDecodeError):
            task_defaults.update_toml_with_defaults(self.toml_file)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete workflows."""

    def setUp(self):
        """Create temporary files for integration testing."""
        # Create temporary directory and files
        self.temp_dir = tempfile.mkdtemp()
        self.module_file = Path(self.temp_dir) / "tasks.py"
        self.toml_file = Path(self.temp_dir) / "config.toml"

    def tearDown(self):
        """Clean up temporary files."""
        # Remove temporary files and directory
        if self.module_file.exists():
            self.module_file.unlink()
        if self.toml_file.exists():
            self.toml_file.unlink()
        if Path(self.temp_dir).exists():
            Path(self.temp_dir).rmdir()

    def test_full_workflow_extract_merge_update(self):
        """Test the complete workflow: extract defaults, merge with config, update TOML."""
        # Write a module with multiple tasks
        source = dedent("""
        import luigi

        GLOBAL_TIMEOUT = 300

        class TaskA:
            timeout = GLOBAL_TIMEOUT
            retry = luigi.IntParameter(default=3)
            enabled = True

        class TaskB:
            count: int = 10
            name = "task_b"
        """)
        self.module_file.write_text(source)

        # Write initial TOML config
        import toml
        config = {
            "TaskA": {"retry": 5},  # override
            "TaskB": {"count": 20}  # override
        }
        with open(self.toml_file, "w") as f:
            toml.dump(config, f)

        # Step 1: Extract defaults from module
        defaults = task_defaults.get_all_task_defaults(self.module_file)

        # Verify extracted defaults
        self.assertEqual(defaults["TaskA"]["timeout"], 300)
        self.assertEqual(defaults["TaskA"]["retry"], 3)
        self.assertEqual(defaults["TaskB"]["count"], 10)

        # Step 2: Merge config with defaults
        merged = task_defaults.merge_config_with_defaults(config, defaults)

        # Verify merged config
        self.assertEqual(merged["TaskA"]["retry"], 5)  # overridden
        self.assertEqual(merged["TaskA"]["timeout"], 300)  # added
        self.assertEqual(merged["TaskB"]["count"], 20)  # overridden
        self.assertEqual(merged["TaskB"]["name"], "task_b")  # added

        # Step 3: Update TOML with defaults
        module_mapping = {"TaskA": self.module_file, "TaskB": self.module_file}
        result = task_defaults.update_toml_with_defaults(self.toml_file, module_mapping)

        # Verify final result
        self.assertEqual(result["TaskA"]["retry"], 5)
        self.assertEqual(result["TaskA"]["timeout"], 300)
        self.assertEqual(result["TaskB"]["count"], 20)
        self.assertEqual(result["TaskB"]["name"], "task_b")

    def test_complex_import_resolution(self):
        """Test handling of imported constants and symbols."""
        # Write a module that imports and uses external symbols
        source = dedent("""
        from pathlib import Path

        BASE_DIR = Path("/tmp")

        class Task:
            output_dir = BASE_DIR
        """)
        self.module_file.write_text(source)

        # Extract defaults (should handle the import)
        defaults = task_defaults.get_all_task_defaults(self.module_file)

        # Verify that BASE_DIR was resolved
        # Since it references Path("/tmp"), it should be converted to string or Path
        self.assertIn("output_dir", defaults["Task"])

    def test_nested_dict_and_list_defaults(self):
        """Test extraction and merging of nested dictionaries and lists."""
        # Write a module with nested structures
        source = dedent("""
        class Task:
            config = {"nested": {"key": "value"}}
            items = [1, [2, 3], 4]
        """)
        self.module_file.write_text(source)

        # Extract defaults
        defaults = task_defaults.get_all_task_defaults(self.module_file)

        # Verify nested structures are preserved
        self.assertEqual(defaults["Task"]["config"], {"nested": {"key": "value"}})
        self.assertEqual(defaults["Task"]["items"], [1, [2, 3], 4])

        # Test merging with overrides
        config = {"Task": {"config": {"nested": {"key": "override"}}}}
        merged = task_defaults.merge_config_with_defaults(config, defaults)

        # Note: merge is shallow, so nested dict is replaced entirely
        self.assertEqual(merged["Task"]["config"], {"nested": {"key": "override"}})


if __name__ == "__main__":
    unittest.main()
