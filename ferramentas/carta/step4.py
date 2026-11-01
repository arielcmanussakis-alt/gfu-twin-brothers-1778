from geo import *
from scipy import ndimage as ndi
land=np.load('land.npy')>0; isl=np.load('isl.npy')>0
LAND=land|isl
Ha=np.load('H_atlas.npy')*85.0
yy,xx=np.mgrid[0:NY,0:NX].astype(np.float32)
WX=X0+xx*RES; WY=Y0+yy*RES
def g(x,y,a,sx,sy=None,rot=0):
    sy=sy or sx; c,s=np.cos(np.radians(rot)),np.sin(np.radians(rot))
    dx=WX-x; dy=WY-y; u=c*dx+s*dy; v=-s*dx+c*dy
    return a*np.exp(-(u*u/(2*sx*sx)+v*v/(2*sy*sy)))
H=Ha.copy()
# Younger Brother: raise to ~1198
H+=g(600,34950,560,1700,2100,30)
# synthetic hills east/north
for (x,y,a,sx,sy,r) in [(12600,8200,150,2600,3600,20),(14300,12800,110,2000,2600,-10),(11600,4300,95,1800,None,0),(16200,6200,85,1600,2200,-30),
                         (17200,21150,38,450,350,0),(21200,17600,28,700,500,-40),(28400,23600,95,2600,1800,-15),(25200,25400,55,1800,None,0),
                         (21500,26800,45,2200,None,0),(9500,30500,40,2500,1500,0),(28575,12400,22,250,None,0),(19500,29500,35,2000,None,0)]:
    H+=g(x,y,a,sx,sy,r)
rng=np.random.default_rng(1778)
noise=ndi.gaussian_filter(rng.standard_normal((NY,NX)).astype(np.float32),40)
noise=noise/np.abs(noise).max()*14
H+=noise
dc=ndi.distance_transform_edt(LAND)*RES
# Cliffs: Atlantic coast of north landmass (x>14500, 3000<y<17500) and Tide Cave coast north of N. Harbour
cliffmask=((WX>14000)&(WY>-1500)&(WY<17800)).astype(np.float32)
cliffmask=ndi.gaussian_filter(cliffmask,30)
H+=cliffmask*52*(1-np.exp(-dc/70))*np.exp(-dc/900)
H*=np.minimum(1,dc/25)  # shore at 0
H[~LAND]=0
H=ndi.gaussian_filter(H,1.2); H[~LAND]=0
np.save('H.npy',H.astype(np.float32))
print('max',H.max())
for name,(x,y) in {'elder':(-1800,21450),'younger':(600,34950),'kemb':(17700,21825),'nh':(13771,2769)}.items():
    px,py=int((x-X0)/RES),int((y-Y0)/RES); print(name,round(float(H[py,px])), bool(LAND[py,px]))
v=np.clip(H/1250*255,0,255).astype(np.uint8); v=cv2.applyColorMap(v,cv2.COLORMAP_TURBO); v[~LAND]=(90,60,40)
cv2.imwrite('H.png',cv2.resize(v,(NX//3,NY//3),interpolation=cv2.INTER_AREA))
