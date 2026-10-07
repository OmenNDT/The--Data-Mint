"""Benchmark results tool — compare 6 base models for LoRA training effectiveness."""

import json
from pathlib import Path


def register(mcp, project_root: Path):
    @mcp.tool()
    def benchmark_results(model_name: str = None) -> dict:
        """Get benchmark comparison results across base models.

        Args:
            model_name: Optional filter — 'baseline', 'medxray', 'realvis', 'absreal', 'cyberreal', 'medxray-direct'
        """
        benchmark_dir = project_root / "output" / "validation"
        results_file = benchmark_dir / "validation-results.json"
        report_file = benchmark_dir / "validation-report.md"

        result = {}

        # Try reading structured results
        if results_file.exists():
            try:
                data = json.loads(results_file.read_text())
                if model_name:
                    # Filter by model name
                    filtered = {k: v for k, v in data.items() if model_name.lower() in k.lower()}
                    result["results"] = filtered if filtered else {"message": f"No results for '{model_name}'"}
                else:
                    result["results"] = data
            except (json.JSONDecodeError, OSError) as e:
                result["results_error"] = str(e)

        # Check benchmark pipeline output
        benchmark_output = project_root / "pipeline" / "config" / "benchmark"
        if benchmark_output.exists():
            result["benchmark_configs"] = [f.name for f in sorted(benchmark_output.iterdir()) if f.is_file()]

        # Include report summary if available
        if report_file.exists():
            try:
                content = report_file.read_text()
                # Return first 2000 chars as summary
                result["report_summary"] = content[:2000]
            except OSError:
                pass

        if not result:
            result["status"] = "no_benchmark_results_found"
            result["expected_paths"] = [str(results_file), str(report_file)]

        return result
