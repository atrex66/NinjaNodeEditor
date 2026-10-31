import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model import Graph
from session import ProjectSession


class SessionTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name);self.session=ProjectSession(self.root/'state')

    def project(self,name='project.json',value=3):
        graph=Graph();node=graph.add('math');graph.set_expression(node,str(value))
        path=self.root/name;graph.save(path);return path,graph

    def test_remember_and_restore_last_project(self):
        path,original=self.project();self.session.remember(path)
        graph,loaded,notice=self.session.startup()
        self.assertEqual(graph.nodes,original.nodes);self.assertEqual(loaded,path.resolve())
        self.assertIn('Loaded',notice)
        self.assertEqual(json.loads(self.session.path.read_text())['last_project'],str(path.resolve()))

    def test_empty_switch_skips_all_settings_and_project_reads(self):
        path,_=self.project();self.session.remember(path);stored=self.session.path.read_bytes()
        with patch.object(self.session,'last_project',side_effect=AssertionError('must not read settings')),patch('session.Graph.load',side_effect=AssertionError('must not load a project')):
            graph,loaded,notice=self.session.startup(no_restore=True)
        self.assertEqual(graph.nodes,{});self.assertIsNone(loaded);self.assertIn('--no-restore',notice)
        self.assertEqual(self.session.path.read_bytes(),stored)

    def test_missing_or_broken_project_starts_empty(self):
        path,_=self.project();self.session.remember(path)
        for content in [None,'{broken json','[]','{"version": 99}',
                        '{"version": 3, "nodes": {"1": null}, "links": []}']:
            if content is None:path.unlink()
            else:path.write_text(content)
            graph,loaded,notice=self.session.startup()
            self.assertEqual(graph.nodes,{});self.assertIsNone(loaded)
            self.assertIn('Started empty',notice)
            self.assertEqual(self.session.last_project(),path.resolve())

    def test_broken_settings_starts_empty(self):
        self.session.path.parent.mkdir()
        for content in ['{invalid','[]','{"version": 1, "last_project": 42}']:
            self.session.path.write_text(content)
            graph,loaded,notice=self.session.startup()
            self.assertEqual(graph.nodes,{});self.assertIsNone(loaded)
            self.assertIn('settings',notice);self.assertEqual(self.session.path.read_text(),content)

    def test_explicit_project_overrides_and_remembers(self):
        old,_=self.project('old.json');new,original=self.project('new.json',12)
        self.session.remember(old)
        graph,loaded,notice=self.session.startup(new)
        self.assertEqual(graph.nodes,original.nodes);self.assertEqual(loaded,new.resolve())
        self.assertEqual(self.session.last_project(),new.resolve())

    def test_failed_explicit_load_preserves_previous_project(self):
        path,_=self.project();self.session.remember(path)
        graph,loaded,notice=self.session.startup(self.root/'missing.json')
        self.assertEqual(graph.nodes,{});self.assertIsNone(loaded)
        self.assertEqual(self.session.last_project(),path.resolve())

    def test_unwritable_settings_do_not_block_startup(self):
        path,original=self.project()
        with patch.object(self.session,'remember',side_effect=PermissionError('read-only state')):
            graph,loaded,notice=self.session.startup(path)
        self.assertEqual(graph.nodes,original.nodes);self.assertEqual(loaded,path.resolve())
        self.assertIn('could not remember',notice)


if __name__=='__main__':unittest.main()
