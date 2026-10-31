"""Property editors for bounded processing nodes."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,
 QSpinBox,QDoubleSpinBox,QPushButton,QLabel,QDialogButtonBox,QFormLayout,QLineEdit,QComboBox,QMessageBox,QHeaderView)
from i18n import tr
import processing

FIELDS={
 'latch':(('initial','Initial state','bool'),('priority','Priority','choice',('reset','set'))),
 'hysteresis':(('initial','Initial state','bool'),('low','Lower threshold','number'),('high','Upper threshold','number')),
 'watchdog':(('timeout_ms','Timeout ms','number'),('watch_mode','Heartbeat edge','choice',('rising','both')),('latched','Latch fault until reset','bool'),('enabled','Default enable','bool')),
 'ramp':(('initial','Initial value','number'),('rise_rate','Rise units / s','number'),('fall_rate','Fall units / s','number'),('enabled','Default enable','bool')),
 'filter':(('initial','Initial value','number'),('filter_mode','Filter mode','choice',('lowpass','average','median')),('tau_ms','Time constant ms','number'),('window','Window samples (1..63)','number'),('enabled','Default enable','bool')),
 'sequencer':(('enabled','Default enable','bool'),),
}
NOTES={
 'latch':'SET/RESET levels store one bit. Priority resolves simultaneous inputs.',
 'hysteresis':'HIGH at or above the upper threshold; LOW at or below the lower threshold. Holds inside the band.',
 'watchdog':'Heartbeat edges restart the timeout. A held signal is not a heartbeat. Enable starts a grace interval; reset or disable clears the fault. healthy is LOW while disabled/reset.',
 'ramp':'Separate rise/fall rates in units per second. Disabled holds output; reset restores initial value. A zero rate holds in that direction.',
 'filter':'Lowpass uses dt/(tau+dt). Average/median use the most recent samples (maximum 63). Startup uses available samples. Disabled holds; reset clears history.',
 'sequencer':'Starts at state 0. Each advanceN rising edge leaves state N for its configured target. Last state is terminal. Timeout has priority and latches a fault. Reset returns to state 0; disabled freezes time and discards edges.',
 'memory_read':'Reads the previous cycle value of the named memory. Readers in every module share it. Initial value applies on simulation reset or HAL reload.',
 'memory_write':'Commits its input at the end of the cycle. All readers see it next cycle. Only one writer per memory; no input means zero.',
}

def populate(editor,i,layout,field):
 n=editor.graph.nodes[i];kind=n['kind']
 for spec in FIELDS.get(kind,()):field(*spec)
 if kind=='sequencer':
  b=QPushButton(tr('Edit states…'));b.setObjectName('edit-states');b.clicked.connect(lambda:edit_states(editor,i));layout.addWidget(b)
 if kind.startswith('memory_'):
  b=QPushButton(tr('Configure memory…'));b.setObjectName('edit-memory');b.clicked.connect(lambda:edit_memory(editor,i));layout.addWidget(b)
  layout.addWidget(QLabel(tr('Shared memory')+': '+n['p']['memory']))
 label=QLabel(tr(NOTES[kind]));label.setWordWrap(True);layout.addWidget(label)


def edit_states(editor,i):
 if editor.live_process:return
 states=deepcopy(editor.graph.nodes[i]['p']['states'])
 dialog=QDialog(editor);dialog.setWindowTitle(tr('State machine'));dialog.resize(570,400);layout=QVBoxLayout(dialog)
 table=QTableWidget(0,3);table.setHorizontalHeaderLabels([tr('State name'),tr('Next state'),tr('Timeout ms')]);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(table)
 def add(state=None):
  row=table.rowCount()
  if row>=16:return
  state=state or dict(name='State '+str(row),next=row,timeout_ms=0)
  table.insertRow(row);table.setVerticalHeaderItem(row,QTableWidgetItem(str(row)));table.setRowHeight(row,36);table.setItem(row,0,QTableWidgetItem(state['name']))
  target=QSpinBox();target.setRange(0,15);target.setValue(state['next']);table.setCellWidget(row,1,target)
  timeout=QDoubleSpinBox();timeout.setRange(0,1e12);timeout.setDecimals(3);timeout.setValue(state['timeout_ms']);table.setCellWidget(row,2,timeout)
 for state in states:add(state)
 row=QHBoxLayout();layout.addLayout(row)
 for name,callback in [('Add state',lambda:add()),('Remove last state',lambda:table.removeRow(table.rowCount()-1) if table.rowCount()>2 else None)]:
  b=QPushButton(tr(name));b.clicked.connect(callback);row.addWidget(b)
 note=QLabel(tr('Last state is terminal. Timeout 0 disables supervision. State numbering starts at 0.'));note.setWordWrap(True);layout.addWidget(note)
 buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
 def accept():
  result=[dict(name=table.item(r,0).text(),next=table.cellWidget(r,1).value(),timeout_ms=table.cellWidget(r,2).value()) for r in range(table.rowCount())]
  p=dict(editor.graph.nodes[i]['p'],states=result)
  try:
   processing.validate('sequencer',p)
   if len(result)!=len(states) and editor.graph.has_connections(i):raise ValueError('Disconnect all inputs and outputs before changing this node.')
  except ValueError as e:QMessageBox.warning(dialog,tr('State machine'),tr(str(e)));return
  editor.change(i,'states',result);dialog.accept()
 buttons.accepted.connect(accept);dialog.exec()


def edit_memory(editor,i):
 if editor.live_process:return
 node=editor.graph.nodes[i];p=node['p'];dialog=QDialog(editor);dialog.setWindowTitle(tr('Shared memory'));form=QFormLayout(dialog)
 name=QLineEdit(p['memory']);form.addRow(tr('Memory name'),name)
 dtype=QComboBox();dtype.addItems(('bit','float','s32','u32'));dtype.setCurrentText(p['dtype']);form.addRow(tr('Type'),dtype)
 group=[j for j,n in editor.graph.nodes.items() if n['kind'].startswith('memory_') and n['p']['memory']==p['memory']]
 readers=[j for j in group if editor.graph.nodes[j]['kind']=='memory_read']
 initial=QDoubleSpinBox();initial.setRange(-2147483648,4294967295);initial.setDecimals(6);initial.setValue(editor.graph.parameters(readers[0])['initial'] if readers else 0);form.addRow(tr('Initial value'),initial)
 note=QLabel(tr('Renames and configures every node in this memory group.'));note.setWordWrap(True);form.addRow(note)
 buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons);buttons.rejected.connect(dialog.reject)
 def accept():
  from model import convert
  old={j:deepcopy(editor.graph.nodes[j]['p']) for j in group}
  try:
   for j in group:
    q=editor.graph.nodes[j]['p'];q.update(memory=name.text().strip(),dtype=dtype.currentText())
    if j in readers:q['initial']=convert(initial.value(),q['dtype'])
   editor.graph.validate()
  except ValueError as e:
   for j,value in old.items():editor.graph.nodes[j]['p']=value
   QMessageBox.warning(dialog,tr('Shared memory'),tr(str(e)));return
  editor.graph.reset();editor.rebuild(i);dialog.accept()
 buttons.accepted.connect(accept);dialog.exec()
