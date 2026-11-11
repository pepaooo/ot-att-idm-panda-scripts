# PANDA IdM CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Convert combined PANDA profiles into the four Salesforce-compatible IdM CSV outputs using PANDA identifiers and DNs.

**Architecture:** A standalone converter loads and validates the complete input,
normalizes unique combinations into records with ID, ID2, and CN, then uses
dedicated row builders for the four layouts. Render ordinary fields with standard
CSV quoting and metadata fields with the reference's backslash-escaped quoting.
Validate all selected paths and all records before opening any output.

**Tech Stack:** Python 3 standard library; argparse, json, csv, pathlib, unittest.

**Spec:** `docs/superpowers/specs/2026-11-11-panda-idm-csv-design.md`

## Global Constraints

- Create `panda_profiles_to_resource_csv.py`; do not change Salesforce converter or API exporter.
- Input is a JSON object with a `content` array; process its combinations only.
- Support `--generaRecursos`, `--genereRoles`, `--generaAsociaciones`, `--generaMapeoRol10`, each taking an output CSV path.
- CN is `PANDA-<template.key>-<area.key>-<level.key>`; ID omits the prefix; ID2 joins names in the same order.
- Resource permission DN: `cn=Permission,cn=MID-PANDA,cn=DriverSet1,ou=idm,ou=services,o=system`.
- Association resource DN: `cn=PANDA-Permission-DRS,cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system`.
- Resource/role category: `panda-perfil`; retain reference's resource base and Level10 base DNs.
- Preserve exact 13/12/12/3-column layouts from the spec; only mapping has header `Name,Id,DN`; UTF-8, all fields quoted.
- Metadata uses compact JSON followed by legacy backslash escaping; no manual interpolation of name values into JSON.
- Skip exact duplicate combinations, preserve first order, reject conflicting names or joined-ID collisions.
- Reject missing/empty string fields, unsafe or over-64-character CNs, and aliased input/output paths before writing.
- No flags returns 3; expected input/write errors return nonzero without tracebacks; print paths and counts on success.

## Review Focus

- Quoted/backslashed names must survive metadata serialization, including newlines and Unicode.
- Same keys with different names must not silently select one display name.
- Hyphens within different key triples must not produce duplicate joined IDs.
- Output aliases, including symlinks/hardlinks to input or another output, must be rejected before any write.
- Empty content must produce empty unheaded CSVs and a mapping header only.

### Task 1: Implement the standalone converter and document usage

**Files:** Create `panda_profiles_to_resource_csv.py`, `tests/test_panda_profiles_to_resource_csv.py`; update `README.md` with a separate converter section.

**Interfaces:**
- `load_profiles(input_path: Path) -> list`: load and validate JSON, deduplicate records, derive ID/ID2/CN.
- `validate_output_paths(input_path: Path, output_paths: list) -> None`: check resolved paths, existing-file identities, writable file targets, and existing output parent directories without opening outputs for writing.
- `row_recursos(record: dict) -> str`, `row_roles(record: dict) -> str`, `row_asociaciones(record: dict) -> str`, `row_mapeo_rol10(record: dict) -> str`: build lines in spec-defined order without trailing newline.
- `main(argv=None) -> int`: select builders, validate everything, write chosen files and print row counts.
- `ConversionError`: expected data/path validation failure.

- [x] Write tests with literal expected rows for the `6-HORUS-ULAVP` example:
  resource has 13 columns, role 12, association 12, mapping 3 with quoted header;
  assert exact CNs, DNs, descriptions, category, and escaped metadata fields.
- [x] Add end-to-end CLI tests for all flags together and each independently;
  input with duplicates must emit one row per unique combination in first order.
  Assert leading-zero keys survive, and decode metadata with quotes/backslashes/
  newlines/Unicode to the exact ID/ID2 strings. Verify sanitized display fields
  while descriptions, mapping names, and metadata retain original names.
- [x] Add validation tests for invalid JSON/envelope/fields, conflicting duplicate
  names, joined-ID collisions, CN length/special/control characters, empty content,
  no flags, missing input, and invalid/aliased paths. Check preexisting sentinel
  files remain unchanged after validation failure, including a malformed late
  record and an invalid later output path. Exercise symlink/hardlink aliases where
  supported and a real write failure with nonzero exit/no traceback.
- [x] Run `python3 -m unittest discover -s tests -v`; confirm new tests fail because
  the PANDA converter is absent while existing exporter tests continue to pass.
- [x] Implement validation, identifiers, dedicated row builders, and the four-flag
  CLI. Serialize metadata as compact JSON, then JSON-encode that string to obtain
  the reference-compatible quoted/backslash-escaped field. Ordinary fields use
  standard CSV doubled quotes. Validate full input and all paths before writes.
- [x] Run `python3 -m unittest discover -s tests -v`; expect all tests passing.
- [x] Document invocation with all four flags, output layouts, combination naming,
  deduplication/errors, metadata convention, and partial-write limitation in README.
- [x] Run `python3 panda_profiles_to_resource_csv.py --help` and the full unittest
  suite; expect exit 0 and all tests passing. Obtain an independent read-only
  final review under executing-plans, fixing material findings with regression tests.

## Execution context

Continue direct implementation in this session, as previously selected. The
workspace now reports a Git repository on `main`; inspect applicable instructions
and isolation support before implementation. Preserve the existing untracked
`sfdc_profiles_to_resource_csv.py` and all unrelated work. Do not merge or publish.
