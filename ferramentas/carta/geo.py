import re, json, numpy as np, cv2
X0,Y0,W,H=-5700.0,-1500.0,42450.0,40500.0
RES=10.0
NX,NY=int(W/RES),int(H/RES)
def parse(d):
    toks=re.findall(r'[MLZmlzHhVv]|-?\d*\.?\d+(?:e-?\d+)?',d)
    polys=[];cur=[];i=0;cmd=None;x=y=0
    while i<len(toks):
        t=toks[i]
        if t in 'MLZmlzHhVv':
            cmd=t;i+=1
            if t in 'Zz':
                if cur: polys.append((cur,True)); cur=[]
            continue
        if cmd in 'ML':
            x=float(toks[i]);y=float(toks[i+1]);i+=2
            if cmd=='M':
                if cur: polys.append((cur,False))
                cur=[(x,y)];cmd='L'
            else: cur.append((x,y))
        elif cmd=='h': x+=float(t);cur.append((x,y));i+=1
        elif cmd=='v': y+=float(t);cur.append((x,y));i+=1
        else: i+=1
    if cur: polys.append((cur,False))
    return polys
def topx(pts):
    a=np.array(pts,float); return np.round(np.c_[(a[:,0]-X0)/RES,(a[:,1]-Y0)/RES]*16).astype(np.int32)
def fill(dlist,img=None,val=255):
    if img is None: img=np.zeros((NY,NX),np.uint8)
    for d in dlist:
        for pts,cl in parse(d):
            if len(pts)>2: cv2.fillPoly(img,[topx(pts)],val,lineType=cv2.LINE_8,shift=4)
    return img
def stroke(dlist,img=None,val=255,th=1):
    if img is None: img=np.zeros((NY,NX),np.uint8)
    for d in dlist:
        for pts,cl in parse(d):
            if len(pts)>1: cv2.polylines(img,[topx(pts)],cl,val,th,lineType=cv2.LINE_8,shift=4)
    return img
G=json.load(open('geo_raw.json'))
