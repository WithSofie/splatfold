![](splatfold.logo.png)

**Splatfold** is a single-file Python source preprocessor. It gives local
wildcard imports an additional build-time meaning while keeping the development
source valid, ordinary Python.

> Splat modules open. Fold them into one file.

Upgrading from the former Obtuse project? See the
[migration guide](https://github.com/WithSofie/splatfold/blob/main/MIGRATING.md)
for command compatibility and intentional safety changes.

It recursively expands:

```python
from module import *
```


into the source code of the referenced local Python file, eventually producing a single combined Python file that can be distributed or executed independently.

Conceptually, it is similar to the C/C++:

```c
#include "module.c"
```

mechanism.

However, during development, your project remains a normal multi-file Python project. IDEs, LSPs, autocomplete, static analyzers, type checkers, code navigation, and refactoring tools can continue to understand the project normally.

## Installation

Splatfold requires Python 3.9 or newer. After the first PyPI release, install it
with:

```zsh
python3 -m pip install splatfold
```

For now, install a local checkout with:

```zsh
python3 -m pip install -e .
```

The project intentionally keeps its complete implementation in the standalone
`splatfold.py` module. It has no runtime dependencies outside the Python
standard library.

CI tests Splatfold on CPython 3.9 through 3.14. Splatfold uses the parser from
the interpreter that runs it, so that interpreter must understand every syntax
feature used by the input project. It validates and folds source; it does not
transpile newer Python syntax for older interpreters.

## Command-line and Python APIs

The preferred command-line form uses a positional input:

```zsh
splatfold main.py -o dist/app.py
```

The original `-i` and `--input` spellings remain supported:

```zsh
splatfold -i main.py -o dist/app.py
```

Programmatic builds do not write automatically:

```python
from splatfold import build

result = build("main.py", output="dist/app.py")
print(result.included_paths)
result.write()
```

This separation makes validation and build-system integration side-effect free
until the caller explicitly writes the validated result.

`build()` always reads, resolves, renders, and compile-checks the complete
artifact before returning. Its keyword arguments correspond to the CLI's
resolution, strictness, guard, marker, and tracing options. The returned
`BuildResult` exposes:

- `source`: validated generated Python source;
- `included_paths`: absolute paths in render order, beginning with the entry;
- `unresolved_wildcards`: preserved imports as `(source_path, module)` pairs;
- `cycles`: skipped recursion edges as `(importer, target)` pairs;
- `output_path`: the absolute default or requested destination.

`BuildResult.write()` performs the only output mutation. It uses an atomic
same-directory replacement, refuses to overwrite any included source, and
revalidates the current `source` value immediately before writing. It returns
the destination path. `SplatfoldError` is the public base exception;
`ResolutionError` identifies unresolved imports in strict mode.

The CLI returns status `0` on success and status `2` for argument, resolution,
source, rendering, validation, or write errors. Diagnostics go to standard
error; `--list-deps` writes its machine-friendly path list to standard output.
Splatfold is still pre-1.0, so incompatible public-API changes require a minor
version increment and changelog entry.

---

# 1. Basic Usage

Suppose your project looks like this:

```text
project/
├── main.py
├── tools.py
└── utils.py
```

`main.py`:

```python
from tools import *

def main():
    print(double("hello"))

if __name__ == "__main__":
    main()
```

`tools.py`:

```python
from utils import *

def double(value):
    return duplicate(value)
```

`utils.py`:

```python
def duplicate(value):
    return value + value
```

Run the following command from the `project/` directory:

```zsh
splatfold main.py
```

The preprocessor generates:

```text
main.flat.py
```

Both:

```python
from tools import *
```

and:

```python
from utils import *
```

are recursively replaced with their actual source code.

You can then run:

```zsh
python3 main.flat.py
```

---

# 2. Basic Command Format

Preferred form:

```zsh
splatfold INPUT [options]
```

The most common command is:

```zsh
splatfold main.py
```

To specify the output file:

```zsh
splatfold \
    main.py \
    -o dist/app.py
```

---

# 3. Positional input and `-i` / `--input`

The preferred positional argument specifies the entry-point Python file:

```zsh
splatfold main.py
```

For compatibility, `-i` and `--input` specify the same file:

Example:

```zsh
splatfold -i main.py
```

Equivalent to:

```zsh
splatfold --input main.py
```

The input file is the starting point of the dependency graph.

For example:

```text
main.py
    ↓
tools.py
    ↓
utils.py
```

Running:

```zsh
splatfold -i main.py
```

starts from `main.py` and recursively traces all expandable:

```python
from ... import *
```

statements.

---

# 4. `-o` / `--output`

Specifies the generated output file.

Example:

```zsh
splatfold \
    -i main.py \
    -o build/app.py
```

This generates:

```text
build/app.py
```

If `-o` is omitted:

```zsh
splatfold -i main.py
```

then:

```text
main.py
```

generates:

```text
main.flat.py
```

Likewise:

```text
server.py
```

generates:

```text
server.flat.py
```

---

# 5. Which Imports Are Expanded?

Only wildcard imports of the form:

```python
from module import *
```

are treated as include directives.

For example:

```python
from tools import *
```

is expanded if the preprocessor can resolve a local:

```text
tools.py
```

file.

---

## Imports That Are Expanded

```python
from tools import *
```

```python
from package.tools import *
```

```python
from .tools import *
```

```python
from ..common import *
```

```python
from . import *
```

An expanded wildcard import must occupy its own physical line. A trailing
comment is allowed:

```python
from tools import *  # folded by Splatfold
```

Splatfold rejects semicolon-separated forms such as
`from tools import *; ready = True`, because replacing the whole physical line
would otherwise silently discard unrelated code. Future imports that Splatfold
hoists follow the same rule.

---

## Imports That Are Not Expanded

A normal import:

```python
import tools
```

is not expanded.

A named import:

```python
from tools import helper
```

is not expanded.

An aliased import:

```python
import tools as t
```

is not expanded.

These imports remain in the generated file unchanged.

---

# 6. Standard Library and Third-Party Imports

By default, if:

```python
from something import *
```

cannot be resolved to a local Python source file, it is preserved unchanged.

For example:

```python
from math import *
```

remains:

```python
from math import *
```

in the generated output.

This allows normal standard-library and third-party imports to continue working.

---

# 7. `--strict`

If you want every wildcard import to resolve to a local source file, use:

```zsh
splatfold \
    -i main.py \
    --strict
```

For example:

```python
from nonexistent import *
```

If no local:

```text
nonexistent.py
```

can be found, normal mode:

```zsh
splatfold -i main.py
```

preserves:

```python
from nonexistent import *
```

However:

```zsh
splatfold \
    -i main.py \
    --strict
```

reports an error and stops preprocessing.

---

# 8. Module Resolution Rules

For:

```python
from tools import *
```

the preprocessor attempts to resolve:

```text
tools/__init__.py
```

or:

```text
tools.py
```

For:

```python
from package.tools import *
```

it attempts to resolve:

```text
package/tools/__init__.py
```

or:

```text
package/tools.py
```

This package-before-module order matches normal Python imports when both forms
exist on the same search-path entry.

---

# 9. `-r` / `--root`

`--root` specifies the source root used for absolute local imports.

By default:

> root = directory containing the input file

For example:

```text
project/
├── splatfold.py
├── main.py
└── lib/
    └── tools.py
```

If the source contains:

```python
from lib.tools import *
```

then:

```zsh
splatfold -i main.py
```

normally resolves it correctly.

---

If your project instead looks like:

```text
project/
├── splatfold.py
├── app/
│   └── main.py
└── src/
    └── tools.py
```

and:

```python
from tools import *
```

should resolve relative to:

```text
src/
```

use:

```zsh
splatfold \
    -i app/main.py \
    --root src
```

or the short form:

```zsh
splatfold \
    -i app/main.py \
    -r src
```

---

# 10. `-I` / `--search-path`

Additional local module search directories can be supplied with:

```text
-I / --search-path
```

Example project:

```text
project/
├── splatfold.py
├── main.py
├── src/
│   └── tools.py
└── shared/
    └── common.py
```

Run:

```zsh
splatfold \
    -i main.py \
    -I src \
    -I shared
```

`-I` may be specified multiple times.

Example:

```zsh
splatfold \
    -i main.py \
    -I src \
    -I shared \
    -I vendor
```

---

# 11. Relative Imports

Normal Python relative imports are supported.

For example:

```python
from .tools import *
```

and:

```python
from ..common import *
```

can be resolved according to the source file's package location.

Example:

```text
package/
├── main.py
├── tools.py
└── helpers/
    └── common.py
```

Modules may continue to use standard Python relative-import syntax.

---

# 12. Circular Dependencies

Circular dependencies do not cause infinite recursion.

For example:

```text
main.py
    ↓
another.py
    ↓
tools.py
    ↓
another.py
```

That is:

`main.py`

```python
from another import *
```

`another.py`

```python
from tools import *
```

`tools.py`

```python
from another import *
```

The preprocessor detects:

```text
another → tools → another
```

and stops recursively expanding that cycle.

Each source file is emitted at most once.

---

# 13. Duplicate Dependencies

For example:

```text
main.py
├── a.py
│   └── common.py
└── b.py
    └── common.py
```

Even though:

```text
common.py
```

is referenced through two different paths, it is emitted only once.

This behavior is called:

```text
include once
```

---

# 14. Default Source Markers

By default, the generated file contains structural markers such as:

```python
# >>> splatfold: begin tools.py
```

and:

```python
# <<< splatfold: end tools.py
```

These indicate which generated sections came from which dependency.

Example:

```python
# >>> splatfold: begin tools.py

def double(value):
    return value * 2

# <<< splatfold: end tools.py
```

Circular or duplicate includes may also produce explanatory comments.

These markers are useful for:

* reading generated files;
* debugging;
* understanding dependencies;
* identifying source boundaries.

---

# 15. `--no-markers`

To generate a cleaner output file:

```zsh
splatfold \
    -i main.py \
    --no-markers
```

This disables structural comments such as:

```python
# >>> splatfold: begin ...
```

and:

```python
# <<< splatfold: end ...
```

The actual Python code is unaffected.

---

# 16. `--inline-source-map`

If you want each generated line to indicate which original file and line number it came from, use:

```zsh
splatfold \
    -i main.py \
    --inline-source-map
```

For example, if line 70 of:

```text
main.py
```

contains:

```python
print("hello")
```

the output becomes:

```python
print("hello") # main.py 70
```

Example:

```python
def main(): # main.py 68
    message = "hello" # main.py 69
    print(message) # main.py 70
```

Dependencies are traced in the same way:

```python
def double(value): # tools.py 21
    return value * 2 # tools.py 22
```

This is useful for:

* debugging;
* inspecting flattened output;
* comparing generated code to source files;
* quickly locating original code.

---

## Inline Source Map Safety Rules

The preprocessor does not add inline comments where doing so would change Python semantics.

For example:

```python
MESSAGE = """hello
world
"""
```

must not become:

```python
MESSAGE = """hello # main.py 10
world # main.py 11
"""
```

because the inserted text would become part of the string.

Therefore, such lines are not forcibly annotated.

---

Likewise:

```python
value = 1 + \
    2
```

must not become:

```python
value = 1 + \ # main.py 20
```

because that would break Python syntax.

Therefore:

> `--inline-source-map` annotates source lines whenever it is safe to do so, but never at the cost of changing program behavior.

---

# 17. `--source-marker`

The second source-tracing mode is:

```zsh
splatfold \
    -i main.py \
    --source-marker
```

Instead of adding a comment after every line, it inserts source-location markers before contiguous source regions.

For example:

```python
# >>> splatfold: source main.py:70
print("hello")
```

Or:

```python
# >>> splatfold: source main.py:68
def main():
    message = "hello"
    print(message)
```

This indicates that the first source line after the marker corresponds to:

```text
main.py:68
```

and subsequent uninterrupted source lines continue from there.

---

If preprocessing switches to another dependency:

```python
# >>> splatfold: source main.py:20

def foo():
    pass

# >>> splatfold: source tools.py:1

def helper():
    pass

# >>> splatfold: source main.py:24

def bar():
    pass
```

This representation is more compact than an inline source map.

---

# 18. `--inline-source-map` vs. `--source-marker`

### Inline Source Map

Use:

```zsh
--inline-source-map
```

Output:

```python
x = 10 # main.py 20
y = 20 # main.py 21
print(x + y) # main.py 22
```

Advantages:

* source location is visible on every annotated line;
* very convenient for debugging.

Disadvantages:

* generated output is longer;
* source comments are more visually intrusive.

---

### Source Marker

Use:

```zsh
--source-marker
```

Output:

```python
# >>> splatfold: source main.py:20
x = 10
y = 20
print(x + y)
```

Advantages:

* cleaner output;
* closer to the original source;
* source provenance is still preserved.

For normal inspection, prefer:

```zsh
--source-marker
```

For detailed debugging, prefer:

```zsh
--inline-source-map
```

---

# 19. The Two Source-Tracing Modes Are Mutually Exclusive

Do not use:

```zsh
splatfold \
    -i main.py \
    --inline-source-map \
    --source-marker
```

at the same time.

These options are mutually exclusive.

Choose one source-tracing mode.

---

# 20. `--source-marker` with `--no-markers`

This is a useful combination:

```zsh
splatfold \
    -i main.py \
    --source-marker \
    --no-markers
```

Structural markers such as:

```python
# >>> splatfold: begin tools.py
```

are disabled.

However, source-location markers such as:

```python
# >>> splatfold: source tools.py:20
```

are still generated.

This gives relatively clean output while retaining source tracing.

---

# 21. `if __name__ == "__main__"`

Suppose a dependency:

```text
tools.py
```

contains:

```python
def helper():
    pass

if __name__ == "__main__":
    print("testing tools")
```

Under normal Python imports:

```python
from tools import *
```

the following code does not execute:

```python
print("testing tools")
```

Blindly flattening the entire file would change that behavior.

Therefore, by default, the preprocessor removes conventional top-level:

```python
if __name__ == "__main__":
```

blocks from dependency files.

However, the root input file's own:

```python
if __name__ == "__main__":
    main()
```

block is preserved.

A dependency guard with an `else` clause is not a conventional removable main
guard: normal importing executes that `else` branch. Splatfold therefore fails
with a clear error instead of silently deleting live code. Rewrite that module
so import-time definitions live outside the guard, or use
`--keep-main-guards` when literal inclusion is intentionally desired.

---

# 22. `--keep-main-guards`

If you intentionally want dependency:

```python
if __name__ == "__main__":
```

blocks to remain in the output, use:

```zsh
splatfold \
    -i main.py \
    --keep-main-guards
```

This option is generally not recommended.

Use it only when you explicitly want behavior closer to literal textual inclusion.

---

# 23. `from __future__ import ...`

The preprocessor automatically handles special imports such as:

```python
from __future__ import annotations
```

Python requires future imports to appear near the beginning of the module.

Therefore, if a dependency contains:

```python
from __future__ import annotations
```

the preprocessor does not simply copy it into the middle of the generated file.

Instead it:

1. collects future imports;
2. deduplicates them;
3. removes them from their original positions;
4. places them in a valid position near the top of the final module.

For example:

```python
"""Application."""

from __future__ import annotations
```

remains a valid module structure.

Users normally do not need to handle this manually.

---

# 24. Source Encodings

The preprocessor uses Python's own source-encoding detection rules.

For example:

```python
# -*- coding: latin-1 -*-
```

is supported.

Different dependencies may use different encodings.

The final generated file is always written as:

```text
UTF-8
```

Therefore, source files do not need to be manually converted first.

---

# 25. Shebang Handling

If the root input file begins with:

```python
#!/usr/bin/env python3
```

the shebang is preserved in the generated file.

Dependency shebangs are not treated as additional final-file shebangs.

---

# 26. `--check-only`

To verify that the project can be flattened successfully without writing an output file, use:

```zsh
splatfold \
    -i main.py \
    --check-only
```

This still performs:

1. dependency discovery;
2. source parsing;
3. circular dependency detection;
4. preprocessing;
5. flattening;
6. final Python syntax validation.

However, it does not write:

```text
main.flat.py
```

This is useful for validation before a build.

A recommended workflow is:

```zsh
splatfold \
    -i main.py \
    --check-only
```

and, if that succeeds:

```zsh
splatfold -i main.py
```

---

# 27. `--list-deps`

To display the source files used by the build:

```zsh
splatfold \
    -i main.py \
    --list-deps
```

Example output:

```text
main.py
another.py
tools.py
common.py
```

The files are shown in their actual processing/inclusion order.

This is useful for:

* checking dependencies;
* detecting unexpectedly included files;
* debugging module resolution.

---

# 28. `-v` / `--verbose`

Enable verbose diagnostics:

```zsh
splatfold \
    -i main.py \
    -v
```

or:

```zsh
splatfold \
    -i main.py \
    --verbose
```

This prints additional information about dependency resolution, unresolved imports, circular dependencies, and related processing.

A useful debugging command is:

```zsh
splatfold \
    -i main.py \
    --check-only \
    --list-deps \
    -v
```

---

# 29. Displaying the Version

Run:

```zsh
splatfold --version
```

Current version:

```text
splatfold 0.2.0
```

---

# 30. Displaying CLI Help

Run:

```zsh
splatfold --help
```

or:

```zsh
splatfold -h
```

to display all available command-line options.

---

# 31. Recommended Development Workflow

During development, keep the project as a normal multi-file Python project:

```text
project/
├── main.py
├── tools.py
├── parser.py
├── utils.py
└── splatfold.py
```

Write normal Python imports such as:

```python
from tools import *
from parser import *
```

Your IDE continues to treat them as regular Python modules.

---

During development, run the original project normally:

```zsh
python3 main.py
```

---

To validate flattening:

```zsh
splatfold \
    -i main.py \
    --check-only \
    --list-deps
```

---

To create a debugging build:

```zsh
splatfold \
    -i main.py \
    --inline-source-map
```

---

To create relatively clean output while retaining source tracing:

```zsh
splatfold \
    -i main.py \
    --source-marker \
    --no-markers
```

---

For a clean release build:

```zsh
splatfold \
    -i main.py \
    -o dist/app.py \
    --no-markers
```

---

Finally, test the generated file:

```zsh
python3 dist/app.py
```

---

# 32. Recommended Debugging Command

If something goes wrong, first run:

```zsh
splatfold \
    -i main.py \
    --check-only \
    --list-deps \
    -v
```

This allows you to:

* avoid modifying any output file;
* inspect dependencies;
* inspect module resolution;
* validate the final Python source.

If additional source-level tracing is needed:

```zsh
splatfold \
    -i main.py \
    --inline-source-map
```

Then inspect:

```text
main.flat.py
```

and its:

```python
# filename.py LINE
```

annotations.

---

# 33. Syntax Errors

If any source file contains invalid Python syntax, for example:

```python
def hello(
    print("hello")
```

the preprocessor detects the error before generating the final output.

The error report includes:

* filename;
* line number;
* column number;
* Python's syntax error message.

The final flattened output is also validated with:

```python
compile()
```

Therefore:

> Individual source files being valid does not guarantee that the flattened result is valid. The final output is checked again.

---

# 34. The Preprocessor Does Not Execute Project Source Code

During preprocessing, the tool only:

* reads source code;
* parses source code;
* analyzes imports;
* generates source code;
* compile-checks source code.

It does not discover dependencies by executing:

```python
import your_module
```

and it does not use:

```python
exec(...)
```

to run project source code.

Therefore, preprocessing itself does not trigger module runtime side effects.

---

# 35. Complete Example

Project:

```text
project/
├── splatfold.py
├── main.py
├── another.py
└── tools.py
```

`main.py`:

```python
from another import *

def run():
    print(double_string("21"))

if __name__ == "__main__":
    run()
```

`another.py`:

```python
from tools import *

def is_string(value):
    return isinstance(value, str)
```

`tools.py`:

```python
from another import *

def double_string(value):
    if is_string(value):
        return str(int(value) * 2)

    return value
```

This contains a circular dependency:

```text
another
    ↓
tools
    ↓
another
```

Run:

```zsh
splatfold \
    -i main.py \
    --source-marker
```

The preprocessor:

1. reads `main.py`;
2. resolves `another.py`;
3. resolves `tools.py`;
4. encounters `another.py` again;
5. detects the cycle;
6. does not expand the same source file again;
7. generates a single:

   ```text
   main.flat.py
   ```
8. validates the final Python syntax.

Then run:

```zsh
python3 main.flat.py
```

Expected output:

```text
42
```

---

# 36. When Should You Use This Tool?

This tool is suitable when you:

* want to develop a normal multi-file Python project;
* want to distribute a single Python file;
* want IDE and LSP support during development;
* do not want to introduce a custom `#include` syntax;
* are building small utilities;
* are building single-file CLIs;
* are building scripts;
* are building plugins;
* want easily distributable Python source;
* are experimenting with compiler/preprocessor-style tooling.

---

# 37. When Should You Not Use It?

If the application heavily depends on true Python module namespaces, for example:

```python
import foo

foo.value
```

or relies heavily on:

```python
__name__
__package__
__file__
sys.modules
```

as well as complex:

* import hooks;
* plugin systems;
* dynamic imports;
* module initialization side effects;
* C extension modules;

then you should not assume that flattened behavior will always exactly match the original multi-module project.

Splatfold deliberately expands only module-level wildcard imports. Imports
inside functions, classes, conditionals, and exception handlers remain normal
Python imports.

Included modules share one generated global namespace. Unlike normal module
imports, flattening does not preserve a private namespace per source file, and
`__all__` does not hide definitions that are physically present in the combined
file. Projects should therefore avoid conflicting top-level names and should
not depend on module-specific metadata or initialization isolation.

Collected `from __future__ import ...` statements are hoisted to the generated
module header, as Python requires. A future feature used by one dependency
therefore applies to the entire generated module; projects should keep future
feature choices consistent across their source tree.

This tool is a:

```text
source preprocessor / source flattener
```

not a complete:

```text
Python import system emulator
```

---

# 38. Most Important Design Rule

Development source code should continue to use normal Python:

```python
from tools import *
```

Your IDE understands it as normal Python.

The preprocessor simply gives that existing syntax an additional build-time meaning:

> Include this local module's source code in the generated single-file output.

Therefore:

> Keep the original multi-file project as the real source code.

Treat:

```text
*.flat.py
```

as:

> automatically generated build artifacts.

Do not manually edit `.flat.py`.

Make changes in the original:

```text
.py
```

files, then run the preprocessor again.

---

# 39. Common Command Reference

Basic build:

```zsh
splatfold -i main.py
```

Specify output:

```zsh
splatfold \
    -i main.py \
    -o app.py
```

Validation only:

```zsh
splatfold \
    -i main.py \
    --check-only
```

List dependencies:

```zsh
splatfold \
    -i main.py \
    --list-deps
```

Verbose diagnostics:

```zsh
splatfold \
    -i main.py \
    --check-only \
    --list-deps \
    -v
```

Inline source tracing:

```zsh
splatfold \
    -i main.py \
    --inline-source-map
```

Source-marker tracing:

```zsh
splatfold \
    -i main.py \
    --source-marker
```

Clean source-marker build:

```zsh
splatfold \
    -i main.py \
    --source-marker \
    --no-markers
```

Clean release build:

```zsh
splatfold \
    -i main.py \
    -o dist/app.py \
    --no-markers
```

Strict build:

```zsh
splatfold \
    -i main.py \
    --strict
```

Additional module search paths:

```zsh
splatfold \
    -i main.py \
    -I src \
    -I shared
```

Display help:

```zsh
splatfold --help
```

Display version:

```zsh
splatfold --version
```
