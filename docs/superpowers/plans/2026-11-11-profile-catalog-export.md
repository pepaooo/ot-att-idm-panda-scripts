# Profile Catalog Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Export unique template, area, and level pairs from every API page into three CSVs.

**Architecture:** One standalone script uses argparse, urllib.request, json, and csv.
Fetch and validate every page into three sets before writing sorted reports.
Use unittest with mocked HTTP responses; no live credentials are needed.

**Tech Stack:** Python 3 standard library only.

**Spec:** `docs/superpowers/specs/2026-11-11-profile-catalog-export-design.md`

## Global Constraints

- Required `--token TOKEN`; no token acquisition, refresh, storage, or logging.
- Default URL `https://app.acme.com.mx/apiQA/v1/catalogs/profiles`.
- Optional `--url`, `--page-size` (default 100), `--output-dir` (default current directory).
- Output `templates.csv`, `areas.csv`, `levels.csv`; headers `name,key`; UTF-8.
- Deduplicate exact string pairs, preserve leading zeroes, sort by name then key.
- Validate all API results before writing; finite request timeout and nonzero errors.

## Review Focus

- Conflicting pagination metadata must cause an error rather than incomplete output.
- Existing URL query parameters must survive page/size replacement.
- HTTP failures must not expose tokens or response bodies in error messages.
- Missing/null/non-string catalog fields must fail before replacing reports.
- Empty catalogs must yield three CSV files with headers only.

### Task 1: Implement and verify the standalone exporter

**Files:** Create `export_profile_catalogs.py`, `tests/test_export_profile_catalogs.py`, `README.md`.

**Interfaces:**
- `collect_catalogs(url: str, token: str, page_size: int) -> dict`: category names mapped to sets of `(name, key)` string tuples.
- `write_catalogs(catalogs: dict, output_dir: pathlib.Path) -> None`: write sorted reports and print counts/paths.
- `main(argv=None) -> int`: parse arguments, perform export, report sanitized failures.
- `ExportError`: expected API/validation failure.

- [x] Write unittest cases for multi-page collection, Authorization header and page query,
  duplicate pairs across pages, same name/different key, same key/different name,
  leading zeroes, comma/quote/newline/Unicode CSV round trips, and empty catalogs.
  Add cases for malformed JSON/fields, inconsistent or repeated page numbers,
  HTTP 401 and network failures, invalid CLI inputs, preserved query parameters,
  and unchanged existing reports when fetching fails. Check captured errors omit tokens.
- [x] Run `python3 -m unittest discover -s tests -v`; verify tests fail because the exporter is absent.
- [x] Implement the interfaces using standard library HTTP and CSV handling.
  Reject unsafe URL schemes, use a 30-second request timeout, and validate page
  number, total pages, and last-page metadata. Disable redirects to avoid forwarding
  the bearer token to another destination. Create the output directory after collection.
- [x] Run `python3 -m unittest discover -s tests -v`; expect all cases to pass.
- [x] Document Python invocation, raw token input, output paths, overwrite behavior,
  exact pair uniqueness, pagination, error exit codes, and local test command in README.
- [x] Run `python3 export_profile_catalogs.py --help` and review implementation against
  the approved design. Re-run tests only if further changes warrant it.

## Workspace note

The supplied directory is not a Git repository (`git status` fails), so no commit
or worktree operations are planned. Files remain directly reviewable in the workspace.
