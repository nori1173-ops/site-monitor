import pathlib

import pytest
import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
STACKS_DIR = PROJECT_ROOT / "stacks"


class CfnLoader(yaml.SafeLoader):
    """CloudFormation 組み込みタグを辞書として読み込むカスタムローダー"""


CFN_TAGS = [
    "Ref", "Sub", "GetAtt", "Join", "Select", "Split",
    "If", "Equals", "And", "Or", "Not",
    "FindInMap", "Base64", "Cidr", "ImportValue",
    "GetAZs", "Transform",
]

for tag in CFN_TAGS:
    CfnLoader.add_constructor(
        f"!{tag}",
        lambda loader, node, t=tag: {
            f"Fn::{t}" if t != "Ref" else t: loader.construct_scalar(node)
            if isinstance(node, yaml.ScalarNode)
            else loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode)
            else loader.construct_mapping(node)
        },
    )


def load_template(stack_name: str) -> dict:
    path = STACKS_DIR / stack_name / "template.yaml"
    with open(path) as f:
        return yaml.load(f, Loader=CfnLoader)


@pytest.fixture
def database_template():
    return load_template("database")


@pytest.fixture
def auth_template():
    return load_template("auth")


@pytest.fixture
def queue_template():
    return load_template("queue")


@pytest.fixture
def web_template():
    return load_template("web")


@pytest.fixture
def api_template():
    return load_template("api")


@pytest.fixture
def ses_template():
    path = STACKS_DIR / "ses" / "template.yaml"
    with open(path) as f:
        return yaml.load(f, Loader=CfnLoader)


@pytest.fixture
def main_template():
    path = PROJECT_ROOT / "template.yaml"
    with open(path) as f:
        return yaml.load(f, Loader=CfnLoader)
