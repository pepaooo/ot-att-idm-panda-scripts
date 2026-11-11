#!/usr/bin/env python3
"""Convert combined PANDA profiles JSON into IdM resource, role, and mapping CSVs."""

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path


RESOURCE_BASE_DN = ('cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,'
                    'cn=DriverSet1,ou=idm,ou=services,o=system')
ROLE_BASE_DN = ('cn=Level10,cn=RoleDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,'
                'cn=DriverSet1,ou=idm,ou=services,o=system')
PERMISSION_DN = 'cn=Permission,cn=MID-PANDA,cn=DriverSet1,ou=idm,ou=services,o=system'
ASSOCIATION_RESOURCE_DN = 'cn=PANDA-Permission-DRS,' + RESOURCE_BASE_DN
CATEGORY = 'panda-perfil'
SANITIZE_NAME = re.compile(r'[\*\+\~=\/\\#",;]')


class ConversionError(Exception):
    """Input or output configuration cannot safely produce the requested CSVs."""


def load_profiles(input_path: Path) -> list:
    """Validate all combinations and return unique ID/ID2/CN records in input order."""
    try:
        with input_path.open(encoding='utf-8') as handle:
            data = json.load(handle)
    except (ValueError, UnicodeError):
        raise ConversionError('Input must contain valid UTF-8 JSON.') from None
    if not isinstance(data, dict) or not isinstance(data.get('content'), list):
        raise ConversionError('Input must be an object containing a content array.')

    records = []
    seen_keys = {}
    seen_ids = {}
    for index, profile in enumerate(data['content'], start=1):
        keys, names = [], []
        for kind in ('template', 'area', 'level'):
            value = profile.get(kind) if isinstance(profile, dict) else None
            if (not isinstance(value, dict)
                    or not isinstance(value.get('key'), str) or not value['key'].strip()
                    or not isinstance(value.get('name'), str) or not value['name'].strip()):
                raise ConversionError(f'Profile {index}: {kind} requires nonempty string key and name.')
            try:
                value['key'].encode('utf-8')
                value['name'].encode('utf-8')
            except UnicodeError:
                raise ConversionError(f'Profile {index}: {kind} contains invalid Unicode.') from None
            keys.append(value['key'])
            names.append(value['name'])

        keys, names = tuple(keys), tuple(names)
        identifier = '-'.join(keys)
        cn = 'PANDA-' + identifier
        if (len(cn) > 64 or cn[-1].isspace()
                or any(char in ',+"\\<>;=#' or unicodedata.category(char) == 'Cc' for char in cn)):
            raise ConversionError(f'Profile {index}: CN exceeds 64 characters or contains unsafe DN characters.')
        if keys in seen_keys:
            if seen_keys[keys] != names:
                raise ConversionError(f'Profile {index}: conflicting names for the same key combination.')
            continue
        if identifier in seen_ids and seen_ids[identifier] != keys:
            raise ConversionError(f'Profile {index}: different key combinations produce the same ID/CN.')
        seen_keys[keys] = names
        seen_ids[identifier] = keys
        records.append({'ID': identifier, 'ID2': '-'.join(names), 'CN': cn})
    return records


def validate_output_paths(input_path: Path, output_paths: list) -> None:
    """Reject invalid targets and path/inode aliases before any file is opened for writing."""
    resolved_paths = {input_path.resolve()}
    input_stat = input_path.stat()
    identities = {(input_stat.st_dev, input_stat.st_ino)}
    for path in output_paths:
        resolved = path.resolve()
        if resolved in resolved_paths:
            raise ConversionError('Output paths must differ from the input and from each other.')
        resolved_paths.add(resolved)
        if not resolved.parent.is_dir() or not os.access(resolved.parent, os.W_OK | os.X_OK):
            raise ConversionError(f'Output directory must exist and be writable: {path.parent}')
        if resolved.exists():
            if not resolved.is_file() or not os.access(resolved, os.W_OK):
                raise ConversionError(f'Output must be a writable regular file: {path}')
            stat = resolved.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in identities:
                raise ConversionError('Output files must not be links to the input or another output.')
            identities.add(identity)


def csv_quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def metadata_json(record: dict) -> str:
    return json.dumps({'ID': record['ID'], 'ID2': record['ID2']},
                      ensure_ascii=False, separators=(',', ':'))


def render_row(fields: list, metadata_index=None) -> str:
    # The IdM importer expects backslash escaping for the metadata field only.
    # JSON-encoding the JSON string quotes it and escapes both quotes and slashes.
    return ','.join(json.dumps(value, ensure_ascii=False) if index == metadata_index
                    else csv_quote(value) for index, value in enumerate(fields))


def row_recursos(record: dict) -> str:
    return render_row([
        'create', '', f"cn={record['CN']},{RESOURCE_BASE_DN}", '', '', '',
        SANITIZE_NAME.sub('', record['ID2']), record['ID2'] + '. Perfil del sistema PANDA',
        PERMISSION_DN, metadata_json(record), 'UA', CATEGORY, 'false',
    ], metadata_index=9)


def row_roles(record: dict) -> str:
    return render_row([
        'create', '', '', '', f"cn={record['CN']},{ROLE_BASE_DN}",
        SANITIZE_NAME.sub('', record['ID2']),
        record['ID2'] + '. Rol por excepción de PANDA en IdM.', CATEGORY, '10', '', '', '',
    ])


def row_asociaciones(record: dict) -> str:
    return render_row([
        'resourceassociation', '', '', '', f"cn={record['CN']},{ROLE_BASE_DN}", '',
        'Rol por excepción de PANDA en IDM', '', '', 'true', ASSOCIATION_RESOURCE_DN,
        metadata_json(record),
    ], metadata_index=11)


def row_mapeo_rol10(record: dict) -> str:
    return render_row([record['ID2'], record['ID'], f"cn={record['CN']},{ROLE_BASE_DN}"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_json', type=Path, help='Combined PANDA profiles.json with a content array')
    parser.add_argument('--generaRecursos', type=Path, metavar='CSV', help='Output resources CSV')
    parser.add_argument('--genereRoles', type=Path, metavar='CSV', help='Output Level10 roles CSV')
    parser.add_argument('--generaAsociaciones', type=Path, metavar='CSV', help='Output resource associations CSV')
    parser.add_argument('--generaMapeoRol10', type=Path, metavar='CSV', help='Output Name,Id,DN mapping CSV')
    args = parser.parse_args(argv)
    modes = [
        (args.generaRecursos, row_recursos, 'Recursos', None),
        (args.genereRoles, row_roles, 'Roles', None),
        (args.generaAsociaciones, row_asociaciones, 'Asociaciones', None),
        (args.generaMapeoRol10, row_mapeo_rol10, 'MapeoRol10', ['Name', 'Id', 'DN']),
    ]
    selected = [mode for mode in modes if mode[0] is not None]
    if not selected:
        print('Nothing to do: specify at least one output flag (see --help).', file=sys.stderr)
        return 3
    try:
        records = load_profiles(args.input_json)
        validate_output_paths(args.input_json, [mode[0] for mode in selected])
        for path, builder, label, header in selected:
            with path.open('w', encoding='utf-8', newline='') as handle:
                if header:
                    handle.write(render_row(header) + '\n')
                for record in records:
                    handle.write(builder(record) + '\n')
            print(f'[{label}] Wrote {len(records)} rows -> {path}', flush=True)
    except (ConversionError, OSError, ValueError, UnicodeError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
