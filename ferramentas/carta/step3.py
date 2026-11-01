from geo import *
from scipy import ndimage as ndi
land=np.load('land.npy')>0
lab=np.load('lab.npy'); lvl=np.load('lvl.npy')
lines=(lab==0)&land
Lr=np.where(lab>0,lvl[lab],-1).astype(np.int32)
# fill line pixels with max of neighbor levels? use nearest region
idx=ndi.distance_transform_edt(Lr<0,return_distances=False,return_indices=True)
Lf=Lr[idx[0],idx[1]]
Lf[~land]=0
maxl=Lf.max()
H=np.zeros(Lf.shape,np.float32)
for k in range(0,maxl+1):
    m=Lf==k
    if not m.any(): continue
    dl=ndi.distance_transform_edt(~(Lf<k)) if k>0 else ndi.distance_transform_edt(land)  # distance to lower (sea for k=0)
    hi=Lf>k
    if hi.any():
        dh=ndi.distance_transform_edt(~hi)
        frac=dl/(dl+dh+1e-6)
    else:
        frac=np.minimum(1.0, dl/40.0)
    H[m]=(k-0.5+frac[m]) if k>0 else frac[m]*0.5
H[~land]=0
Hs=ndi.gaussian_filter(H,2.0)
np.save('H_atlas.npy',Hs)
print('line px',lines.sum(),'H max',Hs.max())
v=(Hs/Hs.max()*255).astype(np.uint8)
v=cv2.applyColorMap(v,cv2.COLORMAP_TURBO); v[~land]=(90,60,40)
cv2.imwrite('H_atlas.png',cv2.resize(v,(NX//3,NY//3),interpolation=cv2.INTER_AREA))
