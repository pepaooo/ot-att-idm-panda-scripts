# PANDA Role Approvers XML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Join PANDA approvers and Level 10 role CSVs by Id and emit the four-column workflow mapping XML.

**Architecture:** One standalone CLI loads and validates both CSVs into ID-keyed
records, joins approvers to supplied DNs in input order, validates the complete
XML document and output path, then writes one UTF-8 file. Keep CSV parsing,
duplicate checks, joining, and serialization as focused helpers.

**Tech Stack:** Python 3.9+ standard library: argparse, csv, pathlib, xml.etree.ElementTree, unittest.

**Spec:** `docs/superpowers/specs/2026-11-11-panda-role-approvers-xml-design.md`

## Global Constraints

- Create `panda_roles10_to_mapping_xml.py`; leave every existing script unchanged.
- Interface: `INPUT.csv OUTPUT.xml --perfilMapeo ROLES.csv [--delimiter CHAR]`.
- Approvers headers: Name, Id, Grupo IDM; default delimiter tab. Lookup headers: Name, Id, DN; delimiter comma.
- Accept delimiter names tab/comma or a single character; UTF-8 BOM accepted; trim required field boundaries and preserve interior text/leading zeroes.
- Join by exact Id only, ignoring cross-file Name differences; use supplied DN unchanged after trimming.
- XML root mapping-table; nocase columns DN de perfil, Primer aprobador, Segundo aprobador, Tercer aprobador.
- Row values: lookup DN, Gerente o nivel superior, Grupo IDM, #NOT_REQUIRED#.
- Preserve first approver order; skip identical repeated IDs within each input; conflicting duplicates fail.
- Unused lookup roles allowed; missing referenced role IDs and blank groups fail before output writes.
- Validate complete CSVs, XML characters and path aliases before writing; expected errors have no traceback.
- UTF-8 XML declaration, tab indentation, carriage-return-preserving serialization; header-only approvers yields definitions only.
- Exit 0 success, 1 conversion/write error, 2 invalid CLI; print counts and written path.

## Review Focus

- Different cross-file names must not prevent an exact-ID match or trigger name-based lookup.
- Conflicting duplicate IDs must not silently overwrite approver groups or DNs.
- A missing lookup ID near the end must preserve any existing XML file.
- Output aliases to either input, including hardlinks/symlinks, must fail before writes.
- CSV interior newlines, carriage returns, XML special characters, and Unicode must survive XML parsing.

### Task 1: Implement and verify the standalone converter

**Files:** Create `panda_roles10_to_mapping_xml.py`, `tests/test_panda_roles10_to_mapping_xml.py`; update `README.md`.

**Interfaces:**
- `load_records(path: Path, required: tuple, delimiter: str) -> dict`: validate CSV and return Id-to-required-fields records in first-occurrence order; reject conflicting duplicates.
- `build_mapping_table(approvers: dict, roles: dict) -> bytes`: validate exact-ID joins, generate the four-column XML and return complete UTF-8 bytes.
- `validate_output_path(output: Path, inputs: list) -> None`: reject invalid/aliased targets without opening for writing.
- `main(argv=None) -> int`: parse arguments, read both CSVs, build/validate, write and print counts.
- `ConversionError`: expected input, join, or path failure.

- [x] Add tests for the real tab/comma schemas, the 6-HORUS-ULAVP example, exact
  column definitions/fixed approvers and supplied role DN, Id joins despite name
  differences, shuffled order, leading zeroes, delimiter tab/comma/custom support,
  BOM/header reordering/extra columns, whitespace trimming, XML escaping and
  Unicode/newline/carriage-return preservation, and header-only input.
- [x] Add tests for identical/conflicting duplicates in both inputs, missing late
  lookup IDs, blank group/required values, missing/duplicate/blank headers,
  malformed quoting/field counts, invalid UTF-8/XML characters, missing input,
  invalid CLI/delimiters, bad output paths, and aliases to either input. Assert
  validation errors preserve a sentinel XML; inject a write error and check a
  nonzero result without traceback or success message.
- [x] Run `python3 -B -m unittest discover -s tests -v`; confirm new tests fail
  because the converter is absent while all existing tests pass.
- [x] Implement strict CSV validation and duplicate handling, exact-Id joins, the
  four XML definitions and row values, XML text validation and tab indentation.
  Escape carriage returns as character references to retain them when parsed.
- [x] Implement the reference-style CLI, delimiter normalization, full pre-write
  validation and inode/resolved-path alias checks. Report useful counts and
  expected errors with the specified exit codes.
- [x] Run the full tests; expect all passing. Document the invocation with both
  actual filenames, delimiter overrides, column mapping, matching/duplicate rules,
  validation, output location and partial-write limitation in README.
- [x] Run `python3 -B panda_roles10_to_mapping_xml.py --help`, full tests and
  `git diff --check`; expect success. Validate/round-trip actual PANDA inputs in
  memory without writing reports. Obtain an independent read-only final review
  under executing-plans and fix material findings with regression tests.

## Execution context

Continue direct execution in the current approved workspace without commits or
branch changes. Preserve unrelated tracked and untracked files. Development
verification must not overwrite actual user XML reports.
