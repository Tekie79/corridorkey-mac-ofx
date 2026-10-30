"""Actual authenticated same-user v2 transport, with an explicitly fake network."""
import hashlib,json,os,socket,struct,threading,time,secrets,sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from ckmac.engine import Engine,Server
from ckmac.generations import digest

pytestmark=pytest.mark.skipif(sys.platform!="darwin",reason="Installed v2 transport uses macOS getpeereid")


@patch("ckmac.resolve_geometry.GeometryCache.schedule")
def test_v2_serialization_snapshot_validation_and_durable_clear(_geometry,tmp_path):
    e=Engine(dict(build_id='v2-test',code_root=str(tmp_path),model_root=str(tmp_path)),tmp_path/'temporary')
    calls=[]
    def infer(a,**settings):
        calls.append(1);time.sleep(.01);return a.copy()
    e.backend=SimpleNamespace(infer=infer,diagnostics=lambda:{},_model=object(),_torch=None)
    e.state='ready';path=Path('/tmp')/('ckv2-'+secrets.token_hex(6)+'.sock');server=Server(str(path),e,'unit-token');os.chmod(path,0o600)
    thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.01),daemon=True);thread.start()
    token_file=Path(str(path)+'.token');token_file.write_text('unit-token');token_file.chmod(0o600)
    base=dict(protocol=2,build_id='v2-test',token='unit-token',session_id='node-a',request_id=1,effect_generation=0,width=5,height=3,input_space=1,hint=False,quality=.75,despill=0.)
    def request(op,body=b'',**extra):
        req=dict(base,op=op,payload_bytes=len(body),**extra);encoded=json.dumps(req).encode()
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
            c.settimeout(10);c.connect(str(path));c.sendall(b'CKJ2'+struct.pack('>I',len(encoded))+encoded+body)
            def read(n):
                result=b''
                while len(result)<n:
                    chunk=c.recv(n-len(result));assert chunk;result+=chunk
                return result
            response=json.loads(read(struct.unpack('>I',read(4))[0]));return response,read(response['payload_bytes'])
    try:
        a=np.ones((3,5,4),np.float32);data=a.tobytes();key=hashlib.sha256(struct.pack('>II',5,3)+data).hexdigest()
        assert request('stage',data,key=key)[0]['new']
        before=e.cache.path(key).stat()
        assert not request('stage',data,key=key)[0]['new']
        assert e.cache.path(key).stat().st_mtime_ns==before.st_mtime_ns
        with patch('ckmac.profiles.Profile.configure'):
            with ThreadPoolExecutor(4) as pool:answers=list(pool.map(lambda _:request('frame_cached',source_key=key),range(8)))
        assert len(calls)==1 and all(x[0]['ok'] for x in answers)
        assert request('frame_lookup',source_key=key)[0]['present']
        identity=e.temporal.identity([key,key],e.settings(base),provenance=dict(start=0,end=1,fps=25,source_size=[10,6]))
        g=digest(identity);outputs=[digest([g,i]) for i in range(2)]
        for output in outputs:e.cache.put(output,a)
        e.records.complete(g,identity,outputs,'node-a')
        req=dict(generation=g,source_keys=[key,key],requested=0)
        response,payload=request('result_get',**req);assert response['ok'] and payload==data
        status=dict(keys=[key,key],requested=0,revision=0,provenance=identity['provenance'])
        assert request('analyze_status',**status)[0]['state']=='Analyzed'
        assert request('analyze_status',**dict(status,revision=1))[0]['miss_reasons']==['revision_changed']
        assert request('analyze_status',**dict(status,keys=['b'*64,key]))[0]['miss_reasons']==['inputs_changed']
        assert request('analyze_status',**dict(status,profile=dict(window=8)))[0]['miss_reasons']==['profile_changed']
        e.cache.path(outputs[0]).write_bytes(b'corrupt')
        stale=request('analyze_status',**status)[0]
        assert stale['state']=='Stale' and stale['miss_reasons']==['corrupt_or_invalid_blob']
        e.cache.put(outputs[0],a)
        req['source_keys']=['b'*64,key]
        assert not request('result_get',**req)[0]['ok']
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha')
        assert response['ok'] and response['temporary_owned']
        baked=json.loads(Path(response['manifest']).read_text())
        assert [baked['width'],baked['height']]==[10,6]  # Match source by default.
        source_manifest=response['manifest']
        from ckmac.bake import bake as original_bake
        entered=threading.Event();finish=threading.Event()
        def delayed_bake(*pos,**kw):
            entered.set();assert finish.wait(3);return original_bake(*pos,**kw)
        with patch('ckmac.bake.bake',side_effect=delayed_bake),ThreadPoolExecutor(1) as pool:
            pending=pool.submit(request,'bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha',size_mode=1)
            try:
                assert entered.wait(2)
                health=request('health')[0];assert health['state']=='baking' and health['active_jobs']==1
                assert not request('release')[0]['ok']
            finally:finish.set()
            assert pending.result()[0]['ok']
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha',resolve_host=True)
        assert not response['ok'] and 'Retry Bake' in response['error']
        assert Path(source_manifest).exists()
        e.source_geometry.sizes['node-a:'+g]=[12,8]
        e.source_geometry.verified.add('node-a:'+g)
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha',resolve_host=True)
        assert response['ok']
        original_size=json.loads(Path(response['manifest']).read_text())
        assert [original_size['width'],original_size['height']]==[12,8]
        verified_manifest=response['manifest'];assert original_size['source_size_basis']=='resolve_sdk'
        # Clearing the owner removes outputs and completion, but never media.
        assert request('clear_shot')[0]['removed_entries']>=3
        assert not (e.cache.root/(g+'.analysis.json')).exists()
        puts=e.cache.stats['puts']
        e.source_geometry.verified.clear()  # Worker restart/disconnected Source.
        response,_=request('bake',generation=g,source_manifest=verified_manifest,destination=str(tmp_path/'durable'),kind='alpha',resolve_host=True)
        assert response['ok'] and not response['temporary_owned']
        assert json.loads(Path(response['manifest']).read_text())['source_size']==[12,8]
        response,_=request('bake',generation=g,source_manifest=source_manifest,destination=str(tmp_path/'durable'),kind='alpha',size_mode=4,output_size=[20,12])
        assert response['ok'] and not response['temporary_owned']
        exported=json.loads(Path(response['manifest']).read_text())
        assert [exported['width'],exported['height']]==[20,12]
        assert e.cache.stats['puts']==puts and len(calls)==1
        assert request('health')[0]['counters']['input_stage_new']==1
        from ckmac.maintenance import running_engine_health
        support=running_engine_health(dict(build_id='v2-test'),path)
        assert support['counters']['input_stage_new']==1 and 'token' not in support
        assert 'unit-token' not in json.dumps(support)
        assert not request('health',token='invalid')[0]['ok']
    finally:
        server.shutdown();server.server_close();thread.join(2);path.unlink(missing_ok=True);token_file.unlink(missing_ok=True)
