# PANDA catalog CSVs to XML mapping tables

## Intent

Create `panda_catalogs_to_xml.py` to convert any subset of the templates, areas,
and levels catalog CSVs into separate XML mapping tables. Use
`sfdc_profiles_to_xml.py` as a structural reference; keep existing scripts unchanged.

## Approaches

- One standalone converter with category flags: recommended and selected by the
  user. Converts any requested subset in one invocation with category defaults.
- Generic single-file converter invoked repeatedly: simpler interface, but needs
  multiple commands and explicit output names; not selected.

## Interface and outputs

Use Python 3 standard library only. Support these independently optional inputs:

| Input flag | Optional output override | Default output filename |
| --- | --- | --- |
| `--templates INPUT.csv` | `--templates-output OUTPUT.xml` | `MT-Catalogo-templates.xml` |
| `--areas INPUT.csv` | `--areas-output OUTPUT.xml` | `MT-Catalogo-area.xml` |
| `--levels INPUT.csv` | `--levels-output OUTPUT.xml` | `MT-Catalogo-level.xml` |

Default output files go into the current directory. An override is a complete
output path. Require at least one input; reject an output override without its
matching input. Output directories must already exist. Print each written path
and data-row count. Existing selected outputs are overwritten after validation.

## Mapping and XML format

- Read UTF-8 CSV with `name` and `key` headers, including an optional UTF-8 BOM.
  Match columns by header name, independent of their position.
- Each file produces a complete XML 1.0 document with UTF-8 declaration and
  `mapping-table` root.
- First child: `<col-def name="id" type="nocase"/>`.
- Second child: `<col-def name="name" type="nocase"/>`.
- Each CSV record produces `<row>` with two `<col>` children: key first, name
  second. Preserve exact string values, row order, duplicates, and leading zeroes.
- Use tab indentation and XML escaping. The serializer may use equivalent
  whitespace around self-closing tags and a newline after the declaration.
- A header-only CSV produces the root and both column definitions, with no rows.

## Proposed validation and error behavior

- Load and validate every selected CSV and output path before writing any XML.
- Require unique `name` and `key` headers; reject duplicate header names or
  missing required headers. Permit additional named columns and ignore their
  values, provided each record has the same number of fields as the header.
- Reject malformed CSV, missing/extra fields, and blank/whitespace-only key or
  name values. Skip physically blank CSV lines as normal CSV parsing does.
- Preserve nonblank values without trimming or case conversion. Reject text that
  cannot appear in XML 1.0 rather than silently removing characters. Unicode,
  punctuation, quoted commas, and quoted newlines are supported.
- Reject output paths aliasing any selected input or another output, including
  symlinks/hardlinks, before writing.
- Expected input/path/write errors print a clear message and return nonzero
  without a traceback. Invalid CLI arguments return 2; conversion failures return
  1; successful conversions return 0.
- Input, validation, or path failures leave existing outputs untouched. Disk-write
  errors can leave partial outputs; files are not a multi-file transaction.

## Non-goals and implementation choices

No API calls, tokens, JSON input, sorting, deduplication, Cartesian products, or
IdM imports. Do not change Salesforce scripts, the PANDA API exporter, or the IdM
CSV converter. Function organization and exact error wording are implementation
choices. Do not copy Salesforce's four-column definitions into this converter.

## Verification

Test each category separately and all three together, exact default names and
overrides, key/name column ordering, required column definitions, well-formed XML,
leading zeroes, Unicode and escaping, CSV quoting/newlines, preserved duplicate
order, and empty catalogs. Exercise invalid CSV/text, orphan overrides, no inputs,
path aliases, invalid later inputs/outputs preserving earlier outputs, and write
errors. Run the existing test suite and CLI help. Validate existing catalog CSVs
without overwriting actual reports during development.
