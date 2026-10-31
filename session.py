"""Remember the last successfully opened/saved project, with safe startup fallback."""
import json
import os
from pathlib import Path
import tempfile

from model import Graph, demo


class ProjectSession:
    def __init__(self, directory=None):
        root=directory or os.environ.get('PLC_STATE_DIR') or Path(__file__).parent/'.state'
        self.path=Path(root)/'last-project.json'

    def last_project(self):
        if not self.path.exists():return None
        data=json.loads(self.path.read_text())
        if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('last_project'),str):
            raise ValueError('Invalid last-project settings')
        return Path(data['last_project'])

    def remember(self, path):
        data=dict(version=1,last_project=str(Path(path).resolve()))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',dir=self.path.parent,prefix='.last-project-',delete=False) as file:
                temporary=Path(file.name);json.dump(data,file,indent=2)
            temporary.replace(self.path)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)

    def startup(self, project=None, no_restore=False):
        if no_restore:return Graph(),None,'Started empty (--no-restore).'
        try:path=Path(project).resolve() if project is not None else self.last_project()
        except Exception as error:
            return Graph(),None,f'Could not read last-project settings: {error}. Started empty.'
        if path is None:return demo(),None,''
        try:graph=Graph.load(path)
        except Exception as error:
            return Graph(),None,f'Could not load {path}: {error}. Started empty; use Open to select another project.'
        notice='Loaded '+str(path)
        if project is not None:
            try:self.remember(path)
            except OSError as error:notice+=f' • could not remember project: {error}'
        return graph,path,notice
