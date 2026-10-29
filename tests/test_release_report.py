"""Evidence bookkeeping only; these fixtures never qualify a real artifact."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def test_report_rejects_stale_or_changed_evidence_and_preserves_spec_classes(tmp_path,monkeypatch):
    repo=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo/'scripts/release'))
    spec=importlib.util.spec_from_file_location('qualification_report',repo/'scripts/release/report.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    work=tmp_path/'.build';out=tmp_path/'dist';docs=tmp_path/'docs'
    work.mkdir();out.mkdir();docs.mkdir()
    (docs/'PERSONAL_INSTALLER_SPEC.md').write_bytes((repo/'docs/PERSONAL_INSTALLER_SPEC.md').read_bytes())
    (docs/'PERFORMANCE.md').write_text('Unit fixture')
    for name in ('USER_GUIDE.md','KNOWN_LIMITATIONS.md'):(tmp_path/name).write_text('Unit fixture')
    artifact=dict(filename='fixture.pkg',size=1,sha256='f'*64,qualified=False)
    (out/'artifact.json').write_text(json.dumps(artifact))
    evidence=work/'fixture.json';evidence.write_text('{}')
    record=dict(path='.build/fixture.json',sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())
    events={
        'QA-01':dict(status='Passed',artifact_sha256='e'*64,evidence=[record]),
        'QA-02':dict(status='Passed',artifact_sha256='f'*64,evidence=[]),
        'QA-03':dict(status='Passed',artifact_sha256='f'*64,evidence=[record],id='QA-99',**{'class':'C'}),
        'QA-04':dict(status='Passed',artifact_sha256='f'*64,evidence=[dict(record,sha256='0'*64)]),
    }
    (work/'qualification-events.json').write_text(json.dumps(events))
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'WORK',work);monkeypatch.setattr(module,'OUT',out)
    module.main()
    q=json.loads((out/'qualification.json').read_text());rows={r['id']:r for r in q['acceptance']}
    assert len(rows)==45
    assert rows['QA-01']['status']==rows['QA-02']['status']==rows['QA-04']['status']=='Not run'
    assert rows['QA-03']['status']=='Passed' and rows['QA-03']['class']=='U'
    assert q['release_status']=='UNQUALIFIED PERSONAL BETA' and not q['qualified_combinations']
