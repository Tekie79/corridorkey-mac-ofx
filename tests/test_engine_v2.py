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
        req['source_keys']=['b'*64,key]
        assert not request('result_get',**req)[0]['ok']
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha')
        assert response['ok'] and response['temporary_owned']
        baked=json.loads(Path(response['manifest']).read_text())
        assert [baked['width'],baked['height']]==[10,6]  # Match source by default.
        source_manifest=response['manifest']
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha',resolve_host=True)
        assert not response['ok'] and 'Retry Bake' in response['error']
        assert Path(source_manifest).exists()
        e.source_geometry.sizes['node-a:'+g]=[12,8]
        response,_=request('bake',generation=g,destination=str(tmp_path/'durable'),kind='alpha',resolve_host=True)
        assert response['ok']
        original_size=json.loads(Path(response['manifest']).read_text())
        assert [original_size['width'],original_size['height']]==[12,8]
        # Clearing the owner removes outputs and completion, but never media.
        assert request('clear_shot')[0]['removed_entries']>=3
        assert not (e.cache.root/(g+'.analysis.json')).exists()
        puts=e.cache.stats['puts']
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
