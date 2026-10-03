"""The ER decision policy file (ADR-0014)."""

from pathlib import Path

import pytest

from villasanj.entity_resolution.application.villas import DecisionPolicy
from villasanj.entity_resolution.infrastructure.policy_file import load_er_config
from villasanj.shared.application.errors import ConfigurationError

CONFIG = Path(__file__).parents[4] / "config" / "er.toml"


def test_the_repository_policy_is_the_adr_0014_operating_point() -> None:
    config = load_er_config(CONFIG)
    assert config.policy == DecisionPolicy(-0.25, -2.0, 3.0, 0.8)
    assert config.human_queue == "er-human"


@pytest.mark.parametrize(
    "text",
    [
        "[policy]\nthreshold = -0.25\n",  # incomplete
        "[policy]\nthreshold = 0\njudge_low = 3\njudge_high = -2\njudge_min_confidence = 0.8\n"
        '[human]\nqueue = "q"\n',  # an empty zone
        "not toml",
    ],
)
def test_a_bad_policy_file_is_refused(tmp_path: Path, text: str) -> None:
    path = tmp_path / "er.toml"
    path.write_text(text)
    with pytest.raises(ConfigurationError):
        load_er_config(path)
