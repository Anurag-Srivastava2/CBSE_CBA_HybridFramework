import json
import os
from pathlib import Path
from shutil import copy2
import subprocess


class QARArtifactFixtureBuilder:
    """Invoke the artifact-tool workbook builder from an isolated temp folder."""

    DEPENDENCY_ENV = "QAR_ARTIFACT_TOOL_NODE_MODULES"

    @classmethod
    def build(
        cls,
        template_path,
        temp_dir,
        prefix,
        scenario_name,
        source_text="",
    ):
        dependency_dir = os.getenv(cls.DEPENDENCY_ENV, "").strip()
        if not dependency_dir:
            raise RuntimeError(
                f"{cls.DEPENDENCY_ENV} is required and must point to the "
                "node_modules directory returned by load_workspace_dependencies."
            )

        dependency_path = Path(dependency_dir).resolve()
        if not dependency_path.is_dir():
            raise RuntimeError(
                f"{cls.DEPENDENCY_ENV} does not exist: {dependency_path}"
            )

        temp_path = Path(temp_dir).resolve()
        temp_path.mkdir(parents=True, exist_ok=True)
        node_modules_link = temp_path / "node_modules"
        if not node_modules_link.exists():
            node_modules_link.symlink_to(dependency_path, target_is_directory=True)

        project_root = Path(__file__).resolve().parents[1]
        source_builder = project_root / "tools" / "qar_bulk_fixture_builder.mjs"
        local_builder = temp_path / "qar_bulk_fixture_builder.mjs"
        copy2(source_builder, local_builder)

        output_path = temp_path / f"{prefix} {scenario_name}.xlsx"
        scenario = {
            "prefix": prefix,
            "name": scenario_name,
            "sourceText": source_text,
        }
        process = subprocess.run(
            [
                "node",
                str(local_builder),
                str(Path(template_path).resolve()),
                str(output_path),
                json.dumps(scenario),
            ],
            cwd=temp_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"artifact-tool failed to create {scenario_name}: {process.stderr.strip()}"
            )
        evidence = json.loads(process.stdout)
        if not output_path.exists():
            raise RuntimeError(f"artifact-tool did not export {output_path}.")
        preview_path = Path(evidence["previewPath"])
        if not preview_path.exists():
            raise RuntimeError(f"artifact-tool did not render {preview_path}.")
        return evidence

