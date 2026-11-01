import re, json
s=open('../artifact-files/70eb91c9-0248-42e7-851c-5c54212fccf8/index.html').read()
svg=s[16672:1154290]
d=svg.find('</defs>'); defs=svg[:d]; body=svg[d+7:]
def paths(cls):
    return [m.group(1) for m in re.finditer(r'<path d="([^"]+)"[^>]*class="'+re.escape(cls)+r'"',body)]
G={}
G['land']=paths('land')
G['shelf1']=paths('shelf1'); G['shelf2']=paths('shelf2')
G['surf']=paths('surf'); G['sandband']=paths('sandband')
G['cont']=paths('cont'); G['contmajor']=paths('cont major')
G['lake']=paths('lake'); G['island']=paths('island')
G['river']=paths('river'); G['creek']=paths('creek')
G['peak']=re.findall(r'<path d="([^"]+)" class="peak relief"',body)
G['cLand']=re.search(r'<clipPath id="cLand"><path d="([^"]+)"',defs).group(1) if 'id="cLand"' in defs else None
G['cSea']=re.search(r'<clipPath id="cSea"><path([^>]+)>',defs).group(1)[:300] if 'id="cSea"' in defs else None
for k,v in G.items():
    if isinstance(v,list): print(k,len(v),[len(x) for x in v][:6])
    else: print(k, (v or '')[:120])
json.dump(G,open('geo_raw.json','w'))
