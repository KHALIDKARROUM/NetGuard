"""Refresh explanatory report text from verified results without refitting."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netguard_workflow.generalization_report import render_report
from netguard_workflow.workflow import file_sha256


def main():
    report_path = ROOT/"data/reports/generalization.json"
    manifest_path = ROOT/"artifacts/generalization/manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for name, digest in report["source_sha256"].items():
        if name != "netguard_workflow/generalization_report.py" and file_sha256(ROOT/name) != digest:
            raise ValueError("Evaluation implementation changed; regenerate results before rendering.")
    renderer = "netguard_workflow/generalization_report.py"
    report["source_sha256"][renderer] = file_sha256(ROOT/renderer)
    report["report_rendered_utc"] = datetime.now(timezone.utc).isoformat()
    (ROOT/"notebooks/GENERALIZATION.md").write_text(render_report(report), encoding="utf-8", newline="\n")
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(report)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    print("Explanatory report refreshed; fitted models, scores, thresholds and intervals unchanged")


if __name__ == "__main__":
    main()
