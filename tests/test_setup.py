import ast
import pathlib
import unittest


class SetupPyTests(unittest.TestCase):
    def test_runtime_dependencies_include_wcwidth(self):
        setup_py = pathlib.Path(__file__).resolve().parents[1] / "setup.py"
        module = ast.parse(setup_py.read_text())

        setup_call = next(
            node.value
            for node in module.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "setup"
        )
        install_requires = next(
            keyword.value
            for keyword in setup_call.keywords
            if keyword.arg == "install_requires"
        )
        deps = [elt.value for elt in install_requires.elts]

        self.assertIn("wcwidth", deps)


if __name__ == "__main__":
    unittest.main()
