import tempfile
import unittest
from pathlib import Path

from scripts.validate_workflows import validate_workflow


class WorkflowValidationTests(unittest.TestCase):
    def test_missing_fi_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.yml"
            path.write_text("""
name: broken
jobs:
  test:
    steps:
      - name: broken shell
        run: |
          if true; then
            echo broken
""", encoding="utf-8")
            errors = validate_workflow(path)
        self.assertTrue(errors)

    def test_github_expressions_are_sanitized_before_bash_check(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.yml"
            path.write_text("""
name: valid
jobs:
  test:
    steps:
      - name: valid shell
        run: |
          if [[ "${{ steps.plan.outputs.due == 'true' }}" == "0" ]]; then
            echo valid
          fi
""", encoding="utf-8")
            errors = validate_workflow(path)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
