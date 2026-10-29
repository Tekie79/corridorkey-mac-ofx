"""Float32 upstream 4/2 temporal reference: continuous RVM, tapered baton, full-resolution refinement.

Owned host frames are supplied by content identity. No movie is reopened here.
The reference intentionally retains float32 intermediate features, rather than
the CUDA runtime's disk float16 quantization. Recompute from the shot reset
boundary after an incomplete transaction; no partial checkpoint is trusted.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from dataclasses import asdict,replace

import numpy as np
from .backend import prepare_frame,finish_frame
from .profiles import Profile


class TemporalProcessor:
    def __init__(self,backend,cache,build):
        self.backend,self.cache,self.build=backend,cache,build
        self.last_outputs=set()

    def run(self,keys,settings,requested,*,revision=0,first_hint=False,provenance=None,cancel=lambda:False,progress=lambda x:None,profile=None,expected_shape=None):
        profile=profile or Profile()
        if first_hint and settings.get('hint_mode')!='none' and profile.window<2:
            raise ValueError('Reference hints need a Window of 2 or higher for propagation')
        if not 2<=len(keys)<=240 or not 0<=requested<len(keys):
            raise ValueError('Temporal range must contain 2–240 integer frames; select a shorter range or bake retiming')
        if not 0<=profile.reference_index<len(keys):raise ValueError('Reference Frame must lie inside the selected shot')
        if profile.reference_index:
            # Independent recurrent passes start at the explicit reference,
            # moving outwards. Both halves finish before any result is returned.
            # This is an explicitly named bidirectional variant, not last-viewed
            # recurrent state. The full source set remains in each provenance.
            ref=profile.reference_index
            origin=dict(parent=provenance,all_inputs=keys,variant='reference-outward-two-pass-v1')
            runs=[(keys[ref::-1],ref-requested,'backward'),(keys[ref:],requested-ref,'forward')]
            answer=None
            for part,index,direction in runs:
                if len(part)==1:
                    frame=self.cache.get(part[0])
                    if frame is None:raise RuntimeError('Reference input was evicted; analyze again')
                    if expected_shape is not None and frame.shape!=expected_shape:raise ValueError('Reference input extent does not match the requested canvas')
                    value=self.backend.infer(profile.resize(frame,settings['input_space']),**settings)
                    value=profile.restore(value,frame.shape[:2],settings['input_space'])
                else:
                    value=self.run(part,settings,min(len(part)-1,max(0,index)),revision=revision,first_hint=first_hint,
                                   provenance=dict(origin,direction=direction),cancel=cancel,progress=progress,
                                   profile=replace(profile,reference_index=0),expected_shape=expected_shape)
                if 0<=index<len(part):answer=value
            return answer
        stride=max(1,profile.window//2)
        identity=dict(algorithm='upstream-float32-RVM-continuous-Hann-configurable-v2',build=self.build,
                      inputs=keys,settings=settings,first_hint=first_hint,revision=revision,provenance=provenance,profile=asdict(profile))
        master=hashlib.sha256(json.dumps(identity,sort_keys=True,allow_nan=False).encode()).hexdigest()
        outputs=[hashlib.sha256(f'{master}:{i}'.encode()).hexdigest() for i in range(len(keys))]
        self.last_outputs.update(outputs)
        complete=self.cache.root/(master+'.analysis.json')
        if complete.exists():
            try:
                record=json.loads(complete.read_text())
                if record['identity']==identity and record['outputs']==outputs:
                    result=self.cache.get(outputs[requested])
                    # A completion marker is valid only while the complete set
                    # remains present and checksummed, not merely this one frame.
                    if result is not None and (expected_shape is None or result.shape==expected_shape) and all(self.cache.valid(k) for k in outputs):return result
            except (OSError,ValueError,KeyError):pass
        torch=self.backend._torch;model=self.backend._model
        if model is None:self.backend.load();torch=self.backend._torch;model=self.backend._model
        profile.configure(self.backend)
        from corridorkey.video_io import window_starts,taper_weights
        from corridorkey.rope import refresh_all_augs
        def check():
            if cancel():raise RuntimeError('Temporal job canceled; incomplete generation was not activated')
        def prepared(i):
            check();frame=self.cache.get(keys[i])
            if frame is None:raise RuntimeError('Temporal input cache was evicted/corrupted. Analyze the shot again.')
            if expected_shape is not None and frame.shape!=expected_shape:raise ValueError('Temporal input extent does not match the requested canvas')
            s=dict(settings);s.pop('despill_strength',None)
            if first_hint and i:s['hint_mode']='none'
            return prepare_frame(profile.resize(frame,s['input_space']),**s)
        def cpu(x):return torch.from_numpy(np.ascontiguousarray(x.transpose(2,0,1)))[None,None]
        def gpu(x):return cpu(x).to('mps',dtype=torch.float32)
        # Preflight storage before features/output; preserve the entire input set.
        sample=self.cache.get(keys[0])
        if sample is None:raise RuntimeError('Temporal input was evicted or corrupted. Shorten the range or analyze again.')
        if expected_shape is not None and sample.shape!=expected_shape:raise ValueError('Temporal input extent does not match the requested canvas')
        nbytes=sample.nbytes
        if 2*nbytes*len(keys)+2**30>self.cache.budget:
            raise OSError('The complete native temporal range exceeds the cache budget. Select a shorter range.')
        self.cache.pin(keys)
        try:
            self.cache.reserve(nbytes*len(keys)+2**30)
            with tempfile.TemporaryDirectory(prefix='.temporal-',dir=self.cache.root) as tmp:
                tmp=Path(tmp);state=None;geometry=None
                with torch.inference_mode():
                    # Frozen context is computed once, in source order. RVM uses
                    # upstream's bilinear quarter proxy and carries through every frame.
                    for i in range(len(keys)):
                        p=prepared(i);h,w=p['model'].shape[:2]
                        if geometry is None:geometry=(h,w,p['native_hw'])
                        if geometry!=(h,w,p['native_hw']):raise ValueError('Temporal geometry changed inside the range')
                        proxy=cpu(p['display']).flatten(0,1)
                        radio=torch.nn.functional.interpolate(proxy,size=(h//4,w//4),mode='area').to('mps')
                        moge=torch.nn.functional.interpolate(proxy,size=(h*7//32,w*7//32),mode='area').to('mps')
                        rvm=torch.nn.functional.interpolate(proxy,size=(h//4,w//4),mode='bilinear',align_corners=False)[None].to('mps')
                        f=model.foundations(rgb_cradio=radio,rgb_moge=moge,rgb_rvm=rvm,rvm_state=state)
                        state=f.get('rvm_state')
                        tensors={k:v.float().cpu().numpy() for k,v in f.items() if k in ('cradio','moge','rvm')}
                        np.savez(tmp/f'{i}.npz',**tensors)
                        del f,tensors,proxy,radio,moge,rvm,p
                        progress(.3*(i+1)/len(keys))
                    del state
                    starts=window_starts(len(keys),profile.window,stride);live={};weights={};carry={}
                    def flush(limit):
                        for i in sorted(j for j in live if j<limit):
                            check();p=prepared(i)
                            baton=torch.from_numpy(live.pop(i)/max(weights.pop(i),1e-6))[None,None].to('mps')
                            rgb=gpu(p['model'])
                            logits=model.stage2(rgb,baton)
                            if isinstance(logits,tuple):logits=logits[0]
                            fg=logits[0,0,1:4].permute(1,2,0).float().cpu().numpy()
                            alpha=logits[0,0,0:1].permute(1,2,0).float().cpu().numpy()
                            result=finish_frame(fg,alpha,p,input_space=settings['input_space'],despill_strength=settings['despill_strength'])
                            result=profile.restore(result,sample.shape[:2],settings['input_space'])
                            self.cache.put(outputs[i],result)
                            del baton,rgb,logits,fg,alpha,result,p
                    for window,t0 in enumerate(starts):
                        check();t1=min(t0+profile.window,len(keys));count=t1-t0
                        ps=[prepared(i) for i in range(t0,t1)]
                        rgb=torch.cat([gpu(p['model']) for p in ps],dim=1)
                        hints=torch.cat([gpu(p['hint']) for p in ps],dim=1)
                        qualities=torch.zeros((1,count),device='mps',dtype=torch.float32)
                        present=False
                        for j,i in enumerate(range(t0,t1)):
                            if ps[j]['hint_quality']>=0:qualities[0,j]=ps[j]['hint_quality'];present=True
                            if i in carry:hints[0,j]=carry[i].to('mps');qualities[0,j]=profile.internal_hint_quality;present=True
                        if not present:qualities.fill_(-1)
                        fs=[]
                        for i in range(t0,t1):
                            with np.load(tmp/f'{i}.npz',allow_pickle=False) as f:
                                fs.append({k:torch.from_numpy(f[k].copy()) for k in f.files})
                        features={k:torch.cat([f[k] for f in fs],dim=0)[None].to('mps') for k in fs[0]}
                        refresh_all_augs(model,device=rgb.device)
                        stage=model.stage1(rgb,hints,features['moge'],cradio_feat=features['cradio'],rvm_feat=features['rvm'],t_stride=1.,hint_quality=qualities)
                        baton=stage['baton'][0].float()
                        aux=torch.nn.functional.interpolate(stage['aux'][0,:,0:1].float(),size=(h,w),mode='bilinear',align_corners=False).clamp(0,1).cpu()
                        for j,i in enumerate(range(t0,t1)):carry[i]=aux[j].clone()
                        next_start=starts[window+1] if window+1<len(starts) else len(keys)
                        for i in list(carry):
                            if i<next_start:del carry[i]
                        taper=taper_weights(count,stride,is_first=window==0,is_last=window==len(starts)-1,device='cpu',dtype=torch.float32).numpy()
                        weighted=baton.cpu().numpy()*taper[:,None,None,None]
                        for j,i in enumerate(range(t0,t1)):
                            if i in live:live[i]+=weighted[j];weights[i]+=float(taper[j])
                            else:live[i]=weighted[j].copy();weights[i]=float(taper[j])
                        del stage,baton,aux,weighted,features,fs,rgb,hints,qualities,ps
                        flush(next_start)
                        progress(.3+.7*(window+1)/len(starts))
                    flush(len(keys));torch.mps.synchronize();check()
            # Only a complete, immutable set can be activated. No pickle/state RPC.
            fd,temp=tempfile.mkstemp(prefix='.analysis-',dir=self.cache.root)
            try:
                with os.fdopen(fd,'w') as f:
                    json.dump(dict(identity=identity,outputs=outputs),f,allow_nan=False);f.flush();os.fsync(f.fileno())
                os.replace(temp,complete)
            finally:Path(temp).unlink(missing_ok=True)
            result=self.cache.get(outputs[requested])
            if result is None:raise RuntimeError('Temporal output was not retained')
            self.backend._temporal_completed += 1
            return result
        finally:self.cache.unpin(keys)
