import json
import os
from pathlib import Path
import string
import sys
import tempfile
import unittest
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.argv=[sys.argv[0],'--windowed']
from PySide6.QtWidgets import QApplication,QComboBox,QLabel,QDialog,QTextBrowser
from PySide6.QtCore import QTimer
from app import Editor
from model import Graph
import i18n

class TranslationTests(unittest.TestCase):
    def tearDown(self):i18n.set_language('en')
    def test_manual_follows_language_with_english_fallback(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PLC_STATE_DIR':tmp}):
            w=Editor();self.addCleanup(w.close);self.addCleanup(w.shutdown)
            docs=Path(__file__).parent/'docs'
            for code in [*i18n.LANGUAGES,'missing']:
                expected=(docs/f'USER_GUIDE.{code if code in i18n.LANGUAGES else "en"}.md').read_text(encoding='utf-8').splitlines()[0].removeprefix('# ')
                with self.subTest(code=code),patch('app.language',return_value=code):
                    def inspect():
                        dialog=w.findChildren(QDialog)[-1]
                        self.assertTrue(dialog.findChild(QTextBrowser).toPlainText().startswith(expected))
                        self.assertIn('<<',dialog.findChild(QTextBrowser).toPlainText())
                        return 0
                    with patch.object(QDialog,'exec',side_effect=inspect):w.show_manual()
    def test_catalogs_have_identical_keys_and_placeholders(self):
        english=json.loads((i18n.ROOT/'en.json').read_text(encoding='utf-8'))['messages']
        def fields(text):return sorted(name for _,name,_,_ in string.Formatter().parse(text) if name is not None)
        for code in i18n.LANGUAGES:
            data=json.loads((i18n.ROOT/(code+'.json')).read_text(encoding='utf-8'))
            self.assertEqual(data['language'],code);self.assertEqual(set(data['messages']),set(english))
            for source,target in data['messages'].items():
                self.assertTrue(isinstance(target,str) and target);self.assertEqual(fields(source),fields(target),(code,source))
            i18n.set_language(code)
            self.assertIn('myfile.comp',i18n.tr('Exported myfile.comp • build: halcompile --compile myfile.comp'))
        i18n.set_language('hu')
        self.assertEqual(i18n.tr('Unknown constant: @speed_limit'),'Ismeretlen konstans: @speed_limit')
        self.assertEqual(i18n.tr('An unlisted diagnostic'),'An unlisted diagnostic')
        self.assertIn('törölve',i18n.tr('Updated debounce • removed 2 obsolete connection(s)'))
    def test_language_preferences_and_override(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PLC_STATE_DIR':tmp}):
            self.assertEqual(i18n.preferred_language(),'en');i18n.remember_language('pl')
            self.assertEqual(i18n.preferred_language(),'pl');self.assertEqual(i18n.preferred_language('de'),'de')
            i18n.settings_path().write_text('{invalid');self.assertEqual(i18n.preferred_language(),'en')
    def test_live_switch_keeps_graph_state_identifiers_and_internal_choices(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PLC_STATE_DIR':tmp}):
            w=Editor();self.addCleanup(w.close);self.addCleanup(w.shutdown)
            g=Graph();source=g.add('input');g.nodes[source]['p']['name']='open'
            fifo=g.add('fifo');g.connect(source,fifo,'in');w.graph=g;w.rebuild(source);w.show()
            w.run(True);w.timer.stop();w.tick();state=dict(g.state[fifo]);links=list(g.links)
            for code in i18n.LANGUAGES:
                w.language_picker.setCurrentIndex(w.language_picker.findData(code));app.processEvents()
                self.assertEqual(w.width(),800);self.assertEqual(w.height(),600)
                self.assertTrue(w.running);self.assertEqual(g.state[fifo],state);self.assertEqual(g.links,links)
                self.assertEqual(g.nodes[source]['p']['name'],'open');self.assertEqual(w.items[source].title_text.text(),'open')
                self.assertEqual(w.scroll.widget().objectName(),'simulation-panel')
            w.run(False);w.items[source].setSelected(True);w.selection()
            w.language_picker.setCurrentIndex(w.language_picker.findData('hu'));app.processEvents()
            trigger=next(c for c in w.scroll.widget().findChildren(QComboBox) if c.findData('rising')>=0)
            trigger.setCurrentIndex(trigger.findData('rising'));app.processEvents()
            self.assertEqual(g.nodes[source]['p']['edge'],'rising')
            self.assertEqual(trigger.currentText(),'felfutó él')
            self.assertEqual(i18n.preferred_language(),'hu')
            # The manual is available without a browser or a display server.
            QTimer.singleShot(0,lambda:next(d for d in w.findChildren(QDialog)).accept())
            w.show_manual()
            browser=w.findChild(QTextBrowser);self.assertIn('FIFO',browser.toPlainText())
