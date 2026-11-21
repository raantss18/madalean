#!/usr/bin/env bash
# One-command test suite for Madalean 2.0 (no GPU needed). Options:
#   --all     also the slow tests (real models + GPU; integrator only)
#   --legacy  the tests of the old PySide6 app (tests/legacy, needs PySide6 + pytest-qt), run separately
set -e
cd "$(dirname "$0")"
case "${1:-}" in
  --all)    exec .venv/bin/python -m pytest -v -p no:cacheprovider tests/ ;;
  --legacy) exec .venv/bin/python -m pytest -v -p no:cacheprovider -m "not slow" -c tests/legacy/pytest.ini --rootdir tests/legacy tests/legacy ;;
  *)        exec .venv/bin/python -m pytest -v -p no:cacheprovider -m "not slow" tests/ ;;
esac
