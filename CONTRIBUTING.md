# Contributing

Splatfold keeps its complete runtime implementation in `splatfold.py` so the
tool itself remains easy to copy and run as one file. Tests, documentation,
packaging metadata, and automation live beside it.

## Development checks

From this directory, run:

```zsh
python3 -m pip install -e ".[dev,release]"
ruff check splatfold.py tests
ruff format --check splatfold.py tests
mypy splatfold.py
python3 -m coverage run -m pytest
python3 -m coverage report
uvx zizmor .github/workflows
python3 -m compileall -q splatfold.py
validate-pyproject pyproject.toml
python3 -m build
python3 -m twine check dist/*
check-wheel-contents dist/*.whl
```

Changes to resolution or rendering semantics must include a focused regression
test. Tests should compare generated behavior with normal Python behavior when
Splatfold claims equivalence, and should make intentional differences explicit.

Before a release, install the built wheel into a clean virtual environment and
use that installed CLI—not the source checkout—to fold and run the Acute
integration fixture.
