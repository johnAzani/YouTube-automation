"""Dashboard writers must use code and data from the staged tree, not stale jobs."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DashboardSnapshotWorkflowTests(unittest.TestCase):
    def test_writers_execute_staged_code_against_staged_data(self):
        for workflow in ('produce.yml', 'monitor.yml'):
            with self.subTest(workflow=workflow), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                (repo / 'scripts').mkdir()
                (repo / 'docs').mkdir()
                (repo / 'scripts' / '__init__.py').write_text('')
                generator = repo / 'scripts' / 'build_dashboard_data.py'
                generator.write_text(
                    'import argparse\nfrom pathlib import Path\n'
                    'p = argparse.ArgumentParser()\n'
                    'p.add_argument("--repo-root", type=Path)\n'
                    'p.add_argument("--out", type=Path)\n'
                    'a = p.parse_args()\n'
                    'a.out.write_text("current-code:" + (a.repo_root / "data.txt").read_text())\n'
                )
                (repo / 'data.txt').write_text('current-data')
                (repo / 'docs' / 'network-state.json').write_text('old-dashboard')
                subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
                subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
                # Simulate reset --mixed: index is current main, worktree is old.
                generator.write_text('raise RuntimeError("stale generator ran")\n')
                (repo / 'data.txt').write_text('stale-data')
                data = yaml.safe_load((ROOT / '.github' / 'workflows' / workflow).read_text())
                steps = [s for j in data['jobs'].values() for s in j.get('steps', [])]
                step = next(s for s in steps if s.get('name') == (
                    'Commit queue state (job moved to published/)' if workflow == 'produce.yml'
                    else 'Commit the monitor snapshot'))
                script = step['run']
                start = script.index('idx_dir="$(mktemp -d)"')
                end = script.index('rm -rf "$idx_dir"', start) + len('rm -rf "$idx_dir"')
                env = dict(os.environ, PYTHONPATH=str(repo))  # hostile stale import path
                subprocess.run(['bash', '-e', '-c', script[start:end]], cwd=repo,
                               env=env, check=True, capture_output=True, text=True)
                staged = subprocess.check_output(['git', 'show', ':docs/network-state.json'],
                                                 cwd=repo, text=True)
                self.assertEqual(staged, 'current-code:current-data')


if __name__ == '__main__':
    unittest.main()
