import contextlib
import csv
import io
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import panda_roles10_to_mapping_xml as converter


ROLE_DN = ('cn=PANDA-6-HORUS-ULAVP,cn=Level10,cn=RoleDefs,cn=RoleConfig,cn=AppConfig,'
           'cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system')
GROUP_DN = 'cn=grupo-aprobacion-panda,ou=approvers,ou=workflows,ou=groups,ou=att,o=data'


class RoleApproversXmlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.approvers = self.directory / 'approvers.csv'
        self.roles = self.directory / 'roles.csv'
        self.output = self.directory / 'mapping.xml'
        self.approver_rows = [['Name', 'Id', 'Grupo IDM'],
                              ['Horus User-Horus Access-AVP', '6-HORUS-ULAVP', GROUP_DN]]
        self.role_rows = [['Name', 'Id', 'DN'],
                          ['Horus User-Horus Access-AVP', '6-HORUS-ULAVP', ROLE_DN]]
        self.save()

    def write_csv(self, path, rows, delimiter=','):
        with path.open('w', encoding='utf-8', newline='') as handle:
            csv.writer(handle, delimiter=delimiter).writerows(rows)

    def save(self):
        self.write_csv(self.approvers, self.approver_rows, '\t')
        self.write_csv(self.roles, self.role_rows)

    def run_cli(self, extra=()):
        args = [self.approvers, self.output, '--perfilMapeo', self.roles, *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = converter.main([str(arg) for arg in args])
        return code, out.getvalue(), err.getvalue()

    def xml_rows(self):
        root = ET.parse(self.output).getroot()
        return [[col.text for col in row] for row in root.findall('row')]

    def test_example_exact_xml_columns_and_values(self):
        code, output, errors = self.run_cli()
        self.assertEqual(code, 0, errors)
        self.assertIn('1 role mappings', output)
        self.assertIn('1 approver mappings', output)
        self.assertIn('1 rows', output)
        raw = self.output.read_bytes()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'\n\t<row>', raw)
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, 'mapping-table')
        self.assertEqual([node.attrib for node in root.findall('col-def')], [
            {'name': name, 'type': 'nocase'} for name in
            ('DN de perfil', 'Primer aprobador', 'Segundo aprobador', 'Tercer aprobador')])
        self.assertEqual(self.xml_rows(),
                         [[ROLE_DN, 'Gerente o nivel superior', GROUP_DN, '#NOT_REQUIRED#']])

    def test_join_by_id_despite_name_differences_and_preserve_approver_order(self):
        self.approver_rows += [['Same name', '0007', 'Second group']]
        self.role_rows = [self.role_rows[0], ['Same name', '0007', 'cn=second-role'],
                          ['Changed name', '6-HORUS-ULAVP', ROLE_DN],
                          ['Unused role', 'UNUSED', 'cn=unused']]
        self.save()
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual([row[0] for row in self.xml_rows()], [ROLE_DN, 'cn=second-role'])
        records = converter.load_records(self.roles, ('Name', 'Id', 'DN'), ',')
        self.assertIn('0007', records)

    def test_delimiter_variants(self):
        for argument, delimiter in (('tab', '\t'), ('comma', ','), (';', ';'), ('\t', '\t')):
            with self.subTest(argument=argument):
                self.write_csv(self.approvers, self.approver_rows, delimiter)
                code, _, errors = self.run_cli(['--delimiter', argument])
                self.assertEqual(code, 0, errors)
                self.assertEqual(self.xml_rows()[0][2], GROUP_DN)

    def test_bom_header_order_extra_columns_and_trimming(self):
        self.approvers.write_text('\ufeffId\tGrupo IDM\tName\tExtra\n 001 \t Group \t Label \tx\n',
                                  encoding='utf-8')
        self.roles.write_text('\ufeffDN,Name,Id\n cn=exact-dn ,Different label, 001 \n', encoding='utf-8')
        code, _, errors = self.run_cli()
        self.assertEqual(code, 0, errors)
        self.assertEqual(self.xml_rows(), [['cn=exact-dn', 'Gerente o nivel superior', 'Group', '#NOT_REQUIRED#']])

    def test_xml_unicode_escaping_and_interior_newlines(self):
        group = 'cn=Área & <Group> "A"\nLine\r\nNext\rEnd'
        self.approver_rows[1][2] = group
        self.save()
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.xml_rows()[0][2], group)
        self.assertIn('Área'.encode(), self.output.read_bytes())
        self.assertIn(b'&amp;', self.output.read_bytes())
        self.assertIn(b'&#13;', self.output.read_bytes())

    def test_identical_duplicates_in_both_files_emit_one_row(self):
        self.approver_rows += [self.approver_rows[1]]
        self.role_rows += [self.role_rows[1]]
        self.save()
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(len(self.xml_rows()), 1)

    def test_conflicting_duplicates_and_missing_late_id_preserve_output(self):
        cases = [('approvers', ['Another name', '6-HORUS-ULAVP', GROUP_DN]),
                 ('approvers', ['Horus User-Horus Access-AVP', '6-HORUS-ULAVP', 'Different group']),
                 ('roles', ['Horus User-Horus Access-AVP', '6-HORUS-ULAVP', 'cn=other']),
                 ('approvers', ['Missing', 'NOT-IN-LOOKUP', GROUP_DN])]
        for which, row in cases:
            with self.subTest(which=which, row=row):
                self.save()
                path = self.approvers if which == 'approvers' else self.roles
                with path.open('a', encoding='utf-8', newline='') as handle:
                    csv.writer(handle, delimiter='\t' if which == 'approvers' else ',').writerow(row)
                self.output.write_text('existing')
                code, _, errors = self.run_cli()
                self.assertEqual(code, 1)
                self.assertNotIn('Traceback', errors)
                self.assertEqual(self.output.read_text(), 'existing')

    def test_header_only_approvers(self):
        self.write_csv(self.approvers, [self.approver_rows[0]], '\t')
        self.assertEqual(self.run_cli()[0], 0)
        root = ET.parse(self.output).getroot()
        self.assertEqual(len(root.findall('col-def')), 4)
        self.assertEqual(root.findall('row'), [])

    def test_invalid_input_csv_and_xml_text_preserve_output(self):
        cases = [b'', b'Name\tId\nA\t1\n', b'Name\tId\tId\tGrupo IDM\n',
                 b'Name\tId\tGrupo IDM\t\n', b'Name\tId\tGrupo IDM\nA\t1\n',
                 b'Name\tId\tGrupo IDM\nA\t1\tG\textra\n',
                 b'Name\tId\tGrupo IDM\nA\t1\t \n', b'Name\tId\tGrupo IDM\n \t1\tG\n',
                 b'Name\tId\tGrupo IDM\n"unfinished', b'Name\tId\tGrupo IDM\n"A"junk\t1\tG\n',
                 b'Name\tId\tGrupo IDM\nA\t1\t\xff\n', b'Name\tId\tGrupo IDM\nA\t1\tG\x00\n']
        for payload in cases:
            with self.subTest(payload=payload):
                self.approvers.write_bytes(payload)
                self.output.write_text('existing')
                code, _, errors = self.run_cli()
                self.assertEqual(code, 1)
                self.assertIn('Error:', errors)
                self.assertEqual(self.output.read_text(), 'existing')

    def test_blank_lookup_dn_or_invalid_unused_lookup_fails(self):
        for dn in (' ', 'cn=bad\x01'):
            self.role_rows.append(['Unused', 'UNUSED', dn])
            self.save()
            self.output.write_text('existing')
            self.assertEqual(self.run_cli()[0], 1)
            self.assertEqual(self.output.read_text(), 'existing')
            self.role_rows.pop()

    def test_invalid_cli_and_delimiters(self):
        for args in ([], [str(self.approvers), str(self.output)],
                     [str(self.approvers), str(self.output), '--perfilMapeo', str(self.roles),
                      '--delimiter', 'invalid'],
                     [str(self.approvers), str(self.output), '--perfilMapeo', str(self.roles),
                      '--delimiter', '\n']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    converter.main(args)
                self.assertEqual(caught.exception.code, 2)

    def test_missing_files_and_invalid_output_paths(self):
        for target in (self.directory, self.directory / 'missing' / 'out.xml'):
            self.output = target
            code, _, errors = self.run_cli()
            self.assertEqual(code, 1)
            self.assertNotIn('Traceback', errors)
        self.output = self.directory / 'out.xml'
        self.roles.unlink()
        self.assertEqual(self.run_cli()[0], 1)

    def test_output_cannot_alias_either_input(self):
        for source in (self.approvers, self.roles):
            original = source.read_bytes()
            self.output = source
            self.assertEqual(self.run_cli()[0], 1)
            self.assertEqual(source.read_bytes(), original)

    def test_symlink_and_hardlink_aliases_to_both_inputs(self):
        for kind in ('symlink', 'hardlink'):
            for index, source in enumerate((self.approvers, self.roles)):
                alias = self.directory / f'{kind}-{index}.xml'
                try:
                    if kind == 'symlink':
                        alias.symlink_to(source)
                    else:
                        os.link(source, alias)
                except (OSError, NotImplementedError):
                    continue
                original = source.read_bytes()
                self.output = alias
                self.assertEqual(self.run_cli()[0], 1)
                self.assertEqual(source.read_bytes(), original)

    def test_write_failure_reports_error_without_xml_success(self):
        original_open = Path.open

        def fail_write(path, mode='r', *args, **kwargs):
            if 'w' in mode:
                raise OSError('Disk write failed')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', fail_write):
            code, output, errors = self.run_cli()
        self.assertEqual(code, 1)
        self.assertNotIn('written', output)
        self.assertIn('Disk write failed', errors)
        self.assertNotIn('Traceback', errors)


if __name__ == '__main__':
    unittest.main()
