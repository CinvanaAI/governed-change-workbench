import json
import tempfile
from pathlib import Path
from governed_change_workbench import ChangeWorkbench, RunnerFailedError

root=Path(tempfile.mkdtemp(prefix='change-retry-demo-'))
workbench=ChangeWorkbench(root)
session=workbench.freeze_implementation(workbench.create('Make one synthetic change.').session_id)
def failed(phase,prompt):
    return {'run_outcome':'failed','raw_output':'No files changed.'}
try:
    workbench.dispatch_implementation(session.session_id,failed,authorize=True)
except RunnerFailedError:
    pass
after_failure=workbench.require(session.session_id)
assert after_failure.status=='implementation_ready'
def complete(phase,prompt):
    return {'run_outcome':'complete','raw_output':'Synthetic runner completion; not a real implementation claim.'}
retried=workbench.dispatch_implementation(session.session_id,complete,authorize=True)
assert retried.status=='implementation_complete'
failures=list((root/session.session_id/'artifacts').glob('implementation_failed_*.json'))
assert len(failures)==1
print(json.dumps({'after_failure':after_failure.status,'after_retry':retried.status,'preserved_failures':len(failures),'evidence_root':str(root)},indent=2))
