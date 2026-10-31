import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
sys.argv=[sys.argv[0],'--windowed']
import tempfile
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication,QComboBox,QLineEdit,QLabel
from PySide6.QtCore import Qt
from app import Editor,ExpressionEdit

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from unittest.mock import patch
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        state=patch.dict(os.environ,{'PLC_STATE_DIR':directory.name});state.start();self.addCleanup(state.stop)
    def editor(self):
        w=Editor();self.addCleanup(w.shutdown);self.addCleanup(w.close);w.show();self.app.processEvents();return w
    def test_global_hal_chooser_is_transient_child_of_global_io(self):
        from unittest.mock import patch
        from PySide6.QtCore import QTimer
        from io_dialogs import GlobalIOWindow,HALChooser
        editor=self.editor();window=GlobalIOWindow(editor);self.addCleanup(window.close)
        window.show();self.app.processEvents();observations=[]
        original_exec=HALChooser.exec
        def execute(chooser):
            def inspect():
                observations.append((chooser.parentWidget(),chooser.windowModality(),
                    chooser.windowHandle().transientParent(),chooser.editor))
                chooser.reject()
            QTimer.singleShot(0,inspect)
            return original_exec(chooser)
        with patch.object(HALChooser,'exec',execute):window.add_hal()
        self.assertEqual(observations,[(window,Qt.WindowModality.WindowModal,window.windowHandle(),editor)])
        self.assertTrue(window.isVisible())
    def test_live_install_password_dialog_uses_hidden_input_and_handles_cancel(self):
        from unittest.mock import Mock,patch
        import json
        w=self.editor();process=Mock();w.live_process=process
        try:
            for answer in (('test-only-secret',True),('',False)):
                with patch('app.QInputDialog.getText',return_value=answer) as prompt:
                    w.apply_live_event(dict(event='authorization'))
                    self.assertEqual(prompt.call_args.args[-1],QLineEdit.EchoMode.Password)
                    message=json.loads(process.write.call_args.args[0])
                    self.assertEqual(message,dict(cmd='authorize',password=answer[0] if answer[1] else None))
        finally:w.live_process=None
    def test_wheel_zoom_recovers_after_module_auto_fit_outside_limits(self):
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtCore import QPoint,QPointF
        from model import Graph
        w=self.editor();w.resize(1600,1000);self.app.processEvents()
        g=Graph();small=g.add_module('Small');large=g.add_module('Large')
        g.add('input',(0,0),module=small)
        g.add('input',(-20000,0),module=large);g.add('output',(20000,0),module=large)
        w.graph=g;w.rebuild()
        def wheel(delta):
            point=w.view.viewport().rect().center()
            event=QWheelEvent(QPointF(point),QPointF(w.view.viewport().mapToGlobal(point)),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
            self.app.sendEvent(w.view.viewport(),event)
        for module,delta,bound in ((small,-120,2.5),(large,120,.18)):
            w.module_picker.setCurrentIndex(w.module_picker.findData(module));self.app.processEvents()
            fitted=w.view.transform().m11()
            self.assertTrue(fitted>bound if delta<0 else fitted<bound)
            wheel(delta);changed=w.view.transform().m11()
            self.assertTrue(changed<fitted if delta<0 else changed>fitted)
            for _ in range(60):wheel(delta)
            self.assertGreaterEqual(w.view.transform().m11(),.18-1e-9)
            self.assertLessEqual(w.view.transform().m11(),2.5+1e-9)
            before=w.view.transform().m11();wheel(-delta)
            self.assertNotEqual(w.view.transform().m11(),before)
    def test_mouse_connection_selection_and_delete_at_different_zoom(self):
        from PySide6.QtGui import QMouseEvent,QKeyEvent
        from PySide6.QtCore import QEvent,QPointF
        from PySide6.QtCore import QPoint
        from model import Graph
        for scale in (1,.25,2):
            w=self.editor();w.new();g=Graph();a=g.add('input',(0,0));b=g.add('output',(500,0));g.connect(a,b,'in');w.graph=g;w.rebuild();w.view.resetTransform();w.view.scale(scale,scale);w.view.centerOn(350,60);self.app.processEvents()
            edge=w.edges[0];point=w.view.mapFromScene(edge.path().pointAtPercent(.5))+QPoint(0,4)
            for event_type,buttons in ((QEvent.Type.MouseButtonPress,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,Qt.MouseButton.NoButton)):
                event=QMouseEvent(event_type,QPointF(point),QPointF(w.view.viewport().mapToGlobal(point)),Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier)
                self.app.sendEvent(w.view.viewport(),event)
            self.app.processEvents()
            self.assertTrue(edge.isSelected(),scale)
            w.update_edges();self.assertTrue(w.edges[0].isSelected())
            self.app.sendEvent(w.view,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier));self.app.processEvents()
            self.assertEqual(g.links,[]);self.assertEqual(len(g.nodes),2)
    def test_logger_dynamic_inputs_and_locked_input_count(self):
        from PySide6.QtWidgets import QDoubleSpinBox
        w=self.editor();w.new();w.add('logger');logger=w.selected
        count=w.scroll.widget().findChild(QDoubleSpinBox,'logger:input_count');count.setValue(3);self.app.processEvents()
        self.assertEqual(w.graph.inputs(logger),('in1','in2','in3','trigger'))
        source=w.graph.add('input');w.graph.nodes[source]['p']['dtype']='s32';w.graph.connect(source,logger,'in2');w.rebuild(logger)
        self.assertIn('s32',w.items[logger].input_labels['in2'][0].text())
        count=w.scroll.widget().findChild(QDoubleSpinBox,'logger:input_count');self.assertFalse(count.isEnabled())
        w.change(logger,'input_count',1);self.assertEqual(w.graph.nodes[logger]['p']['input_count'],3)
        w.disconnect(logger,True);self.app.processEvents();w.change(logger,'input_count',1);self.assertEqual(w.graph.inputs(logger),('in1','trigger'))
    def test_logger_simulation_saves_in_project_directory(self):
        from model import Graph
        import csv
        w=self.editor();w.new();g=Graph();value=g.add('input');g.nodes[value]['p'].update(name='sampled-value',dtype='s32',value=-123)
        trigger=g.add('input');g.nodes[trigger]['p']['value']=1
        logger=g.add('logger');g.nodes[logger]['p'].update(filename='history.csv',sample_ms=1)
        g.connect(value,logger,'in1');g.connect(trigger,logger,'trigger');w.graph=g;w.rebuild(logger)
        with tempfile.TemporaryDirectory() as tmp:
            w.project=Path(tmp)/'project.json';w.run(True);w.timer.stop();w.tick()
            for future in list(w.logger_writer.futures.values()):future.result(timeout=3)
            w.poll_logger();self.assertIn('history.csv',w.status.text())
            with (Path(tmp)/'history.csv').open() as stream:rows=list(csv.reader(stream))
            self.assertEqual(rows[1][1],'-123');self.assertIn('sampled-value.out [s32]',rows[0][1])
            label=w.scroll.widget().findChild(QLabel,f'simulation-value:{logger}:value');self.assertEqual(label.text(),'Samples: 1 / 1000')
    def test_global_banks_visibility_driver_jump_and_positions(self):
        from model import Graph
        w=self.editor();w.new();g=Graph();a=g.add('input',global_io=True);out=g.add('output',global_io=True)
        module=g.add_module('Tools');source=g.add('input',(200,100),module=module);g.connect(source,out,'in');g.view_module=0;w.graph=g;w.rebuild()
        self.assertIn(a,w.items);self.assertIn(out,w.items);self.assertNotIn(source,w.items)
        self.assertIn('Tools',w.items[out].driver_link.text())
        w.banks[0].setPos(100,200);self.assertEqual(g.global_positions['0:input'],[100,200])
        w.jump_to_node(source);self.assertEqual(g.view_module,module);self.assertTrue(w.items[source].isSelected());self.assertIn(a,w.items)
        w.graph.view_module=0;w.rebuild();self.assertEqual(w.banks[0].pos().x(),100)
    def test_hal_dialog_catalogue_selection_and_existing_driver(self):
        from hal_bindings import Catalogue
        from io_dialogs import HALChooser
        w=self.editor();w.new();w.add('input');i=w.selected
        w.hal_catalogue=Catalogue.parse('io float OUT 12.5 io.position\n','')
        dialog=HALChooser(w,'input',i);self.addCleanup(dialog.close)
        self.assertEqual(dialog.table.rowCount(),1);dialog.table.selectRow(0);dialog.choose()
        self.assertEqual(dialog.chosen[0]['name'],'io.position');self.assertEqual(dialog.chosen[0]['dtype'],'float')
    def test_live_values_display_real_outputs_and_runtime(self):
        from model import Graph
        from unittest.mock import patch
        w=self.editor();w.new();g=Graph();a=g.add('input');out=g.add('output');g.connect(a,out,'in');w.graph=g;w.rebuild();w.run(True);w.timer.stop()
        with patch.object(g,'step',side_effect=AssertionError('local simulation must not run')):
            w.apply_live_event(dict(event='values',inputs={str(a):1},values=[dict(node=a,port='out',value=1),dict(node=out,port=None,value=1)],time_ns=1234,tmax_ns=5678,hal_time=9012))
        self.assertEqual(g.values[out],1);self.assertIn('1.234 µs',w.status.text());self.assertIn('5.678 µs',w.status.text());self.assertIn('9012',w.status.text())
    def test_timer_creation_properties_and_simulation_monitor(self):
        from PySide6.QtWidgets import QPushButton,QDoubleSpinBox
        w=self.editor();w.new()
        next(b for b in w.findChildren(QPushButton) if b.text()=='+ Timer').click()
        timer=w.selected;self.assertEqual(w.graph.nodes[timer]['kind'],'timer')
        duration=w.scroll.widget().findChild(QDoubleSpinBox,'time:duration_ms')
        self.assertEqual(duration.decimals(),0);self.assertEqual(duration.singleStep(),1)
        duration.setValue(20);self.assertEqual(w.graph.nodes[timer]['p']['duration_ms'],20)
        mode=next(c for c in w.scroll.widget().findChildren(QComboBox) if c.findData('pulse')>=0)
        mode.setCurrentIndex(mode.findData('pulse'));self.assertEqual(w.graph.nodes[timer]['p']['timer_mode'],'pulse')
        start=w.graph.add('input');w.graph.nodes[start]['p']['value']=1
        w.graph.connect(start,timer,'trigger');w.rebuild(timer)
        w.run(True);w.timer.stop();w.tick();w.tick()
        label=w.scroll.widget().findChild(QLabel,f'simulation-value:{timer}:out')
        self.assertEqual(label.text(),'ON (1)');w.tick();self.assertEqual(label.text(),'OFF (0)')
    def test_workspace_toolbar_order_fullscreen_and_selection_panel(self):
        w=self.editor();w.new();self.app.processEvents()
        groups=[w.toolbars[name] for name in ('Project','Settings','Modules','Nodes')]
        self.assertEqual([w.findChild(QLabel,'toolbar-label-'+name.lower()).text() for name in ('Project','Settings','Modules')],['Project','Settings','Modules'])
        self.assertEqual(groups[-1].title(),'Nodes')
        self.assertEqual([group.y() for group in groups],sorted(group.y() for group in groups))
        self.assertFalse(w.scroll.isVisible());wide=w.view.width()
        w.add('input');self.app.processEvents()
        self.assertTrue(w.scroll.isVisible());self.assertLess(w.view.width(),wide)
        links=list(w.graph.links);w.scene.clearSelection();self.app.processEvents()
        self.assertFalse(w.scroll.isVisible())
        w.fullscreen_button.click();self.app.processEvents()
        self.assertTrue(w.isFullScreen());self.assertTrue(groups[-1].isVisible())
        self.assertTrue(all(not group.isVisible() for group in groups[:-1]))
        self.assertFalse(w.status.isVisible());self.assertTrue(w.fullscreen_button.isVisible())
        w.items[next(iter(w.items))].setSelected(True);self.app.processEvents()
        self.assertTrue(w.scroll.isVisible())
        w.scene.clearSelection();w.run(True);w.timer.stop();w.tick();self.app.processEvents()
        self.assertTrue(w.scroll.isVisible());self.assertEqual(w.scroll.widget().objectName(),'simulation-panel')
        state=dict(w.graph.values);w.fullscreen_button.click();self.app.processEvents()
        self.assertFalse(w.isFullScreen());self.assertTrue(all(group.isVisible() for group in groups))
        self.assertTrue(w.running);self.assertEqual(w.graph.values,state);self.assertEqual(w.graph.links,links)
        w.run(False);self.app.processEvents();self.assertFalse(w.scroll.isVisible())
        # Leaving the workspace mode preserves a display already running fullscreen.
        w.showFullScreen();self.app.processEvents();w.fullscreen_button.click();w.fullscreen_button.click()
        self.assertTrue(w.isFullScreen())
    def test_module_views_keep_global_simulation_and_connections(self):
        from model import Graph
        from PySide6.QtWidgets import QDoubleSpinBox
        from unittest.mock import patch
        w=self.editor();w.graph=Graph()
        source=w.graph.add('input');w.graph.nodes[source]['p'].update(dtype='float',value=4)
        output=w.graph.add('output');w.graph.nodes[output]['p']['dtype']='float';w.graph.connect(source,output,'in');w.rebuild(output)
        with patch('app.QInputDialog.getText',return_value=('Outputs',True)):w.new_module()
        module=w.graph.view_module;self.assertEqual(w.items,{})
        w.graph.move_nodes([output],module);w.rebuild(output)
        self.assertEqual(set(w.items),{output});self.assertEqual(w.edges,[])
        self.assertIn('Main / node',w.items[output].ports['in','in'].toolTip())
        with patch('app.QInputDialog.getText',return_value=('Machine outputs',True)):w.rename_module()
        self.assertEqual(w.module_picker.currentText(),'Machine outputs')
        w.run(True);w.timer.stop();w.tick();self.assertEqual(w.graph.values[output],4)
        control=w.scroll.widget().findChild(QDoubleSpinBox,f'simulation-input:{source}');control.setValue(8);w.tick()
        self.assertEqual(w.graph.values[output],8)
        w.module_picker.setCurrentIndex(w.module_picker.findData(None))
        self.assertIsNone(w.graph.view_module);self.assertEqual(set(w.items),{source,output});self.assertEqual(len(w.edges),1)
        self.assertEqual(w.graph.values[output],8)
        w.module_picker.setCurrentIndex(w.module_picker.findData(module));w.remove_module();w.tick()
        self.assertEqual(w.graph.modules,{0:'Main'});self.assertEqual(set(w.items),{source,output})
        self.assertEqual(w.graph.values[output],8);self.assertEqual(w.graph.links,[[source,'out',output,'in']])
        w.run(False);w.scene.clearSelection();w.items[source].setSelected(True)
        module=w.graph.add_module('Inputs');w.move_selected(module)
        self.assertEqual(set(w.items),{source});self.assertEqual(w.graph.nodes[source]['module'],module)
        w.add('constant');self.assertEqual(w.graph.nodes[w.selected]['module'],module)
    def test_constant_node_expression_parameter_picker_and_live_edit(self):
        from PySide6.QtWidgets import QPushButton,QDoubleSpinBox
        from model import Graph
        w=self.editor();w.graph=Graph();w.rebuild()
        next(b for b in w.findChildren(QPushButton) if b.text()=='+ Const').click()
        constant=w.selected;w.change(constant,'name','gain');w.change(constant,'value',3)
        self.assertEqual(w.items[constant].ports,{})
        self.assertEqual(w.items[constant].title_text.text(),'@gain')
        w.add('math');math=w.selected;w.change(math,'expression','@gain * 2');self.app.processEvents()
        self.assertEqual(w.items[math].ports.keys(),{('out','result')})
        w.add('pid');pid=w.selected
        picker=w.scroll.widget().findChild(QComboBox,'reference:parameter:kp')
        index=picker.findData('@gain');picker.setCurrentIndex(index);picker.activated.emit(index);self.app.processEvents()
        self.assertEqual(w.graph.nodes[pid]['p']['kp'],'@gain')
        self.assertFalse(w.scroll.widget().findChild(QDoubleSpinBox,'pid:kp').isEnabled())
        w.run(True);w.timer.stop();w.tick()
        control=w.scroll.widget().findChild(QDoubleSpinBox,f'simulation-input:{constant}');control.setValue(4);w.tick()
        self.assertEqual(w.graph.values[math],8)
        w.run(False);w.scene.clearSelection();w.items[constant].setSelected(True);w.delete_selected()
        self.assertIn(constant,w.graph.nodes);self.assertIn('still in use',w.status.text())
    def test_simulation_monitor_live_inputs_outputs_and_fifo_history(self):
        from PySide6.QtWidgets import QCheckBox,QDoubleSpinBox
        from model import Graph
        w=self.editor();w.graph=Graph()
        source=w.graph.add('input');w.graph.nodes[source]['p'].update(name='counter',dtype='u32',value=10)
        fifo=w.graph.add('fifo');output=w.graph.add('output');w.graph.nodes[output]['p'].update(name='previous',dtype='u32')
        bit=w.graph.add('input');w.graph.nodes[bit]['p']['name']='enable'
        w.graph.connect(source,fifo,'in');w.graph.connect(fifo,output,'in','last');w.rebuild(source)
        w.run(True);w.timer.stop();w.tick()
        panel=w.scroll.widget();self.assertEqual(panel.objectName(),'simulation-panel')
        control=panel.findChild(QDoubleSpinBox,f'simulation-input:{source}')
        self.assertEqual(control.maximum(),4294967295)
        self.assertEqual(panel.findChild(QLabel,f'simulation-value:{fifo}:now').text(),'10')
        control.setValue(4294967295);w.tick()
        self.assertEqual(w.graph.value(fifo,'last'),10)
        self.assertEqual(panel.findChild(QLabel,f'simulation-value:{output}:value').text(),'10')
        self.assertEqual(panel.findChild(QLabel,f'simulation-value:{fifo}:now').text(),'4294967295')
        toggle=panel.findChild(QCheckBox,f'simulation-input:{bit}');toggle.setChecked(True);w.tick()
        self.assertEqual(w.graph.nodes[bit]['p']['value'],1)
        self.assertEqual(panel.findChild(QLabel,f'simulation-value:{bit}:out').text(),'ON (1)')
        w.toggle_bit(bit);self.assertFalse(toggle.isChecked())
        # Selection cannot replace the monitor with properties while running.
        w.scene.clearSelection();w.items[output].setSelected(True)
        self.assertEqual(w.scroll.widget().objectName(),'simulation-panel')
        w.run(False);self.assertNotEqual(w.scroll.widget().objectName(),'simulation-panel')
        self.assertEqual(w.scroll.widget().findChild(QLineEdit).text(),'previous')
    def test_simulation_monitor_all_ports_and_graph_rebuild(self):
        from model import Graph
        w=self.editor();w.graph=Graph()
        pid=w.graph.add('pid');condition=w.graph.add('condition');w.rebuild(pid)
        w.run(True);w.timer.stop()
        self.assertEqual(w.scroll.widget().findChild(QLabel,f'simulation-value:{pid}:error').text(),'—')
        w.tick()
        for i,port in ((pid,'out'),(pid,'error'),(condition,'true'),(condition,'false')):
            self.assertIsNotNone(w.scroll.widget().findChild(QLabel,f'simulation-value:{i}:{port}'))
        w.add('input');w.tick()
        self.assertIn(w.selected,w.simulation_controls)
        w.delete_selected();w.tick()
        self.assertEqual(w.scroll.widget().objectName(),'simulation-panel')
    def test_display_node_properties_and_simulation_preview(self):
        from PySide6.QtWidgets import QPushButton,QCheckBox
        from model import Graph
        w=self.editor();w.graph=Graph();gate=w.graph.add('input');w.rebuild()
        button=next(b for b in w.findChildren(QPushButton) if b.text()=='+ Display');button.click();self.app.processEvents()
        display=w.selected;self.assertEqual(set(w.items[display].ports),{('in','trigger'),('in','value'),('in','reset')})
        message=w.scroll.widget().findChild(QLineEdit);message.setText('Debug error');message.editingFinished.emit();self.app.processEvents()
        w.change(display,'show_value',True);w.change(display,'cooldown_ms',1000)
        w.port_press(w.items[gate].ports[('out','out')]);w.port_release(w.items[display].ports[('in','trigger')])
        w.change(gate,'value',1);w.tick();self.assertEqual(w.status.text(),'SIM DISPLAY • Debug error: 0')
        for _ in range(5):w.tick();self.assertEqual(w.graph.messages,[])
        self.assertEqual(w.graph.nodes[display]['p']['message'],'Debug error')
        w.change(display,'trigger_high',False);w.change(gate,'value',0);w.tick()
        self.assertEqual(w.graph.messages,['Debug error: 0'])
        self.assertIsNone(w.scroll.widget().findChild(QComboBox))
        self.assertEqual(w.items[display].title_text.text(),'DISPLAY')
    def test_pid_creation_properties_wiring_and_simulation(self):
        from PySide6.QtWidgets import QPushButton,QDoubleSpinBox
        from model import Graph
        w=self.editor();w.graph=Graph();w.rebuild()
        button=next(b for b in w.findChildren(QPushButton) if b.text()=='+ PID');button.click();self.app.processEvents()
        pid=w.selected;self.assertEqual(w.graph.nodes[pid]['kind'],'pid')
        self.assertEqual(set(w.items[pid].ports),{('in',p) for p in ('setpoint','feedback','enable','reset')}|{('out','out'),('out','error')})
        control=w.scroll.widget().findChild(QDoubleSpinBox,'pid:kp');control.setValue(2.5);self.app.processEvents()
        self.assertEqual(w.graph.nodes[pid]['p']['kp'],2.5)
        source=w.graph.add('input');w.graph.nodes[source]['p'].update(dtype='u32',value=4);w.rebuild(pid)
        w.port_press(w.items[source].ports[('out','out')]);w.port_release(w.items[pid].ports[('in','setpoint')]);self.app.processEvents()
        self.assertEqual(w.scroll.widget().findChild(QLabel,'conversion:setpoint').text(),'Conversion: u32 → float')
        w.tick();self.assertEqual(w.graph.values[pid],10);self.assertEqual(w.graph.value(pid,'error'),4)
        self.assertIn('out=10',w.items[pid].value_text.text())
        self.assertTrue(w.scroll.widget().findChild(QDoubleSpinBox,'pid:ki').isEnabled())
        # Invalid limits restore the model and the displayed control.
        w.scroll.widget().findChild(QDoubleSpinBox,'pid:output_min').setValue(101);self.app.processEvents()
        self.assertEqual(w.graph.nodes[pid]['p']['output_min'],-100)
        self.assertEqual(w.scroll.widget().findChild(QDoubleSpinBox,'pid:output_min').value(),-100)
        from PySide6.QtWidgets import QCheckBox
        ff=w.scroll.widget().findChild(QCheckBox,'pid:ff_enabled');self.assertFalse(ff.isChecked())
        w.scroll.widget().findChild(QDoubleSpinBox,'pid:ff_gain').setValue(.75);self.app.processEvents()
        ff.setChecked(True);self.app.processEvents();w.tick()
        self.assertEqual(w.graph.values[pid],13)
        self.assertEqual(w.items[pid].title_text.text(),'PID + FF')
        w.scroll.widget().findChild(QCheckBox,'pid:ff_enabled').setChecked(False);self.app.processEvents();w.tick()
        self.assertEqual(w.graph.values[pid],10)
        self.assertEqual(w.items[pid].title_text.text(),'PID')
    def test_editor_properties_wiring_and_build(self):
        w=self.editor();self.assertEqual((w.width(),w.height()),(800,600));self.assertEqual(w.selected,3)
        w.change(4,'on_delay',300);self.assertEqual(w.graph.nodes[4]['p']['on_delay'],300)
        w.port_press(w.items[1].ports[('out','out')]);w.port_release(w.items[3].ports[('in','pressure')])
        self.assertIn([1,'out',3,'pressure'],w.graph.links)
        w.change(1,'value',8);w.run(True);w.tick()
        self.assertEqual(w.graph.values[1],8);w.run(False)
        with tempfile.TemporaryDirectory() as tmp:
            w.project=Path(tmp)/'test.json';w.save();self.assertTrue(w.project.exists())
            w.last_export=Path(tmp)/'ui_plc.comp';w.build()
            self.assertTrue(w.builder.waitForFinished(30000))
            self.app.processEvents();self.assertEqual(w.builder.exitCode(),0)
            self.assertTrue(w.last_export.with_suffix('.so').exists())
    def test_expression_edit_and_typed_variable_widgets(self):
        w=self.editor();w.disconnect(3,True);self.app.processEvents();w.scene.clearSelection();w.items[3].setSelected(True);self.app.processEvents()
        expr=w.scroll.widget().findChild(ExpressionEdit)
        expr.setPlainText('pressure >= minimum and door_closed');expr.editingFinished.emit();self.app.processEvents()
        self.assertEqual(w.graph.inputs(3),('pressure','door_closed'))
        self.assertIn(('out','true'),w.items[3].ports);self.assertIn(('out','false'),w.items[3].ports)
        dtype=w.scroll.widget().findChild(QComboBox,'type:door_closed');self.assertEqual(dtype.currentText(),'bit')
        dtype.setCurrentText('float');self.app.processEvents();self.assertEqual(w.graph.input_type(3,'door_closed'),'float')
        mode=w.scroll.widget().findChild(QComboBox,'source:door_closed');mode.setCurrentIndex(1);self.app.processEvents()
        self.assertNotIn(('in','door_closed'),w.items[3].ports)
        self.assertEqual(w.graph.inputs(3),('pressure',))
        mode=w.scroll.widget().findChild(QComboBox,'source:door_closed');mode.setCurrentIndex(0);self.app.processEvents()
        w.change_variable(3,'door_closed','dtype','bit');self.app.processEvents()
        output=w.graph.add('output',(260,400));w.graph.nodes[output]['p']['name']='not-ready';w.rebuild(3)
        w.port_press(w.items[3].ports[('out','false')]);w.port_release(w.items[output].ports[('in','in')])
        self.assertIn([3,'false',output,'in'],w.graph.links)
        w.tick();self.assertEqual(w.graph.values[output],1)
        w.fit();self.app.processEvents();w.grab().save('/tmp/plc-node-properties.png')

    def test_integer_pin_property_and_inverter_ui(self):
        w=self.editor();w.scene.clearSelection();w.items[1].setSelected(True);self.app.processEvents()
        dtype=w.scroll.widget().findChild(QComboBox);dtype.setCurrentText('u32');self.app.processEvents()
        self.assertEqual(w.graph.nodes[1]['p']['dtype'],'u32')
        from PySide6.QtWidgets import QDoubleSpinBox,QPushButton
        value=w.scroll.widget().findChild(QDoubleSpinBox);self.assertEqual(value.decimals(),0);self.assertEqual(value.maximum(),4294967295)
        value.setValue(4294967295);self.assertEqual(w.graph.nodes[1]['p']['value'],4294967295)
        button=next(b for b in w.findChildren(QPushButton) if b.text()=='+ Invert');button.click();self.app.processEvents()
        inverter=w.selected;self.assertEqual(w.graph.nodes[inverter]['kind'],'invert')
        self.assertEqual(set(w.items[inverter].ports),{('in','in'),('out','out')})
        w.port_press(w.items[3].ports[('out','true')]);w.port_release(w.items[inverter].ports[('in','in')])
        w.tick();self.assertEqual(w.graph.values[inverter],0)
        w.graph.nodes[1]['p']['value']=0;w.tick();self.assertEqual(w.graph.values[inverter],1)

    def test_conversion_annotations_follow_connections_and_types(self):
        w=self.editor();w.disconnect(3,True);self.app.processEvents();w.change_variable(3,'pressure','dtype','s32');self.app.processEvents()
        w.graph.connect(2,3,'pressure');w.rebuild(3)
        note=w.scroll.widget().findChild(QLabel,'conversion:pressure')
        self.assertEqual(note.text(),'Conversion: float → s32')
        label,annotation=w.items[3].input_labels['pressure']
        self.assertEqual(annotation.text(),'float → s32')
        self.assertEqual(label.brush().color().name(),'#ff8585')
        w.disconnect(2,True);self.app.processEvents();w.change(2,'dtype','s32');self.app.processEvents()
        w.graph.connect(2,3,'pressure');w.rebuild(3)
        self.assertEqual(w.graph.dtype(2),'s32')
        self.assertEqual(w.items[3].input_labels['pressure'][1].text(),'')
        self.assertIsNone(w.scroll.widget().findChild(QLabel,'conversion:pressure'))
        w.disconnect(2,True);self.app.processEvents();w.change(2,'dtype','float');self.app.processEvents()
        w.graph.connect(2,3,'pressure');w.rebuild(3)
        self.assertEqual(w.items[3].input_labels['pressure'][1].text(),'float → s32')
        w.disconnect(3);self.app.processEvents()
        self.assertEqual(w.items[3].input_labels['pressure'][1].text(),'')
        self.assertIsNone(w.scroll.widget().findChild(QLabel,'conversion:pressure'))
        w.port_press(w.items[1].ports[('out','out')]);w.port_release(w.items[3].ports[('in','pressure')])
        self.assertEqual(w.scroll.widget().findChild(QLabel,'conversion:pressure').text(),'Conversion: float → s32')

    def test_math_result_selector_and_numeric_bit_conversion(self):
        w=self.editor();w.disconnect(2,True);self.app.processEvents();w.scene.clearSelection();w.items[2].setSelected(True);self.app.processEvents()
        result_type=w.scroll.widget().findChild(QComboBox)
        self.assertEqual([result_type.itemText(i) for i in range(result_type.count())],['bit','float','s32','u32'])
        result_type.setCurrentText('u32');self.app.processEvents()
        self.assertEqual(w.graph.dtype(2),'u32')
        w.graph.connect(1,2,'pressure');w.graph.connect(2,3,'pressure');w.update_edges()
        self.assertEqual(w.items[3].input_labels['pressure'][1].text(),'u32 → float')
        w.scene.clearSelection();w.items[4].setSelected(True);self.app.processEvents()
        w.port_press(w.items[2].ports[('out','result')]);w.port_release(w.items[4].ports[('in','in')])
        self.assertEqual(w.scroll.widget().findChild(QLabel,'conversion:in').text(),'Conversion: u32 → bit')
        w.tick();self.assertEqual(w.graph.values[2],8)

    def test_replacing_all_math_ports_with_weighted_inputs(self):
        from unittest.mock import patch
        from PySide6.QtCore import qInstallMessageHandler
        w=self.editor();w.new()
        inputs=[w.graph.add('input',(0,j*130)) for j in range(4)]
        m=w.graph.add('math',(270,80));out=w.graph.add('output',(540,80))
        w.graph.nodes[out]['p']['dtype']='u32'
        w.graph.connect(inputs[0],m,'x');w.graph.connect(m,out,'in');w.rebuild(m)
        w.disconnect(m,True);self.app.processEvents()
        exceptions=[];messages=[]
        handler=qInstallMessageHandler(lambda kind,context,message:messages.append(message))
        try:
            with patch('sys.excepthook',side_effect=lambda *error:exceptions.append(error)):
                expr=w.scroll.widget().findChild(ExpressionEdit)
                expr.setPlainText('n0 * 1 + n1 * 2 + n2 * 4 + n3 * 8')
                expr.editingFinished.emit();self.app.processEvents()
                self.assertEqual(w.graph.inputs(m),('n0','n1','n2','n3'))
                self.assertEqual(set(w.items[m].input_labels),set(w.graph.inputs(m)))
                for j,source in enumerate(inputs):w.graph.connect(source,m,f'n{j}')
                w.graph.connect(m,out,'in')
                w.update_edges()
                self.assertTrue(all(edge.scene() is w.scene for edge in w.edges))
                for bits in range(16):
                    for j,source in enumerate(inputs):w.graph.nodes[source]['p']['value']=(bits>>j)&1
                    w.tick();self.assertEqual(w.graph.values[m],bits);self.assertEqual(w.graph.values[out],bits)
                # Structural editing requires removing all connections first.
                w.disconnect(m,True);self.app.processEvents()
                w.change(m,'expression','n0 + n2');self.app.processEvents()
                w.change_variable(m,'n2','mode','constant');self.app.processEvents()
                self.assertEqual(w.graph.inputs(m),('n0',))
                w.items[m].setPos(330,110)
                self.assertEqual(w.graph.nodes[m]['pos'],[330,110])
                self.assertTrue(all(edge.scene() is w.scene for edge in w.edges))
        finally:qInstallMessageHandler(handler)
        self.assertEqual(exceptions,[])
        self.assertFalse(any('removeItem' in message for message in messages),messages)

    def test_constants_are_visible_without_input_sockets(self):
        w=self.editor();w.disconnect(2,True);self.app.processEvents();w.change(2,'expression','n0 * 1 + n1 * 2 + n2 * 4 + n3 * 8');self.app.processEvents()
        w.change_variable(2,'n1','mode','constant');self.app.processEvents()
        w.change_variable(2,'n1','value',3.9);self.app.processEvents()
        self.assertNotIn(('in','n1'),w.items[2].ports)
        self.assertEqual(w.items[2].constant_labels['n1'].text(),'n1 : float = 3.9')
        self.assertEqual(w.items[2].ports[('in','n2')].pos().y(),128)
        w.change_variable(2,'n1','dtype','s32');self.app.processEvents()
        self.assertEqual(w.items[2].constant_labels['n1'].text(),'n1 : s32 = 3')
        w.change_variable(2,'n1','dtype','u32');w.change_variable(2,'n1','value',4294967295);self.app.processEvents()
        self.assertEqual(w.items[2].constant_labels['n1'].text(),'n1 : u32 = 4294967295')
        w.change_variable(2,'n1','mode','port');self.app.processEvents()
        self.assertIn(('in','n1'),w.items[2].ports)
        self.assertNotIn('n1',w.items[2].constant_labels)
        self.assertEqual(w.items[2].ports[('in','n1')].pos().y(),92)
        w.change_variable(2,'n1','mode','constant');w.change_variable(2,'n1','dtype','bit')
        w.change_variable(2,'n1','value',9);self.app.processEvents()
        self.assertEqual(w.items[2].constant_labels['n1'].text(),'n1 : bit = 1')

    def test_one_click_simulated_bit_and_checkbox(self):
        from PySide6.QtCore import QEvent,QPointF,QPoint
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QCheckBox
        def click(widget,pos=None):
            pos=pos if pos is not None else QPoint(8,widget.height()//2)
            for event_type,buttons in [(QEvent.Type.MouseButtonPress,Qt.MouseButton.LeftButton),
                                       (QEvent.Type.MouseButtonRelease,Qt.MouseButton.NoButton)]:
                event=QMouseEvent(event_type,QPointF(pos),QPointF(widget.mapToGlobal(pos)),Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier)
                self.app.sendEvent(widget,event)
        w=self.editor();w.new();source=w.graph.add('input');w.rebuild(source);w.fit();self.app.processEvents()
        checkbox=w.scroll.widget().findChild(QCheckBox,'simulated-bit')
        self.assertFalse(checkbox.isChecked())
        click(checkbox);self.app.processEvents()
        self.assertEqual(w.graph.nodes[source]['p']['value'],1)
        self.assertIn('ON 1',w.items[source].value_text.text())
        toggle=w.items[source].value_text
        pos=w.view.mapFromScene(toggle.sceneBoundingRect().center())
        click(w.view.viewport(),pos);self.app.processEvents()
        self.assertEqual(w.graph.nodes[source]['p']['value'],0)
        self.assertIs(w.items[source].value_text,toggle)
        self.assertFalse(checkbox.isChecked())
        w.run(True);w.tick();state=w.graph.state[source]
        w.toggle_bit(source);w.tick();self.assertIs(w.graph.state[source],state)
        self.assertEqual(w.graph.values[source],1)
        checkbox=w.scroll.widget().findChild(QCheckBox,f'simulation-input:{source}')
        self.assertTrue(checkbox.isChecked());w.run(False)

    def test_math_template_dropdown_and_custom_save(self):
        w=self.editor();w.disconnect(2,True);self.app.processEvents();w.scene.clearSelection();w.items[2].setSelected(True);self.app.processEvents()
        picker=w.scroll.widget().findChild(QComboBox,'math-template-picker')
        index=next(i for i in range(1,picker.count()) if Path(picker.itemData(i)).name=='4-bit-to-u32.json')
        picker.activated.emit(index);self.app.processEvents()
        self.assertEqual(w.graph.dtype(2),'u32')
        self.assertEqual(w.items[2].title_text.text(),'4 bit → U32')
        self.assertEqual(w.graph.inputs(2),('n0','n1','n2','n3'))
        self.assertTrue(all(w.graph.input_type(2,p)=='bit' for p in w.graph.inputs(2)))
        self.assertFalse(w.graph.has_connections(2))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'custom.json';w.math_template_file(2,path,True)
            self.assertTrue(path.exists());w.change(2,'expression','sqrt(x)');self.app.processEvents()
            w.math_template_file(2,path);self.app.processEvents()
            self.assertEqual(w.graph.inputs(2),('n0','n1','n2','n3'))
            self.assertEqual(w.graph.dtype(2),'u32')
            self.assertEqual(w.items[2].title_text.text(),'4 bit → U32')
            w.change(2,'template_name','Custom packer');self.app.processEvents()
            self.assertEqual(w.items[2].title_text.text(),'Custom packer')

    def test_arrow_canvas_pan_and_mouse_port_wiring(self):
        from PySide6.QtCore import QEvent,QPointF,QPoint
        from PySide6.QtGui import QMouseEvent
        w=self.editor();w.new();source=w.graph.add('input');m=w.graph.add('math',(270,80))
        w.rebuild(m);w.fit();self.app.processEvents()
        viewport=w.view.viewport()
        def event(kind,pos,buttons):
            mouse=QMouseEvent(kind,QPointF(pos),QPointF(viewport.mapToGlobal(pos)),
                Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
                buttons,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(viewport,mouse)
        start=next(pos for pos in [QPoint(5,5),QPoint(viewport.width()-5,5),QPoint(5,viewport.height()-5)] if w.view.itemAt(pos) is None)
        h=w.view.horizontalScrollBar().value();v=w.view.verticalScrollBar().value()
        event(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
        event(QEvent.Type.MouseMove,start+QPoint(20,10),Qt.MouseButton.LeftButton)
        event(QEvent.Type.MouseButtonRelease,start+QPoint(20,10),Qt.MouseButton.NoButton)
        self.assertEqual(w.view.horizontalScrollBar().value(),h-20)
        self.assertEqual(w.view.verticalScrollBar().value(),v-10)
        self.assertIsNone(w.view.pan_origin)
        for port in [w.items[source].ports[('out','out')],w.items[m].ports[('in','x')]]:
            pos=w.view.mapFromScene(port.scenePos())
            event(QEvent.Type.MouseButtonPress,pos,Qt.MouseButton.LeftButton)
            event(QEvent.Type.MouseButtonRelease,pos,Qt.MouseButton.NoButton)
        self.assertIn([source,'out',m,'x'],w.graph.links)

    def test_circular_math_locked_until_all_connections_removed(self):
        from copy import deepcopy
        from model import Graph
        from PySide6.QtWidgets import QPushButton
        w=self.editor();w.graph=Graph.load(Path(__file__).parent/'examples/circular-direction.json');w.rebuild(3);self.app.processEvents()
        panel=w.scroll.widget();picker=panel.findChild(QComboBox,'math-template-picker')
        self.assertFalse(picker.isEnabled());self.assertFalse(panel.findChild(ExpressionEdit).isEnabled())
        self.assertFalse(panel.findChild(QComboBox,'type:actual').isEnabled())
        self.assertFalse(panel.findChild(QComboBox,'source:actual').isEnabled())
        buttons={b.text():b for b in panel.findChildren(QPushButton)}
        self.assertFalse(buttons['Load template'].isEnabled());self.assertTrue(buttons['Save template'].isEnabled())
        nodes=deepcopy(w.graph.nodes);links=deepcopy(w.graph.links)
        w.math_template_file(3,Path(__file__).parent/'templates/4-bit-to-u32.json')
        w.change(3,'expression','x * 2');w.change(3,'dtype','u32');w.change_variable(3,'actual','mode','constant')
        self.assertEqual(w.graph.nodes,nodes);self.assertEqual(w.graph.links,links)
        # Constant values remain adjustable on a connected node.
        w.change_variable(3,'stations','value',24);self.app.processEvents()
        self.assertEqual(w.graph.nodes[3]['p']['variables']['stations']['value'],24)
        button=next(b for b in w.scroll.widget().findChildren(QPushButton) if b.text()=='Disconnect all')
        button.click();self.app.processEvents()
        self.assertFalse(w.graph.has_connections(3));self.assertTrue(w.graph.links)
        picker=w.scroll.widget().findChild(QComboBox,'math-template-picker');self.assertTrue(picker.isEnabled())
        index=next(i for i in range(1,picker.count()) if Path(picker.itemData(i)).name=='4-bit-to-u32.json')
        picker.activated.emit(index);self.app.processEvents();self.app.processEvents()
        self.assertEqual(w.graph.inputs(3),('n0','n1','n2','n3'))
        self.assertEqual(w.items[3].title_text.text(),'4 bit → U32')

    def test_successful_open_and_save_are_restored_next_start(self):
        from unittest.mock import patch
        from app import args
        path=Path(os.environ['PLC_STATE_DIR'])/'saved.json'
        w=self.editor();w.project=path;w.save()
        self.assertEqual(w.session.last_project(),path.resolve())
        restored=self.editor();self.assertEqual(restored.project,path.resolve())
        self.assertEqual(restored.graph.nodes,w.graph.nodes)
        other=path.with_name('other.json');w.graph.save(other)
        with patch.object(w,'choose',return_value=other):w.open()
        self.assertEqual(w.session.last_project(),other.resolve())
        with patch.object(args,'no_restore',True):empty=self.editor()
        self.assertEqual(empty.graph.nodes,{});self.assertIsNone(empty.project)
        self.assertEqual(w.session.last_project(),other.resolve())
        other.write_text('{corrupt')
        fallback=self.editor();self.assertEqual(fallback.graph.nodes,{})
        self.assertIsNone(fallback.project);self.assertIn('Started empty',fallback.status.text())

    def test_fifo_ui_wiring_values_and_inherited_type(self):
        from PySide6.QtWidgets import QPushButton,QDoubleSpinBox
        w=self.editor();w.new()
        source=w.graph.add('input');w.graph.nodes[source]['p']['dtype']='u32';w.rebuild(source)
        button=next(b for b in w.findChildren(QPushButton) if b.text()=='+ FIFO');button.click();self.app.processEvents()
        fifo=w.selected;self.assertEqual(w.graph.nodes[fifo]['kind'],'fifo')
        self.assertEqual(set(w.items[fifo].ports),{('in','in'),('out','last'),('out','now')})
        w.port_press(w.items[source].ports[('out','out')]);w.port_release(w.items[fifo].ports[('in','in')]);self.app.processEvents()
        self.assertEqual(w.graph.dtype(fifo),'u32')
        self.assertEqual(w.items[fifo].input_labels['in'][0].text(),'in : u32')
        self.assertEqual(w.items[fifo].output_labels['last'].text(),'last : u32')
        self.assertEqual(w.items[fifo].output_labels['now'].text(),'now : u32')
        initial=w.scroll.widget().findChild(QDoubleSpinBox);self.assertEqual(initial.maximum(),4294967295)
        w.change(source,'value',4294967295);w.tick()
        self.assertEqual(w.graph.value(fifo,'last'),0);self.assertEqual(w.graph.value(fifo,'now'),4294967295)
        w.change(source,'value',4);w.tick()
        self.assertEqual(w.graph.value(fifo,'last'),4294967295);self.assertEqual(w.graph.value(fifo,'now'),4)
        w.change(source,'dtype','s32');self.app.processEvents()
        self.assertEqual(w.graph.dtype(fifo),'s32')
        self.assertEqual(w.items[fifo].output_labels['last'].text(),'last : s32')
        self.assertEqual(w.items[fifo].input_labels['in'][0].text(),'in : s32')

if __name__=='__main__':unittest.main(argv=[sys.argv[0]])
