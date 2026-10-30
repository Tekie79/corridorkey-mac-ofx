"""Versioned EXR transactions from legally owned completed analysis buffers.

Writing/verifying does not activate or clean. The host validates the native
reader and sets a saved render-affecting manifest parameter before cleanup.
"""
from pathlib import Path
import hashlib
import json
import uuid
import os
import shutil
import numpy as np
from . import exr
from .generations import atomic_json
from .backend import decode_input_rgb,encode_output_rgb


def postprocess(keyed,source,settings,space):
    s=settings or {};a=keyed.astype(np.float64).copy();alpha=np.clip(a[...,3:4],0,1)
    white=float(s.get('whitePoint',1))
    if not 0<white<=1:raise ValueError('Invalid white point')
    if s.get('recoverDetails'):a[...,:3]=np.where(alpha>.95,source[...,:3],a[...,:3])
    strength=float(s.get('despill',0))
    if not 0<=strength<=1:raise ValueError('Invalid despill')
    if strength:
        screen=int(s.get('screen',0));method=int(s.get('method',0))
        if screen not in range(4) or method not in range(3):raise ValueError('Invalid despill settings')
        if screen==0:
            display=encode_output_rgb(decode_input_rgb(source[...,:3],space),'srgb').astype(np.float64)
            colour=(np.maximum(display,0)*(1-alpha)**4).sum(axis=(0,1));peak=colour.max()
            colour=colour/peak if peak>1e-8 else np.array([0,1,0])
        else:colour=np.asarray(([0,1,0] if screen==1 else [0,0,1]) if screen<3 else s['picked'],dtype=np.float64)
        if colour.shape!=(3,) or not np.isfinite(colour).all() or (colour<0).any() or (colour>1).any():raise ValueError('Invalid screen colour')
        q=colour-colour.mean();peak=q.max()
        linear=decode_input_rgb(a[...,:3],space);display=encode_output_rgb(linear,'srgb').astype(np.float64)
        if peak>1e-8:
            q/=peak;dom=int(colour.argmax());amount=np.maximum((display*q).sum(axis=2,keepdims=True),0)
            if method==1:amount=np.minimum(amount,np.maximum(display[...,dom:dom+1]-np.max(np.delete(display,dom,axis=2),axis=2,keepdims=True),0))
            if method==2:
                grey=(display*np.array([.2126,.7152,.0722])).sum(axis=2,keepdims=True)
                factor=np.clip(amount/(np.abs(display[...,dom:dom+1])+1e-8),0,1)*strength
                display+=(grey-display)*factor
            else:display-=strength*amount*q
            linear=decode_input_rgb(display,'srgb')
        a[...,:3]=encode_output_rgb(linear,'linear' if s.get('linearize') else space)
    elif s.get('linearize'):a[...,:3]=decode_input_rgb(a[...,:3],space)
    a[...,3:4]=np.clip(alpha/white,0,1)
    a=a.astype(np.float32)
    if not np.isfinite(a).all():raise ValueError('Nonfinite baked output')
    return a


def resize_pixels(values,size,encoding='linear'):
    """Map complete pixel-center extents; no crop, border or neural inference."""
    if size is None:return values
    if not isinstance(size,(list,tuple)) or len(size)!=2 or any(type(v) is not int for v in size):raise ValueError('Invalid export dimensions')
    w,h=size
    if min(w,h)<1 or max(w,h)>8192 or w*h>33554432:raise ValueError('Export dimensions exceed the supported image limit')
    if (h,w)==values.shape[:2]:return values
    import cv2
    if values.shape[2]==1:
        return np.ascontiguousarray(np.clip(cv2.resize(values[...,0],(w,h),interpolation=cv2.INTER_LINEAR),0,1)[...,None],dtype=np.float32)
    rgb=decode_input_rgb(values[...,:3],encoding)
    rgb=encode_output_rgb(cv2.resize(rgb,(w,h),interpolation=cv2.INTER_LINEAR),encoding)
    alpha=np.clip(cv2.resize(values[...,3],(w,h),interpolation=cv2.INTER_LINEAR),0,1)[...,None]
    return np.ascontiguousarray(np.concatenate((rgb,alpha),axis=2),dtype=np.float32)


def write_sequence(provider,count,metadata,destination,kind,precision,size=None):
    if kind not in ('alpha','rgba'):raise ValueError('Choose alpha or rgba bake')
    if precision not in ('half','float'):raise ValueError('Choose half or float EXR')
    if not destination.is_absolute():raise ValueError('Choose an absolute durable media folder')
    start,end=metadata['start'],metadata['end']
    if type(start) is not int or type(end) is not int or end-start+1!=count or not 1<=count<=240:raise ValueError('Bake frame mapping mismatch')
    if not isinstance(metadata.get('fps'),(int,float)) or not np.isfinite(metadata['fps']) or metadata['fps']<=0:raise ValueError('Bake requires verified fps')
    first=provider(0);source_hw=first.shape[:2]
    first=resize_pixels(first,size,metadata['rgb_encoding']);h,w=first.shape[:2]
    destination.mkdir(parents=True,exist_ok=True)
    expected_bytes=h*w*(1 if kind=='alpha' else 4)*(2 if precision=='half' else 4)*count
    if shutil.disk_usage(destination).free<expected_bytes+5*2**30:raise OSError('Insufficient durable bake storage; keep 5 GiB free')
    bake_id=uuid.uuid4().hex;staging=destination/('.staging-'+bake_id);staging.mkdir(mode=0o700);final=destination/('bake-'+bake_id)
    channels=('A',) if kind=='alpha' else ('R','G','B','A');files=[]
    for i in range(count):
        values=first if i==0 else resize_pixels(provider(i),size,metadata['rgb_encoding'])
        if values.shape!=(h,w,len(channels)) or not np.isfinite(values).all():raise ValueError('Bake canvas or finite-sample contract changed')
        name=f'frame.{start+i:08d}.exr';path=staging/name
        exr.write(path,values,channels,precision,pixel_aspect=metadata.get('pixel_aspect',1.))
        read,names,types,origin=exr.read(path)
        expected=values.astype(np.float16).astype(np.float32) if precision=='half' else values
        expected=expected[...,[channels.index(c) for c in names]]
        if names!=sorted(channels) or not np.array_equal(read,expected):raise ValueError('EXR readback verification failed')
        alpha=read[...,names.index('A')]
        if alpha.min()<0 or alpha.max()>1:raise ValueError('EXR alpha outside [0,1]')
        files.append(dict(name=name,frame=start+i,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if {p.name for p in staging.glob('*.exr')}!={entry['name'] for entry in files}:raise ValueError('Unexpected bake frame set')
    manifest=dict(metadata,version=1,state='Verified',bake_id=bake_id,kind=kind,precision=precision,width=w,height=h,files=files)
    manifest.setdefault('analysis_size',[source_hw[1],source_hw[0]])
    manifest.setdefault('source_size',[source_hw[1],source_hw[0]])
    manifest['resampling']=dict(method='bilinear_pixel_centers_full_frame_no_crop',from_size=[source_hw[1],source_hw[0]],to_size=[w,h],applied=(h,w)!=source_hw)
    original=metadata.get('origin',[0,0]);manifest['origin']=[round(original[0]*w/source_hw[1]),round(original[1]*h/source_hw[0])]
    atomic_json(staging/'manifest.json',manifest)
    os.rename(staging,final)
    fd=os.open(destination,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(state='Verified',manifest=str(final/'manifest.json'),generation=metadata['generation'],bake_id=bake_id)


def bake(records,generation,destination,kind,precision='half',post=None,size=None,source_size=None):
    if destination.resolve()==records.cache.temporary_root.resolve() or records.cache.temporary_root.resolve() in destination.resolve().parents:raise ValueError('Bake media must be outside the temporary cache')
    record=records.record(generation)
    if record is None:raise RuntimeError('Complete analysis is required before baking')
    identity=record['identity'];provenance=identity.get('provenance') or {};keys=identity['inputs']+record['outputs'];records.cache.pin(keys)
    try:
        if records.status(generation)['state']!='Analyzed':raise RuntimeError('Complete analysis is required before baking')
        def provider(i):
            image=records.result(generation,i)
            source=records.cache.get(identity['inputs'][i]) if post and (post.get('recoverDetails') or post.get('despill')) else image
            if source is None:raise RuntimeError('Source captures needed for output controls were evicted; recapture before baking')
            image=postprocess(image,source,post,identity['settings']['input_space'])
            return image[...,3:4] if kind=='alpha' else image
        metadata=dict(generation=generation,start=provenance.get('start'),end=provenance.get('end'),fps=provenance.get('fps'),origin=provenance.get('origin',[0,0]),
                      pixel_aspect=provenance.get('pixel_aspect',1),input_space=identity['settings']['input_space'],
                      rgb_encoding='linear' if (post or {}).get('linearize') else identity['settings']['input_space'],alpha='straight',post=post or {},identity=identity)
        if source_size:metadata['source_size']=source_size
        elif provenance.get('source_size'):metadata['source_size']=provenance['source_size']
        return write_sequence(provider,len(record['outputs']),metadata,destination,kind,precision,size)
    finally:records.cache.unpin(keys)


def bake_from_manifest(path,destination,kind,precision='half',size=None,source_size=None,generation=None):
    """Re-export verified durable media after cache cleanup, with no model access."""
    path=Path(path);original=json.loads(path.read_text())
    if original.get('version')!=1 or original.get('state')!='Verified':raise ValueError('Use a verified bake')
    if generation is not None and original['generation']!=generation:raise ValueError('Bake generation mismatch')
    if kind=='rgba' and original['kind']!='rgba':raise ValueError('This alpha bake contains no recovered foreground; revert to an RGBA bake first')
    files=original['files']
    if not isinstance(files,list) or not 1<=len(files)<=240:raise ValueError('Invalid bake frame set')
    def provider(i):
        entry=files[i];name=entry['name']
        if Path(name).name!=name or entry['frame']!=original['start']+i:raise ValueError('Invalid bake frame mapping')
        p=path.parent/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Source bake checksum mismatch; relink verified media')
        a,names,types,origin=exr.read(p)
        expected=['A'] if original['kind']=='alpha' else ['A','B','G','R']
        if names!=expected or types!=[1 if original['precision']=='half' else 2]*len(names) or a.shape[:2]!=(original['height'],original['width']):raise ValueError('Source bake profile mismatch')
        if kind=='alpha':return a[...,names.index('A'):names.index('A')+1]
        return a[...,[names.index(c) for c in 'RGBA']]
    metadata={k:v for k,v in original.items() if k not in ('files','bake_id','state','width','height','precision','kind','resampling')}
    metadata['source_bake_id']=original['bake_id']
    if source_size:metadata['source_size']=source_size
    return write_sequence(provider,len(files),metadata,destination,kind,precision,size)
