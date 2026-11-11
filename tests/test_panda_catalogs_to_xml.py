import contextlib
import csv
import io
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import panda_catalogs_to_xml as converter


class CatalogXmlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.source = self.directory / 'catalog.csv'
        self.write_csv([['name', 'key'], ['Admin User', '14'], ['CSO Manager', '25']])

    def write_csv(self, rows):
        with self.source.open('w', encoding='utf-8', newline='') as handle:
            csv.writer(handle).writerows(rows)

    def run_cli(self, args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = converter.main([str(arg) for arg in args])
        return code, output.getvalue(), errors.getvalue()

    def test_each_category_default_filename(self):
        defaults = {'templates': 'MT-Catalogo-templates.xml',
                    'areas': 'MT-Catalogo-area.xml', 'levels': 'MT-Catalogo-level.xml'}
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            for category, filename in defaults.items():
                with self.subTest(category=category):
                    code, output, errors = self.run_cli(['--' + category, self.source])
                    self.assertEqual(code, 0, errors)
                    self.assertIn('2 rows', output)
                    raw = Path(filename).read_bytes()
                    self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
                    self.assertIn(b'\n\t<row>', raw)
                    root = ET.fromstring(raw)
                    self.assertEqual(root.tag, 'mapping-table')
                    self.assertEqual([child.tag for child in root], ['col-def', 'col-def', 'row', 'row'])
                    self.assertEqual([child.attrib for child in root.findall('col-def')],
                                     [{'name': 'id', 'type': 'nocase'}, {'name': 'name', 'type': 'nocase'}])
                    self.assertEqual([[col.text for col in row] for row in root.findall('row')],
                                     [['14', 'Admin User'], ['25', 'CSO Manager']])
        finally:
            os.chdir(previous)

    def test_all_categories_and_output_overrides(self):
        args = []
        targets = []
        for category in ('templates', 'areas', 'levels'):
            source = self.directory / (category + '.csv')
            source.write_text(f'name,key\n{category},{category.upper()}\n')
            target = self.directory / ('custom-' + category + '.xml')
            targets.append(target)
            args.extend(['--' + category, source, '--' + category + '-output', target])
        code, output, errors = self.run_cli(args)
        self.assertEqual(code, 0, errors)
        self.assertEqual(output.count('1 rows'), 3)
        for category, target in zip(('templates', 'areas', 'levels'), targets):
            self.assertEqual([col.text for col in ET.parse(target).getroot().find('row')],
                             [category.upper(), category])

    def test_header_order_bom_extra_columns_and_duplicate_order(self):
        self.source.write_text('\ufeffkey,ignored,name\n001,x,First\n002,y,Second\n001,z,First\n',
                               encoding='utf-8')
        rows = converter.read_catalog(self.source)
        self.assertEqual(rows, [('001', 'First'), ('002', 'Second'), ('001', 'First')])
        root = ET.fromstring(converter.build_mapping_table(rows))
        self.assertEqual([[col.text for col in row] for row in root.findall('row')],
                         [['001', 'First'], ['002', 'Second'], ['001', 'First']])

    def test_unicode_escaping_whitespace_and_multiline_round_trip(self):
        name = '  Área & <Core>, "Transport"\nLine two\r\nLine three\rEnd\t  '
        self.write_csv([['name', 'key'], [name, '001&<']])
        raw = converter.build_mapping_table(converter.read_catalog(self.source))
        self.assertIn('Área'.encode(), raw)
        self.assertIn(b'&amp;', raw)
        self.assertIn(b'&lt;', raw)
        self.assertIn(b'&#13;', raw)
        self.assertEqual([col.text for col in ET.fromstring(raw).find('row')], ['001&<', name])

    def test_header_only_csv_produces_column_definitions(self):
        self.write_csv([['name', 'key']])
        root = ET.fromstring(converter.build_mapping_table(converter.read_catalog(self.source)))
        self.assertEqual(len(root.findall('col-def')), 2)
        self.assertEqual(root.findall('row'), [])

    def test_invalid_csv_and_xml_text_preserve_existing_output(self):
        target = self.directory / 'catalog.xml'
        bad = ['', 'name\nUser\n', 'name,key,name\nUser,1,Other\n',
               'name,key,\nUser,1,x\n', 'name,key\nUser\n', 'name,key\nUser,1,extra\n',
               'name,key\n,1\n', 'name,key\nUser, \n', 'name,key\n"unclosed,1\n',
               'name,key\n"User"junk,1\n', 'name,key\nUser\x00,1\n',
               'name,key\nUser,1\x0b\n', 'name,key\nUser\uffff,1\n']
        for text in bad:
            with self.subTest(text=text):
                self.source.write_text(text, encoding='utf-8')
                target.write_text('existing')
                code, _, errors = self.run_cli(['--templates', self.source, '--templates-output', target])
                self.assertEqual(code, 1)
                self.assertIn('Error:', errors)
                self.assertNotIn('Traceback', errors)
                self.assertEqual(target.read_text(), 'existing')

    def test_missing_input_and_invalid_utf8(self):
        target = self.directory / 'catalog.xml'
        for payload in (None, b'name,key\n\xff,1\n'):
            if payload is None:
                self.source.unlink()
            else:
                self.source.write_bytes(payload)
            self.assertEqual(self.run_cli(['--templates', self.source, '--templates-output', target])[0], 1)
            self.assertFalse(target.exists())

    def test_no_inputs_and_orphan_overrides(self):
        for args in ([], ['--templates-output', 'custom.xml'],
                     ['--templates', self.source, '--areas-output', 'custom.xml']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    converter.main([str(arg) for arg in args])
                self.assertEqual(caught.exception.code, 2)

    def test_later_bad_input_or_output_preserves_first_output(self):
        first = self.directory / 'first.xml'
        other_input = self.directory / 'areas.csv'
        other_input.write_text('wrong,headers\n')
        for other_source, other_target in (
                (other_input, self.directory / 'second.xml'),
                (self.source, self.directory / 'missing' / 'second.xml'),
                (self.source, self.directory)):
            first.write_text('existing')
            code, _, _ = self.run_cli(['--templates', self.source, '--templates-output', first,
                                      '--areas', other_source, '--areas-output', other_target])
            self.assertEqual(code, 1)
            self.assertEqual(first.read_text(), 'existing')

    def test_path_aliases_across_all_selected_inputs_and_outputs(self):
        target = self.directory / 'first.xml'
        target.write_text('existing')
        original = self.source.read_text()
        for second_target in (target, self.source):
            code, _, _ = self.run_cli(['--templates', self.source, '--templates-output', target,
                                      '--areas', self.source, '--areas-output', second_target])
            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(), 'existing')
            self.assertEqual(self.source.read_text(), original)

    def test_symlink_and_hardlink_aliases(self):
        for kind in ('symlink', 'hardlink'):
            alias = self.directory / (kind + '.xml')
            try:
                if kind == 'symlink':
                    alias.symlink_to(self.source)
                else:
                    os.link(self.source, alias)
            except (OSError, NotImplementedError):
                continue
            original = self.source.read_text()
            self.assertEqual(self.run_cli(['--levels', self.source, '--levels-output', alias])[0], 1)
            self.assertEqual(self.source.read_text(), original)
            target = self.directory / (kind + '-target.xml')
            target.write_text('existing')
            alias.unlink()
            if kind == 'symlink':
                alias.symlink_to(target)
            else:
                os.link(target, alias)
            code, _, _ = self.run_cli(['--templates', self.source, '--templates-output', target,
                                      '--levels', self.source, '--levels-output', alias])
            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(), 'existing')

    def test_write_failure_reports_error_without_success(self):
        original_open = Path.open

        def fail_write(path, mode='r', *args, **kwargs):
            if 'w' in mode:
                raise OSError('Disk write failed')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', fail_write):
            code, output, errors = self.run_cli(['--templates', self.source,
                                                '--templates-output', self.directory / 'out.xml'])
        self.assertEqual(code, 1)
        self.assertEqual(output, '')
        self.assertIn('Disk write failed', errors)
        self.assertNotIn('Traceback', errors)


if __name__ == '__main__':
    unittest.main()
