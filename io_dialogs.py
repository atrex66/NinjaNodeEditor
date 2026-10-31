"""Shared pin/signal chooser and global I/O management windows (MIT)."""
from pathlib import Path
from PySide6.QtCore import Qt,QProcess,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QPushButton,QLabel,QFileDialog,QAbstractItemView,QCheckBox)
from i18n import tr
from hal_bindings import Catalogue

class HALChooser(QDialog):
    def __init__(self,editor,role,node=None,multiple=False,*,parent=None):
        super().__init__(editor if parent is None else parent);self.editor=editor;self.role=role;self.node=node;self.chosen=[];self.catalogue=editor.hal_catalogue
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(tr('Select HAL pin / signal'));self.resize(760,460)
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row)
        self.search=QLineEdit();self.search.setPlaceholderText(tr('Search pins, signals or components'));self.search.textChanged.connect(self.populate);row.addWidget(self.search,1)
        self.kind=QComboBox();self.kind.addItem(tr('Pins and signals'),'all');self.kind.addItem(tr('Pins'),'pin');self.kind.addItem(tr('Signals'),'signal');self.kind.currentIndexChanged.connect(self.populate);row.addWidget(self.kind)
        for label,callback in [('Refresh',self.refresh),('Load catalogue',self.load),('Save catalogue',self.save)]:
            button=QPushButton(tr(label));button.clicked.connect(callback);row.addWidget(button)
        filters=QHBoxLayout();layout.addLayout(filters)
        self.type_filter=QComboBox();self.type_filter.addItem(tr('All types'),'all')
        for dtype in ('bit','float','s32','u32'):self.type_filter.addItem(dtype,dtype)
        self.type_filter.currentIndexChanged.connect(self.populate);filters.addWidget(self.type_filter)
        self.direction_filter=QComboBox();self.direction_filter.addItem(tr('All directions'),'all')
        for direction in ('IN','OUT','IO'):self.direction_filter.addItem(direction,direction)
        self.direction_filter.currentIndexChanged.connect(self.populate);filters.addWidget(self.direction_filter)
        self.compatible=QCheckBox(tr('Compatible only'));self.compatible.toggled.connect(self.populate);filters.addWidget(self.compatible);filters.addStretch()
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels([tr(x) for x in ('Kind','Name','Type','Direction','Value','HAL signal','Project driver')]);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multiple else QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.details);self.table.itemDoubleClicked.connect(lambda item:self.choose());layout.addWidget(self.table,1)
        self.info=QLabel();self.info.setWordWrap(True);layout.addWidget(self.info)
        row=QHBoxLayout();layout.addLayout(row);self.jump=QPushButton(tr('Go to driver'));self.jump.clicked.connect(self.jump_driver);row.addWidget(self.jump);row.addStretch()
        self.accept_button=QPushButton(tr('Add selected'));self.accept_button.clicked.connect(self.choose);row.addWidget(self.accept_button)
        cancel=QPushButton(tr('Cancel'));cancel.clicked.connect(self.reject);row.addWidget(cancel)
        self.process=None;self.populate()
    def rows(self):
        for kind,items in (('pin',self.catalogue.pins),('signal',self.catalogue.signals)):
            for item in items.values():yield kind,item
    def matched_nodes(self,kind,item):
        for i,n in self.editor.graph.nodes.items():
            b=n['p'].get('hal_binding')
            if b and ((b['kind'],b['name'])==(kind,item['name']) or kind=='signal' and b.get('signal')==item['name']):yield i,n
    def populate(self,*unused):
        self.table.setRowCount(0);query=self.search.text().casefold();wanted=self.kind.currentData()
        for kind,item in self.rows():
            if wanted not in ('all',kind) or query not in (item['name']+' '+item.get('owner','')).casefold():continue
            if self.type_filter.currentData() not in ('all',item['dtype']) or self.direction_filter.currentData() not in ('all',item.get('direction')):continue
            drivers=[]
            for i,n in self.matched_nodes(kind,item):
                if n['kind']!='output':continue
                d=self.editor.graph.driver(i)
                if d:drivers.append(self.editor.graph.modules.get(self.editor.graph.driver_module(i),tr('All modules'))+f' / node {d[0]}')
                else:drivers.append(n['p']['name'])
            try:binding=self.catalogue.binding(kind,item['name'],self.role);error=None
            except ValueError as e:binding=None;error=str(e)
            if self.compatible.isChecked() and error:continue
            values=(kind,item['name'],item['dtype'],item.get('direction',''),str(item.get('value','')),item.get('signal',''),', '.join(drivers))
            r=self.table.rowCount();self.table.insertRow(r)
            for c,value in enumerate(values):
                cell=QTableWidgetItem(value)
                if c==0:cell.setData(Qt.ItemDataRole.UserRole,(kind,item['name']))
                if error:cell.setToolTip(tr(error));cell.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(r,c,cell)
        self.table.resizeColumnsToContents();self.table.setColumnWidth(1,max(180,self.table.columnWidth(1)));self.details()
    def selected(self):return [self.table.item(index.row(),0).data(Qt.ItemDataRole.UserRole) for index in self.table.selectionModel().selectedRows()]
    def details(self):
        self.jump_node=None;self.jump_output=None;selected=self.selected();self.accept_button.setEnabled(bool(selected))
        text=[]
        for kind,name in selected:
            try:self.catalogue.binding(kind,name,self.role)
            except ValueError as e:self.accept_button.setEnabled(False);text.append(tr(str(e)))
            item=(self.catalogue.pins if kind=='pin' else self.catalogue.signals)[name];signal=item.get('signal') if kind=='pin' else name
            members=self.catalogue.signals.get(signal,{}).get('pins',[])
            text.append(name+(' → '+signal if signal and signal!=name else '')+': '+', '.join(p['direction']+' '+p['name'] for p in members))
            for i,n in self.matched_nodes(kind,item):
                if n['kind']=='output' and self.editor.graph.driver(i):self.jump_node=self.editor.graph.driver(i)[0];self.jump_output=i
        self.info.setText('\n'.join(text));self.jump.setEnabled(self.jump_node is not None)
    def jump_driver(self):
        if self.jump_node is not None:
            i=self.jump_output;self.accept();QTimer.singleShot(0,lambda:self.editor.jump_to_driver(i))
    def choose(self):
        try:self.chosen=[self.catalogue.binding(kind,name,self.role) for kind,name in self.selected()]
        except ValueError as e:self.info.setText(tr(str(e)));return
        if self.chosen:self.editor.hal_catalogue=self.catalogue;self.accept()
    def refresh(self):
        if self.process and self.process.state()!=QProcess.ProcessState.NotRunning:return
        self.pin_text=None;self.process=QProcess(self);self.process.finished.connect(self.refreshed);self.process.errorOccurred.connect(lambda error:self.info.setText(self.process.errorString()))
        self.info.setText(tr('Reading HAL…'));self.process.start('halcmd',['-s','show','pin'])
    def refreshed(self,code,status):
        data=bytes(self.process.readAllStandardOutput()).decode(errors='replace');error=bytes(self.process.readAllStandardError()).decode(errors='replace')
        if code:self.info.setText(error or tr('HAL discovery failed'));return
        if self.pin_text is None:self.pin_text=data;self.process.start('halcmd',['-s','show','sig']);return
        try:self.catalogue=Catalogue.parse(self.pin_text,data);self.editor.hal_catalogue=self.catalogue;self.populate()
        except (ValueError,KeyError,TypeError) as e:self.info.setText(str(e))
    def load(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Load catalogue'),'','JSON (*.json)',options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            try:self.catalogue=Catalogue.load(path);self.editor.hal_catalogue=self.catalogue;self.populate()
            except (OSError,ValueError,KeyError,TypeError) as e:self.info.setText(str(e))
    def save(self):
        path,_=QFileDialog.getSaveFileName(self,tr('Save catalogue'),'hal-catalogue.json','JSON (*.json)',options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            try:self.catalogue.save(path)
            except (OSError,ValueError,TypeError) as e:self.info.setText(str(e))
    def done(self,result):
        if self.process and self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill();self.process.waitForFinished(1000)
        super().done(result)

class GlobalIOWindow(QDialog):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.setWindowTitle(tr('Global I/O'));self.resize(650,430)
        layout=QVBoxLayout(self);row=QHBoxLayout();layout.addLayout(row)
        self.role=QComboBox();self.role.addItem(tr('Global Inputs'),'input');self.role.addItem(tr('Global Outputs'),'output');self.role.currentIndexChanged.connect(self.populate);row.addWidget(self.role)
        for text,callback in [('Add input / output',self.add),('Add HAL signals…',self.add_hal),('Remove selected',self.remove)]:
            b=QPushButton(tr(text));b.clicked.connect(callback);row.addWidget(b)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels([tr(x) for x in ('Name','Type','HAL signal','Project driver')]);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.itemDoubleClicked.connect(self.edit);layout.addWidget(self.table)
        self.info=QLabel(tr('Double-click a signal to edit it. Removing it also removes its connections in all modules.'));self.info.setWordWrap(True);layout.addWidget(self.info)
        close=QPushButton(tr('Close'));close.clicked.connect(self.accept);layout.addWidget(close);self.populate()
    def populate(self,*unused):
        self.table.setRowCount(0)
        for i,n in self.editor.graph.nodes.items():
            if not n['p'].get('global_io') or n['kind']!=self.role.currentData():continue
            b=n['p'].get('hal_binding');d=self.editor.graph.driver(i);driver=self.editor.graph.modules.get(self.editor.graph.driver_module(i),tr('All modules'))+f' / node {d[0]}' if d else tr('Unconnected')
            r=self.table.rowCount();self.table.insertRow(r)
            for c,text in enumerate((n['p']['name'],n['p']['dtype'],b['name'] if b else '—',driver)):
                cell=QTableWidgetItem(text);cell.setData(Qt.ItemDataRole.UserRole,i);self.table.setItem(r,c,cell)
        self.table.resizeColumnsToContents()
    def add(self):self.editor.add_global(self.role.currentData());self.populate()
    def add_hal(self):
        dialog=HALChooser(self.editor,self.role.currentData(),multiple=True,parent=self)
        if dialog.exec():
            for binding in dialog.chosen:self.editor.add_global(self.role.currentData(),binding)
            self.populate()
    def remove(self):
        ids={self.table.item(index.row(),0).data(Qt.ItemDataRole.UserRole) for index in self.table.selectionModel().selectedRows()}
        for i in ids:del self.editor.graph.nodes[i]
        self.editor.graph.links=[link for link in self.editor.graph.links if link[0] not in ids and link[2] not in ids];self.editor.graph.reset();self.editor.rebuild();self.populate()
    def edit(self,item):
        i=item.data(Qt.ItemDataRole.UserRole);self.accept();QTimer.singleShot(0,lambda:self.editor.jump_to_node(i))
