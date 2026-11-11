# Combined Profiles JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Save all PANDA profiles in one JSON document and generate the same three CSV reports from its content.

**Architecture:** Separate full-record retrieval from catalog extraction. Accumulate
each page's records into one document, validate all records before writing, then
save that document and derive the CSVs from it. Retain the existing collection
function as a compatibility wrapper for callers and existing tests.

**Tech Stack:** Python 3 standard library; unittest and mocked HTTP responses.

**Spec:** `docs/superpowers/specs/2026-11-11-combined-profiles-json-design.md`

## Global Constraints

- Fetch pages starting at zero through the last page, with existing pagination validation and progress.
- Save `profiles.json` as `{"content": [...]}` in `--output-dir`.
- Preserve full records, nested fields, duplicates, and retrieval order.
- Keep CSV filenames, `name,key` headers, sorting, and exact pair uniqueness unchanged.
- API or validation errors must leave all existing reports untouched.
- Keep existing CLI and token handling; standard library only.
- Leave `sfdc_profiles_to_resource_csv.py` unchanged.

## Review Focus

- Repeated profiles must remain in JSON while catalog pairs remain unique in CSVs.
- Extra nested fields and Unicode must survive a JSON read/write round trip.
- A malformed catalog value on a later page must not replace an earlier JSON export.
- Empty results must produce valid JSON and three header-only CSVs.
- Completion must be printed only after the JSON and all CSVs are written.

### Task 1: Add combined JSON retrieval and report generation

**Files:** Modify `export_profile_catalogs.py`, `tests/test_export_profile_catalogs.py`, `README.md`.

**Interfaces:**
- `fetch_profiles(url: str, token: str, page_size: int) -> dict`: return the combined content document, retaining existing HTTP and pagination checks.
- `extract_catalogs(profiles: dict) -> dict`: validate records and return the existing category-to-pairs mapping without mutating the document.
- `collect_catalogs(url: str, token: str, page_size: int) -> dict`: compatibility wrapper combining the above.
- `write_profiles(profiles: dict, output_dir: Path) -> None`: save indented UTF-8 JSON with Unicode preserved and print path/count.
- `main(argv=None) -> int`: fetch, extract/validate, write JSON, write CSVs, print completion.

- [x] Add tests asserting full JSON contents/order across pages, duplicate retention,
  nested/Unicode round trips, unchanged unique CSV rows, and empty JSON/CSV output.
  Extend failure tests to check existing `profiles.json` is preserved; cover invalid
  later-page records and JSON writing failure suppressing success output.
- [x] Run `python3 -m unittest discover -s tests -v`; confirm new behavior fails before implementation.
- [x] Refactor retrieval into `fetch_profiles`, accumulate with list extension, and
  move category validation/deduplication into `extract_catalogs`. Preserve the
  `collect_catalogs` interface and validate all profiles before any output is written.
- [x] Add `write_profiles` using `json.dump(..., ensure_ascii=False, indent=2)` and a
  trailing newline. Integrate the four outputs into `main`; retain existing error
  exit codes and sanitized messages. Describe write failures as affecting report files.
- [x] Update README with `profiles.json`, preservation semantics, full record count,
  unchanged CLI examples, and the documented limit on filesystem transactionality.
- [x] Run `python3 -m unittest discover -s tests -v` and `python3 export_profile_catalogs.py --help`;
  expect all tests passing and help exit 0. Complete an independent read-only final
  review per the executing-plans skill, fixing any material findings with regression tests.

## Execution context

Continue direct implementation in this session, as previously selected. This
workspace is not a Git repository; worktree, commit, and Git review-package steps
do not apply. Review files directly.
