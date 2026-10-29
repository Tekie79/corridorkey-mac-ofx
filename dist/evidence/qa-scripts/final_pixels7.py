import os
os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
from pathlib import Path
import cv2,numpy as np,json,hashlib
from PIL import Image,ImageDraw
b=Path('/private/tmp/ckmac-native-qualification');e=Path('.build/evidence');sha='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86'
def read(p):
 x=cv2.imread(str(p),-1);assert x is not None and np.isfinite(x).all();return x[...,[2,1,0,3]]
def err(a,b):
 assert a.shape==b.shape;return float(np.max(np.abs(a-b)))
p=b/'0.9.7-lifecycle';enabled=read(p/'enabled0002.exr');checks={}
for n in ['reenabled','undo','reopened']: checks[n]=err(enabled,read(p/(n+'0002.exr')))
checks['disable_is_source']=err(read(p/'disabled0002.exr'),read(p/'source0002.exr'));checks['peer_survives_delete']=err(read(p/'peer-before0002.exr'),read(p/'peer-after-delete0002.exr'));assert max(checks.values())==0,checks
(e/'native-0.9.7-lifecycle.json').write_text(json.dumps(dict(status='Passed',artifact_sha256=sha,scope='Actual native add/copy, disable/enable, delete primary copied node, Undo, close/reopen saved project; all output comparisons exact. Other copied node survives independent deletion.',maximum_rgba_errors=checks),indent=2)+'\n')
rows=[];canvas=Image.new('RGB',(1440,3*300),(20,23,29));d=ImageDraw.Draw(canvas)
for i,(title,prefix) in enumerate([('Green','green'),('Blue','blue'),('Glass','glass')]):
 if prefix=='green':
  src=read(b/'0.9.7-quality/green-source0030.exr');key=read(b/'0.9.7-single/rgba0030.exr');old=read(b/'0.9.6-single/frame0030.exr')
 else:src=read(b/('0.9.7-quality/'+prefix+'-source0030.exr'));key=read(b/('0.9.7-quality/'+prefix+'-key0030.exr'));old=read(b/('0.9.6-quality/'+prefix+'-key0030.exr'))
 er=err(key,old);assert er==0,(title,er)
 a=key[...,3:4];images=[src[...,:3],np.repeat(a,3,2),key[...,:3]+np.array([.2,.2,.2])*(1-a),key[...,:3]+np.array([1.,.1,.1])*(1-a)]
 for j,(im,label) in enumerate(zip(images,['Source','Matte','Grey','Red'])):
  pic=Image.fromarray(np.uint8(np.clip(im,0,1)*255)).resize((360,260));canvas.paste(pic,(j*360,i*300+30));d.text((j*360+8,i*300+10),title+' / '+label,fill='white')
 rows.append(dict(clip=title,frame=30,shape=list(key.shape),maximum_error_vs_previously_reviewed_native=er,alpha_min=float(a.min()),alpha_max=float(a.max()),soft_alpha_fraction=float(((a>.01)&(a<.99)).mean())))
canvas.save(e/'native-0.9.7-quality-review.jpg',quality=90)
(e/'native-0.9.7-quality-review.json').write_text(json.dumps(dict(status='Recorded',artifact_sha256=sha,scope='Actual installed0.9.7 Full1080 green/blue/glass native output; all pixels exactly match prior native reviewed outputs. Fresh contact sheet requires visual review.',frames=rows),indent=2)+'\n');print(checks,rows)
