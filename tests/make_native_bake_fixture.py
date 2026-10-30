"""Create tiny independent native-reader harness fixture, not a model output."""
import sys
from pathlib import Path
import numpy as np
from ckmac.cache import DiskCache
from ckmac.generations import Generations,digest
from ckmac.bake import bake
root=Path(sys.argv[1]);c=DiskCache(root/'cache');r=Generations(c)
a=np.ones((2,2,4),np.float32);a[...,:3]=[-2,.125,16];a[0,:,3]=.25;a[1,:,3]=.5
k=digest('native-capture');o=digest('native-result');c.put(k,a);c.put(o,a)
identity=dict(inputs=[k],settings=dict(input_space='linear'),provenance=dict(start=12,end=12,fps=25,origin=[-2,3]))
g=digest(identity);r.complete(g,identity,[o],'fixture')
print(bake(r,g,root/'durable','rgba')['manifest'])
r.clear('fixture',g)
