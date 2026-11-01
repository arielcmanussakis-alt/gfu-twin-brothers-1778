"""Exporta a carta dos jogadores (SVG autônomo, SVG para o atlas, CSS escopado) e a imagem da cena."""
import re, json, os, sys, subprocess
from PIL import Image
SC='/tmp/claude-0/-home-claude/85204d6e-106e-5c81-b78a-2c97864117b2/scratchpad'
REPO='/home/claude/gfu-twin-brothers-1778'
inner=open('chart_inner.svg').read()
inner=re.sub(r'<g id="lyr-gm">.*?</g>','',inner,flags=re.S)
inner=re.sub(r'<g class="ref gm-only".*?</g>','',inner,flags=re.S)
for w in ['gm-note','gm-only','Cálice','Mercy','Jonah','cripta']:
    assert w not in inner, w
a=open('assemble.py').read()
css=a[a.index('/* ---- carta'):a.index('</style>')]
css=re.sub(r'#lyr-gm,\.ref\.gm-only\{display:none\}\nbody\.mestre[^\n]*\n','',css)
css=re.sub(r'\.ref\.gm-only[^\n]*\n','',css)
VARS='--ink:#2f2216;--sepia:#6e5537;--red:#9a2b1e;--sea-ink:#3f5f60;--f-title:"IM Fell Great Primer","IM Fell English","GFS Baskerville","Baskerville",Georgia,serif;--f-cap:"IM Fell Double Pica","IM Fell English","GFS Baskerville","Baskerville",Georgia,serif;--f-body:"IM Fell English","GFS Baskerville","Baskerville",Georgia,serif;--f-sc:"IM Fell English SC","IM Fell English","GFS Baskerville","Baskerville",Georgia,serif'
meta=json.load(open('chart_meta.json')); vbl=meta['vb']; vb=' '.join(str(int(v)) for v in vbl)
fonts='@import url("https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&amp;family=IM+Fell+English+SC&amp;family=IM+Fell+Double+Pica:ital@0;1&amp;family=IM+Fell+Great+Primer:ital@0;1&amp;display=swap");\n'
# 1) standalone SVG for the repo
svg=f'<svg id="map" xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{int(vbl[2]/25)}" height="{int(vbl[3]/25)}"><title>Carta da Ilha dos Dois Irmãos, 1778</title><style>{fonts}:root,svg{{{VARS}}}\n{css}</style>{inner}</svg>'
open(REPO+'/carta/carta-1778.svg','w').write(svg)
# 2) atlas SVG body: ids prefixed, no <style>
P='g78-'
ids=set(re.findall(r' id="([^"]+)"',inner))
body=inner
for i in sorted(ids,key=len,reverse=True):
    body=body.replace(f' id="{i}"',f' id="{P}{i}"').replace(f'url(#{i})',f'url(#{P}{i})').replace(f'href="#{i}"',f'href="#{P}{i}"')
os.makedirs(REPO+'/modulo/assets',exist_ok=True)
open(REPO+'/modulo/assets/carta-atlas.svg','w').write(f'<svg class="g78-map" xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" preserveAspectRatio="xMidYMid meet">{body}</svg>')
# 3) scoped CSS for the atlas
def scope(css):
    out=[]
    for rule in re.findall(r'([^{}]+)\{([^{}]*)\}',css):
        sel,decl=rule; sel=sel.strip()
        if sel.startswith('/*'): sel=re.sub(r'/\*.*?\*/','',sel,flags=re.S).strip()
        if sel.startswith('@'): continue
        sels=[]
        for s in sel.split(','):
            s=s.strip().replace('#map','').strip()
            for i in sorted(ids,key=len,reverse=True):
                s=re.sub(r'#'+re.escape(i)+r'(?![\w-])','#'+P+i,s)
            sels.append(('.gfu-atlas .g78-map '+s).strip())
        out.append(','.join(sels)+'{'+decl+'}')
    return '\n'.join(out)
open(SC+'/carta/atlas-chart.css','w').write(scope(css))
# 4) raster for the scene (no reference letters: the Notes carry them)
rast=re.sub(r'<g id="lyr-refs" class="lyr">.*$', '', inner, flags=re.S)
assert rast.count('<g')>10
W,H=7000,int(round(7000*vbl[3]/vbl[2]))
page=f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:#efe2bf}}svg{{display:block}}</style><svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{W}" height="{H}"><style>:root,svg{{{VARS}}}\n{css}</style>{rast}</svg>'
open(SC+'/raster/carta.html','w').write(page)
subprocess.run(['python3',SC+'/raster/shot.py',SC+'/raster/carta.html',SC+'/raster/carta.png'],check=True)
im=Image.open(SC+'/raster/carta.png').convert('RGB'); assert im.size==(7000,6788) or True
im=im.crop((0,0,W,H))
im.save(REPO+'/modulo/assets/carta-1778.webp','WEBP',quality=82,method=6)
t=im.copy(); t.thumbnail((400,400)); t.save(REPO+'/modulo/assets/carta-1778-thumb.webp','WEBP',quality=80)
json.dump({'vb':vbl,'W':W,'H':H},open(SC+'/carta/scene_meta.json','w'))
print('ok',W,H,os.path.getsize(REPO+'/modulo/assets/carta-1778.webp')/1e6)
