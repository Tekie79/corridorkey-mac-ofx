"""Verify HF publisher blob identities, then lock complete native build inputs."""
from pathlib import Path
import hashlib
import base64
import json
import zipfile
from common import ROOT,WORK,OUT,PYTHON,MODEL_SET,sha,write_json

SOURCES = {
 'weights':('nikopueringer/CorridorKey2.0','cf44a8db3f024bb49fd59daa408848ccf05f7477'),
 'vfms/cradio/C-RADIOv4-SO400M':('nvidia/C-RADIOv4-SO400M','c0457f5dc26ca145f954cd4fc5bb6114e5705ad8'),
 'vfms/moge':('Ruicheng/moge-2-vitb-normal','ca5f0e07ff01d3e5a364c1d954ed12ee1814b368')}


def main():
    archive=WORK/'downloads'/PYTHON['name']
    if sha(archive)!=PYTHON['sha256'] or archive.stat().st_size!=PYTHON['size']:
        raise RuntimeError('Standalone Python archive differs from publisher digest')
    assets=[]
    for sub,(repo,revision) in SOURCES.items():
        root=WORK/'models'/sub
        for p in sorted(root.rglob('*')):
            rel=p.relative_to(root)
            if not p.is_file() or '.cache' in rel.parts:
                continue
            metadata=root/'.cache/huggingface/download'/ (str(rel)+'.metadata')
            if not metadata.exists():
                locked=json.loads((ROOT/'scripts/release/model-lock.json').read_text())
                expected=next(x for x in locked['files'] if x['path']==p.relative_to(WORK/'models').as_posix())
                if p.stat().st_size!=expected['size'] or sha(p)!=expected['sha256']:raise RuntimeError(f'Asset differs from locked publisher file: {p}')
                assets.append(expected)
                continue
            lines=metadata.read_text().splitlines()
            if lines[0]!=revision:
                raise RuntimeError(f'Wrong publisher revision: {p}')
            etag=lines[1]
            actual=sha(p)
            if len(etag)==64:
                if etag!=actual:
                    raise RuntimeError(f'Publisher SHA256 mismatch: {p}')
            elif len(etag)==40:
                h=hashlib.sha1(f'blob {p.stat().st_size}\0'.encode())
                with p.open('rb') as f:
                    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
                if h.hexdigest()!=etag:
                    raise RuntimeError(f'Publisher Git blob mismatch: {p}')
            else:
                raise RuntimeError(f'Unknown publisher digest: {p}')
            assets.append(dict(path=p.relative_to(WORK/'models').as_posix(),size=p.stat().st_size,sha256=actual,
                source=f'https://huggingface.co/{repo}/resolve/{revision}/{rel.as_posix()}',revision=revision,
                publisher_blob=etag,role='executable_snapshot_code' if p.suffix=='.py' else sub,
                notice='licenses/CorridorKey-THIRD_PARTY_NOTICES.md'))
    rvm=WORK/'models/vfms/rvm/pretrain_rvm_small16_256_204031069.npz'
    if base64.b64encode(hashlib.md5(rvm.read_bytes()).digest()).decode()!='ZJb6kj8+tasiJbVeplXu7Q==':
        raise RuntimeError('RVM publisher MD5 mismatch')
    assets.append(dict(path=rvm.relative_to(WORK/'models').as_posix(),size=rvm.stat().st_size,sha256=sha(rvm),
        source='https://storage.googleapis.com/representations4d/checkpoints/'+rvm.name,role='recurrent_foundation',
        publisher_md5_base64='ZJb6kj8+tasiJbVeplXu7Q==',notice='licenses/CorridorKey-THIRD_PARTY_NOTICES.md'))
    write_json(OUT/'model-manifest.json',dict(model_set_id=MODEL_SET,files=assets))
    wheels=[]
    requirements=[]
    for p in sorted((WORK/'wheelhouse').glob('*.whl')):
        with zipfile.ZipFile(p) as z:
            metadata=z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))).decode()
        fields=dict(line.split(': ',1) for line in metadata.splitlines() if line.startswith(('Name: ','Version: ')))
        wheels.append(dict(filename=p.name,name=fields['Name'],version=fields['Version'],size=p.stat().st_size,sha256=sha(p)))
        requirements.append(f"{fields['Name']}=={fields['Version']} --hash=sha256:{sha(p)}")
    (OUT/'requirements.lock').write_text('\n'.join(requirements)+'\n')
    write_json(OUT/'runtime-lock.json',dict(python=PYTHON,wheels=wheels,deployment_target='14.0',
        upstream_commit='485f5e9ab759ead6138cc990776184b59d6ea971',
        openfx_commit='c3f1c2dcf4f51762b794c4fc21181b4a501be1bf',
        utils3d_commit='83bfa5bda008803f6521ce9547f94023b8afeddd',adapter_math_version=3,cache_format=3,protocol=2))
    print(f'Verified {len(assets)} publisher assets and locked {len(wheels)} wheels',flush=True)

if __name__=='__main__':main()
