"""cfn-lint による CloudFormation テンプレート検証"""

import pathlib
import subprocess

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]

TEMPLATE_FILES = [
    PROJECT_ROOT / "template.yaml",
    PROJECT_ROOT / "stacks" / "database" / "template.yaml",
    PROJECT_ROOT / "stacks" / "auth" / "template.yaml",
    PROJECT_ROOT / "stacks" / "queue" / "template.yaml",
    PROJECT_ROOT / "stacks" / "web" / "template.yaml",
    PROJECT_ROOT / "stacks" / "ses" / "template.yaml",
    PROJECT_ROOT / "stacks" / "api" / "template.yaml",
]


def _cfn_lint_available() -> bool:
    try:
        result = subprocess.run(
            ["cfn-lint", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _cfn_lint_available(), reason="cfn-lint not installed")
@pytest.mark.parametrize(
    "template_path",
    TEMPLATE_FILES,
    ids=[str(p.relative_to(PROJECT_ROOT)) for p in TEMPLATE_FILES],
)
def test_cfn_lint_no_errors(template_path: pathlib.Path) -> None:
    assert template_path.exists(), f"{template_path} が存在しない"

    result = subprocess.run(
        [
            "cfn-lint",
            str(template_path),
            "--include-checks", "E",
            "--region", "ap-northeast-1",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        errors = result.stdout.strip() or result.stderr.strip()
        pytest.fail(f"cfn-lint errors in {template_path.name}:\n{errors}")
