import inspect
import sys
import unittest
from typing import List

from data_juicer.tools.DJ_mcp_granular_ops import (
    process_parameter,
    resolve_signature_annotations,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


# --- Helper functions for testing resolve_signature_annotations ---

def func_with_annotations(x: int, y: str) -> float:
    """A simple function with annotations."""
    pass


def func_without_annotations(x, y):
    """A function without any type annotations."""
    pass


def func_with_complex_annotations(items: List[int], name: str) -> List[str]:
    """A function with complex annotations."""
    pass


def func_with_return_only(x, y) -> int:
    """A function with only a return annotation."""
    pass


class TestResolveSignatureAnnotations(DataJuicerTestCaseBase):
    """Tests for resolve_signature_annotations."""

    def test_regular_annotations_resolved_correctly(self):
        """Given a function with regular annotations, returns correct
        signature with those types."""
        sig = inspect.signature(func_with_annotations)
        resolved = resolve_signature_annotations(func_with_annotations, sig)

        params = resolved.parameters
        self.assertEqual(params['x'].annotation, int)
        self.assertEqual(params['y'].annotation, str)
        self.assertEqual(resolved.return_annotation, float)

    def test_function_without_annotations_unchanged(self):
        """Given a function without annotations, returns same signature
        unchanged."""
        sig = inspect.signature(func_without_annotations)
        resolved = resolve_signature_annotations(func_without_annotations, sig)

        params = resolved.parameters
        self.assertEqual(params['x'].annotation, inspect.Parameter.empty)
        self.assertEqual(params['y'].annotation, inspect.Parameter.empty)
        self.assertEqual(resolved.return_annotation, inspect.Signature.empty)

    def test_complex_annotations_resolved(self):
        """Given a function with complex annotations (e.g. List[int]),
        returns correct resolved types."""
        sig = inspect.signature(func_with_complex_annotations)
        resolved = resolve_signature_annotations(
            func_with_complex_annotations, sig
        )

        params = resolved.parameters
        self.assertEqual(params['items'].annotation, List[int])
        self.assertEqual(params['name'].annotation, str)
        self.assertEqual(resolved.return_annotation, List[str])

    def test_return_annotation_resolved(self):
        """Return annotation is also resolved when present."""
        sig = inspect.signature(func_with_return_only)
        resolved = resolve_signature_annotations(func_with_return_only, sig)

        self.assertEqual(resolved.return_annotation, int)
        # Parameters without annotations remain empty
        params = resolved.parameters
        self.assertEqual(params['x'].annotation, inspect.Parameter.empty)
        self.assertEqual(params['y'].annotation, inspect.Parameter.empty)

    def test_get_type_hints_raises_falls_back(self):
        """When get_type_hints raises, gracefully falls back to original
        annotations."""
        # Create a function whose __module__ points to a non-existent module
        # so that get_type_hints will fail
        def bad_func(x: int, y: str) -> float:
            pass

        # Corrupt the module reference to trigger an exception in
        # get_type_hints
        bad_func.__module__ = '__non_existent_module_xyz__'
        # Ensure the module is not in sys.modules
        sys.modules.pop('__non_existent_module_xyz__', None)

        sig = inspect.signature(bad_func)

        # Even though __module__ is invalid, the function should still work
        # because get_type_hints may still succeed or fail gracefully.
        # We force failure by adding a bad annotation string.
        bad_func.__annotations__ = {
            'x': 'NonExistentType',
            'y': 'AnotherBadType',
            'return': 'BadReturn',
        }

        # Rebuild sig after annotation change
        sig = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    'x',
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation='NonExistentType',
                ),
                inspect.Parameter(
                    'y',
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation='AnotherBadType',
                ),
            ],
            return_annotation='BadReturn',
        )

        resolved = resolve_signature_annotations(bad_func, sig)

        # Should fall back to original string annotations since
        # get_type_hints cannot resolve them
        params = resolved.parameters
        self.assertEqual(params['x'].annotation, 'NonExistentType')
        self.assertEqual(params['y'].annotation, 'AnotherBadType')
        self.assertEqual(resolved.return_annotation, 'BadReturn')


class TestProcessParameter(DataJuicerTestCaseBase):
    """Tests for process_parameter."""

    def test_normal_int_annotation_unchanged(self):
        """With a normal annotation like int, returns parameter unchanged."""
        param = inspect.Parameter(
            'x', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int
        )
        result = process_parameter('x', param)
        self.assertEqual(result.annotation, int)
        self.assertEqual(result.name, 'x')

    def test_normal_str_annotation_unchanged(self):
        """With a normal annotation like str, returns parameter unchanged."""
        param = inspect.Parameter(
            'name', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
        )
        result = process_parameter('name', param)
        self.assertEqual(result.annotation, str)
        self.assertEqual(result.name, 'name')

    def test_no_annotation_unchanged(self):
        """With no annotation (empty), returns parameter unchanged."""
        param = inspect.Parameter(
            'val', inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        result = process_parameter('val', param)
        self.assertEqual(result.annotation, inspect.Parameter.empty)

    def test_jsonargparse_not_loaded_returns_unchanged(self):
        """When jsonargparse.typing module is not loaded, returns parameter
        unchanged because there is no ClosedUnitInterval to match."""
        # Temporarily remove jsonargparse.typing from sys.modules if present
        saved = sys.modules.pop('jsonargparse.typing', None)
        try:
            param = inspect.Parameter(
                'ratio',
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=float,
            )
            result = process_parameter('ratio', param)
            self.assertEqual(result.annotation, float)
            self.assertEqual(result.name, 'ratio')
        finally:
            if saved is not None:
                sys.modules['jsonargparse.typing'] = saved

    def test_parameter_with_default_preserved(self):
        """Parameter default value is preserved through processing."""
        param = inspect.Parameter(
            'count',
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=int,
            default=10,
        )
        result = process_parameter('count', param)
        self.assertEqual(result.annotation, int)
        self.assertEqual(result.default, 10)
        self.assertEqual(result.name, 'count')


if __name__ == '__main__':
    unittest.main()
