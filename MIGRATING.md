# Migrating from Obtuse

Splatfold is the production continuation of the project previously published
on GitHub as **Obtuse**. It keeps the wildcard-include model while replacing
the prototype's script-only release process with a tested Python distribution.

## Source compatibility

Existing module-level directives remain valid:

```python
from module import *
from package.module import *
from .local import *
```

The original `-i` and `--input` CLI forms remain supported, along with the
output, root, search-path, strictness, marker, tracing, dependency-listing, and
check-only behavior. The preferred form now uses a positional input:

```zsh
splatfold main.py -o dist/app.py
```

## Names that changed

- The command and standalone implementation are now named `splatfold` and
  `splatfold.py`; no `preprocessor` or `obtuse` package is installed.
- Generated comments identify `splatfold` instead of the prototype script.
- The importable API is `splatfold.build(...)`, returning a `BuildResult` whose
  `write()` method performs the explicit filesystem mutation.

Code that invokes an old checkout as `python3 preprocessor.py ...` should
install Splatfold and invoke the `splatfold` console command instead. Existing
automation may keep `-i/--input` while migrating.

## Intentional safety changes

Several prototype behaviors were bugs and are not preserved:

- When `name.py` and `name/__init__.py` coexist on one search entry, the
  package now wins, matching Python's import system.
- A dependency `if __name__ == "__main__": ... else: ...` is rejected unless
  `--keep-main-guards` is requested; the prototype silently discarded the
  import-time `else` branch.
- Wildcard and future imports that share a physical line with another Python
  statement are rejected instead of silently deleting neighboring code.
- Output writes work on Python 3.9, are atomic, preserve appropriate file
  permissions, and refuse to overwrite any included source.
- Future features are deduplicated individually and included files missing a
  final newline cannot merge with the importing file's next statement.

These changes favor explicit failure over generating code with altered
semantics. Projects relying on a rejected edge case should first rewrite the
source into ordinary multi-line Python; `--keep-main-guards` is available only
when literal guard inclusion is genuinely intended.

## Release and packaging changes

Splatfold requires Python 3.9 or newer and has no runtime dependencies outside
the standard library. Releases provide both a universal wheel and source
distribution. The version is available as `splatfold.__version__`, and the CLI
reports the same value with `splatfold --version`.

PyPI publication uses GitHub OIDC Trusted Publishing. The obsolete Obtuse
workflow and long-lived upload tokens must not be reused.
