"""Explicit saved spatial/context profiles; never an automatic quality fallback."""
from dataclasses import dataclass
import math
import numpy as np
from .backend import decode_input_rgb,encode_output_rgb

@dataclass(frozen=True)
class Profile:
    resolution:int=0
    window:int=4
    memory_limit:int=0
    low_memory:bool=False
    internal_hint_quality:float=.95
    reference_index:int=0

    @classmethod
    def from_request(cls,request):
        p=cls(**request.get('profile',{}))
        for name,lo,hi in [('resolution',0,3),('window',1,48),('memory_limit',0,5),('reference_index',0,239)]:
            value=getattr(p,name)
            if type(value) is not int or not lo<=value<=hi:raise ValueError(f'Invalid {name}')
        if type(p.low_memory) is not bool:raise ValueError('Invalid low memory setting')
        if not math.isfinite(p.internal_hint_quality) or not 0<=p.internal_hint_quality<=1:raise ValueError('Invalid internal hint strength')
        return p

    def dimensions(self,h,w):
        scale=(1.,2/3,.5,.25)[self.resolution]
        height,width=max(1,round(h*scale)),max(1,round(w*scale))
        if width>2048 or height>1152:
            raise ValueError('CK-PROFILE: this beta has not qualified MPS above 2048×1152 internally. Choose an explicit lower Internal Resolution; a native 4K request is never silently reduced.')
        return height,width

    def resize(self,rgba,space):
        import cv2
        h,w=self.dimensions(*rgba.shape[:2])
        if (h,w)==rgba.shape[:2]:return rgba
        # Resample light, not encoded display values. Hints retain alignment.
        rgb=encode_output_rgb(cv2.resize(decode_input_rgb(rgba[...,:3],space),(w,h),interpolation=cv2.INTER_AREA),space)
        alpha=cv2.resize(rgba[...,3],(w,h),interpolation=cv2.INTER_AREA)[...,None]
        return np.ascontiguousarray(np.concatenate((rgb,alpha),axis=2),dtype=np.float32)

    def restore(self,rgba,hw,space):
        import cv2
        if rgba.shape[:2]==hw:return rgba
        h,w=hw
        rgb=encode_output_rgb(cv2.resize(decode_input_rgb(rgba[...,:3],space),(w,h),interpolation=cv2.INTER_LINEAR),space)
        alpha=np.clip(cv2.resize(rgba[...,3],(w,h),interpolation=cv2.INTER_LINEAR),0,1)[...,None]
        return np.ascontiguousarray(np.concatenate((rgb,alpha),axis=2),dtype=np.float32)

    def configure(self,backend):
        backend.load()
        torch=backend._torch
        # This is a fraction of Metal's recommended working set, not physical
        # RAM or an assertion that this memory is currently free.
        fraction=(.8,.5,.6,.7,.8,.9)[self.memory_limit]
        torch.mps.set_per_process_memory_fraction(fraction)
        from corridorkey.runtime import InferenceConfig,configure_low_vram_inference
        cfg=InferenceConfig()
        if self.low_memory:
            cfg.low_vram_mlp_chunk_tokens=16384
            cfg.low_vram_swin_window_batch=4
            cfg.low_vram_full_attn_query_chunk_tokens=512
        configure_low_vram_inference(backend._model,cfg)
