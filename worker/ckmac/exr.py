"""Small bounded uncompressed scanline EXR codec: HALF/FLOAT, A or RGBA.

No PNG, clipping, premultiplication, external executable or image library.
Other EXR encodings are deliberately rejected by the native reader.
"""
import struct
from pathlib import Path
import numpy as np


def write(path,pixels,channels=('R','G','B','A'),precision='half',origin=(0,0),pixel_aspect=1.):
    a=np.asarray(pixels,dtype=np.float32)
    if a.ndim!=3 or a.shape[2]!=len(channels) or not np.isfinite(a).all():raise ValueError('Invalid EXR pixels')
    if precision not in ('half','float'):raise ValueError('EXR precision must be half or float')
    if precision=='half' and np.abs(a).max()>65504:raise ValueError('HALF would overflow RGB; select FLOAT explicitly')
    if not np.isfinite(pixel_aspect) or pixel_aspect<=0:raise ValueError('Invalid EXR pixel aspect')
    h,w=a.shape[:2];x,y=origin
    typ=1 if precision=='half' else 2;dtype='<f2' if typ==1 else '<f4';size=2 if typ==1 else 4
    def attr(name,kind,data):return name.encode()+b'\0'+kind.encode()+b'\0'+struct.pack('<I',len(data))+data
    ch=b''.join(c.encode()+b'\0'+struct.pack('<iB3xii',typ,0,1,1) for c in sorted(channels))+b'\0'
    header=struct.pack('<II',20000630,2)+attr('channels','chlist',ch)+attr('compression','compression',b'\0')
    box=struct.pack('<iiii',x,y,x+w-1,y+h-1)
    header+=attr('dataWindow','box2i',box)+attr('displayWindow','box2i',box)+attr('lineOrder','lineOrder',b'\0')
    header+=attr('pixelAspectRatio','float',struct.pack('<f',pixel_aspect))+attr('screenWindowCenter','v2f',b'\0'*8)+attr('screenWindowWidth','float',struct.pack('<f',1))+b'\0'
    row=w*len(channels)*size
    with Path(path).open('xb') as f:
        f.write(header)
        start=len(header)+h*8
        f.write(struct.pack('<'+'Q'*h,*(start+i*(row+8) for i in range(h))))
        for i in range(h):
            f.write(struct.pack('<iI',y+i,row))
            for c in sorted(channels):f.write(a[i,:,channels.index(c)].astype(dtype).tobytes())
        f.flush()
        import os
        os.fsync(f.fileno())


def read(path):
    with Path(path).open('rb') as f:
        def exact(n):
            b=f.read(n)
            if len(b)!=n:raise ValueError('Truncated EXR')
            return b
        def z():
            b=bytearray()
            while True:
                c=exact(1)
                if c==b'\0':return b.decode('ascii')
                b+=c
                if len(b)>255:raise ValueError('EXR name too long')
        if struct.unpack('<II',exact(8))!=(20000630,2):raise ValueError('Unsupported EXR version')
        attrs={}
        while True:
            name=z()
            if not name:break
            kind=z();size=struct.unpack('<I',exact(4))[0]
            if size>65536:raise ValueError('Unbounded EXR attribute')
            attrs[name]=(kind,exact(size))
        if attrs['compression'][1]!=b'\0':raise ValueError('Expected uncompressed EXR')
        x,y,x1,y1=struct.unpack('<iiii',attrs['dataWindow'][1]);w=x1-x+1;h=y1-y+1
        if min(h,w)<1 or max(h,w)>8192 or h*w>33554432:raise ValueError('Invalid EXR canvas')
        raw=attrs['channels'][1];channels=[];types=[]
        while raw!=b'\0':
            name,raw=raw.split(b'\0',1);typ,linear,xs,ys=struct.unpack('<iB3xii',raw[:16]);raw=raw[16:]
            if typ not in (1,2) or (xs,ys)!=(1,1):raise ValueError('Unsupported EXR channel')
            channels.append(name.decode());types.append(typ)
        offsets=struct.unpack('<'+'Q'*h,exact(8*h));a=np.empty((h,w,len(channels)),np.float32)
        row=sum(w*(2 if t==1 else 4) for t in types)
        for i,offset in enumerate(offsets):
            f.seek(offset);line,n=struct.unpack('<iI',exact(8))
            if line!=y+i or n!=row:raise ValueError('EXR scanline mismatch')
            for j,t in enumerate(types):a[i,:,j]=np.frombuffer(exact(w*(2 if t==1 else 4)),dtype='<f2' if t==1 else '<f4')
        if not np.isfinite(a).all():raise ValueError('Nonfinite EXR')
        return a,channels,types,(x,y)
