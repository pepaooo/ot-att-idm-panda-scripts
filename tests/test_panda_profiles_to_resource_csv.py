import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import panda_profiles_to_resource_csv as panda


def profile(template='6', area='HORUS', level='ULAVP', name='Horus User'):
    return {'template': {'key': template, 'name': name},
            'area': {'key': area, 'name': 'Horus Access'},
            'level': {'key': level, 'name': 'AVP'}}


EXPECTED = {
    '--generaRecursos': (
        '"create","","cn=PANDA-6-HORUS-ULAVP,cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system",'
        '"","","","Horus User-Horus Access-AVP","Horus User-Horus Access-AVP. Perfil del sistema PANDA",'
        '"cn=Permission,cn=MID-PANDA,cn=DriverSet1,ou=idm,ou=services,o=system",'
        r'"{\"ID\":\"6-HORUS-ULAVP\",\"ID2\":\"Horus User-Horus Access-AVP\"}",'
        '"UA","panda-perfil","false"\n'),
    '--genereRoles': (
        '"create","","","","cn=PANDA-6-HORUS-ULAVP,cn=Level10,cn=RoleDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system",'
        '"Horus User-Horus Access-AVP","Horus User-Horus Access-AVP. Rol por excepción de PANDA en IdM.",'
        '"panda-perfil","10","","",""\n'),
    '--generaAsociaciones': (
        '"resourceassociation","","","","cn=PANDA-6-HORUS-ULAVP,cn=Level10,cn=RoleDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system",'
        '"","Rol por excepción de PANDA en IDM","","","true",'
        '"cn=PANDA-Permission-DRS,cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system",'
        r'"{\"ID\":\"6-HORUS-ULAVP\",\"ID2\":\"Horus User-Horus Access-AVP\"}"' + '\n'),
    '--generaMapeoRol10': (
        '"Name","Id","DN"\n'
        '"Horus User-Horus Access-AVP","6-HORUS-ULAVP",'
        '"cn=PANDA-6-HORUS-ULAVP,cn=Level10,cn=RoleDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system"\n'),
}


class PandaConverterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.input = self.directory / 'profiles.json'
        self.save([profile()])

    def save(self, records):
        self.input.write_text(json.dumps({'content': records}, ensure_ascii=False), encoding='utf-8')

    def run_cli(self, args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = panda.main([str(self.input)] + [str(arg) for arg in args])
        return code, output.getvalue(), errors.getvalue()

    def test_exact_example_all_four_layouts(self):
        args = []
        for number, flag in enumerate(EXPECTED):
            args.extend([flag, self.directory / f'{number}.csv'])
        code, output, errors = self.run_cli(args)
        self.assertEqual(code, 0, errors)
        self.assertEqual(errors, '')
        self.assertEqual(output.count('1 rows'), 4)
        for number, (flag, expected) in enumerate(EXPECTED.items()):
            with self.subTest(flag=flag):
                self.assertEqual((self.directory / f'{number}.csv').read_text(encoding='utf-8'), expected)

    def test_each_flag_can_be_selected_independently(self):
        for flag, expected in EXPECTED.items():
            target = self.directory / (flag[2:] + '.csv')
            with self.subTest(flag=flag):
                code, _, errors = self.run_cli([flag, target])
                self.assertEqual(code, 0, errors)
                self.assertEqual(target.read_text(encoding='utf-8'), expected)

    def test_duplicate_combinations_preserve_first_order_and_leading_zeroes(self):
        first = profile(template='006')
        self.save([first, profile(template='7'), first])
        records = panda.load_profiles(self.input)
        self.assertEqual([record['ID'] for record in records], ['006-HORUS-ULAVP', '7-HORUS-ULAVP'])
        target = self.directory / 'mapping.csv'
        code, _, errors = self.run_cli(['--generaMapeoRol10', target])
        self.assertEqual(code, 0, errors)
        with target.open(encoding='utf-8', newline='') as handle:
            rows = list(csv.reader(handle))
        self.assertEqual([row[1] for row in rows[1:]], ['006-HORUS-ULAVP', '7-HORUS-ULAVP'])

    def test_metadata_round_trip_and_display_sanitization(self):
        name = 'Área "Core"\\Path\n*+~=/#;,ñ'
        self.save([profile(name=name)])
        record = panda.load_profiles(self.input)[0]
        original = name + '-Horus Access-AVP'
        for builder in (panda.row_recursos, panda.row_asociaciones):
            line = builder(record)
            metadata = '"{' + line.rsplit(',"{', 1)[1]
            if builder is panda.row_recursos:
                metadata = metadata.removesuffix(',"UA","panda-perfil","false"')
            self.assertEqual(json.loads(json.loads(metadata)),
                             {'ID': '6-HORUS-ULAVP', 'ID2': original})
        role = next(csv.reader(io.StringIO(panda.row_roles(record))))
        self.assertEqual(role[5], 'Área CorePath\nñ-Horus Access-AVP')
        self.assertEqual(role[6], original + '. Rol por excepción de PANDA en IdM.')
        mapping = next(csv.reader(io.StringIO(panda.row_mapeo_rol10(record))))
        self.assertEqual(mapping[0], original)

    def test_invalid_records_leave_existing_output_untouched(self):
        invalids = [None, {}, {'template': None}, profile(template=6), profile(template=''),
                    profile(name='   '), profile(template='x' * 55), profile(template='A,B'),
                    profile(template='A+B'), profile(template='A\\B'), profile(template='A\nB'),
                    profile(level='U ')]
        for invalid in invalids:
            with self.subTest(record=invalid):
                self.save([profile(), invalid])
                target = self.directory / 'roles.csv'
                target.write_text('existing')
                code, _, errors = self.run_cli(['--genereRoles', target])
                self.assertEqual(code, 1)
                self.assertIn('Error:', errors)
                self.assertEqual(target.read_text(), 'existing')

    def test_conflicting_names_and_joined_id_collisions_rejected(self):
        for records in ([profile(), profile(name='Different')],
                        [profile(template='A-B', area='C'), profile(template='A', area='B-C')]):
            with self.subTest(records=records):
                self.save(records)
                with self.assertRaises(panda.ConversionError):
                    panda.load_profiles(self.input)

    def test_cn_at_length_limit_is_preserved(self):
        self.save([profile(template='X' * 54, area='H', level='U')])
        record = panda.load_profiles(self.input)[0]
        self.assertEqual(record['CN'], 'PANDA-' + 'X' * 54 + '-H-U')
        self.assertEqual(len(record['CN']), 64)

    def test_invalid_json_and_envelopes(self):
        for text in ('not json', '[]', '{}', '{"content":null}', '{"content":{}}'):
            with self.subTest(text=text):
                self.input.write_text(text)
                code, _, errors = self.run_cli(['--genereRoles', self.directory / 'roles.csv'])
                self.assertEqual(code, 1)
                self.assertNotIn('Traceback', errors)

    def test_empty_outputs(self):
        self.save([])
        args = []
        for number, flag in enumerate(EXPECTED):
            args.extend([flag, self.directory / f'{number}.csv'])
        code, _, errors = self.run_cli(args)
        self.assertEqual(code, 0, errors)
        for number, flag in enumerate(EXPECTED):
            expected = '"Name","Id","DN"\n' if flag == '--generaMapeoRol10' else ''
            self.assertEqual((self.directory / f'{number}.csv').read_text(), expected)

    def test_no_output_flags_and_missing_input(self):
        self.assertEqual(self.run_cli([])[0], 3)
        self.input.unlink()
        code, _, errors = self.run_cli(['--genereRoles', self.directory / 'roles.csv'])
        self.assertEqual(code, 1)
        self.assertNotIn('Traceback', errors)

    def test_invalid_later_output_path_preserves_first_file(self):
        target = self.directory / 'roles.csv'
        target.write_text('existing')
        for invalid in (self.directory, self.directory / 'missing' / 'out.csv'):
            with self.subTest(invalid=invalid):
                code, _, _ = self.run_cli(['--genereRoles', target, '--generaAsociaciones', invalid])
                self.assertEqual(code, 1)
                self.assertEqual(target.read_text(), 'existing')

    def test_output_aliases_rejected_without_modifying_input_or_output(self):
        target = self.directory / 'roles.csv'
        target.write_text('existing')
        original = self.input.read_text()
        cases = [(['--genereRoles', self.input], original),
                 (['--genereRoles', target, '--generaAsociaciones', target], original)]
        for args, original_input in cases:
            self.assertEqual(self.run_cli(args)[0], 1)
            self.assertEqual(self.input.read_text(), original_input)
            self.assertEqual(target.read_text(), 'existing')

    def test_symlink_and_hardlink_aliases(self):
        for kind in ('symlink', 'hardlink'):
            alias = self.directory / (kind + '.csv')
            try:
                if kind == 'symlink':
                    alias.symlink_to(self.input)
                else:
                    os.link(self.input, alias)
            except (OSError, NotImplementedError):
                continue
            original = self.input.read_text()
            self.assertEqual(self.run_cli(['--genereRoles', alias])[0], 1)
            self.assertEqual(self.input.read_text(), original)
            target = self.directory / (kind + '-target.csv')
            target.write_text('existing')
            alias.unlink()
            if kind == 'symlink':
                alias.symlink_to(target)
            else:
                os.link(target, alias)
            self.assertEqual(self.run_cli(['--genereRoles', target, '--generaRecursos', alias])[0], 1)
            self.assertEqual(target.read_text(), 'existing')

    def test_write_failure_returns_error_without_traceback_or_success_count(self):
        target = self.directory / 'roles.csv'
        original_open = Path.open

        def fail_write(path, mode='r', *args, **kwargs):
            if mode == 'w':
                raise OSError('Disk write failed')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', fail_write):
            code, output, errors = self.run_cli(['--genereRoles', target])
        self.assertEqual(code, 1)
        self.assertNotIn('Wrote', output)
        self.assertIn('Disk write failed', errors)
        self.assertNotIn('Traceback', errors)


if __name__ == '__main__':
    unittest.main()
