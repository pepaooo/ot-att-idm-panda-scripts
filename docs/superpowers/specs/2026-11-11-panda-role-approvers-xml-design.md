# PANDA Level 10 role approvers mapping XML

## Intent and scope

Create a standalone `panda_roles10_to_mapping_xml.py`, using
`sfdc_roles10_to_mapping_xml.py` as the reference, to join role approvers to their
Level 10 role DNs and write the IdM workflow XML mapping table. Read the existing
PANDA CSVs locally; do not call APIs or change the Salesforce reference.

## Approaches

- Standalone PANDA converter: recommended and selected by the user. Preserves the
  Salesforce-style interface while matching the actual PANDA inputs by Id.
- Extend the Salesforce converter: shares code but changes existing behavior and
  introduces application switches; not selected.

## Inputs and interface

Command:

`python3 panda_roles10_to_mapping_xml.py INPUT.csv OUTPUT.xml --perfilMapeo ROLES.csv [--delimiter CHAR]`

- `INPUT.csv`: approvers file with `Name`, `Id`, `Grupo IDM` headers; tab-separated
  by default, matching `reports/panda_role10_approvers_mapping.csv`.
- `ROLES.csv`: comma-separated lookup with `Name`, `Id`, `DN` headers, matching
  `reports/panda_role10_mapping.csv`.
- Accept `--delimiter tab`, `--delimiter comma`, or a single delimiter character
  for the approvers file. The lookup delimiter remains comma.
- Both inputs use UTF-8 with optional BOM. Header order is flexible; additional
  named columns are ignored. Reject duplicate/blank headers and inconsistent
  record field counts. Skip physically blank lines.
- Trim surrounding whitespace on required values as the Salesforce reference
  does. Require nonempty names, IDs, role DNs and second-approver group values.
  Preserve leading zeroes and interior characters; do not convert IDs to numbers.

## Join and XML mapping

Join the approvers file's `Id` to the role lookup's `Id`, using exact,
case-sensitive string matching after trimming. `Name` is descriptive and is not
the join key; matching IDs may have different names. Use the supplied role DN
without reconstructing it from the role name or ID.

Produce a complete UTF-8 XML 1.0 document with a `mapping-table` root and these
four `col-def` elements, in order, each with `type="nocase"`:

1. `DN de perfil`
2. `Primer aprobador`
3. `Segundo aprobador`
4. `Tercer aprobador`

Each `row` has four `col` children, in the same order:

1. Lookup `DN` for this `Id`.
2. `Gerente o nivel superior` (confirmed by the user).
3. Approvers file `Grupo IDM`.
4. `#NOT_REQUIRED#` (confirmed by the user).

Use tab indentation and XML escaping, preserving Unicode and interior multiline
text, including carriage returns when parsed back. Output only roles present in
the approvers input; unused lookup rows are permitted. Preserve approvers input
order. Header-only approvers input produces the four definitions with no rows.

## Proposed validation and duplicate behavior

- Validate both complete files, join results, XML text, and output path before
  opening the XML for writing. Missing lookup IDs or blank second approvers fail
  the entire conversion rather than silently skipping records.
- For repeated lookup IDs, identical normalized `Name`/`DN` rows are allowed;
  conflicting values are errors. For repeated approver IDs, identical normalized
  `Name`/`Grupo IDM` rows produce a single XML row in first-occurrence order;
  conflicting values are errors.
- Reject output paths aliasing either input, including symlinks/hardlinks. Output
  parent must exist and be writable; existing output must be a writable regular
  file. Existing output is overwritten only after validation succeeds.
- Reject malformed CSV, invalid UTF-8, and text forbidden by XML 1.0; do not
  silently remove invalid characters. DN strings are not checked against a live
  directory or parsed as LDAP schemas.
- Print input/unique mapping counts and the written XML path/row count. Expected
  conversion/write errors return 1 with a clear error and no traceback; invalid
  CLI arguments return 2; success returns 0.
- Validation failures leave an existing XML untouched. Filesystem write failure
  may leave a partial output; atomic replacement is outside this change.

## Constraints and non-goals

Python 3.9+ standard library only, consistent with the catalog XML converter.
Keep the exporter, IdM CSV generator, catalog XML converter, and all Salesforce
scripts unchanged. No default group, fallback name-based matching, partial-success
output, live IdM import, or completeness requirement for unused lookup roles.
Function structure and exact error wording remain implementation choices.

## Verification

Verify the supplied PANDA file formats and sample role mapping, exact column
definitions/fixed values, Id-based joins despite changed names, order, leading
zeroes, XML escaping/Unicode/newlines, header-only files, duplicate rules, missing
IDs, blank groups, invalid input, delimiter handling, and input/output aliasing.
Check validation failures preserve existing XML and write failures report errors.
Run the full existing test suite and CLI help. Validate the actual 4,878-row PANDA
inputs without overwriting actual reports during development.
