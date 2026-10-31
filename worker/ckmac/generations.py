"""Durable immutable analysis manifests and shared temporary-cache ownership.

Records survive worker restarts. Reads never update SQLite or blob timestamps.
The engine GPU lock serializes jobs/cleanup; the DB transaction protects ownership.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading


def atomic_json(path, value):
    fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,sort_keys=True,allow_nan=False)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        d=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(d)
        finally:os.close(d)
    finally:Path(tmp).unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


class Generations:
    def __init__(self,cache):
        self.cache=cache
        self.lock=threading.RLock()
        self.db=sqlite3.connect(cache.root/'ownership.sqlite3',check_same_thread=False)
        with self.db:
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ownership(owner TEXT, key TEXT, kind TEXT,
                PRIMARY KEY(owner,key));
            CREATE TABLE IF NOT EXISTS generations(id TEXT PRIMARY KEY, record TEXT);
            CREATE TABLE IF NOT EXISTS leases(owner TEXT, generation TEXT,
                PRIMARY KEY(owner,generation));
            ''')

    def remember(self,owner,keys,kind='capture'):
        if not isinstance(owner,str) or not 1<=len(owner)<=128:return
        keys=list(keys)
        for key in keys:self.cache.path(key)
        with self.lock:
            new=[k for k in keys if not self.db.execute('SELECT 1 FROM ownership WHERE owner=? AND key=?',(owner,k)).fetchone()]
            if new:
                with self.db:self.db.executemany('INSERT INTO ownership VALUES(?,?,?)',[(owner,k,kind) for k in new])

    def record(self,generation):
        self.cache.path(generation)
        with self.lock:
            row=self.db.execute('SELECT record FROM generations WHERE id=?',(generation,)).fetchone()
        return json.loads(row[0]) if row else None

    def complete(self,generation,identity,outputs,owner=None,children=None):
        record=dict(version=1,generation=generation,identity=identity,outputs=outputs,state='Analyzed')
        if children:record['children']=children
        path=self.cache.root/(generation+'.analysis.json')
        if not path.exists():atomic_json(path,record)
        elif json.loads(path.read_text())!=record:raise ValueError('Conflicting immutable generation')
        with self.lock:
            existing=self.record(generation)
            if existing is not None and existing!=record:raise ValueError('Conflicting generation record')
            if existing is None:
                with self.db:self.db.execute('INSERT INTO generations VALUES(?,?)',(generation,json.dumps(record,sort_keys=True)))
        self.lease(owner,generation)
        return record

    def lease(self,owner,generation):
        if not owner:return
        record=self.record(generation)
        if record is None:raise RuntimeError('Unknown analysis generation')
        self.remember(owner,record['identity']['inputs'],'capture')
        self.remember(owner,record['outputs'],'result')
        with self.lock:
            if not self.db.execute('SELECT 1 FROM leases WHERE owner=? AND generation=?',(owner,generation)).fetchone():
                with self.db:self.db.execute('INSERT INTO leases VALUES(?,?)',(owner,generation))

    def status(self,generation):
        record=self.record(generation)
        if record is None:return dict(state='Unanalyzed',generation=generation)
        missing=[i for i,k in enumerate(record['outputs']) if not self.cache.valid(k)]
        return dict(state='Stale' if missing else 'Analyzed',generation=generation,missing=missing,record=record)

    def result(self,generation,index,shape=None):
        record=self.record(generation)
        if record is None:raise RuntimeError('Unknown analysis generation; use Analyze/Resume')
        if type(index) is not int or not 0<=index<len(record['outputs']):raise ValueError('Invalid frame index')
        image=self.cache.get(record['outputs'][index])
        if image is None:raise RuntimeError('Stale analysis: requested output missing/corrupt. Use Analyze/Resume; playback never reanalyzes a completed generation.')
        if shape is not None and image.shape!=shape:raise ValueError('Analysis canvas mismatch')
        return image

    def owned_generations(self,owner):
        with self.lock:
            return [r[0] for r in self.db.execute('SELECT generation FROM leases WHERE owner=? ORDER BY rowid DESC',(owner,))]

    def clear(self,owner,generation=None):
        # Hold metadata and blob locks through deletion. Shared captures/results
        # and generations leased by other nodes are preserved after restart too.
        with self.lock,self.cache.transaction(),self.db:
            selected=self.owned_generations(owner) if generation is None else [generation]
            if generation is not None and generation not in self.owned_generations(owner):raise ValueError('Generation is not owned by this node')
            for g in list(selected):
                rec=self.record(g)
                for child in (rec or {}).get('children',[]):
                    if child in self.owned_generations(owner) and child not in selected:selected.append(child)
            kinds=dict(self.db.execute('SELECT key,kind FROM ownership WHERE owner=?',(owner,)))
            keys=set(kinds);retained=set()
            if generation is not None:
                selected_keys=set()
                for g in selected:
                    rec=self.record(g);selected_keys.update(rec['identity']['inputs']+rec['outputs'])
                keys &= selected_keys
                # Same owner's other generations retain their captures.
                for g in self.owned_generations(owner):
                    if g not in selected:
                        r=self.record(g);keep=keys&set(r['identity']['inputs']+r['outputs']);retained.update(keep);keys-=keep
            shared={k for k in keys if self.db.execute('SELECT 1 FROM ownership WHERE key=? AND owner<>?',(k,owner)).fetchone()}
            removable=keys-shared
            if any(k in self.cache.pins for k in removable):raise RuntimeError('Active analysis lease prevents cleanup')
            report=dict(removed_entries=0,removed_captures=0,removed_results=0,reclaimed_bytes=0,
                        already_missing_entries=0,shared_entries_preserved=0,shared_missing_entries=0,
                        retained_entries_for_other_generations=len(retained),completion_records_removed=0,
                        completion_records_preserved=0,cleanup_complete=True,failures=[])
            for key in shared:
                report['shared_entries_preserved' if self.cache.path(key).exists() else 'shared_missing_entries']+=1
            failed=set();released=set(shared)
            for key in sorted(removable):
                path=self.cache.path(key)
                try:
                    size=path.lstat().st_size if path.exists() else 0
                    count=self.cache.remove([key])
                except OSError as exc:
                    failed.add(key);report['failures'].append(dict(key=key,error=str(exc)));continue
                released.add(key);report['removed_entries']+=count
                report['removed_results' if kinds[key]=='result' else 'removed_captures']+=count
                report['already_missing_entries']+=int(count==0);report['reclaimed_bytes']+=size if count else 0
            self.db.executemany('DELETE FROM ownership WHERE owner=? AND key=?',[(owner,k) for k in released])
            for g in selected:
                record=self.record(g)
                if failed.intersection(record['identity']['inputs']+record['outputs']):
                    report['completion_records_preserved']+=1;continue
                shared_generation=self.db.execute('SELECT 1 FROM leases WHERE generation=? AND owner<>?',(g,owner)).fetchone()
                if not shared_generation:
                    try:(self.cache.root/(g+'.analysis.json')).unlink(missing_ok=True)
                    except OSError as exc:
                        report['failures'].append(dict(generation=g,error=str(exc)));report['completion_records_preserved']+=1;continue
                    self.db.execute('DELETE FROM generations WHERE id=?',(g,));report['completion_records_removed']+=1
                else:report['completion_records_preserved']+=1
                self.db.execute('DELETE FROM leases WHERE owner=? AND generation=?',(owner,g))
            from .temporal_scratch import clear_scratch
            scratch=clear_scratch(self.cache.root,owner,generation)
            report.update(scratch);report['failures'].extend(scratch['scratch_failures'])
            report['cleanup_complete']=not report['failures'] and not scratch['active_scratch_jobs_preserved'] and not scratch['unmarked_scratch_directories_preserved']
            return report
