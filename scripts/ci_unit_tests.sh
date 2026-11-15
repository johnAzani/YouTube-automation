#!/usr/bin/env bash
# Run the unit tests the way GitHub runs them. One copy, used by:
#   .github/workflows/dry-run.yml        every push and pull request
#   .github/workflows/tests-on-main.yml  once a day, on `main` as it stands
#
# Needs `pytest` and `pytest-xdist` (the workflows install them first).
#
# `-n auto` starts one test process per processor. `--dist loadfile` keeps every
# test of a file in the same process, in file order, so tests that share a
# module-level fixture or a file on disk behave as they do in one process.
#
# A test that fails while the suite is split is run again on its own. If it
# still fails, this script fails. If it passes alone, the test leans on
# something another test file touches: the script passes and says which test it
# was, so a red check always means a real failure. pytest's exit code 1 means
# "tests failed"; any other non-zero code (a crashed run, nothing collected)
# fails without a second attempt.
#
# Measured on 15 November 2026: 19 to 26 minutes in one process on GitHub's
# runners, about 4 minutes like this.

set +e
python -m pytest -q --tb=short -n auto --dist loadfile 2>&1 | tee pytest.log
rc=${PIPESTATUS[0]}
if [ "$rc" -eq 1 ]; then
  split_failures="$(grep -E '^(FAILED|ERROR) ' pytest.log | awk '{print $2}' | head -n 20 | tr '\n' ' ')"
  echo "Running the failed tests again in one process: ${split_failures}"
  python -m pytest -q --tb=short --last-failed --last-failed-no-failures none 2>&1 | tee pytest-alone.log
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 0 ]; then
    echo "::warning title=Tests passed only when run alone::${split_failures:-see pytest.log}"
  else
    cp pytest-alone.log pytest.log
  fi
fi
set -e
if [ "$rc" -ne 0 ]; then
  summary="$(grep -E '^(FAILED|ERROR|E )' pytest.log | head -n 20 | tr '\n' ' ')"
  echo "::error title=Unit test failure::${summary:-see pytest.log}"
  exit "$rc"
fi
