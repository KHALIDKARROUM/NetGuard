"""Contract checks for the standalone, Run All analysis report."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConsolidatedNotebookChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "notebooks/00_netguard_complete.ipynb"
        cls.notebook = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_one_notebook_and_every_code_cell_executes(self):
        self.assertEqual([p.name for p in (ROOT / "notebooks").glob("*.ipynb")], [self.path.name])
        cells = self.notebook["cells"]
        self.assertEqual(len({cell["id"] for cell in cells}), len(cells))
        code = [cell for cell in cells if cell["cell_type"] == "code"]
        self.assertEqual([cell["id"] for cell in code],
                         self.notebook["metadata"]["netguard_workflow"]["executable_cell_ids"])
        for cell in code:
            self.assertIn("netguard-current", cell["metadata"]["tags"])
            self.assertFalse(any(output["output_type"] == "error" for output in cell["outputs"]))

    def test_analysis_needs_no_project_python_modules(self):
        for cell in self.notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            tree = ast.parse("".join(cell["source"]), filename=cell["id"])
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertEqual(node.level, 0)
                    modules = [node.module]
                elif isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                else:
                    continue
                self.assertFalse(any(name.split(".")[0] in {"netguard_workflow", "backend", "frontend", "scripts"}
                                     for name in modules))

    def test_original_sources_survive_consolidation(self):
        legacy = self.notebook["metadata"]["netguard_consolidation"]["legacy_sources"]
        self.assertEqual(len(legacy), 7)
        for entry in legacy:
            digest = sha256(json.dumps(entry["cells"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(digest, entry["source_sha256"])
            self.assertTrue(entry["cells"])

    def test_fresh_outputs_describe_this_run(self):
        text = "\n".join("".join(cell["source"]) for cell in self.notebook["cells"])
        self.assertIn("cloudpickle.dump", text)
        self.assertIn("single_and_batch_match", text)
        self.assertIn("RUN_EXTENDED_GENERALIZATION", text)
        self.assertNotIn("Path(__file__)", text)
        self.assertNotIn("sys.path.insert", text)


if __name__ == "__main__":
    unittest.main()
