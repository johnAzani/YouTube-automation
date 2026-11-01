"""The queue entry point must use the approved renderer, never the legacy one."""
from pathlib import Path
from unittest.mock import patch

from pipeline.run import process


def test_queue_entry_delegates_to_approved_prayer_pipeline():
    with patch("pipeline.prayer_pipeline.produce", return_value={"ok": True}) as renderer, \
         patch("pipeline.run._disabled_legacy_process") as legacy:
        assert process(Path("queue.md"), True) == {"ok": True}
        renderer.assert_called_once()
        assert renderer.call_args.args[0] == Path("queue.md")
        legacy.assert_not_called()
