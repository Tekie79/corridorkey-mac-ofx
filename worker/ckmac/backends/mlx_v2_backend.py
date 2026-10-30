"""Experimental community CorridorKey *v2* MLX graph adapter.

Uses raw float predictions, never MLXRenderer/PNG. Only CPU tensor interpolation
uses torch. Every learned network executes on MLX GPU; errors are terminal.
Only pinned FP32 padded profiles are accepted, with no implicit resizing.
"""
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import numpy as np
from ..backend import BackendError,prepare_frame,finish_frame

SUPPORTED=((768,1280),(1024,1536))
SOURCE_COMMIT='74065491ebd2eddea494ab34c15a6d84d7415353'


def verify(root,files):
    root=Path(root).resolve()
    for entry in files:
        path=(root/entry['path']).resolve()
        if root not in path.parents:raise BackendError('Untrusted MLX asset path')
        h=hashlib.sha256()
        with path.open('rb') as f:
            while chunk:=f.read(8*1024*1024):h.update(chunk)
        if h.hexdigest()!=entry['sha256']:raise BackendError(f'MLX asset integrity failure: {entry["path"]}')


class MLXV2Backend:
    fixture_shape=(720,1280)
    def __init__(self,source_root,model_root,lock):
        self.source_root=Path(source_root).resolve();self.model_root=Path(model_root).resolve()
        self.lock=json.loads(Path(lock).read_text()) if isinstance(lock,(str,Path)) else lock
        if self.lock['source_commit']!=SOURCE_COMMIT:raise BackendError('Unreviewed MLX source revision')
        self._torch=None;self._model=None;self.mx=None;self.graphs={};self.stats={}
        self._temporal_completed=0;self._network_calls={};self.shape=None;self.verified=set()
        self.torch_module_forward_calls=0;self.torch_hook=None
        self.identity=dict(backend='mlx_v2',precision='float32',source_commit=SOURCE_COMMIT,
                           model_manifest_sha256=self.lock['model_manifest_sha256'],adapter='raw-float-v1')

    def load(self):
        if self.mx is not None:return self
        if platform.system()!='Darwin' or platform.machine()!='arm64':raise BackendError('MLX v2 requires Apple Silicon')
        verify(self.source_root,self.lock['source_files'])
        verify(self.model_root,self.lock.get('model_license_files',[]))
        existing=sys.modules.get('corridorkey_mlx')
        if existing and Path(existing.__file__).resolve().parent!=self.source_root/'corridorkey_mlx':raise BackendError('Another MLX source package is loaded')
        sys.path.insert(0,str(self.source_root))
        self.mx=importlib.import_module('mlx.core')
        self.mx.set_default_device(self.mx.gpu)
        if self.mx.default_device()!=self.mx.gpu:raise BackendError('MLX GPU unavailable')
        self.mx.set_cache_limit(256*1024*1024)
        self._torch=importlib.import_module('torch')  # CPU interpolation only.
        def torch_forward(_module,_inputs,_output):self.torch_module_forward_calls+=1
        self.torch_hook=self._torch.nn.modules.module.register_module_forward_hook(torch_forward)
        self.graph_type=importlib.import_module('corridorkey_mlx.mlx_graph').MLXGraph
        self._model=self
        return self

    def configure_profile(self,profile):
        if profile.window not in (1,4):raise BackendError('MLX beta supports only t1/t4; select Window 1 or 4')
        if profile.low_memory:raise BackendError('MLX beta has no qualified Low GPU Memory execution profile')
        self.load()
        recommended=self.mx.device_info().get('max_recommended_working_set_size')
        if recommended:self.mx.set_memory_limit(int(recommended*(.8,.5,.6,.7,.8,.9)[profile.memory_limit]))

    def validate_canvas(self,h,w,profile):
        h,w=profile.dimensions(h,w)
        shape=(((h+127)//128)*128,((w+127)//128)*128)
        if shape not in SUPPORTED:raise BackendError(f'MLX unsupported padded canvas {shape}; native 1080p needs unavailable 1152x2048 graphs. Select MPS; no downscale was performed.')
        if profile.window not in (1,4):raise BackendError('MLX supports t1/t4 profiles only')

    def check_shape(self,shape):
        if shape not in SUPPORTED:
            raise BackendError(f'MLX v2 unsupported padded canvas {shape}. Native 1080p needs unavailable 1152x2048 graphs/exporter; use explicit MPS. No downscale was performed.')
        self.load()
        if self.shape is not None and self.shape!=shape:
            self.graphs.clear();self.mx.clear_cache()
        self.shape=shape
        if shape not in self.verified:
            prefix=f'{shape[0]}x{shape[1]}-'
            files=[e for e in self.lock['model_files'] if e['path'].startswith(prefix)]
            if not files:raise BackendError('No locked MLX profile inventory')
            verify(self.model_root,files)
            self.stats=json.loads((self.model_root/f'{shape[0]}x{shape[1]}-t1/stats.json').read_text())
            self.verified.add(shape)
        else:self.stats=json.loads((self.model_root/f'{shape[0]}x{shape[1]}-t1/stats.json').read_text())

    def graph(self,component,t=1):
        key=(component,t)
        if key not in self.graphs:
            h,w=self.shape
            self.graphs[key]=self.graph_type(self.model_root/f'{h}x{w}-t{t}'/component,False,optimizations=())
            if self.graphs[key].precision!='fp32':raise BackendError('Only FP32 is qualified for this experimental adapter')
        return self.graphs[key]

    def call(self,component,*arrays,t=1):
        mx=self.mx
        arrays=[a if isinstance(a,mx.array) else mx.array(np.asarray(a,dtype=np.float32)) for a in arrays]
        with mx.stream(mx.gpu):
            result=self.graph(component,t)(*arrays)
            mx.eval(result)
        self._network_calls[component]=self._network_calls.get(component,0)+1
        return result

    @staticmethod
    def btchw(a):return np.ascontiguousarray(a.transpose(2,0,1))[None,None]

    def resize(self,x,size,mode):
        torch=self._torch
        value=torch.from_numpy(np.ascontiguousarray(x))
        return torch.nn.functional.interpolate(value,size=size,mode=mode,**({'align_corners':False} if mode=='bilinear' else {})).numpy()

    def features(self,p,state):
        h,w=p['model'].shape[:2];self.check_shape((h,w));mx=self.mx
        display=self.btchw(p['display'])[0]
        radio=self.resize(display,(h//4,w//4),'area')
        moge=self.resize(display,(h*7//32,w*7//32),'area')
        small=self.resize(display,(h//4,w//4),'bilinear')[None]
        if state is None:state=mx.zeros((1,1+(h//64)*(w//64),384))
        recurrent,state=self.call('rvm',small,state)
        r,m=self.call('foundations',radio,moge)
        mean=np.asarray(self.stats['rvm_mean'],np.float32).reshape(1,1,-1,1,1)
        std=np.maximum(np.asarray(self.stats['rvm_std'],np.float32).reshape(1,1,-1,1,1),1e-6)
        return dict(cradio=np.array(r),moge=np.array(m),rvm=(np.array(recurrent)-mean)/std),state

    def predict(self,p,baton,space,despill):
        result=self.call('stage2',self.btchw(p['model']),baton)
        # Graph output is the raw (logits, ...), matching StageTwo.forward[0].
        logits=np.array(result[0] if isinstance(result,(tuple,list)) else result,dtype=np.float32)
        if logits.ndim!=5 or logits.shape[2]!=4:raise BackendError('Unexpected raw MLX stage2 output')
        return finish_frame(logits[0,0,1:4].transpose(1,2,0),logits[0,0,:1].transpose(1,2,0),p,input_space=space,despill_strength=despill)

    def infer(self,rgba,**settings):
        p=prepare_frame(rgba,**{k:v for k,v in settings.items() if k!='despill_strength'})
        self.check_shape(p['model'].shape[:2]);features,_=self.features(p,None)
        baton,_=self.call('stage1',self.btchw(p['model']),self.btchw(p['hint']),features['moge'][None],features['cradio'][None],features['rvm'],np.array([[p['hint_quality']]],np.float32))
        return self.predict(p,baton,settings.get('input_space','srgb'),settings.get('despill_strength',0))

    def analyze_ordered_shot(self,provider,count,settings,profile,write,cancel,progress,root):
        self.configure_profile(profile)
        if profile.window==4 and count<4:raise BackendError('MLX t4 requires at least four frames; no t2/t3 stage1 graphs are published')
        # Reuse the exact official scheduling/taper math used by the MPS path.
        # This tiny CPU scheduling dependency is supplied by the installed v2 source.
        from corridorkey.video_io import window_starts,taper_weights
        def prepared(i):
            if cancel():raise RuntimeError('Canceled MLX analysis; bake unchanged')
            s={k:v for k,v in settings.items() if k!='despill_strength'}
            if getattr(self,'first_hint',False) and i:s['hint_mode']='none'
            return prepare_frame(profile.resize(provider(i),s['input_space']),**s)
        with tempfile.TemporaryDirectory(prefix='.mlx-features-',dir=root) as tmp:
            tmp=Path(tmp);state=None
            for i in range(count):
                p=prepared(i);features,state=self.features(p,state)
                np.savez(tmp/f'{i}.npz',**features)
                progress(.3*(i+1)/count)
            del state
            stride=max(1,profile.window//2);starts=window_starts(count,profile.window,stride)
            live={};weights={};carry={}
            for window,t0 in enumerate(starts):
                indices=list(range(t0,min(t0+profile.window,count)));ps=[prepared(i) for i in indices]
                hints=np.concatenate([self.btchw(p['hint']) for p in ps],axis=1)
                confidence=np.zeros((1,len(indices)),np.float32);present=False
                for j,i in enumerate(indices):
                    if ps[j]['hint_quality']>=0:confidence[0,j]=ps[j]['hint_quality'];present=True
                    if i in carry:hints[0,j]=carry[i];confidence[0,j]=profile.internal_hint_quality;present=True
                if not present:confidence.fill(-1)
                fs=[]
                for i in indices:
                    with np.load(tmp/f'{i}.npz',allow_pickle=False) as f:fs.append({k:f[k].copy() for k in f.files})
                radio=np.concatenate([f['cradio'] for f in fs],axis=0)[None]
                moge=np.concatenate([f['moge'] for f in fs],axis=0)[None]
                rvm=np.concatenate([f['rvm'] for f in fs],axis=1)
                baton,aux=self.call('stage1',np.concatenate([self.btchw(p['model']) for p in ps],axis=1),hints,moge,radio,rvm,confidence,t=len(indices))
                baton=np.array(baton)[0];aux=np.array(aux)[0,:,:1]
                aux=np.clip(self.resize(aux,ps[0]['model'].shape[:2],'bilinear'),0,1)
                taper=taper_weights(len(indices),stride,is_first=window==0,is_last=window==len(starts)-1,device='cpu',dtype=self._torch.float32).numpy()
                boundary=starts[window+1] if window+1<len(starts) else count
                for j,i in enumerate(indices):
                    if i>=boundary:carry[i]=aux[j].copy()
                    value=baton[j]*taper[j]
                    if i in live:live[i]+=value;weights[i]+=float(taper[j])
                    else:live[i]=value.copy();weights[i]=float(taper[j])
                for i in sorted(j for j in live if j<boundary):
                    p=prepared(i);native=provider(i).shape[:2]
                    value=self.predict(p,(live.pop(i)/max(weights.pop(i),1e-6))[None,None],settings['input_space'],settings['despill_strength'])
                    write(i,profile.restore(value,native,settings['input_space']));carry.pop(i,None)
                progress(.3+.7*(window+1)/len(starts))
            self.mx.synchronize();self._temporal_completed+=1

    def diagnostics(self):
        return dict(self.identity,loaded=self._model is not None,device='mlx_gpu',automatic_mps_fallback=False,
                    cpu_preprocessing=['transfer','padding','torch CPU interpolation','scheduling'],
                    supported_padded_shapes=SUPPORTED,completed_network_calls=dict(self._network_calls),
                    completed_temporal_shots=self._temporal_completed,experimental=True,
                    torch_module_forward_calls=self.torch_module_forward_calls,neural_components=['RVM','C-RADIO','MoGe','stage1','stage2'],
                    active_bytes=int(self.mx.get_active_memory()) if self.mx else 0,
                    peak_bytes=int(self.mx.get_peak_memory()) if self.mx else 0)

    def unload(self):
        self.graphs.clear();self._model=None
        if self.torch_hook:self.torch_hook.remove();self.torch_hook=None
        if self.mx:self.mx.clear_cache()
        self.mx=None;self._torch=None;self.verified.clear();self.shape=None
