# PANDA profiles to IdM CSV

## Intent and scope

Create a standalone `panda_profiles_to_resource_csv.py` using
`sfdc_profiles_to_resource_csv.py` as the CSV format reference. Read the complete
`profiles.json` produced by the PANDA exporter and generate resource, level-10
role, association, and role-mapping CSVs for the combinations already present in
`content`. Do not generate a Cartesian product or call the API.

## Approaches

- Standalone PANDA converter: recommended and selected by the user. Retains the
  Salesforce command-line conventions and layouts without changing that script.
- Shared configurable Salesforce/PANDA converter: reduces duplication but requires
  refactoring the reference and introduces unnecessary configuration; not selected.

## Interface

`python3 panda_profiles_to_resource_csv.py profiles.json` followed by one or more:

- `--generaRecursos OUT.csv`
- `--genereRoles OUT.csv`
- `--generaAsociaciones OUT.csv`
- `--generaMapeoRol10 OUT.csv`

Use Python 3 standard library only. Accept any combination of flags. Print output
paths and data-row counts. Require at least one output. Match the reference's
header behavior: no headers except `Name,Id,DN` for the mapping CSV, with all
fields quoted. Existing selected outputs are overwritten on successful validation.

## User-specified mapping

For each record, in template, area, level order:

- `ID`: keys joined with hyphens, e.g. `6-HORUS-ULAVP`.
- `CN`: `PANDA-` plus ID, e.g. `PANDA-6-HORUS-ULAVP`.
- `ID2`: names joined with hyphens, e.g. `Horus User-Horus Access-AVP`.
- Resource permission DN:
  `cn=Permission,cn=MID-PANDA,cn=DriverSet1,ou=idm,ou=services,o=system`.
- Association resource DN:
  `cn=PANDA-Permission-DRS,cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system`.
- Resource and role category: `panda-perfil`.

Keep the reference's resource base DN and Level10 role base DN unchanged.
Use the exact key-derived CN for both resource and role, preserving leading zeroes.

## CSV layouts

Each numbered position below is a field in the same order as the reference.

**Resources (13 columns):**
`create`, empty, resource DN, empty, empty, empty, sanitized ID2 display name,
`<ID2>. Perfil del sistema PANDA`, resource permission DN, escaped metadata,
`UA`, `panda-perfil`, `false`.

**Roles (12 columns):**
`create`, empty, empty, empty, Level10 role DN, sanitized ID2 display name,
`<ID2>. Rol por excepción de PANDA en IdM.`, `panda-perfil`, `10`, empty, empty,
empty.

**Associations (12 columns):**
`resourceassociation`, empty, empty, empty, Level10 role DN, empty,
`Rol por excepción de PANDA en IDM`, empty, empty, `true`, association resource DN,
escaped metadata.

**Role mapping (3 columns plus header):**
ID2, ID, Level10 role DN. Header: `Name,Id,DN`.

Metadata is compact JSON containing `ID` and `ID2`, with JSON quotes escaped with
backslashes and wrapped in a quoted CSV field, matching the reference's legacy
format. Example field:
`"{\"ID\":\"6-HORUS-ULAVP\",\"ID2\":\"Horus User-Horus Access-AVP\"}"`.
Use proper JSON serialization before applying that legacy quoting so quotes,
backslashes, and newlines inside names remain recoverable. Ordinary CSV fields
use normal doubled-quote escaping. Preserve Unicode in UTF-8.

## Proposed validation and duplicate behavior

These are implementation proposals for approval with this design:

- Validate the entire input before opening outputs. Require a JSON object with a
  `content` array and nonempty string `name` and `key` values in all three fields.
- Emit one row per unique key triple, retaining first-occurrence order. Skip
  exact repeated combinations. Fail if the same keys have different names or if
  distinct triples produce the same joined ID/CN.
- Preserve the exact CN rather than truncating it. Fail if a CN exceeds the
  reference's 64-character limit or contains DN-special characters/control
  characters requiring escaping. Names may contain Unicode and punctuation.
- As in the reference, sanitize only display-name fields in resource and role
  rows by removing `* + ~ = / \\ # " , ;`. Preserve original names in metadata,
  descriptions, and mapping output.
- Reject output paths that refer to the input or to another selected output.
- Invalid JSON/data, naming conflicts, or invalid paths must leave existing
  outputs untouched. Filesystem failures while writing may leave partial output;
  this is not an atomic multi-file transaction.
- Empty `content` yields empty resource/role/association files and a header-only
  mapping file. Do not silently skip malformed records.

## Non-goals and remaining choices

Do not change the exporter or Salesforce script. Do not create role-to-individual-
resource links in place of the specified shared PANDA permission resource.
No online lookups, token handling, offline configuration, or new dependencies.
Function decomposition, precise error wording, and helper organization remain
implementation choices. Use clear nonzero exits and no traceback for expected
input/output errors; retain the reference's exit 3 when no output flag is given.

## Verification

Check the supplied example's exact CN, all four row layouts, DN constants,
category, and metadata bytes against independent expected fixtures. Round-trip
metadata containing quotes/backslashes/newlines and Unicode. Exercise duplicate
and conflicting triples, joined-ID collisions, leading zeroes, invalid or
overlong CNs, missing fields, empty input, output/input aliasing, and preservation
of existing output on validation failures. Run the existing exporter tests too.
