#!/usr/bin/env python3
"""Convert any subset of PANDA templates, areas, and levels CSVs into XML mapping tables."""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


DEFAULT_OUTPUTS = {
    'templates': 'MT-Catalogo-templates.xml',
    'areas': 'MT-Catalogo-area.xml',
    'levels': 'MT-Catalogo-level.xml',
}


class ConversionError(Exception):
    """A catalog or output configuration cannot produce a valid mapping table."""


def valid_xml_text(value: str) -> bool:
    return all(char in '\t\n\r' or 0x20 <= ord(char) <= 0xD7FF
               or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF
               for char in value)


def read_catalog(csv_path: Path) -> list:
    """Read and validate a UTF-8 catalog, returning (key, name) pairs in input order."""
    rows = []
    try:
        with csv_path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.reader(handle, strict=True)
            # csv.reader yields [] for physically blank lines; ignore those only.
            records = (record for record in reader if record)
            headers = next(records, None)
            if (headers is None or any(not header.strip() for header in headers)
                    or len(set(headers)) != len(headers)
                    or not {'name', 'key'}.issubset(headers)):
                raise ConversionError(f'{csv_path}: require unique named headers including name and key.')
            key_index, name_index = headers.index('key'), headers.index('name')
            for record in records:
                if len(record) != len(headers):
                    raise ConversionError(f'{csv_path}, line {reader.line_num}: field count differs from header.')
                key, name = record[key_index], record[name_index]
                if not key.strip() or not name.strip():
                    raise ConversionError(f'{csv_path}, line {reader.line_num}: key and name must be nonempty.')
                if not valid_xml_text(key) or not valid_xml_text(name):
                    raise ConversionError(f'{csv_path}, line {reader.line_num}: text contains invalid XML 1.0 characters.')
                rows.append((key, name))
    except csv.Error as exc:
        raise ConversionError(f'{csv_path}: malformed CSV ({exc}).') from None
    except UnicodeError:
        raise ConversionError(f'{csv_path}: input must be valid UTF-8.') from None
    return rows


def build_mapping_table(rows: list) -> bytes:
    """Serialize the two-column mapping table with tab indentation and a UTF-8 declaration."""
    root = ET.Element('mapping-table')
    for name in ('id', 'name'):
        ET.SubElement(root, 'col-def', name=name, type='nocase')
    for key, name in rows:
        row = ET.SubElement(root, 'row')
        ET.SubElement(row, 'col').text = key
        ET.SubElement(row, 'col').text = name
    ET.indent(root, space='\t')
    body = ET.tostring(root, encoding='utf-8')
    # Literal carriage returns are normalized by XML parsers. Character references
    # preserve the CSV's original text when the mapping table is parsed again.
    body = body.replace(b'\r', b'&#13;')
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body + b'\n'


def validate_paths(inputs: list, outputs: list) -> None:
    """Reject invalid targets and path/inode aliases across the whole conversion."""
    resolved_paths = set()
    identities = set()
    for source in inputs:
        resolved_paths.add(source.resolve())
        info = source.stat()
        identities.add((info.st_dev, info.st_ino))
    for target in outputs:
        resolved = target.resolve()
        if resolved in resolved_paths:
            raise ConversionError('Output paths must differ from every input and other output.')
        resolved_paths.add(resolved)
        if not resolved.parent.is_dir() or not os.access(resolved.parent, os.W_OK | os.X_OK):
            raise ConversionError(f'Output directory must exist and be writable: {target.parent}')
        if resolved.exists():
            if not resolved.is_file() or not os.access(resolved, os.W_OK):
                raise ConversionError(f'Output must be a writable regular file: {target}')
            info = resolved.stat()
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise ConversionError('Output files must not link to an input or another output.')
            identities.add(identity)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for category, default in DEFAULT_OUTPUTS.items():
        parser.add_argument('--' + category, type=Path, metavar='CSV',
                            help=f'Input {category} catalog CSV with name,key headers')
        parser.add_argument('--' + category + '-output', type=Path, metavar='XML',
                            help=f'Output path (default: {default} in current directory)')
    args = parser.parse_args(argv)
    selected = []
    for category, default in DEFAULT_OUTPUTS.items():
        source = getattr(args, category)
        override = getattr(args, category + '_output')
        if override is not None and source is None:
            parser.error(f'--{category}-output requires --{category}')
        if source is not None:
            selected.append((category, source, override if override is not None else Path(default)))
    if not selected:
        parser.error('specify at least one of --templates, --areas, or --levels')
    try:
        # Finish every read, validation, and serialization before opening outputs.
        documents = []
        for category, source, target in selected:
            rows = read_catalog(source)
            documents.append((category, target, len(rows), build_mapping_table(rows)))
        validate_paths([source for _, source, _ in selected],
                       [target for _, _, target in selected])
        for category, target, count, document in documents:
            target.write_bytes(document)
            print(f'{category}: {count} rows -> {target}', flush=True)
    except (ConversionError, OSError, ValueError, UnicodeError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
