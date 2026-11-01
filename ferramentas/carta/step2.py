from geo import *
from scipy import ndimage as ndi
from collections import deque
land=np.load('land.npy')>0
lines=(stroke(G['cont'],th=1)|stroke(G['contmajor'],th=1))>0
free=land & ~lines
lab,n=ndi.label(free,structure=np.ones((3,3)))  # 8-conn ok since lines 1px 8-connected? use 4 for safety
lab,n=ndi.label(free)
print('regions',n)
sea=~land
# adjacency: dilate each line pixel neighborhood
# build pairs from 3x3 windows across line pixels
ys,xs=np.nonzero(lines)
pairs=set()
for dy in (-2,-1,0,1,2):
  for dx in (-2,-1,0,1,2):
    pass
# vectorized: for each line pixel collect labels in 5x5 window
pad=np.pad(lab,2)
win=[pad[2+ys+dy,2+xs+dx] for dy in range(-2,3) for dx in range(-2,3)]
win=np.stack(win,1)
adj={}
for row in win:
    u=set(row[row>0].tolist())
    if len(u)>1:
        u=sorted(u)
        for i in range(len(u)):
            for j in range(i+1,len(u)):
                adj.setdefault(u[i],set()).add(u[j]); adj.setdefault(u[j],set()).add(u[i])
# coast region(s): regions touching sea
seadil=ndi.binary_dilation(sea,iterations=2)
coastlabs=set(np.unique(lab[seadil & free]).tolist())-{0}
sizes=ndi.sum(np.ones_like(lab),lab,index=np.arange(n+1))
print('coast regions',len(coastlabs), sorted([(int(sizes[c]),c) for c in coastlabs])[-5:])
lvl=np.full(n+1,-1)
dq=deque()
for c in coastlabs: lvl[c]=0; dq.append(c)
while dq:
    u=dq.popleft()
    for v in adj.get(u,()):
        if lvl[v]<0: lvl[v]=lvl[u]+1; dq.append(v)
print('max level',lvl.max(), 'unreached', (lvl[1:]<0).sum())
L=lvl[lab].astype(float); L[lab==0]=np.nan
np.save('lvl.npy',lvl); np.save('lab.npy',lab)
for name,(x,y) in {'golgota':(-1800,21450),'atomo':(600,34950)}.items():
    px,py=int((x-X0)/RES),int((y-Y0)/RES)
    print(name, lvl[lab[py,px]] if lab[py,px] else 'line')
