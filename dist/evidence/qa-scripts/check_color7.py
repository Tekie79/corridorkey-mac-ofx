import os
os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
from pathlib import Path
import cv2,numpy as np,json
p=Path('/private/tmp/ckmac-native-qualification/0.9.7-color');ev=Path('.build/evidence');art='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86'
def read(n):
 x=cv2.imread(str(p/('gamma000000.exr' if n=='gamma24' else n+'0000.exr')),-1);assert x is not None and x.shape[-1]==4 and np.isfinite(x).all();return x[...,[2,1,0,3]]
ref=read('linear');comparisons={}
for n in ['srgb','gamma24','slog']:
 x=read(n);err=float(np.max(np.abs(x-ref)));assert err<1e-4,(n,err);comparisons[n]=err
x=read('hdr');assert x[...,:3].min()<0 and x[...,:3].max()>1
r=dict(status='Passed',artifact_sha256=art,scope='Actual installed0.9.7 native Fusion Loader/OFX/Saver for sRGB, linear709, gamma2.4, synthetic SLog3 removal at unchangedRec709 primaries and float HDR/negative output.',policy_absolute=1e-4,maximum_rgba_errors=comparisons,hdr_shape=list(x.shape),hdr_min=float(x[...,:3].min()),hdr_max=float(x[...,:3].max()),slog_limit='Synthetic transfer-function fixture, not camera gamut/footage qualification')
(ev/'native-0.9.7-color-hdr-slog.json').write_text(json.dumps(r,indent=2)+'\n')
merge={}
for n,rgb in [('black',[0,0,0]),('white',[1,1,1]),('red',[1,0,0])]:
 x=read('merge-'+n);expect=ref.copy();expect[...,:3]+=np.array(rgb,dtype=np.float32)*(1-ref[...,3:4]);expect[...,3]=1;err=float(np.max(np.abs(x-expect)));assert err<1e-5,(n,err);merge[n]=err
(ev/'native-0.9.7-alpha-merge.json').write_text(json.dumps(dict(status='Passed',artifact_sha256=art,scope='Actual float32 native Fusion Merge over black, white, saturated red from installed0.9.7 premultiplied result; alpha associated once',policy_absolute=1e-5,maximum_rgba_errors=merge),indent=2)+'\n');print(json.dumps({'color':r,'merge':merge},indent=2))
