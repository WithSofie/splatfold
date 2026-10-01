# Splatfold design contract

Splatfold is a source preprocessor, not an import-system emulator. It gives a
restricted set of valid Python wildcard imports an additional build-time
meaning: include the referenced local source once at the import location.

## Invariants

1. Development sources remain valid Python and continue to work without
   Splatfold when their ordinary imports are valid.
2. Project source is read and parsed, never imported or executed during a
   build.
3. Only module-level `from ... import *` statements are candidates for local
   inclusion. Every other import is preserved.
4. A source file is emitted at most once. Active recursion edges are reported
   as cycles and omitted from the generated module.
5. The generated source is UTF-8 and is compiled for syntax validity both when
   built and immediately before it can be written.
6. Writing is explicit in the Python API and atomic with respect to the final
   destination path.
7. The input and every included source path are protected from accidental
   output overwrite, including filesystem aliases of the same file.
8. The implementation remains a standalone standard-library-only Python file.

## Resolution

Absolute imports are searched in `root` followed by each configured search
path. Relative imports are resolved from the importing file. On each path
entry, `name/__init__.py` takes precedence over `name.py`, matching Python.

An unresolved wildcard import is preserved by default because it may refer to
the standard library or an installed dependency. Strict mode rejects it.

## Rendering

Inclusion is depth-first at the original import location. Dependency shebangs
and encoding cookies are removed. The root shebang is retained and the output
declares UTF-8. Future imports are deduplicated and hoisted after the root
module docstring.

Conventional dependency `if __name__ == "__main__":` blocks without `else`
are removed by default. A guard with `else` is rejected because deleting the
whole statement would discard code that normal importing executes.

Statements that Splatfold removes or replaces must occupy their own physical
lines. A trailing comment is allowed. Sharing such a line with another Python
statement is rejected explicitly rather than risking silent loss of code.

## Intentional limits

All included definitions share one global namespace. Per-module values of
`__name__`, `__package__`, `__file__`, module dictionaries, `sys.modules`
entries, import hooks, and initialization isolation are not reproduced.
`__all__` remains ordinary source metadata but does not hide code that has been
physically included.

These limits are fundamental to source folding and must remain visible in user
documentation and tests.
