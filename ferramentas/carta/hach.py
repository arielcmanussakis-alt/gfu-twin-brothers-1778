from geo import *
from scipy import ndimage as ndi
from skimage import measure
import sys
H=np.load('H.npy').astype(np.float64)
land=(np.load('land.npy')>0)|(np.load('isl.npy')>0)
gy,gx=np.gradient(H)  # per px; slope = |g|/RES
DELTA=float(sys.argv[1]) if len(sys.argv)>1 else 45
SP=float(sys.argv[2]) if len(sys.argv)>2 else 5.0
seeds=[]
for v in np.arange(DELTA, H.max(), DELTA):
    for c in measure.find_contours(H, v):
        if len(c)<3: continue
        seg=np.diff(c,axis=0); L=np.r_[0,np.cumsum(np.hypot(seg[:,0],seg[:,1]))]
        if L[-1]<SP*1.5: continue
        off=np.random.default_rng(int(v)).uniform(0,SP)
        t=np.arange(off,L[-1],SP)
        r=np.interp(t,L,c[:,0]); q=np.interp(t,L,c[:,1])
        seeds.append(np.c_[r,q,np.full(len(t),v)])
S=np.vstack(seeds); print('seeds',len(S))
# jitter along
rng=np.random.default_rng(7)
P=S[:,:2].copy(); V=S[:,2]
def samp(A,P): return ndi.map_coordinates(A,[P[:,0],P[:,1]],order=1,mode='nearest')
start=P.copy(); alive=np.ones(len(P),bool); length=np.zeros(len(P))
pts=[P.copy()]
MAXS=36
for i in range(MAXS):
    g0=samp(gy,P); g1=samp(gx,P); n=np.hypot(g0,g1)+1e-9
    step=np.where(alive,1.0,0.0)
    P=P-np.c_[g0/n,g1/n]*step[:,None]
    length+=step
    h=samp(H,P)
    alive&=(h>V-DELTA)&(samp(land.astype(float),P)>0.5)
    if i in (11,23): pts.append(P.copy())
pts.append(P.copy())
slope=np.minimum(DELTA/(np.maximum(length,1)*RES), 2.0)
# local gradient for truncated
gl=np.hypot(samp(gy,start),samp(gx,start))/RES
slope=np.where(length>=MAXS, gl, slope)
keep=slope>0.075
print('kept',keep.sum(),'slope pct',np.percentile(slope[keep],[10,50,90,99]))
np.savez('hach.npz',start=start[keep],end=P[keep],mid1=pts[1][keep],mid2=pts[2][keep],length=length[keep],slope=slope[keep])
