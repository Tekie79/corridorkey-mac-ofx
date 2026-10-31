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
from dataclasses import asdict,replace

import numpy as np
from .backend import prepare_frame,finish_frame
from .profiles import Profile
from .generations import Generations,digest
from .temporal_scratch import scratch


class TemporalProcessor:
    def __init__(self,backend,cache,build):
        self.backend,self.cache,self.build=backend,cache,build
        self.last_outputs=set()
        self.records=Generations(cache) if cache is not None else None
        self.last_generation=None
        self.stats=dict(analysis_starts=0,analysis_completions=0,result_cache_hits=0,result_cache_misses=0)

    def identity(self,keys,settings,revision=0,first_hint=False,provenance=None,profile=None):
        return dict(algorithm='upstream-float32-RVM-continuous-Hann-configurable-v3',build=self.build,
                    backend=getattr(self.backend,'identity',{'backend':'mps','precision':'float32'}),
                    inputs=keys,settings=settings,first_hint=first_hint,revision=revision,
                    provenance=provenance,profile=asdict(profile or Profile()))

    def run(self,keys,settings,requested,*,revision=0,first_hint=False,provenance=None,cancel=lambda:False,progress=lambda x:None,profile=None,expected_shape=None,resume=False,owner=None):
        profile=profile or Profile()
        if first_hint and settings.get('hint_mode')!='none' and profile.window<2:
            raise ValueError('Reference hints need a Window of 2 or higher for propagation')
        if not 2<=len(keys)<=240 or not 0<=requested<len(keys):
            raise ValueError('Temporal range must contain 2–240 integer frames; select a shorter range or bake retiming')
        if not 0<=profile.reference_index<len(keys):raise ValueError('Reference Frame must lie inside the selected shot')
        identity=self.identity(keys,settings,revision,first_hint,provenance,profile)
        master=digest(identity)
        outputs=[hashlib.sha256(f'{master}:{i}'.encode()).hexdigest() for i in range(len(keys))]
        self.last_outputs=set(outputs)
        self.last_generation=master
        existing=self.records.record(master)
        if existing is not None:
            self.records.lease(owner,master)
            try:
                # A missing *other* result cannot prevent this immutable result
                # from being read. No run-wide availability scan on playback.
                result=self.records.result(master,requested,expected_shape)
                if not resume or self.records.status(master)['state']=='Analyzed':
                    self.stats['result_cache_hits']+=1
                    return result
            except RuntimeError:
                if not resume:
                    self.stats['result_cache_misses']+=1
                    raise
            # Repair is explicit. Old completion cannot describe a partial run.
        self.stats['analysis_starts']+=1
        self.records.remember(owner,keys)
        self.records.remember(owner,outputs,'result')
        if profile.reference_index:
            ref=profile.reference_index;children=[]
            origin=dict(parent=provenance,all_inputs=keys,variant='reference-outward-two-pass-v1')
            for indices,direction in [(list(range(ref,-1,-1)),'backward'),(list(range(ref,len(keys))),'forward')]:
                part=[keys[i] for i in indices]
                if len(part)==1:
                    frame=self.cache.get(part[0])
                    if frame is None:raise RuntimeError('Reference input was evicted; analyze again')
                    value=self.backend.infer(profile.resize(frame,settings['input_space']),**settings)
                    self.cache.put(outputs[indices[0]],profile.restore(value,frame.shape[:2],settings['input_space']))
                else:
                    self.run(part,settings,0,revision=revision,first_hint=first_hint,
                             provenance=dict(origin,direction=direction),cancel=cancel,progress=progress,
                             profile=replace(profile,reference_index=0),expected_shape=expected_shape,resume=resume,owner=owner)
                    child=self.records.record(self.last_generation);children.append(self.last_generation)
                    for j,i in enumerate(indices):
                        # Reference frame belongs to the forward pass.
                        if direction=='backward' and i==ref:continue
                        self.cache.put(outputs[i],self.records.result(child['generation'],j,expected_shape))
            self.last_outputs=set(outputs);self.last_generation=master
            self.records.complete(master,identity,outputs,owner,children)
            self.stats['analysis_completions']+=1
            return self.records.result(master,requested,expected_shape)
        if hasattr(self.backend,'analyze_ordered_shot'):
            self.backend.first_hint=first_hint
            self.cache.pin(keys+outputs)
            try:
                def frame(i):
                    value=self.cache.get(keys[i])
                    if value is None:raise RuntimeError('Captured input missing; Analyze/Resume must recapture')
                    if expected_shape is not None and value.shape!=expected_shape:raise ValueError('Captured input extent mismatch')
                    return value
                with scratch(self.cache.root,owner,master,self.build) as tmp:
                    self.backend.analyze_ordered_shot(frame,len(keys),settings,profile,
                        lambda i,value:None if self.cache.valid(outputs[i]) else self.cache.put(outputs[i],value),cancel,progress,tmp)
                self.records.complete(master,identity,outputs,owner)
                self.stats['analysis_completions']+=1
                return self.records.result(master,requested,expected_shape)
            finally:self.cache.unpin(keys+outputs)
        stride=max(1,profile.window//2)
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
        self.cache.pin(keys+outputs)
        try:
            self.cache.reserve(nbytes*len(keys)+2**30)
            with scratch(self.cache.root,owner,master,self.build) as tmp:
                state=None;geometry=None
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
                            if not self.cache.valid(outputs[i]):self.cache.put(outputs[i],result)
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
            self.records.complete(master,identity,outputs,owner)
            self.stats['analysis_completions']+=1
            result=self.cache.get(outputs[requested])
            if result is None:raise RuntimeError('Temporal output was not retained')
            self.backend._temporal_completed += 1
            return result
        finally:self.cache.unpin(keys+outputs)
