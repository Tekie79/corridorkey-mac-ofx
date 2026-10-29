from pathlib import Path
import os,json
os.environ['OPENCV_IO_ENABLE_OPENEXR']='1'
import cv2,numpy as np
root=Path('/Users/harvest/Documents/Ysew_Project/GIT/corridorkey-mac-ofx')
base=Path('/private/tmp/ckmac-native-qualification')
import argparse
p=argparse.ArgumentParser();p.add_argument('kind');p.add_argument('--reference');a=p.parse_args()
folder=base/('0.9.7-'+a.kind);files=sorted(folder.glob('*.exr'));assert len(files)==60,(folder,len(files))
ref=base/(a.reference or '0.9.6-'+a.kind);old=sorted(ref.glob('*.exr'));assert len(old)==60,(ref,len(old))
errors=[]
for f,g in zip(files,old):
 x=cv2.imread(str(f),-1);y=cv2.imread(str(g),-1);assert x is not None and y is not None and x.shape==y.shape==(1080,1920,4)
 assert np.isfinite(x).all() and x[...,3].min()>=0 and x[...,3].max()<=1
 errors.append(float(np.max(np.abs(x-y))))
assert max(errors)<1e-5,max(errors)
r=dict(status='Passed',artifact_sha256='f58245db7b45ce9ead793732c7e05f12d97c9c9a6e6681c744437b040ff07e86',scope='Actual installed0.9.7 native '+a.kind+'60frame float32 RGBA sequence compared against '+str(ref.name),reference_directory=str(ref),frames=60,dimensions=[1920,1080],max_rgba_error=max(errors),first=str(files[0]),last=str(files[-1]))
(root/'.build/evidence'/('native-0.9.7-'+a.kind+'60.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
