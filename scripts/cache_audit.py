#!/usr/bin/env python3
"""Read-only snapshots distinguish new cache keys, timestamp touches and evictions.

Capture before and after identical navigation in Resolve. Host playback cache
is a separate location; this tool never clears either domain or logs pixels.
"""
import argparse,json,hashlib,socket,struct
from pathlib import Path


def snapshot(root):
    frames=root/'frames' if (root/'frames').is_dir() else root
    entries={}
    for pattern in ('*.ckf','*.analysis.json'):
        for p in frames.glob(pattern):
            s=p.stat();entries[p.name]=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,inode=s.st_ino)
    return dict(domain='worker temporary captures/results; excludes Resolve playback cache and durable EXRs',root=str(frames),entries=entries,count=len(entries),bytes=sum(e['bytes'] for e in entries.values()))


def compare(before,after):
    a,b=before['entries'],after['entries'];shared=a.keys()&b.keys()
    return dict(new=sorted(b.keys()-a.keys()),removed=sorted(a.keys()-b.keys()),
                timestamp_or_inode_changes=sorted(k for k in shared if a[k]!=b[k]),
                byte_delta=after['bytes']-before['bytes'],
                interpretation='New names indicate new content/generations; removed names indicate eviction/cleanup. Timestamp-only changes do not establish neural work. Compare worker analysis/network counters too.')


def health(path,build):
    # Token stays local and is never returned in the report.
    request=dict(op='health',protocol=2,build_id=build,token=Path(str(path)+'.token').read_text(),payload_bytes=0,session_id='cache-audit',request_id=1,effect_generation=0)
    payload=json.dumps(request).encode()
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
        c.settimeout(5);c.connect(str(path));c.sendall(b'CKJ2'+struct.pack('>I',len(payload))+payload)
        def read(n):
            out=b''
            while len(out)<n:
                chunk=c.recv(n-len(out))
                if not chunk:raise RuntimeError('Truncated health response')
                out+=chunk
            return out
        return json.loads(read(struct.unpack('>I',read(4))[0]))


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='op',required=True)
    p=sub.add_parser('snapshot');p.add_argument('--cache-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--socket',type=Path);p.add_argument('--build')
    p=sub.add_parser('compare');p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    args=ap.parse_args()
    if args.op=='compare':print(json.dumps(compare(json.loads(args.before.read_text()),json.loads(args.after.read_text())),indent=2));return
    data=snapshot(args.cache_root)
    if args.socket:
        if not args.build:ap.error('--socket requires --build')
        data['worker_health']=health(args.socket,args.build)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k!='entries'},indent=2))
if __name__=='__main__':main()
