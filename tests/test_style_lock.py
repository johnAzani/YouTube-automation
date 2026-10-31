"""The unapproved long-form montage must never reach rendering or upload."""
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.run import process


@pytest.mark.parametrize("dry_run", [False, True])
def test_queue_renderer_fails_closed_before_any_side_effects(dry_run):
    with patch("pipeline.run.parse_script") as parse, \
         patch("pipeline.run._require_production_prerequisites") as prerequisites:
        with pytest.raises(RuntimeError, match="legacy montage renderer is forbidden"):
            process(Path("queue.md"), dry_run)
        parse.assert_called_once()
        prerequisites.assert_not_called()
