#!/usr/bin/env python3
"""Standalone 800x600 PLC graph editor. No live machine/HAL connection."""
import processing
import processing_ui
import argparse
import json
import os
from pathlib import Path
import sys
from i18n import LANGUAGES,tr,set_language,preferred_language,remember_language,language

parser=argparse.ArgumentParser()
parser.add_argument('--eglfs',action='store_true',help='Direct display, without X11/Wayland')
parser.add_argument('--windowed',action='store_true')
parser.add_argument('--language',choices=tuple(LANGUAGES),help='UI language (overrides the remembered choice)')
parser.add_argument('--screenshot',type=Path,help='Capture the UI and exit (also works offscreen)')
startup=parser.add_mutually_exclusive_group()
startup.add_argument('--project',type=Path,help='Open this project instead of the remembered project')
startup.add_argument('--no-restore','--empty',action='store_true',help='Start empty without reading the remembered project')
args=parser.parse_args()
if args.eglfs:os.environ['QT_QPA_PLATFORM']='eglfs'
elif not any(os.environ.get(k) for k in ('DISPLAY','WAYLAND_DISPLAY','QT_QPA_PLATFORM')):os.environ['QT_QPA_PLATFORM']='eglfs'
os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING','0')

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, QProcess, Signal, QTranslator, QLibraryInfo
from PySide6.QtGui import QColor, QPen, QPainter, QPainterPath, QPainterPathStroker, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QGraphicsScene,
    QGraphicsView,QGraphicsRectItem,QGraphicsEllipseItem,QGraphicsPathItem,
    QGraphicsItem,QGraphicsSimpleTextItem,QHBoxLayout,QVBoxLayout,QFormLayout,
    QLineEdit,QComboBox,QCheckBox,QDoubleSpinBox,QScrollArea,QPushButton,
    QLabel,QFileDialog,QMessageBox,QSplitter,QGroupBox,QPlainTextEdit,QSizePolicy,QInputDialog,QDialog,QMenu)
from model import Graph,demo,TYPES,convert,reference
from session import ProjectSession
from logger_runtime import SnapshotWriter
from hal_bindings import Catalogue
from io_dialogs import HALChooser,GlobalIOWindow
from PySide6.QtWidgets import QLabel as RawLabel,QComboBox as RawComboBox,QGroupBox as RawGroupBox

def translated_widget(base,setter='setText'):
    class Translated(base):
        def __init__(self,text='',parent=None):
            super().__init__(text,parent);self.setProperty('translation_text',text)
            getattr(base,setter)(self,tr(text))
        def setText(self,text):
            self.setProperty('translation_text',str(text));getattr(base,setter)(self,tr(text))
        def setToolTip(self,text):
            self.setProperty('translation_tooltip',str(text));super().setToolTip(tr(text))
    return Translated

QLabel=translated_widget(QLabel)
QPushButton=translated_widget(QPushButton)
QCheckBox=translated_widget(QCheckBox)
QGroupBox=translated_widget(QGroupBox,'setTitle')

class QComboBox(RawComboBox):
    def addItem(self,text,userData=None):
        super().addItem(tr(text),userData)
        self.setItemData(self.count()-1,text,Qt.ItemDataRole.UserRole+1)
    def addItems(self,texts):
        for text in texts:self.addItem(text,text)

COLORS={'constant':'#b6a063','input':'#377daa','output':'#a67537','math':'#56885b','condition':'#885e9d','invert':'#b26069','fifo':'#578e91','pid':'#bf9450','display':'#6b91bc','timer':'#a78dca','counter':'#bd865b','logger':'#89a55e'}

class ExpressionEdit(QPlainTextEdit):
    editingFinished=Signal()
    def __init__(self,text):
        super().__init__(text);self.setFixedHeight(62);self.setTabChangesFocus(True)
    def focusOutEvent(self,e):
        super().focusOutEvent(e);self.editingFinished.emit()
    def keyPressEvent(self,e):
        if e.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.editingFinished.emit();e.accept()
        else:super().keyPressEvent(e)


class Port(QGraphicsEllipseItem):
    def __init__(self,node,name,is_output,pos):
        super().__init__(-7,-7,14,14,node)
        self.node=node;self.name=name;self.is_output=is_output;self.setPos(*pos)
        self.setBrush(QColor('#71bada' if is_output else '#e7bd69'))
        self.setPen(QPen(QColor('#f3f5f7'),1));self.setZValue(5)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip(tr(('Output: ' if is_output else 'Input: ')+name))
    def mousePressEvent(self,e):
        self.node.editor.port_press(self);e.accept()
    def mouseMoveEvent(self,e):
        self.node.editor.port_move(e.scenePos());e.accept()
    def mouseReleaseEvent(self,e):
        editor=self.node.editor
        for item in editor.scene.items(e.scenePos()):
            if isinstance(item,Port) and item is not self:
                editor.port_release(item);break
        e.accept()

class BitToggle(QGraphicsSimpleTextItem):
    def __init__(self,node):
        super().__init__('',node);self.node=node
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setToolTip(tr('Click to toggle the simulated bit input (no hardware output).'))
    def mousePressEvent(self,e):
        self.node.editor.toggle_bit(self.node.ident);e.accept()
    def mouseReleaseEvent(self,e):e.accept()

COLORS.update(latch='#c69855',hysteresis='#99a85c',watchdog='#ce715d',ramp='#67a9bd',filter='#73b79b',sequencer='#b491cb',memory_read='#d5a85b',memory_write='#d5a85b')

class Node(QGraphicsRectItem):
    def __init__(self,editor,i):
        n=editor.graph.nodes[i];ports=editor.graph.inputs(i)
        variables=n['p']['variables'] if n['kind'] in ('math','condition') else {}
        rows=tuple(variables) if variables else ports
        super().__init__(0,0,300 if n['kind'] in processing.KINDS else 260 if n['kind']=='counter' else 208,90 if n['p'].get('global_io') else 82+max(len(rows),len(editor.graph.outputs(i)))*36)
        self.editor=editor;self.ident=i;self.ports={};self.input_labels={};self.constant_labels={};self.output_labels={}
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setBrush(QColor('#26313a'));self.setPen(QPen(QColor(COLORS[n['kind']]),2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(*n['pos']);self.setZValue(1)
        if n['p'].get('global_io'):self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,False)
        title=('@'+n['p']['name']) if n['kind']=='constant' else n['p']['name'] if n['kind'] in ('input','output') else (n['p'].get('template_name') or n['kind'].upper())
        if n['kind']=='pid' and n['p']['ff_enabled']:title='PID + FF'
        if n['kind'] not in ('input','output','constant') and not n['p'].get('template_name'):title=tr(title)
        self.title_text=self.label(title,10,6,'#ffffff')
        self.title_text.setToolTip(title+'\n'+tr('Module: ')+editor.graph.modules[n.get('module',0)])
        p=editor.graph.parameters(i);detail=(('IN / ' if n['kind']=='input' else 'OUT / ') if n['kind'] in ('input','output') else '')+editor.graph.dtype(i)
        if n['kind']=='constant':detail+=' = '+f'{convert(p["value"],p["dtype"]):g}'
        if n['kind']=='input' and p['dtype']=='bit':detail+=' / '+tr(p['edge'])
        if n['kind']=='output' and p['dtype']=='bit':detail+=f' / {p["on_delay"]:g}:{p["off_delay"]:g} ms'
        if n['kind'] in ('math','condition'):detail=p['expression']
        if n['kind']=='math':self.setToolTip(tr('Result type: '+editor.graph.dtype(i)))
        if n['kind']=='pid':detail=f'Kp={p["kp"]:g} Ki={p["ki"]:g} Kd={p["kd"]:g}'
        if n['kind']=='display':detail=p['message'][:26];self.setToolTip(p['message'])
        if n['kind']=='logger':detail=f'{p["sample_ms"]:g} ms / {p["buffer_length"]} / {p["file_format"]}'
        if n['kind']=='timer':detail=f'{p["duration_ms"]:g} ms / '+tr(p['timer_mode'])
        if n['kind']=='counter':detail='s32 / '+tr('Threshold')+f' = {int(p["threshold"])}'
        if n['kind'].startswith('memory_'):detail=p['memory']+' / '+p['dtype']
        if n['kind']=='filter':detail=tr(p['filter_mode'])
        if n['kind']=='sequencer':detail=str(len(p['states']))+' '+tr('states')
        if len(detail)>26:detail=detail[:23]+'…'
        self.detail_text=self.label(detail,10,27,'#aebac6')
        if n['kind']=='input' and p['dtype']=='bit':
            self.value_text=BitToggle(self);self.value_text.setPos(10,self.rect().height()-24)
        else:self.value_text=self.label('—',10,self.rect().height()-24,'#8ce3bb')
        self.show_value()
        for j,name in enumerate(rows):
            typename=editor.graph.input_type(i,name)
            if name in variables and variables[name]['mode']=='constant':
                value=convert(editor.graph.resolve(variables[name]['value']),typename)
                text=str(int(value)) if typename in ('bit','s32','u32') else f'{value:.10g}'
                self.constant_labels[name]=self.label(name+' : '+typename+' = '+text,12,47+j*36,'#e7bd69')
                continue
            self.ports[('in',name)]=Port(self,name,False,(0,56+j*36))
            label=self.label(name+' : '+typename,12,47+j*36,'#c9d2da')
            conversion=self.label('',12,62+j*36,'#ff8585')
            self.input_labels[name]=(label,conversion)
        for j,name in enumerate(editor.graph.outputs(i)):
            self.ports[('out',name)]=Port(self,name,True,(self.rect().width(),56+j*36))
            output_name=name+(' : '+editor.graph.dtype(i,name) if n['kind'] in ('math','fifo','pid','counter') else '')
            label=self.label(output_name,0,47+j*36,'#8fd5e8');label.setX(self.rect().width()-12-label.boundingRect().width())
            self.output_labels[name]=label
        self.driver_link=None
        if n['kind']=='output' and p.get('global_io'):
            self.driver_link=DriverLink(self);self.driver_link.setPos(10,27);self.detail_text.hide()
        self.update_conversions()
    def show_value(self,value=None):
        n=self.editor.graph.nodes[self.ident]
        if n['kind']=='constant' and value is None:value=convert(n['p']['value'],n['p']['dtype'])
        if n['kind']=='input' and n['p']['dtype']=='bit':
            active=bool(self.editor.live_inputs.get(self.ident,self.editor.graph.resolve(n['p']['value'])))
            text=tr(('Live: [ON 1]' if active else 'Live: [OFF 0]') if self.editor.live_process else ('Sim: [ON 1]' if active else 'Sim: [OFF 0]'))
            if value is not None:text+=f' · out {int(value)}'
            self.value_text.setText(text);self.value_text.setBrush(QColor('#8ce3bb' if active else '#e7bd69'))
        elif value is not None:
            if n['kind']=='fifo':self.value_text.setText(f'L={self.editor.graph.value(self.ident,"last"):g} N={value:g}')
            elif n['kind']=='pid':self.value_text.setText(f'out={value:g} err={self.editor.graph.value(self.ident,"error"):g}')
            elif n['kind']=='counter':self.value_text.setText(f'count={int(value)}  reached={int(self.editor.graph.value(self.ident,"reached"))}')
            elif n['kind']=='logger':self.value_text.setText(tr('Samples')+f': {int(value)} / {n["p"]["buffer_length"]}')
            elif n['kind']=='display':self.value_text.setText(tr('Trigger: ON' if value else 'Trigger: OFF'))
            else:self.value_text.setText(f'T={value:g}  F={1-value:g}' if n['kind']=='condition' else f'= {value:g}')
        elif n['kind']=='fifo':
            initial=convert(self.editor.graph.resolve(n['p']['initial']),self.editor.graph.dtype(self.ident));self.value_text.setText(f'L={initial:g} N={initial:g}')
    def update_conversions(self):
        if getattr(self,'driver_link',None):self.driver_link.refresh()
        for port,(label,note) in self.input_labels.items():
            label.setText(port+' : '+self.editor.graph.input_type(self.ident,port))
            conversion=self.editor.graph.conversion(self.ident,port)
            text=' → '.join(conversion) if conversion else ''
            note.setText(text);label.setBrush(QColor('#ff8585' if conversion else '#c9d2da'))
            self.ports[('in',port)].setToolTip(tr('Automatic conversion: '+text) if conversion else port+' : '+self.editor.graph.input_type(self.ident,port))
        if self.editor.graph.nodes[self.ident]['kind']=='fifo':
            dtype=self.editor.graph.dtype(self.ident);self.detail_text.setText(dtype)
            for port,label in self.output_labels.items():
                label.setText(port+' : '+dtype);label.setX(196-label.boundingRect().width())
            self.show_value(self.editor.graph.values.get(self.ident))
    def label(self,text,x,y,color):
        t=QGraphicsSimpleTextItem(text,self);t.setBrush(QColor(color));t.setPos(x,y);return t
    def itemChange(self,change,value):
        # setPos also runs during construction/replacement. Only an installed,
        # fully built node may trigger a global port/edge refresh.
        if (change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
                and not self.editor.editing
                and not self.editor.graph.nodes[self.ident]['p'].get('global_io')
                and self.editor.items.get(self.ident) is self
                and self.scene() is self.editor.scene
                and self.ident in self.editor.graph.nodes):
            self.editor.graph.nodes[self.ident]['pos']=[value.x(),value.y()];self.editor.update_edges()
        return super().itemChange(change,value)
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        if self.isSelected():painter.setPen(QPen(QColor('#ffffff'),1));painter.drawRect(self.rect().adjusted(3,3,-3,-3))

class DriverLink(QGraphicsSimpleTextItem):
    def __init__(self,node):
        super().__init__('',node);self.node=node;self.setBrush(QColor('#8fd5e8'));self.setCursor(Qt.CursorShape.ArrowCursor)
    def refresh(self):
        graph=self.node.editor.graph;driver=graph.driver(self.node.ident)
        text=graph.modules.get(graph.driver_module(self.node.ident),tr('All modules'))+f' / #{driver[0]}' if driver else tr('Unconnected')
        self.setText(text[:25]);self.setToolTip(text)
    def mousePressEvent(self,event):
        driver=self.node.editor.graph.driver(self.node.ident)
        if driver:
            editor=self.node.editor;i=self.node.ident;QTimer.singleShot(0,lambda:editor.jump_to_driver(i))
        event.accept()

class GlobalBank(QGraphicsRectItem):
    def __init__(self,editor,role,ids):
        super().__init__(0,0,228,40+len(ids)*100);self.editor=editor;self.role=role
        self.key=str(editor.graph.view_module)+':'+role
        self.setBrush(QColor('#202b33'));self.setPen(QPen(QColor('#77adce' if role=='input' else '#e7bd69'),2));self.setZValue(1)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        title=QGraphicsSimpleTextItem(tr('Global Inputs' if role=='input' else 'Global Outputs'),self);title.setPos(10,8);title.setBrush(QColor('#ffffff'))
        local=[n['pos'] for n in editor.graph.nodes.values() if not n['p'].get('global_io') and (editor.graph.view_module is None or n['module']==editor.graph.view_module)]
        default=((min((p[0] for p in local),default=0)-270) if role=='input' else (max((p[0] for p in local),default=0)+240),min((p[1] for p in local),default=0))
        self.setPos(*editor.graph.global_positions.get(self.key,default))
        for j,i in enumerate(ids):
            node=Node(editor,i);node.setParentItem(self);node.setPos(10,35+j*100);editor.items[i]=node
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self.editor.editing and self.scene() is self.editor.scene:
            self.editor.graph.global_positions[self.key]=[value.x(),value.y()];self.editor.update_edges()
        return super().itemChange(change,value)

class Edge(QGraphicsPathItem):
    def __init__(self,path,link):
        super().__init__(path);self.link=tuple(link)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.ArrowCursor)
    def shape(self):
        stroker=QPainterPathStroker();stroker.setWidth(14)
        return stroker.createStroke(self.path())
    def boundingRect(self):return self.shape().boundingRect()
    def paint(self,painter,option,widget=None):
        painter.setPen(QPen(QColor('#ffcf70' if self.isSelected() else '#77adce'),3 if self.isSelected() else 2))
        painter.drawPath(self.path())

class View(QGraphicsView):
    def __init__(self,scene):
        super().__init__(scene);self.pan_origin=None
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
    def mousePressEvent(self,e):
        pos=e.position().toPoint()
        item=self.itemAt(pos)
        if e.button()==Qt.MouseButton.LeftButton and (item is None or isinstance(item,Edge)):
            # Keep the hit area usable even when zoomed far out.
            stroker=QPainterPathStroker();stroker.setWidth(14)
            edge=next((edge for edge in reversed(self.window().edges) if stroker.createStroke(self.viewportTransform().map(edge.path())).contains(QPointF(pos))),None)
            if edge:
                self.setFocus()
                if not e.modifiers() & Qt.KeyboardModifier.ControlModifier:self.scene().clearSelection()
                edge.setSelected(not edge.isSelected() if e.modifiers() & Qt.KeyboardModifier.ControlModifier else True)
                e.accept();return
            self.scene().clearSelection();self.pan_origin=pos;e.accept()
        else:super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.pan_origin is not None:
            pos=e.position().toPoint();delta=pos-self.pan_origin;self.pan_origin=pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            e.accept()
        else:super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if self.pan_origin is not None and e.button()==Qt.MouseButton.LeftButton:
            self.pan_origin=None;e.accept()
        else:super().mouseReleaseEvent(e)
    def wheelEvent(self,e):
        delta=e.angleDelta().y()
        if not delta:e.ignore();return
        current=self.transform().m11()
        # fitInView can put a module outside the manual zoom limits. Allow
        # scrolling back towards the supported range instead of locking it.
        if delta>0 and current<2.5:target=min(2.5,current*1.15)
        elif delta<0 and current>.18:target=max(.18,current/1.15)
        else:e.accept();return
        self.scale(target/current,target/current);e.accept()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Delete:self.window().delete_selected()
        elif e.key()==Qt.Key.Key_Escape:self.window().cancel_wire()
        else:super().keyPressEvent(e)

class Editor(QMainWindow):
    def __init__(self):
        set_language(preferred_language(args.language or os.environ.get('PLC_LANGUAGE')))
        super().__init__();self.setWindowTitle(tr('PLC Ninja • local prototype'));self.resize(800,600)
        self.qt_translator=None;self.install_qt_language()
        self.session=ProjectSession()
        self.graph,self.project,startup_notice=self.session.startup(args.project,args.no_restore)
        self.last_export=None;self.builder=None;self.items={};self.edges=[];self.pending=None;self.temp=None
        self.hal_catalogue=Catalogue();self.live_process=None;self.live_buffer=b'';self.live_directory=None;self.live_active=False;self.live_inputs={}
        self.running=False;self.editing=False;self.selected=None;self.property_generation=0
        self.toolbars={};self.fullscreen_previous=False;self.fullscreen_geometry=None
        center=QWidget();outer=QVBoxLayout(center);outer.setContentsMargins(5,5,5,5);outer.setSpacing(4)
        self.setCentralWidget(center)
        def toolbar(title):
            group=QGroupBox(title) if title=='Nodes' else QWidget()
            group.setObjectName('toolbar-'+title.lower())
            self.toolbars[title]=group
            row=QHBoxLayout(group);row.setContentsMargins(5,15,5,5) if title=='Nodes' else row.setContentsMargins(0,0,0,0)
            row.setSpacing(4)
            if title!='Nodes':
                label=QLabel(title);label.setObjectName('toolbar-label-'+title.lower());row.addWidget(label)
            outer.addWidget(group);return row
        row=toolbar('Project')
        for title,callback in [('New',self.new),('Open',self.open),('Save',self.save),('Export',self.export),('Build .so',self.build),('Fit',self.fit),('Exit',self.close)]:
            b=QPushButton(title);b.setMinimumHeight(30);b.clicked.connect(callback);row.addWidget(b)
        row=toolbar('Settings')
        row.addWidget(QLabel('Language'))
        self.language_picker=RawComboBox();self.language_picker.setObjectName('language-picker')
        for code,name in LANGUAGES.items():self.language_picker.addItem(name,code)
        self.language_picker.setCurrentIndex(self.language_picker.findData(language()))
        self.language_picker.currentIndexChanged.connect(self.change_language);row.addWidget(self.language_picker)
        manual=QPushButton('Manual');manual.clicked.connect(self.show_manual);row.addWidget(manual)
        io_button=QPushButton('Global I/O');io_button.clicked.connect(self.global_io_dialog);row.addWidget(io_button)
        self.debug_build=QCheckBox('Debug build');row.addWidget(self.debug_build)
        self.test_mode=QComboBox();self.test_mode.setObjectName('test-mode');self.test_mode.addItem('Local simulation','local');self.test_mode.addItem('Live HAL test','live');row.addWidget(self.test_mode);row.addStretch()
        self.run_button=QPushButton('▶ Simulate');self.run_button.setCheckable(True);self.run_button.clicked.connect(self.run);row.addWidget(self.run_button)
        b=QPushButton('Delete');b.clicked.connect(self.delete_selected);row.addWidget(b)
        row=toolbar('Modules')
        self.module_picker=RawComboBox();self.module_picker.setObjectName('module-picker')
        self.module_picker.currentIndexChanged.connect(self.module_changed);row.addWidget(self.module_picker,1)
        for title,callback in [('New module',self.new_module),('Rename',self.rename_module),('Remove module',self.remove_module),('Move selected…',self.move_selected_dialog)]:
            button=QPushButton(title);button.clicked.connect(callback);row.addWidget(button)
            if title=='Remove module':button.setToolTip('Remove the module grouping; its nodes and connections are kept in another module.')
        row=toolbar('Nodes')
        # Two rows keep every node reachable on the supported 800 x 600 display.
        columns=[]
        for _ in range(6):
            column=QVBoxLayout();column.setSpacing(4);row.addLayout(column);columns.append(column)
        for index,kind in enumerate(('input','output','constant','math','condition','invert','fifo','timer','counter','pid','display','logger')):
            b=QPushButton('+ '+('Const' if kind=='constant' else kind.upper() if kind in ('fifo','pid') else kind.title()));b.setMinimumHeight(30);b.clicked.connect(lambda checked=False,k=kind:self.add(k));columns[index%6].addWidget(b)
        processing_button=QPushButton('Processing…');processing_button.setObjectName('processing-menu')
        menu=QMenu(processing_button)
        for kind in processing.KINDS:
            if kind.startswith('memory_'):continue
            action=menu.addAction(tr(kind.upper()));action.setProperty('translation_text',kind.upper());action.triggered.connect(lambda checked=False,k=kind:self.add(k))
        action=menu.addAction(tr('Memory pair'));action.setProperty('translation_text','Memory pair');action.triggered.connect(self.add_memory_pair)
        processing_button.setMenu(menu);columns[-1].addWidget(processing_button)
        split=QSplitter();outer.addWidget(split,1)
        self.scene=QGraphicsScene();self.scene.setSceneRect(-2000,-1500,5000,4000)
        self.view=View(self.scene);self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QColor('#182128'))
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        split.addWidget(self.view)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setMinimumWidth(230);self.scroll.setMaximumWidth(300)
        split.addWidget(self.scroll);split.setSizes([530,260])
        self.scene.selectionChanged.connect(self.selection)
        footer=QHBoxLayout();outer.addLayout(footer)
        self.status=QLabel('Connect: click output, then input • drag also works • wheel: zoom');self.status.setWordWrap(True);self.status.setMinimumHeight(34);footer.addWidget(self.status,1)
        footer.addStretch()
        self.fullscreen_button=QPushButton('Fullscreen');self.fullscreen_button.setObjectName('fullscreen-button')
        self.fullscreen_button.setCheckable(True);self.fullscreen_button.toggled.connect(self.set_fullscreen)
        self.fullscreen_button.setToolTip('Toggle fullscreen workspace (F11)');footer.addWidget(self.fullscreen_button)
        fullscreen_action=QAction(self);fullscreen_action.setShortcut(QKeySequence('F11'))
        fullscreen_action.triggered.connect(self.fullscreen_button.click);self.addAction(fullscreen_action)
        self.timer=QTimer(self);self.timer.setInterval(20);self.timer.timeout.connect(self.tick)
        self.logger_poll_timer=QTimer(self);self.logger_poll_timer.setInterval(100);self.logger_poll_timer.timeout.connect(self.poll_logger);self.logger_poll_timer.start()
        self.rebuild(next((i for i,n in self.graph.nodes.items() if n['kind']=='condition'),max(self.graph.nodes,default=None)));QTimer.singleShot(0,self.fit)
        action=QAction('Save',self);action.setShortcut(QKeySequence.StandardKey.Save);action.triggered.connect(self.save);self.addAction(action)
        self.setStyleSheet('''
            QMainWindow,QWidget { background:#202a33; color:#dce5ee; }
            QPushButton { background:#344654; border:1px solid #526574; border-radius:3px; padding:4px; }
            QPushButton:checked { background:#34664e; }
            QLineEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox {
                background:#405462; color:#ffffff;
                border:1px solid #8ca5b6; border-radius:3px; padding:3px;
                selection-background-color:#2275a5; selection-color:#ffffff;
            }
            QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {
                background:#4b6272; border:1px solid #8ed6ff;
            }
            QLineEdit:disabled,QPlainTextEdit:disabled,QComboBox:disabled,QDoubleSpinBox:disabled {
                background:#2a3945; color:#8a99a6; border:1px solid #536570;
            }
            QPushButton:disabled { background:#283540; color:#8a99a6; border:1px solid #43525e; }
            QScrollArea { border:0; }
        ''')
        if startup_notice:self.message(startup_notice)
    def closeEvent(self,event):
        if self.live_process:
            self.close_after_live=True;self.stop_live();self.message('Stopping Live HAL test…');event.ignore();return
        super().closeEvent(event)
    def shutdown(self):
        if getattr(self,"_shutting_down",False):return
        self._shutting_down=True
        self.editing=True;self.timer.stop();self.scene.selectionChanged.disconnect(self.selection)
        self.stop_live(wait=True)
        self.logger_poll_timer.stop()
        if getattr(self,'logger_writer',None):self.logger_writer.close()
    def change_language(self,index):
        selected=self.selected;code=self.language_picker.itemData(index)
        if code not in LANGUAGES:return
        set_language(code);self.install_qt_language();self.setWindowTitle(tr('PLC Ninja • local prototype'))
        for widget in self.findChildren(QWidget):
            source=widget.property('translation_text')
            if source is not None:
                if isinstance(widget,RawGroupBox):RawGroupBox.setTitle(widget,tr(source))
                elif isinstance(widget,RawLabel):RawLabel.setText(widget,tr(source))
                elif isinstance(widget,QPushButton):QPushButton.setText(widget,source)
                elif isinstance(widget,QCheckBox):QCheckBox.setText(widget,source)
            tooltip=widget.property('translation_tooltip')
            if tooltip is not None:QWidget.setToolTip(widget,tr(tooltip))
        for action in self.findChildren(QAction):
            source=action.property('translation_text')
            if source is not None:action.setText(tr(source))
        self.rebuild(selected)
        try:remember_language(code)
        except OSError as e:self.message('Could not save language: '+str(e))
    def install_qt_language(self):
        app=QApplication.instance()
        if self.qt_translator is not None:app.removeTranslator(self.qt_translator)
        self.qt_translator=QTranslator(self)
        code='sr_Latn' if language()=='sr' else language()
        if code!='en' and self.qt_translator.load('qtbase_'+code,QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(self.qt_translator)
    def show_manual(self):
        from PySide6.QtWidgets import QDialog,QTextBrowser
        dialog=QDialog(self);dialog.setWindowTitle(tr('Manual'));dialog.resize(740,520)
        layout=QVBoxLayout(dialog);browser=QTextBrowser();browser.setOpenExternalLinks(False)
        docs=Path(__file__).parent/'docs'
        path=docs/f'USER_GUIDE.{language()}.md'
        if not path.is_file():path=docs/'USER_GUIDE.en.md'
        try:browser.setMarkdown(path.read_text(encoding='utf-8'))
        except OSError as e:browser.setPlainText(str(e))
        layout.addWidget(browser);close=QPushButton('Close');close.clicked.connect(dialog.accept);layout.addWidget(close)
        dialog.exec()
    def set_fullscreen(self,active):
        for title in ('Project','Settings','Modules'):self.toolbars[title].setVisible(not active)
        self.status.setVisible(not active)
        self.fullscreen_button.setText('Exit fullscreen' if active else 'Fullscreen')
        if active:
            self.fullscreen_previous=self.isFullScreen();self.fullscreen_geometry=self.saveGeometry()
            self.showFullScreen()
        elif not self.fullscreen_previous:
            self.showNormal()
            if self.fullscreen_geometry is not None:self.restoreGeometry(self.fullscreen_geometry)
    def message(self,text):self.status.setText(str(text))
    def cancel_wire(self):
        self.pending=None
        if self.temp:self.scene.removeItem(self.temp);self.temp=None
    def port_press(self,port):
        if self.live_process:return
        if not port.is_output:
            if self.pending:self.port_release(port)
            else:self.message('Select an output port first.')
            return
        self.cancel_wire();self.pending=port
        self.temp=QGraphicsPathItem();self.temp.setPen(QPen(QColor('#e7bd69'),2));self.scene.addItem(self.temp)
        self.message('Now click an input port. Escape cancels.')
    def port_move(self,pos):
        if self.pending and self.temp:self.temp.setPath(self.curve(self.pending.scenePos(),pos))
    def port_release(self,port):
        if not self.pending or port.is_output:return
        try:
            self.graph.connect(self.pending.node.ident,port.node.ident,port.name,self.pending.name)
            self.message('Connected.');self.cancel_wire();self.update_edges();self.selection()
        except ValueError as e:self.message(e);self.cancel_wire()
    @staticmethod
    def curve(a,b):
        path=QPainterPath(a);dx=max(50,abs(b.x()-a.x())*.5)
        path.cubicTo(a+QPointF(dx,0),b-QPointF(dx,0),b);return path
    def update_edges(self):
        for node in self.items.values():node.update_conversions()
        selected={edge.link for edge in self.edges if edge.isSelected()}
        was_editing=self.editing;self.editing=True
        for edge in self.edges:self.scene.removeItem(edge)
        self.edges=[]
        for a,source,b,port in self.graph.links:
            if a not in self.items or b not in self.items:continue
            line=Edge(self.curve(self.items[a].ports[('out',source)].scenePos(),self.items[b].ports[('in',port)].scenePos()),(a,source,b,port))
            line.setPen(QPen(QColor('#77adce'),2));line.setZValue(0);self.scene.addItem(line);self.edges.append(line);line.setSelected(line.link in selected)
        self.editing=was_editing
        for a,source,b,port in self.graph.links:
            if (a in self.items)==(b in self.items):continue
            visible,hidden,key=(a,b,('out',source)) if a in self.items else (b,a,('in',port))
            item=self.items[visible].ports[key];node=self.graph.nodes[hidden]
            item.setToolTip(item.toolTip()+'\n'+tr(f'Connected to {self.graph.modules[node.get("module",0)]} / node {hidden}'))
    def sync_modules(self):
        self.module_picker.blockSignals(True);self.module_picker.clear()
        self.module_picker.addItem(tr('All modules'),None)
        for i,name in self.graph.modules.items():self.module_picker.addItem(name,i)
        self.module_picker.setCurrentIndex(self.module_picker.findData(self.graph.view_module));self.module_picker.blockSignals(False)
    def module_changed(self,index):
        module=self.module_picker.itemData(index)
        if module is not None and module not in self.graph.modules:return
        self.graph.view_module=module;self.rebuild();self.fit()
    def new_module(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        name,ok=QInputDialog.getText(self,tr('New module'),tr('Module name'))
        if ok:
            try:self.graph.view_module=self.graph.add_module(name);self.rebuild();self.fit()
            except ValueError as e:self.message(e)
    def rename_module(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        module=self.graph.view_module
        if module is None:self.message('Select a module to rename.');return
        name,ok=QInputDialog.getText(self,tr('Rename module'),tr('Module name'),text=self.graph.modules[module])
        if ok:
            try:self.graph.rename_module(module,name);self.sync_modules()
            except ValueError as e:self.message(e)
    def remove_module(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        module=self.graph.view_module
        if module is None:self.message('Select a module to remove.');return
        name=self.graph.modules[module]
        try:
            target=self.graph.delete_module(module);self.graph.view_module=target;self.rebuild();self.fit()
            self.message(f'Removed {name}; nodes and connections kept in {self.graph.modules[target]}.')
        except ValueError as e:self.message(e)
    def move_selected_dialog(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        ids=[n.ident for n in self.scene.selectedItems() if isinstance(n,Node)]
        if not ids:self.message('Select nodes to move to another module.');return
        choices=[name for i,name in self.graph.modules.items() if i!=self.graph.view_module]
        if not choices:self.message('Create another module first.');return
        name,ok=QInputDialog.getItem(self,tr('Move selected nodes'),tr('Destination module'),choices,editable=False)
        if ok:self.move_selected(next(i for i,title in self.graph.modules.items() if title==name))
    def move_selected(self,module):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        ids=[n.ident for n in self.scene.selectedItems() if isinstance(n,Node)]
        try:self.graph.move_nodes(ids,module)
        except ValueError as e:self.message(e);return
        self.graph.view_module=module;self.rebuild(ids[0] if ids else None);self.fit()
        self.message(f'Moved {len(ids)} node(s); all connections retained.')
    def rebuild(self,select=None):
        self.sync_modules()
        self.editing=True;self.cancel_wire();self.scene.clear();self.items={};self.edges=[]
        for i in self.graph.nodes:
            if self.graph.nodes[i]['p'].get('global_io'):continue
            if self.graph.view_module is not None and self.graph.nodes[i].get('module',0)!=self.graph.view_module:continue
            node=Node(self,i);self.items[i]=node;self.scene.addItem(node)
        self.banks=[]
        for role in ('input','output'):
            ids=[i for i,n in self.graph.nodes.items() if n['kind']==role and n['p'].get('global_io')]
            if ids:
                bank=GlobalBank(self,role,ids);self.scene.addItem(bank);self.banks.append(bank)
        self.update_edges()
        if select in self.items:self.items[select].setSelected(True)
        self.editing=False;self.selection()
    def global_io_dialog(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        GlobalIOWindow(self).exec()
    def add_global(self,role,binding=None):
        if self.live_process:return
        i=self.graph.add(role,global_io=True)
        if binding:
            import re
            name=re.sub('[^a-z0-9-]+','-',binding['name'].lower()).strip('-')
            if not name or not name[0].isalpha():name='io-'+name
            base=name;counter=1;used={n['p']['name'] for key,n in self.graph.nodes.items() if key!=i}
            while name in used:counter+=1;name=base+'-'+str(counter)
            self.graph.nodes[i]['p'].update(name=name,dtype=binding['dtype'],hal_binding=binding)
        try:self.graph.validate()
        except ValueError as e:del self.graph.nodes[i];self.message(e);return None
        self.graph.reset();self.rebuild(i);return i
    def jump_to_driver(self,i):
        driver=self.graph.driver(i)
        if driver:
            self.graph.view_module=self.graph.driver_module(i);self.jump_to_node(driver[0])
    def jump_to_node(self,i):
        if i not in self.graph.nodes:return
        if not self.graph.nodes[i]['p'].get('global_io'):self.graph.view_module=self.graph.nodes[i]['module']
        self.rebuild(i);self.view.centerOn(self.items[i]);self.view.ensureVisible(self.items[i],40,40)
    def choose_hal(self,i):
        if self.live_process:return
        dialog=HALChooser(self,self.graph.nodes[i]['kind'],i)
        if dialog.exec() and dialog.chosen:
            from copy import deepcopy
            old=deepcopy(self.graph.nodes[i]['p']);binding=dialog.chosen[0]
            self.graph.nodes[i]['p'].update(hal_binding=binding,dtype=binding['dtype'])
            try:self.graph.validate()
            except ValueError as e:self.graph.nodes[i]['p']=old;self.message(e);return
            self.graph.reset();self.rebuild(i)
    def clear_hal(self,i):
        if self.live_process:return
        self.graph.nodes[i]['p']['hal_binding']=None;self.rebuild(i)
    def set_global(self,i,active):
        if self.live_process:return
        self.graph.nodes[i]['p']['global_io']=bool(active);QTimer.singleShot(0,lambda:self.rebuild(i) if i in self.graph.nodes else None)
    def fit(self):
        if self.items:
            rect=QRectF()
            for node in list(self.items.values())+self.edges:rect=rect.united(node.sceneBoundingRect())
            self.view.fitInView(rect.adjusted(-30,-40,30,40),Qt.AspectRatioMode.KeepAspectRatio)
    def add(self,kind):
        if self.live_process:return
        pos=self.view.mapToScene(self.view.viewport().rect().center())
        i=self.graph.add(kind,(pos.x()-82,pos.y()-50),self.graph.view_module);self.graph.reset();self.rebuild(i)
    def add_memory_pair(self):
        if self.live_process:return
        pos=self.view.mapToScene(self.view.viewport().rect().center())
        writer,reader=self.graph.add_memory_pair((pos.x()-160,pos.y()-50))
        module=self.graph.view_module
        if module is not None:
            for i in (writer,reader):self.graph.nodes[i]['module']=module
        self.graph.reset();self.rebuild(reader)
    def delete_selected(self):
        if self.live_process:return
        ids=[n.ident for n in self.scene.selectedItems() if isinstance(n,Node)]
        links={n.link for n in self.scene.selectedItems() if isinstance(n,Edge)}
        if not ids and not links:return
        from model import REFERENCE,NUMERIC_PARAMETERS
        names={self.graph.nodes[i]['p']['name'] for i in ids if self.graph.nodes[i]['kind']=='constant'}
        for i,n in self.graph.nodes.items():
            if i in ids:continue
            p=n['p'];used=set(REFERENCE.findall(p['expression'])) if n['kind'] in ('math','condition') else set()
            used.update(reference(p.get(key)) for key in NUMERIC_PARAMETERS)
            used.update(reference(b['value']) for b in p.get('variables',{}).values())
            if names & used:self.message('Constant still in use: @'+', @'.join(sorted(names & used)));return
        for i in ids:del self.graph.nodes[i]
        self.graph.links=[l for l in self.graph.links if l[0] not in ids and l[2] not in ids and tuple(l) not in links]
        self.graph.reset();self.rebuild()
    def selection(self):
        if self.editing:return
        self.property_generation+=1;generation=self.property_generation;graph=self.graph
        def commit(callback,*values):
            if self.property_generation==generation and self.graph is graph and not self.editing:
                callback(*values)
        nodes=[n for n in self.scene.selectedItems() if isinstance(n,Node)]
        self.selected=nodes[0].ident if nodes else None
        self.scroll.setVisible(bool(nodes) or self.running)
        if self.running:
            self.simulation_panel();return
        widget=QWidget();layout=QVBoxLayout(widget);layout.setContentsMargins(8,8,8,8)
        if not nodes:layout.addWidget(QLabel('Properties\n\nSelect a node to edit it.'))
        else:
            i=self.selected;n=self.graph.nodes[i];p=self.graph.parameters(i);layout.addWidget(QLabel(f'{n["kind"].upper()} • node {i}'))
            locked=n['kind'] in ('math','condition','fifo','logger') and self.graph.has_connections(i)
            form=QFormLayout();form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow);layout.addLayout(form)
            def conversion_note(port):
                conversion=self.graph.conversion(i,port)
                if not conversion:return None
                label=QLabel('Conversion: '+' → '.join(conversion));label.setObjectName('conversion:'+port)
                label.setStyleSheet('color:#ff8585;');label.setWordWrap(True)
                return label
            def field(key,title,kind='text',options=()):
                if kind=='bool':
                    w=QCheckBox();w.setChecked(bool(p[key]));w.toggled.connect(lambda v,k=key:self.change(i,k,v))
                    if key=='ff_enabled':w.setObjectName('pid:ff_enabled')
                    if key=='value':w.setObjectName('simulated-bit');w.setText('ON (1)' if p[key] else 'OFF (0)')
                elif kind=='choice':
                    w=QComboBox();w.addItems(options);w.setCurrentIndex(w.findData(p[key]));w.currentIndexChanged.connect(lambda index,k=key,obj=w:self.change(i,k,obj.itemData(index)))
                elif kind=='number':
                    w=QDoubleSpinBox();dtype=(self.graph.dtype(i) if n['kind']=='fifo' else p['dtype']) if key in ('value','initial') else 'float'
                    low,high=(0,4294967295) if dtype=='u32' else ((-2147483648,2147483647) if dtype=='s32' else (-1e9,1e9))
                    w.setRange(0 if key in ('debounce','on_delay','off_delay','cooldown_ms','duration_ms') else low,high);w.setDecimals(0 if dtype in ('s32','u32') else 3);w.setValue(p[key]);w.setKeyboardTracking(False)
                    if n['kind']=='pid':
                        w.setRange(0 if key=='filter_ms' else -1e9,1e9);w.setDecimals(6);w.setValue(p[key]);w.setObjectName('pid:'+key)
                        w.setMinimumWidth(70);w.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                    if n['kind']=='counter':
                        w.setRange(-2147483648,2147483647);w.setDecimals(0);w.setValue(p[key]);w.setObjectName('counter:'+key)
                        w.setMinimumWidth(70);w.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                    if key in ('debounce','on_delay','off_delay','cooldown_ms','filter_ms','duration_ms'):
                        w.setDecimals(0);w.setSingleStep(1)
                        if n['kind']!='pid':w.setObjectName('input:debounce' if key=='debounce' else 'time:'+key)
                        w.setToolTip(tr('Whole milliseconds; 0 expires immediately.' if key=='duration_ms' else 'Whole milliseconds; 0 disables the delay/filter. Actual timing follows the update period.'))
                    if key in ('input_count','buffer_length','sample_ms'):
                        w.setDecimals(0);w.setRange(1,18 if key=='input_count' else 100000 if key=='buffer_length' else 1e9);w.setValue(p[key]);w.setObjectName('logger:'+key)
                    if key=='window':w.setDecimals(0);w.setRange(1,63);w.setValue(p[key])
                    w.valueChanged.connect(lambda v,k=key:self.change(i,k,int(v) if k in ('input_count','buffer_length','window') else v))
                elif key=='expression':
                    w=ExpressionEdit(p[key]);w.editingFinished.connect(lambda:commit(self.change,i,key,w.toPlainText()))
                else:
                    w=QLineEdit(str(p[key]));w.editingFinished.connect(lambda k=key,obj=w:commit(self.change,i,k,obj.text()))
                if locked and key in ('expression','dtype','input_count'):
                    w.setEnabled(False);w.setToolTip(tr('Disconnect all inputs and outputs before changing this node.'))
                if ((kind=='number' and key not in ('input_count','buffer_length','window')) or (kind=='bool' and key in ('value','initial','enabled'))) and n['kind']!='constant':
                    w=self.reference_editor(w,n['p'][key],lambda value:commit(self.change,i,key,bool(value) if key=='enabled' and not reference(value) else value),'parameter:'+key)
                if key=='expression':form.addRow(QLabel(title));form.addRow(w)
                else:form.addRow(tr(title),w)
            if n['kind'] in ('input','output','constant'):
                if n['kind']!='constant':
                    field('global_io','Global (all modules)','bool')
                    binding=p.get('hal_binding');label=QLabel('HAL: '+(binding['name'] if binding else tr('Unassigned')));label.setWordWrap(True);layout.addWidget(label)
                    button=QPushButton('Select HAL pin / signal');button.clicked.connect(lambda checked=False,node=i:self.choose_hal(node));layout.addWidget(button)
                    if binding:
                        button=QPushButton('Clear HAL binding');button.clicked.connect(lambda checked=False,node=i:self.clear_hal(node));layout.addWidget(button)
                    if n['kind']=='output' and self.graph.driver(i):
                        source=self.graph.driver(i)[0];button=QPushButton('Go to driver');button.setToolTip(self.graph.modules.get(self.graph.driver_module(i),tr('All modules'))+f' / node {source}');button.clicked.connect(lambda checked=False,node=i:self.jump_to_driver(node));layout.addWidget(button)
                field('name','Constant name' if n['kind']=='constant' else 'HAL pin');field('dtype','Type','choice',TYPES)
                if p['dtype']=='bit' and n['kind']!='constant':field('invert','Invert','bool')
                if n['kind']=='constant':
                    field('value','Default value','bool' if p['dtype']=='bit' else 'number')
                    note=QLabel('Use @'+p['name']+' in expressions or numeric parameters.\nExported as a HAL input pin.');note.setWordWrap(True);layout.addWidget(note)
                elif n['kind']=='input':
                    if p['dtype']=='bit':
                        field('edge','Trigger','choice',('level','rising','falling','both'));field('debounce','Debounce ms','number')
                    field('value','Simulated input','bool' if p['dtype']=='bit' else 'number')
                elif p['dtype']=='bit':
                    field('on_delay','ON delay ms','number');field('off_delay','OFF delay ms','number');field('initial','Initial state','bool')
                else:field('initial','Initial value','number')
                if n['kind']=='output':
                    note=conversion_note('in')
                    if note:layout.addWidget(note)
            elif n['kind']=='invert':
                note=QLabel('Logical NOT\nOne bit input → one bit output.\nUnconnected input defaults to 0.');note.setWordWrap(True);layout.addWidget(note)
                note=conversion_note('in')
                if note:layout.addWidget(note)
            elif n['kind']=='display':
                field('message','Message');field('show_value','Append value','bool')
                field('trigger_high','Trigger HIGH (1)','bool');field('cooldown_ms','Cooldown ms','number')
                note=QLabel('Unchecked trigger level = LOW (0).\nPrint once on entry to the active level.\nRapid triggers during cooldown are dropped.\nReset rising edge overrides cooldown and rearms.\nHeld reset does not repeat messages.\nLinuxCNC error message; no NC abort command.\nSimulation only previews the message.');note.setWordWrap(True);layout.addWidget(note)
                for port in self.graph.inputs(i):
                    note=conversion_note(port)
                    if note:layout.addWidget(note)
            elif n['kind']=='logger':
                field('input_count','Input count','number');field('sample_ms','Sample interval ms','number');field('buffer_length','Ringbuffer length','number')
                field('filename','Output file');field('file_format','File format','choice',('csv','tsv','jsonl'));field('number_format','Number format')
                note=QLabel('Trigger rising edge saves the current history.\nInput types and symbol names follow connections.\nFilename: {timestamp}, {sequence}, {node}.\nNumber format: .10g, .3f or .6e.\nFile writing runs outside the realtime thread.');note.setWordWrap(True);layout.addWidget(note)
            elif n['kind'] in processing.KINDS:
                processing_ui.populate(self,i,layout,field)
                for port in self.graph.inputs(i):
                    note=conversion_note(port)
                    if note:layout.addWidget(note)
            elif n['kind']=='timer':
                field('duration_ms','Duration ms','number');field('timer_mode','Output mode','choice',('level','pulse'))
                note=QLabel('Trigger rising edge starts the timer.\nReset HIGH cancels and clears the output.\nLevel: stays HIGH after expiry until reset.\nPulse: HIGH for one update at expiry.\nBusy triggers are ignored.\nDuration is sampled when triggered.');note.setWordWrap(True);layout.addWidget(note)
                for port in self.graph.inputs(i):
                    note=conversion_note(port)
                    if note:layout.addWidget(note)
            elif n['kind']=='counter':
                field('initial','Initial value','number');field('threshold','Threshold','number');field('enabled','Default enable','bool')
                note=QLabel('up/down rising edges add/subtract 1.\nSimultaneous edges cancel each other.\nReset HIGH restores the initial value, even when disabled.\nDisabled: hold count; incoming edges are discarded.\nreached = count >= threshold (not latched).\nSaturates at the signed 32-bit limits.\nCounts sampled edges, not fast hardware pulses.');note.setWordWrap(True);layout.addWidget(note)
                for port in self.graph.inputs(i):
                    note=conversion_note(port)
                    if note:layout.addWidget(note)
            elif n['kind']=='pid':
                for key,title in (('kp','Kp'),('ki','Ki / s'),('kd','Kd · s'),('output_min','Output min'),
                                  ('output_max','Output max'),('filter_ms','D filter ms'),
                                  ('setpoint','Default setpoint'),('feedback','Default feedback')):
                    field(key,title,'number')
                field('ff_enabled','Feedforward','bool');field('ff_gain','FF gain','number')
                field('enabled','Default enable','bool')
                note=QLabel('out = P + I + D + FF (float)\nFF = FF gain × setpoint, when enabled.\nerror = setpoint − feedback\nD acts on measured feedback.\nLimited output holds outward integration.\nReset or disabled: output 0, history cleared.');note.setWordWrap(True);layout.addWidget(note)
                for port in self.graph.inputs(i):
                    note=conversion_note(port)
                    if note:layout.addWidget(note)
            elif n['kind']=='fifo':
                incoming=any(b==i for a,source,b,port in self.graph.links)
                if incoming:form.addRow(tr('Type (from input)'),QLabel(self.graph.dtype(i)))
                else:field('dtype','Unconnected type','choice',TYPES)
                field('initial','Initial value','bool' if self.graph.dtype(i)=='bit' else 'number')
                note=QLabel('Two-sample FIFO\nnow = current input\nlast = previous update\nFirst update: last = initial value.\nSamples once per simulation/HAL update.');note.setWordWrap(True);layout.addWidget(note)
                note=conversion_note('in')
                if note:layout.addWidget(note)
            else:
                if n['kind']=='math':
                    field('dtype','Result type','choice',TYPES)
                    field('template_name','Template name')
                    templates=RawComboBox();templates.setObjectName('math-template-picker')
                    templates.addItem(tr('Choose template…'),None)
                    for path in sorted((Path(__file__).parent/'templates').glob('*.json')):
                        try:
                            data=json.loads(path.read_text());title=data.get('title') or path.stem
                            if not isinstance(title,str):title=path.stem
                        except (OSError,ValueError,AttributeError):title=path.stem
                        templates.addItem(title,str(path))
                    templates.setEnabled(not locked)
                    templates.setToolTip(tr('Disconnect all inputs and outputs before changing the template.' if locked else 'Load a Math template'))
                    templates.activated.connect(lambda index,node=i,obj=templates:self.queue_math_template(node,obj.itemData(index)))
                    form.addRow(tr('Template'),templates)
                    row=QHBoxLayout()
                    for title,save in [('Load template',False),('Save template',True)]:
                        button=QPushButton(title);button.setEnabled(save or not locked);button.clicked.connect(lambda checked=False,node=i,s=save:self.math_template_dialog(node,s));row.addWidget(button)
                    layout.addLayout(row)
                field('expression','Expression')
                help_text=QLabel('Inputs follow the expression.\nTypes convert automatically at inputs.\nPower: ^ or **; constants: pi, e.\nBit shifts: << and >>; 32-bit, zero-fill; count 0–31.\nFunctions: abs, min, max, clamp, pow, sqrt, sin, cos, tan, asin, acos, atan, atan2, log, log10, exp, floor, ceil.\nAngles are in radians.');help_text.setWordWrap(True);layout.addWidget(help_text)
                if locked:
                    note=QLabel('Connected node: disconnect all inputs and outputs to edit the formula, types or template.');note.setWordWrap(True);layout.addWidget(note)
                for name,binding in p['variables'].items():
                    group=RawGroupBox(name);vform=QFormLayout(group);vform.setContentsMargins(7,6,7,6)
                    dtype=QComboBox();dtype.addItems(TYPES);dtype.setCurrentText(binding['dtype']);dtype.setObjectName('type:'+name)
                    dtype.currentTextChanged.connect(lambda value,var=name:self.change_variable(i,var,'dtype',value));vform.addRow(tr('Type'),dtype)
                    dtype.setEnabled(not locked)
                    mode=QComboBox();mode.addItem('Input port','port');mode.addItem('Constant','constant');mode.setCurrentIndex(0 if binding['mode']=='port' else 1);mode.setObjectName('source:'+name)
                    mode.currentIndexChanged.connect(lambda index,var=name,obj=mode:self.change_variable(i,var,'mode',obj.itemData(index)));vform.addRow(tr('Source'),mode)
                    mode.setEnabled(not locked)
                    if binding['dtype']=='bit':
                        val=QCheckBox();val.setChecked(bool(binding['value']));val.toggled.connect(lambda value,var=name:self.change_variable(i,var,'value',float(value)))
                    else:
                        val=QDoubleSpinBox();dtype=binding['dtype']
                        low,high=(0,4294967295) if dtype=='u32' else ((-2147483648,2147483647) if dtype=='s32' else (-1e9,1e9))
                        val.setRange(low,high);val.setDecimals(0 if dtype in ('s32','u32') else 4);val.setKeyboardTracking(False);val.setValue(binding['value'])
                        val.valueChanged.connect(lambda value,var=name:self.change_variable(i,var,'value',value))
                    val.setObjectName('value:'+name)
                    val=self.reference_editor(val,n['p']['variables'][name]['value'],lambda value,var=name:commit(self.change_variable,i,var,'value',value),'variable:'+name)
                    vform.addRow(tr('Default' if binding['mode']=='port' else 'Value'),val)
                    note=conversion_note(name)
                    if note:vform.addRow(note)
                    layout.addWidget(group)
                if n['kind']=='condition':
                    note=QLabel('true = condition result\nfalse = inverse result\nThese are bit signals, not execution branches.');note.setWordWrap(True);layout.addWidget(note)
            if n['kind'] in ('math','condition','fifo','logger'):
                b=QPushButton('Disconnect all');b.clicked.connect(lambda checked=False,node=i:self.disconnect(node,True))
            else:
                b=QPushButton('Disconnect inputs');b.clicked.connect(lambda checked=False,node=i:self.disconnect(node))
            layout.addWidget(b)
        layout.addStretch();self.scroll.setWidget(widget)
    def reference_editor(self,control,value,callback,name):
        choices=[n['p']['name'] for n in self.graph.nodes.values() if n['kind']=='constant']
        if not choices:return control
        wrapper=QWidget();row=QHBoxLayout(wrapper);row.setContentsMargins(0,0,0,0);row.setSpacing(3)
        picker=RawComboBox();picker.setObjectName('reference:'+name);picker.addItem(tr('Value'),None)
        for constant in choices:picker.addItem('@'+constant,'@'+constant)
        picker.setCurrentIndex(picker.findData(value) if reference(value) else 0)
        control.setEnabled(not reference(value));picker.setMinimumWidth(65)
        picker.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        control.setMinimumWidth(55);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        row.addWidget(picker,1);row.addWidget(control,1)
        def choose(index):
            selected=picker.itemData(index)
            callback(selected if selected else (float(control.isChecked()) if isinstance(control,QCheckBox) else control.value()))
            QTimer.singleShot(0,self.selection)
        picker.activated.connect(choose)
        return wrapper
    def simulation_panel(self):
        widget=QWidget();widget.setObjectName('simulation-panel')
        layout=QVBoxLayout(widget);layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(5)
        title=QLabel('Live HAL test' if self.live_process else 'Simulation');layout.addWidget(title)
        self.live_runtime_label=None
        if self.live_process:
            self.live_runtime_label=QLabel('—');self.live_runtime_label.setObjectName('live-runtime');self.live_runtime_label.setWordWrap(True);layout.addWidget(self.live_runtime_label)
        self.simulation_controls={};self.simulation_values={}
        graph=self.graph;generation=self.property_generation
        def commit(i,value):
            if self.running and self.graph is graph and self.property_generation==generation:
                self.change(i,'value',convert(value,graph.dtype(i)))
        for kind,title in (('input','Inputs'),('constant','Constants'),('output','Outputs'),('internal','Node signals')):
            group=QGroupBox(title);form=QFormLayout(group)
            form.setContentsMargins(6,6,6,6);form.setVerticalSpacing(3)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            count=0
            for i,n in graph.nodes.items():
                if (n['kind'] if n['kind'] in ('input','output','constant') else 'internal')!=kind:continue
                p=n['p'];name=('@'+p['name'] if kind=='constant' else p['name']) if kind!='internal' else (p.get('template_name') or tr(n['kind'].upper()))+f' #{i}'
                def caption(text):
                    label=RawLabel();label.setFixedWidth(110)
                    label.setText(label.fontMetrics().elidedText(text,Qt.TextElideMode.ElideRight,110))
                    label.setToolTip(text+' : '+graph.dtype(i)+'\n'+tr('Module: ')+graph.modules[n.get('module',0)])
                    return label
                row=QHBoxLayout();row.setSpacing(4)
                if kind in ('input','constant'):
                    dtype=graph.dtype(i)
                    if dtype=='bit':
                        control=QCheckBox();control.setChecked(bool(graph.resolve(p['value'])))
                        control.toggled.connect(lambda value,node=i:commit(node,value))
                    else:
                        control=QDoubleSpinBox()
                        low,high=(0,4294967295) if dtype=='u32' else ((-2147483648,2147483647) if dtype=='s32' else (-1e9,1e9))
                        control.setRange(low,high);control.setDecimals(0 if dtype in ('s32','u32') else 6)
                        control.setKeyboardTracking(False);control.setValue(graph.resolve(p['value']))
                        control.valueChanged.connect(lambda value,node=i:commit(node,value))
                    control.setObjectName(f'simulation-input:{i}')
                    control.setMinimumWidth(70);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                    control.setToolTip(name+' : '+dtype)
                    if self.live_process and p.get('hal_binding'):control.setEnabled(False)
                    if reference(p['value']):control.setEnabled(False);control.setToolTip(p['value'])
                    row.addWidget(control,1);self.simulation_controls[i]=control
                ports=graph.outputs(i) or (None,)
                for port in ports:
                    label=QLabel('—');label.setObjectName(f'simulation-value:{i}:{port or "value"}')
                    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    label.setToolTip(name+' : '+graph.dtype(i,port))
                    if kind in ('input','constant'):
                        label.setToolTip('Processed input signal');row.addWidget(label)
                        form.addRow(caption(name),row)
                    else:
                        form.addRow(caption(name+('.'+port if kind=='internal' and port else '')),label)
                    self.simulation_values[i,port]=label
                count+=1
            if not count:form.addRow(QLabel('No nodes'))
            layout.addWidget(group)
        layout.addStretch();self.scroll.setWidget(widget);self.update_simulation_panel()
    def update_simulation_panel(self):
        if not self.running:return
        for i,control in self.simulation_controls.items():
            value=self.live_inputs.get(i,self.graph.resolve(self.graph.nodes[i]['p']['value']));control.blockSignals(True)
            if isinstance(control,QCheckBox):
                control.setChecked(bool(value));control.setText('ON (1)' if value else 'OFF (0)')
            elif not control.hasFocus() and not control.lineEdit().hasFocus():control.setValue(value)
            control.blockSignals(False)
        for (i,port),label in self.simulation_values.items():
            if i not in self.graph.values:
                label.setText('—');label.setStyleSheet('')
                if i in self.simulation_controls:label.setVisible(False)
                continue
            value=self.graph.value(i,port);dtype=self.graph.dtype(i,port)
            if i in self.simulation_controls:
                label.setVisible(value!=convert(self.graph.resolve(self.graph.nodes[i]['p']['value']),dtype))
            if self.graph.nodes[i]['kind']=='logger':label.setText(tr('Samples')+f': {int(value)} / {self.graph.nodes[i]["p"]["buffer_length"]}')
            else:label.setText(('ON (1)' if value else 'OFF (0)') if dtype=='bit' else (str(int(value)) if dtype in ('s32','u32') else f'{value:.10g}'))
            label.setStyleSheet('color:'+('#8ce3bb' if value else '#aebac6')+';')
    def refresh_node(self,i):
        if self.graph.nodes[i]['p'].get('global_io'):QTimer.singleShot(0,lambda:self.rebuild(i) if i in self.graph.nodes else None);return
        if i not in self.items:return
        self.cancel_wire();self.editing=True
        try:
            old=self.items.pop(i);selected=old.isSelected();self.scene.removeItem(old)
            node=Node(self,i);self.items[i]=node;self.scene.addItem(node);node.setSelected(selected)
            self.update_edges()
        finally:self.editing=False
    def change(self,i,key,value):
        if self.live_process:
            if key=='value' and self.graph.nodes[i]['kind'] in ('input','constant') and not self.graph.nodes[i]['p'].get('hal_binding'):
                if reference(value):self.message('Live test inputs require a numeric value.');return
                self.live_process.write((json.dumps(dict(cmd='set',node=i,value=value))+'\n').encode())
            else:self.message('Live HAL source is read-only.' if key=='value' else 'Stop Live HAL test before editing.')
            return
        if key=='global_io':self.set_global(i,value);return
        if i not in self.graph.nodes:return
        self.cancel_wire();p=self.graph.nodes[i]['p']
        if value==p[key]:return
        if self.graph.nodes[i]['kind'] in ('math','condition','fifo','logger') and key in ('expression','dtype','input_count') and self.graph.has_connections(i):
            self.message('Disconnect all inputs and outputs before changing this node.');return
        removed=0
        try:
            if key=='expression':removed=self.graph.set_expression(i,value)
            else:
                old=p[key];p[key]=value
                try:self.graph.validate()
                except Exception:p[key]=old;raise
                if key!='value':self.graph.reset()
        except (ValueError,SyntaxError) as e:
            self.message(e)
            if key=='dtype':QTimer.singleShot(0,self.selection)
            if self.graph.nodes[i]['kind'] in ('pid','constant')+processing.KINDS:QTimer.singleShot(0,self.selection)
            return
        if key=='value' and self.graph.nodes[i]['kind']=='input':
            if i in self.items:self.items[i].show_value()
            if self.running:self.update_simulation_panel()
            if self.selected==i and p['dtype']=='bit':
                checkbox=self.scroll.widget().findChild(QCheckBox,'simulated-bit')
                if checkbox:
                    checkbox.blockSignals(True);checkbox.setChecked(bool(value));checkbox.setText('ON (1)' if value else 'OFF (0)');checkbox.blockSignals(False)
        elif self.graph.nodes[i]['kind']=='constant':
            if self.running and key=='value':
                if i in self.items:self.items[i].show_value(convert(value,p['dtype']))
                self.update_simulation_panel()
            else:self.rebuild(i)
        else:self.refresh_node(i)
        if key in ('dtype','expression','input_count','states'):QTimer.singleShot(0,self.selection)
        self.message('Updated '+key+(f' • removed {removed} obsolete connection(s)' if removed else ''))
    def toggle_bit(self,i):
        n=self.graph.nodes[i]
        if n['kind']=='input' and n['p']['dtype']=='bit':
            if reference(n['p']['value']):self.message('Input value is controlled by '+n['p']['value']);return
            self.change(i,'value',float(not bool(self.live_inputs.get(i,n['p']['value']))))
    def math_template_dialog(self,i,save=False):
        if self.live_process:return
        if not save and self.graph.has_connections(i):
            self.message('Disconnect all inputs and outputs before changing this node.');return
        root=Path(__file__).parent/'templates';root.mkdir(exist_ok=True)
        fn=QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path,_=fn(self,tr('Save template' if save else 'Load template'),str(root/'my-math.json' if save else root),tr('Math template (*.json)'),options=QFileDialog.Option.DontUseNativeDialog)
        if path:self.math_template_file(i,Path(path),save)
    def queue_math_template(self,i,path):
        # Do not destroy the combo box inside its activated event.
        if path:QTimer.singleShot(0,lambda:self.math_template_file(i,Path(path)))
    def math_template_file(self,i,path,save=False):
        if self.live_process:return
        try:
            if save:
                if path.suffix!='.json':path=path.with_suffix('.json')
                self.graph.save_math_template(i,path);self.refresh_node(i);QTimer.singleShot(0,self.selection);self.message('Saved Math template: '+path.name)
            else:
                removed=self.graph.load_math_template(i,path);self.refresh_node(i);QTimer.singleShot(0,self.selection)
                self.message('Loaded Math template: '+path.name+(f' • removed {removed} obsolete connection(s)' if removed else ''))
        except (OSError,ValueError,KeyError,SyntaxError,TypeError) as error:self.message(error)
    def change_variable(self,i,name,key,value):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        if i not in self.graph.nodes or name not in self.graph.nodes[i]['p'].get('variables',{}):return
        if key in ('mode','dtype') and self.graph.has_connections(i):
            self.message('Disconnect all inputs and outputs before changing this node.');return
        try:removed=self.graph.set_variable(i,name,key,value)
        except ValueError as e:
            self.message(e);QTimer.singleShot(0,self.selection);return
        self.refresh_node(i)
        if key in ('mode','dtype'):QTimer.singleShot(0,self.selection)
        self.message('Updated '+name+' '+key+(f' • removed {removed} connection(s)' if removed else ''))
    def disconnect(self,i,all_connections=False):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        if all_connections:self.graph.disconnect_node(i)
        else:self.graph.links=[l for l in self.graph.links if l[2]!=i];self.graph.reset()
        self.update_edges();QTimer.singleShot(0,self.selection)
    def start_live(self):
        if self.live_process:return
        import tempfile
        self.debug_build.setChecked(True)
        try:
            self.graph.validate();self.graph.reset();self.live_directory=tempfile.TemporaryDirectory(prefix='nne-live-')
            root=Path(self.live_directory.name);project=root/'project.json';self.graph.save(project)
            component=root/(f'nne_live_{os.getuid()}.comp')
            self.live_buffer=b'';self.live_active=False;self.live_inputs={};process=QProcess(self);self.live_process=process
            process.readyReadStandardOutput.connect(self.read_live)
            process.readyReadStandardError.connect(lambda:self.message(bytes(process.readAllStandardError()).decode(errors='replace').strip()))
            process.finished.connect(self.live_finished);process.errorOccurred.connect(lambda error:self.live_start_error(process,error))
            self.toolbars['Nodes'].setEnabled(False);self.test_mode.setEnabled(False);self.debug_build.setEnabled(False)
            self.running=True;self.timer.stop();self.run_button.setText('■ Stop');self.selection()
            process.start('/usr/bin/python3',[str(Path(__file__).with_name('live_hal.py')),str(project),str(component),'--base-dir',str(self.project.parent if self.project else Path(__file__).parent)])
            self.message('Starting input-only Live HAL test…')
        except (OSError,ValueError,SyntaxError) as e:self.message(e);self.live_finished()
    def live_start_error(self,process,error):
        self.message(process.errorString())
        if error==QProcess.ProcessError.FailedToStart:self.live_finished()
    def read_live(self):
        process=self.live_process
        if not process:return
        self.live_buffer+=bytes(process.readAllStandardOutput())
        while b'\n' in self.live_buffer:
            line,self.live_buffer=self.live_buffer.split(b'\n',1)
            try:event=json.loads(line)
            except ValueError:continue
            self.apply_live_event(event)
    def apply_live_event(self,event):
        kind=event.get('event')
        if kind in ('log','error'):self.message(event['message'])
        elif kind=='authorization':
            process=self.live_process
            password,ok=QInputDialog.getText(self,tr('HAL installation'),tr('sudo password'),QLineEdit.EchoMode.Password)
            if process is self.live_process and process is not None:
                process.write((json.dumps(dict(cmd='authorize',password=password if ok else None))+'\n').encode())
            password=None
        elif kind=='ready':self.live_active=True;self.message('Live HAL test: inputs connected; outputs monitored')
        elif kind=='values':
            self.graph.monitor_values={(entry['node'],entry['port']):entry['value'] for entry in event['values']}
            self.live_inputs={int(key):value for key,value in event['inputs'].items()}
            for entry in event['values']:
                i=entry['node'];port=entry['port'];value=entry['value'];node=self.graph.nodes[i]
                if node['kind']=='fifo' and port=='last':self.graph.state.setdefault(i,{})['last']=value
                elif node['kind']=='pid' and port=='error':self.graph.state.setdefault(i,{})['error']=value
                elif node['kind']=='counter' and port=='reached':self.graph.state.setdefault(i,{})['reached']=value
                elif port!='false':self.graph.values[i]=float(value)
            for i,item in self.items.items():item.show_value(self.graph.values.get(i))
            if getattr(self,'live_runtime_label',None):self.live_runtime_label.setText(tr('Runtime')+f': {event["time_ns"]/1000:.3f} µs / max {event["tmax_ns"]/1000:.3f} µs\nHAL time: {event["hal_time"]}')
            self.update_simulation_panel();self.message(f'Live HAL • {tr("Runtime")}: {event["time_ns"]/1000:.3f} µs • max: {event["tmax_ns"]/1000:.3f} µs • HAL time: {event["hal_time"]}')
    def stop_live(self,wait=False):
        process=self.live_process
        if not process:return
        process.write(b'{"cmd":"stop"}\n');process.terminate()
        if wait:process.waitForFinished(15000)
    def live_finished(self,*unused):
        process=self.live_process
        if process:self.read_live();process.deleteLater()
        self.live_process=None;self.live_active=False;self.live_inputs={};self.running=False;self.run_button.blockSignals(True);self.run_button.setChecked(False);self.run_button.blockSignals(False);self.run_button.setText('▶ Simulate')
        if self.live_directory:self.live_directory.cleanup();self.live_directory=None
        if not getattr(self,'_shutting_down',False):
            self.toolbars['Nodes'].setEnabled(True);self.test_mode.setEnabled(True);self.debug_build.setEnabled(True);self.rebuild(self.selected)
            if getattr(self,'close_after_live',False):self.close_after_live=False;QTimer.singleShot(0,self.close)
    def run(self,active):
        if active and self.test_mode.currentData()=='live':self.start_live();return
        if not active and self.live_process:self.stop_live();return
        self.running=active;self.graph.reset();self.run_button.setText('■ Stop' if active else '▶ Simulate')
        self.selection()
        if active:self.timer.start();self.message('SIMULATION ONLY • no hardware outputs')
        else:self.timer.stop()
    def poll_logger(self):
        writer=getattr(self,'logger_writer',None)
        if writer:
            for key,path,error in writer.poll():self.message(f'Logger {key}: '+(error or 'Saved '+path))
    def tick(self):
        try:
            self.graph.logger_base_dir=(self.project.parent if self.project else Path(__file__).parent)
            self.poll_logger()
            for i,v in self.graph.step(.02).items():
                if i in self.items:self.items[i].show_value(v)
            for snapshot in self.graph.logger_requests:
                if not getattr(self,'logger_writer',None):self.logger_writer=SnapshotWriter()
                if not self.logger_writer.submit(snapshot):self.message('Logger save busy: snapshot skipped')
            if self.running:self.update_simulation_panel()
            if self.graph.messages:self.message('SIM DISPLAY • '+' | '.join(self.graph.messages))
        except (ValueError,SyntaxError,OverflowError) as e:
            self.run_button.setChecked(False);self.run(False);self.message(e)
    def new(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        self.run_button.setChecked(False);self.run(False);self.graph=Graph();self.project=None;self.last_export=None;self.rebuild()
    def choose(self,title,save=False,filter='PLC project (*.json)'):
        fn=QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path,_=fn(self,tr(title),str(self.project or Path(__file__).parent/'examples/demo.json'),tr(filter),options=QFileDialog.Option.DontUseNativeDialog)
        return Path(path) if path else None
    def open(self):
        if self.live_process:self.message('Stop Live HAL test before editing.');return
        path=self.choose('Open project')
        if path:
            try:g=Graph.load(path);self.run_button.setChecked(False);self.run(False);self.graph=g;self.project=path.resolve();self.last_export=None;self.rebuild();self.fit();self.message('Loaded '+str(path));self.remember_project()
            except (OSError,ValueError,KeyError,SyntaxError,TypeError,AttributeError) as e:self.message(e)
    def save(self):
        path=self.project or self.choose('Save project',True)
        if path:
            try:self.graph.validate();self.graph.save(path);self.project=path.resolve();self.message('Saved '+str(path));self.remember_project()
            except (OSError,ValueError,SyntaxError) as e:self.message(e)
    def remember_project(self):
        try:self.session.remember(self.project)
        except OSError as error:self.message(self.status.text()+f' • could not remember project: {error}')
    def export(self):
        path=self.choose('Export HAL component',True,'HAL component (*.comp)')
        if path:
            if path.suffix!='.comp':path=path.with_suffix('.comp')
            try:
                self.graph.export(path,debug=self.debug_build.isChecked());self.last_export=path
                notice=f'Exported {path.name} • build: halcompile --compile {path.name}'
                if any(n['kind']=='logger' for n in self.graph.nodes.values()):notice+=' • '+path.with_suffix('.logger.hal').name
                self.message(notice)
            except (OSError,ValueError,SyntaxError) as e:self.message(e)

    def build(self):
        if self.builder and self.builder.state()!=QProcess.ProcessState.NotRunning:
            self.message('Build already running.');return
        if self.last_export is None:self.export()
        if self.last_export is None:return
        try:self.graph.export(self.last_export,debug=self.debug_build.isChecked())
        except (OSError,ValueError,SyntaxError) as e:self.message(e);return
        self.builder=QProcess(self)
        self.builder.setWorkingDirectory(str(self.last_export.resolve().parent))
        self.builder.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.builder.finished.connect(self.build_finished)
        self.builder.errorOccurred.connect(lambda error:self.message('Could not start halcompile: '+self.builder.errorString()))
        self.builder.start('halcompile',['--compile',self.last_export.name])
        self.message('Compiling '+self.last_export.name+'…')
    def build_finished(self,code,status):
        output=bytes(self.builder.readAll()).decode(errors='replace')
        log=self.last_export.with_suffix('.build.txt');log.write_text(output)
        self.message(('Built '+self.last_export.with_suffix('.so').name if code==0 else 'Build failed')+' • '+str(log))


def main():
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion');app.setFont(__import__('PySide6.QtGui',fromlist=['QFont']).QFont('DejaVu Sans',9))
    window=Editor();app.aboutToQuit.connect(window.shutdown)
    if os.environ.get('QT_QPA_PLATFORM','').split(':')[0] in ('eglfs','linuxfb') and not args.windowed:window.showFullScreen()
    else:window.show()
    if args.screenshot:
        def capture():
            window.fit();app.processEvents();window.grab().save(str(args.screenshot));app.quit()
        QTimer.singleShot(200,capture)
    return app.exec()

if __name__=='__main__':sys.exit(main())
