from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import splatfold


def write(path: Path, source: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding=encoding)
    return path


def run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_recursive_build_and_write(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "from tools import *\nprint(double('x'))\n",
    )
    write(
        tmp_path / "tools.py",
        "from util import *\ndef double(value):\n    return duplicate(value)\n",
    )
    write(
        tmp_path / "util.py",
        "def duplicate(value):\n    return value + value\n",
    )

    result = splatfold.build(entry, markers=False)
    assert result.output_path == tmp_path / "main.flat.py"
    assert not result.output_path.exists()
    assert [path.name for path in result.included_paths] == [
        "main.py",
        "tools.py",
        "util.py",
    ]

    output = result.write()
    completed = run(output)
    assert completed.returncode == 0
    assert completed.stdout == "xx\n"


def test_cycle_is_skipped_and_reported(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "from another import *\nprint(double_string('21'))\n",
    )
    write(
        tmp_path / "another.py",
        "from tools import *\ndef is_string(value):\n    return isinstance(value, str)\n",
    )
    write(
        tmp_path / "tools.py",
        "from another import *\ndef double_string(value):\n"
        "    return str(int(value) * 2) if is_string(value) else value\n",
    )

    result = splatfold.build(entry)
    output = result.write()
    completed = run(output)
    assert completed.returncode == 0
    assert completed.stdout == "42\n"
    assert len(result.cycles) == 1
    assert "cycle" in result.source


def test_duplicate_dependency_is_emitted_once(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "from a import *\nfrom b import *\nprint(answer())\n",
    )
    write(tmp_path / "a.py", "from common import *\n")
    write(tmp_path / "b.py", "from common import *\n")
    write(tmp_path / "common.py", "def answer():\n    return 42\n")

    result = splatfold.build(entry)
    assert result.source.count("def answer") == 1
    assert "already included" in result.source


@pytest.mark.parametrize("markers", [False, True])
def test_dependency_without_final_newline_does_not_join_following_source(
    tmp_path: Path, markers: bool
) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\nprint(value)\n")
    write(tmp_path / "dep.py", "value = 7")

    result = splatfold.build(entry, markers=markers)
    assert "value = 7\n" in result.source
    completed = run(result.write())
    assert completed.returncode == 0
    assert completed.stdout == "7\n"


def test_future_import_shebang_and_dependency_main_guard(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        '#!/usr/bin/env python3\n"""Application."""\nfrom dep import *\nprint(value)\n',
    )
    write(
        tmp_path / "dep.py",
        "from __future__ import annotations\nvalue: Missing = 3\n"
        "if __name__ == '__main__':\n    print('dependency main')\n",
    )

    result = splatfold.build(entry, markers=False)
    assert result.source.startswith("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-")
    assert '"""Application."""\nfrom __future__ import annotations' in result.source
    assert "dependency main" not in result.source
    completed = run(result.write())
    assert completed.returncode == 0
    assert completed.stdout == "3\n"


def test_future_features_are_deduplicated_individually(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from a import *\nfrom b import *\n")
    write(
        tmp_path / "a.py",
        "from __future__ import annotations, generator_stop\na = 1\n",
    )
    write(tmp_path / "b.py", "from __future__ import annotations\nb = 2\n")

    result = splatfold.build(entry, markers=False)
    assert result.source.count("from __future__ import annotations") == 1
    assert result.source.count("from __future__ import generator_stop") == 1
    compile(result.source, str(result.output_path), "exec")


@pytest.mark.parametrize(
    "source",
    [
        "before = 1; from dep import *\n",
        "from dep import *; after = 2\n",
    ],
)
def test_local_wildcard_import_must_occupy_its_own_line(
    tmp_path: Path, source: str
) -> None:
    entry = write(tmp_path / "main.py", source)
    write(tmp_path / "dep.py", "value = 1\n")

    with pytest.raises(
        splatfold.PreprocessorError,
        match=r"local wildcard import.*must occupy its own physical line",
    ):
        splatfold.build(entry)


def test_future_import_must_occupy_its_own_line(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "from __future__ import annotations; value = 1\n",
    )

    with pytest.raises(
        splatfold.PreprocessorError,
        match=r"future import.*must occupy its own physical line",
    ):
        splatfold.build(entry)


def test_future_import_rejects_root_docstring_sharing_a_line(
    tmp_path: Path,
) -> None:
    entry = write(
        tmp_path / "main.py",
        '"""Application."""; marker = 1\nfrom dep import *\n',
    )
    write(tmp_path / "dep.py", "from __future__ import annotations\nvalue = 1\n")

    with pytest.raises(
        splatfold.PreprocessorError,
        match="docstring that shares a physical line",
    ):
        splatfold.build(entry)


def test_rewritten_import_allows_a_trailing_comment(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "from dep import *  # folded dependency\nprint(value)\n",
    )
    write(
        tmp_path / "dep.py",
        "from __future__ import annotations  # required\nvalue = 3\n",
    )

    completed = run(splatfold.build(entry).write())
    assert completed.returncode == 0
    assert completed.stdout == "3\n"


def test_unresolved_wildcard_is_preserved_unless_strict(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from math import *\nprint(sqrt(9))\n")

    result = splatfold.build(entry)
    assert "from math import *" in result.source
    assert result.unresolved_wildcards == [(entry.resolve(), "math")]

    with pytest.raises(splatfold.ResolutionError, match="cannot resolve wildcard"):
        splatfold.build(entry, strict=True)


def test_package_wins_over_same_named_module(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from both import *\nprint(value)\n")
    write(tmp_path / "both.py", "value = 'module'\n")
    write(tmp_path / "both" / "__init__.py", "value = 'package'\n")

    completed = run(splatfold.build(entry, markers=False).write())
    assert completed.returncode == 0
    assert completed.stdout == "package\n"


def test_dependency_main_guard_with_else_fails_safely(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\nprint(value)\n")
    write(
        tmp_path / "dep.py",
        "if __name__ == '__main__':\n    value = 'main'\nelse:\n    value = 'imported'\n",
    )

    with pytest.raises(splatfold.PreprocessorError, match="else clause"):
        splatfold.build(entry)


def test_relative_import_and_search_path(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "app" / "main.py",
        "from .local import *\nfrom shared import *\nprint(local + shared)\n",
    )
    write(tmp_path / "app" / "local.py", "local = 20\n")
    shared = tmp_path / "shared-src"
    write(shared / "shared.py", "shared = 22\n")

    result = splatfold.build(
        entry,
        root=tmp_path / "app",
        search_paths=[shared],
        markers=False,
    )
    completed = run(result.write())
    assert completed.returncode == 0
    assert completed.stdout == "42\n"


def test_source_tracing_modes_are_mutually_exclusive(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n")
    with pytest.raises(splatfold.PreprocessorError, match="mutually exclusive"):
        splatfold.build(entry, inline_source_map=True, source_marker=True)


def test_inline_source_map_preserves_multiline_string_and_backslash(
    tmp_path: Path,
) -> None:
    entry = write(
        tmp_path / "main.py",
        'message = """hello\nworld\n"""\nvalue = 1 + \\\n    2\nprint(message, value)\n',
    )
    result = splatfold.build(entry, inline_source_map=True)
    compile(result.source, str(result.output_path), "exec")
    assert "hello #" not in result.source
    assert "\\ #" not in result.source


def test_declared_source_encoding_is_read_and_output_is_utf8(tmp_path: Path) -> None:
    entry = tmp_path / "main.py"
    entry.write_bytes("# -*- coding: latin-1 -*-\nprint('caf\xe9')\n".encode("latin-1"))
    result = splatfold.build(entry)
    output = result.write()
    assert "café" in output.read_text(encoding="utf-8")
    assert completed_output(output) == "café\n"


def test_coding_text_in_normal_source_is_not_removed(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        'message = "coding: utf-8"\nprint(message)\n',
    )
    result = splatfold.build(entry)
    assert 'message = "coding: utf-8"' in result.source
    assert completed_output(result.write()) == "coding: utf-8\n"


def test_indented_hashbang_comment_is_not_treated_as_a_shebang(
    tmp_path: Path,
) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\nprint(value)\n")
    write(tmp_path / "dep.py", "  #! ordinary indented comment\nvalue = 4\n")

    result = splatfold.build(entry)
    assert "  #! ordinary indented comment" in result.source
    assert completed_output(result.write()) == "4\n"


def test_public_exports_are_explicit() -> None:
    assert set(splatfold.__all__) == {
        "VERSION",
        "BuildResult",
        "PreprocessorError",
        "ResolutionError",
        "SplatfoldError",
        "__version__",
        "build",
        "main",
    }
    assert splatfold.PreprocessorError is splatfold.SplatfoldError
    assert splatfold.__version__ == splatfold.VERSION


def completed_output(path: Path) -> str:
    completed = run(path)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def test_build_never_executes_project_source(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\n")
    write(tmp_path / "dep.py", "raise RuntimeError('must not run while building')\n")
    result = splatfold.build(entry)
    assert "must not run while building" in result.source


def test_output_cannot_overwrite_a_source_file(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n")
    with pytest.raises(splatfold.PreprocessorError, match="overwrite a source file"):
        splatfold.build(entry, output=entry)

    result = splatfold.build(entry)
    with pytest.raises(splatfold.PreprocessorError, match="overwrite a source file"):
        result.write(entry)


@pytest.mark.skipif(sys.platform == "win32", reason="hard-link fixture")
def test_output_cannot_alias_a_source_file_by_inode(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n")
    alias = tmp_path / "source-alias.py"
    os.link(entry, alias)

    with pytest.raises(splatfold.PreprocessorError, match="overwrite a source file"):
        splatfold.build(entry, output=alias)


def test_custom_write_path_is_atomic_and_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    entry = write(tmp_path / "main.py", "print('new')\n")
    destination = write(tmp_path / "dist" / "app.py", "old content\n")
    result = splatfold.build(entry)

    assert result.write(destination) == destination.resolve()
    assert completed_output(destination) == "new\n"
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode assertion")
def test_write_preserves_existing_output_mode(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "print('new')\n")
    destination = write(tmp_path / "app.py", "old\n")
    os.chmod(destination, 0o750)
    splatfold.build(entry).write(destination)
    assert destination.stat().st_mode & 0o777 == 0o750


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode assertion")
def test_new_output_inherits_input_mode(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "print('new')\n")
    os.chmod(entry, 0o755)
    output = splatfold.build(entry).write()
    assert output.stat().st_mode & 0o777 == 0o755


def test_named_and_plain_imports_are_not_expanded(tmp_path: Path) -> None:
    entry = write(
        tmp_path / "main.py",
        "import helper\nfrom helper import value\nprint(helper.value + value)\n",
    )
    write(tmp_path / "helper.py", "value = 21\n")
    result = splatfold.build(entry)
    assert "import helper" in result.source
    assert "from helper import value" in result.source
    assert result.included_paths == [entry.resolve()]


def test_markers_can_be_enabled_or_disabled(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\n")
    write(tmp_path / "dep.py", "value = 1\n")
    marked = splatfold.build(entry)
    clean = splatfold.build(entry, markers=False)
    assert "# >>> splatfold: begin dep.py" in marked.source
    assert "# <<< splatfold: end dep.py" in marked.source
    assert "splatfold: begin" not in clean.source


def test_source_marker_records_original_region(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\nprint(value)\n")
    result = splatfold.build(entry, source_marker=True)
    assert "# >>> splatfold: source main.py:1" in result.source
    compile(result.source, str(result.output_path), "exec")


def test_keep_main_guards_is_literal_inclusion(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "from dep import *\n")
    write(
        tmp_path / "dep.py",
        "if __name__ == '__main__':\n    print('included main')\n",
    )
    result = splatfold.build(entry, keep_main_guards=True)
    assert "included main" in result.source
    assert completed_output(result.write()) == "included main\n"


def test_source_syntax_error_has_location(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "def broken(\n")
    with pytest.raises(splatfold.PreprocessorError) as caught:
        splatfold.build(entry)
    message = str(caught.value)
    assert str(entry) in message
    assert "syntax error" in message


@pytest.mark.parametrize("input_style", ["positional", "option"])
def test_cli_builds_with_positional_and_legacy_input(
    tmp_path: Path, input_style: str
) -> None:
    entry = write(tmp_path / f"{input_style}.py", "print('ok')\n")
    output = tmp_path / f"{input_style}.out.py"
    command = [sys.executable, str(Path(splatfold.__file__).resolve())]
    if input_style == "positional":
        command.append(str(entry))
    else:
        command.extend(["-i", str(entry)])
    command.extend(["-o", str(output), "--no-markers"])

    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert completed_output(output) == "ok\n"


def test_cli_check_only_does_not_write(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n")
    output = tmp_path / "never-written.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(splatfold.__file__).resolve()),
            str(entry),
            "-o",
            str(output),
            "--check-only",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert not output.exists()
    assert "OK" in completed.stderr


def test_cli_rejects_missing_or_duplicate_input(tmp_path: Path) -> None:
    script = str(Path(splatfold.__file__).resolve())
    missing = subprocess.run(
        [sys.executable, script], text=True, capture_output=True, check=False
    )
    assert missing.returncode == 2
    assert "input file is required" in missing.stderr

    entry = write(tmp_path / "main.py", "value = 1\n")
    duplicate = subprocess.run(
        [sys.executable, script, str(entry), "-i", str(entry)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert duplicate.returncode == 2
    assert "both positionally" in duplicate.stderr


def test_cli_version_uses_product_name() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(splatfold.__file__).resolve()), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == f"splatfold {splatfold.VERSION}"


def test_main_reports_dependencies_unresolved_imports_and_cycles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entry = write(
        tmp_path / "main.py",
        "from dep import *\nfrom math import *\n",
    )
    write(tmp_path / "dep.py", "from main import *\nvalue = 1\n")

    return_code = splatfold.main(
        [str(entry), "--check-only", "--list-deps", "--verbose"]
    )
    captured = capsys.readouterr()
    assert return_code == 0
    assert str(entry.resolve()) in captured.out
    assert str((tmp_path / "dep.py").resolve()) in captured.out
    assert "kept unresolved/external wildcard import 'math'" in captured.err
    assert "cycle edge skipped" in captured.err
    assert "OK; 2 source file(s)" in captured.err


def test_main_returns_error_for_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.py"
    assert splatfold.main([str(missing)]) == 2
    assert "input file does not exist" in capsys.readouterr().err


def test_build_validates_input_root_and_search_paths(tmp_path: Path) -> None:
    non_python = write(tmp_path / "main.txt", "value = 1\n")
    with pytest.raises(splatfold.PreprocessorError, match=r"must end in \.py"):
        splatfold.build(non_python)

    entry = write(tmp_path / "main.py", "value = 1\n")
    with pytest.raises(splatfold.PreprocessorError, match="root directory"):
        splatfold.build(entry, root=tmp_path / "missing-root")
    with pytest.raises(splatfold.PreprocessorError, match="search path"):
        splatfold.build(entry, search_paths=[tmp_path / "missing-search"])


def test_build_result_without_output_path_cannot_write() -> None:
    result = splatfold.BuildResult("value = 1\n", [], [], [])
    with pytest.raises(splatfold.PreprocessorError, match="no output path"):
        result.write()


def test_path_expansion_errors_use_public_error_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_expanduser(_path: Path) -> Path:
        raise OSError("simulated path expansion failure")

    monkeypatch.setattr(Path, "expanduser", fail_expanduser)
    with pytest.raises(
        splatfold.SplatfoldError,
        match="cannot resolve input path",
    ):
        splatfold.build("main.py")


def test_standalone_build_result_uses_safe_default_mode(tmp_path: Path) -> None:
    destination = tmp_path / "standalone.py"
    result = splatfold.BuildResult("value = 1\n", [], [], [], output_path=destination)
    assert result.write() == destination
    assert destination.read_text(encoding="utf-8") == "value = 1\n"
    if sys.platform != "win32":
        assert destination.stat().st_mode & 0o777 == 0o644


def test_build_result_revalidates_source_before_writing(tmp_path: Path) -> None:
    destination = tmp_path / "invalid.py"
    result = splatfold.BuildResult("def broken(\n", [], [], [], output_path=destination)

    with pytest.raises(splatfold.SplatfoldError, match="generated file is not valid"):
        result.write()
    assert not destination.exists()


def test_invalid_encoding_is_reported_as_read_error(tmp_path: Path) -> None:
    entry = tmp_path / "main.py"
    entry.write_bytes(b"# coding: definitely-not-an-encoding\nvalue = 1\n")
    with pytest.raises(splatfold.PreprocessorError, match="cannot read"):
        splatfold.build(entry)


def test_output_parent_that_is_a_file_is_reported(tmp_path: Path) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n")
    parent_file = write(tmp_path / "not-a-directory", "occupied\n")
    result = splatfold.build(entry)
    with pytest.raises(splatfold.PreprocessorError, match="cannot write"):
        result.write(parent_file / "output.py")


def test_inline_map_handles_blank_line_and_final_line_without_newline(
    tmp_path: Path,
) -> None:
    entry = write(tmp_path / "main.py", "value = 1\n\nprint(value)")
    result = splatfold.build(entry, inline_source_map=True)
    assert "\n\n" in result.source
    assert result.source.endswith("# main.py 3")
    compile(result.source, str(result.output_path), "exec")
