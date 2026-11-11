# PANDA Catalog XML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Convert any subset of PANDA catalog CSVs into separate XML mapping tables with key mapped to id and name mapped to name.

**Architecture:** One standalone CLI selects category input/output pairs, validates
all paths and CSV records, builds the XML trees, then writes the requested files.
Use csv parsing and ElementTree serialization; keep the XML escaping and UTF-8
handling in the standard library.

**Tech Stack:** Python 3 standard library: argparse, csv, pathlib, xml.etree.ElementTree, unittest.

**Spec:** `docs/superpowers/specs/2026-11-11-panda-catalogs-xml-design.md`

## Global Constraints

- Create `panda_catalogs_to_xml.py`; leave existing converters and exporter unchanged.
- Inputs: independently optional `--templates`, `--areas`, `--levels`, each taking a CSV path; require at least one.
- Overrides: `--templates-output`, `--areas-output`, `--levels-output`; reject an override without its input.
- Defaults in current directory: `MT-Catalogo-templates.xml`, `MT-Catalogo-area.xml`, `MT-Catalogo-level.xml`.
- UTF-8 XML 1.0 declaration, mapping-table root, col-def id/nocase then name/nocase; each row contains key then name.
- Tab indentation; preserve CSV values, order, duplicates, Unicode, and leading zeroes.
- Parse UTF-8 CSV with optional BOM; require unique headers including name/key; ignore named extra columns but require consistent field count.
- Validate every selected input/output before writing; reject blank required fields, malformed CSV, invalid XML 1.0 characters, and output aliases.
- Existing output directories required. Exit 0 success, 1 conversion/write error, 2 invalid CLI; print written paths and row counts.
- No API access, new dependencies, sorting, deduplication, or import into IdM.

## Review Focus

- Header order must not reverse key/name mapping; quoted multiline values must retain their contents.
- Invalid XML control characters must fail validation rather than create unparseable output.
- A later invalid CSV or output must leave all earlier existing XMLs untouched.
- Symlink/hardlink aliases must not overwrite selected CSVs or another selected output.
- Empty catalogs must still contain the two column definitions and no rows.

### Task 1: Implement the converter and usage documentation

**Files:** Create `panda_catalogs_to_xml.py`, `tests/test_panda_catalogs_to_xml.py`; update `README.md`.

**Interfaces:**
- `read_catalog(csv_path: Path) -> list`: return validated `(key, name)` string pairs in CSV order.
- `build_mapping_table(rows: list) -> bytes`: return complete UTF-8 XML with declaration and tab indentation.
- `validate_paths(inputs: list, outputs: list) -> None`: reject invalid targets and input/output or output/output aliases without opening files for writing.
- `main(argv=None) -> int`: validate CLI selection, read all catalogs/build all documents, validate paths, write selected XML files and counts.
- `ConversionError`: expected input/path validation failure.

- [x] Write failing tests for each category and all three together, exact default
  filenames and custom paths, no inputs/orphan overrides, and XML parse assertions
  for declaration, column definitions and key/name positions. Include swapped
  headers, BOM, extra named columns, leading zeroes, duplicate order, XML special
  characters, Unicode, quoted commas/newlines and header-only CSVs.
- [x] Add failure cases for missing/duplicate headers, invalid field counts, empty
  fields, malformed quotes, invalid UTF-8/XML characters, missing files, invalid
  later CSV/output preserving sentinel files, path/symlink/hardlink aliases, and
  write errors with no traceback. Use standard unittest and temporary directories.
- [x] Run `python3 -B -m unittest discover -s tests -v`; verify new tests fail
  because the converter is absent while existing tests pass.
- [x] Implement strict CSV parsing and XML-character validation, preserving
  nonblank field text without trimming. Build XML trees with id/name definitions,
  key/name row values, tab indentation and a UTF-8 declaration. Use serialization
  that preserves carriage returns when XML is read back.
- [x] Implement category CLI/path validation and validate all selected inputs and
  documents before writes. Reject resolved-path and existing-inode aliases;
  preserve existing outputs for all input/validation/path failures. Catch expected
  errors and report clear messages and the specified exit codes.
- [x] Run the full test command; expect all tests passing. Document subset/all-input
  invocations, overrides, default output location, XML shape, validation and
  partial-write behavior in README.
- [x] Run `python3 -B panda_catalogs_to_xml.py --help` and full tests; expect exit 0
  and all tests passing. Validate existing reports CSVs without writing actual
  XMLs. Obtain an independent read-only final review under executing-plans and
  fix material findings with regression tests.

## Execution context

Continue direct implementation in the current approved workspace without commits
or branch changes, preserving unrelated tracked/untracked work. Do not overwrite
actual user report files as part of development checks.
