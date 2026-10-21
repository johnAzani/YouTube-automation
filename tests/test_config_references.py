"""Every `CONFIG.<name>` reference in the pipeline must exist on the Config object.

The asset loop treats a provider exception as "this source missed" and moves on
(it prints, it does not fail), so a wrong attribute name used to surface only as
a misleading "Scene N has no licensed …" hard-fail in CI — with the real
`AttributeError` buried in a runner log nobody can read. Pipeline-dry-run was
red for weeks because of exactly this (`CONFIG.ASSET_CACHE_DIR`, which was only
ever a module-level constant in config.py). This test makes the whole class of
typo fail loudly in the hermetic `checks` job instead.
"""
import inspect
import pkgutil
import re
import unittest

import pipeline
from pipeline.config import CONFIG

_PATTERN = re.compile(r"\bCONFIG\.([A-Za-z_]\w*)")


class ConfigReferenceTests(unittest.TestCase):
    def test_every_config_attribute_access_exists(self):
        missing = []
        for info in pkgutil.iter_modules(pipeline.__path__):
            if info.name.startswith("_"):
                continue
            mod = __import__(f"pipeline.{info.name}", fromlist=[info.name])
            for name in sorted(set(_PATTERN.findall(inspect.getsource(mod)))):
                if not hasattr(CONFIG, name):
                    missing.append(f"pipeline/{info.name}.py: CONFIG.{name}")
        self.assertEqual(
            missing,
            [],
            "source references Config attributes that do not exist:\n" + "\n".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
