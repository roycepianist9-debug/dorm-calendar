"""Bed calendar run 57 (Oct 26 08:21 slot): Booking NEW 6756773216 Femme Girls (16840329) check-in Nov 4; name/checkout/payout not in mail; counted Nov 4 only. Base = run56 NEW_index 4461855a (Garice, unpublished)."""
import re, json, math, datetime, zoneinfo, hashlib
SRC='/workspace/multi-ota/versions/index_run56_4461855a_base.html'; OUT='/workspace/multi-ota/NEW_index.html'
s=open(SRC,encoding='utf-8').read()
assert hashlib.sha256(s.encode()).hexdigest().startswith("4461855a")
m=re.search(r'(<script type="application/json" id="chart-data">)(.*?)(</script>)',s,re.S)
raw=m.group(2); d=json.loads(raw); assert json.dumps(d,ensure_ascii=False,separators=(',',':'))==raw
now=datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Paris'))
before=[json.dumps(r,ensure_ascii=False) for r in d]; ch=[]
G='Booking guest (name TBC, res 6756773216)'
for i,r in enumerate(d):
    if r['d']=='2026-11-04':
        g=[g for g in r['w'][1] if g[0]=='R'][0]; assert G not in g[1]; g[1].append(G)
        r['f'][0]+=1; r['wbm']=max(0,(r['wbm'] or 0)-1); ch.append(i)
assert len(ch)==1
after=[json.dumps(r,ensure_ascii=False) for r in d]
assert sum(a!=b for a,b in zip(before,after))==1
s=s[:m.start(2)]+json.dumps(d,ensure_ascii=False,separators=(',',':'))+s[m.end(2):]
def jr(x): return math.floor(x+0.5)
def bars(s,label,key,idx):
    svgm=re.search(r'<svg[^>]*aria-label="%s[^"]*".*?</svg>'%label,s,re.S); svg=svgm.group(0); note=[]
    for i in idx:
        u=d[i][key][0]; cap=d[i][key][3]; x=26+20*i; cx=32+20*i
        hf=100*min(u,cap)/cap; h=jr(hf); top=106-h
        svg,k=re.subn(r'M%d,[\d.]+h12v[\d.]+h-12z'%x,'M%d,%dh12v%dh-12z'%(x,top,h),svg)
        if h>=14: lab='<text x="%d" y="%d" text-anchor="middle" fill="#f8fafc" font-size="9" font-weight="700" pointer-events="none">%d</text>'%(cx,jr(106-hf/2+3.5),u)
        else: lab='<text x="%d" y="%d" text-anchor="middle" fill="#f8fafc" font-size="9" font-weight="700" stroke="#0c0e12" stroke-width="2" paint-order="stroke" pointer-events="none">%d</text>'%(cx,top-2,u)
        svg,k2=re.subn(r'<text x="%d" y="\d+"[^>]*pointer-events="none">\d+</text>'%cx,lab,svg)
        assert k<=1 and k2<=1; note.append((d[i]['d'],k,k2))
    print(label,'svg',note)
    return s[:svgm.start()]+svg+s[svgm.end():]
s=bars(s,'Female','f',ch)
ANCH='<tr><td>Booking guest (name TBC)</td><td>3 Nov</td>'
assert s.count(ANCH)==1
s=s.replace(ANCH,'<tr><td>Booking guest (name TBC)</td><td>4 Nov</td><td>TBC</td><td>new booking; res 6756773216; Booking Femme Girls (Old one 16840329); name, check-out and payout not in mail; counted 4 Nov only for now</td></tr>'+ANCH)
utc=now.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
s,k=re.subn(r'(<meta name="calendar-version" content=")[0-9TZ:-]+(">)',r'\g<1>%s\g<2>'%utc,s); assert k==1
sh=now.astimezone(zoneinfo.ZoneInfo('Asia/Shanghai'))
stamp='%s Paris, %s Shanghai (%s)'%(now.strftime('%H:%M'),sh.strftime('%H:%M'),sh.strftime('%Y-%m-%d'))
s=re.sub(r'As of [^<]*?\(\d{4}-\d\d-\d\d\)\.','As of %s.'%stamp,s,count=1)
s=re.sub(r'Last refreshed [^<]*?\(\d{4}-\d\d-\d\d\)\.','Last refreshed %s.'%stamp,s,count=1)
for bad in ['<FORBIDDEN_1>','<FORBIDDEN_2>','<FORBIDDEN_3>','<FORBIDDEN_4>']: assert bad not in s
for must in ["Keti","IMFURAYACU","Ngango","Muhammad","Breakdown","chart-data"]: assert must in s, must
assert s.startswith('<!DOCTYPE html>')
open(OUT,'w',encoding='utf-8').write(s)
print('calendar-version',utc,'sha256',hashlib.sha256(s.encode()).hexdigest(),'bytes',len(s.encode()))
print([(d[i]['d'],d[i]['m'],d[i]['am']) for i in ch])
today=now.date().isoformat()
print('men>=23 from today:',[(r['d'],r['m'][0],r['am']) for r in d if r['d']>=today and r['m'][0]>=23])
print('women>=8 from today:',[(r['d'],r['f'][0],r['wam'],r['wbm']) for r in d if r['d']>=today and r['f'][0]>=8])
