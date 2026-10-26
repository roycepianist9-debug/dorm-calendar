"""Run 59: Booking 6756773216 details from extranet (Ta Sangi) + women Airbnb closed Nov 4-6 (wam 1->0)."""
import re, json, datetime, zoneinfo, hashlib
SRC='/workspace/multi-ota/LAST_GOOD.html'; OUT='/workspace/multi-ota/NEW_index.html'
s=open(SRC,encoding='utf-8').read()
assert hashlib.sha256(s.encode()).hexdigest().startswith("0ab556c3")
m=re.search(r'(<script type="application/json" id="chart-data">)(.*?)(</script>)',s,re.S)
raw=m.group(2); d=json.loads(raw); assert json.dumps(d,ensure_ascii=False,separators=(',',':'))==raw
OLDG='Booking guest (name TBC, res 6756773216)'; NEWG='Ta Sangi'
n=0
for r in d:
    if r['d'] in ('2026-11-04','2026-11-05','2026-11-06'):
        g=[g for g in r['w'][1] if g[0]=='R'][0]; i=g[1].index(OLDG); g[1][i]=NEWG
        assert r['wam']==1; r['wam']=0; n+=1
    else:
        assert OLDG not in json.dumps(r,ensure_ascii=False)
assert n==3
s=s[:m.start(2)]+json.dumps(d,ensure_ascii=False,separators=(',',':'))+s[m.end(2):]
OLD='<tr><td>Booking guest (name TBC)</td><td>4 Nov</td><td>7 Nov</td><td>res 6756773216; Booking Femme Girls (Old one 16840329); 3 nights (4, 5, 6 Nov) per Royce; name and payout not in mail</td></tr>'
assert s.count(OLD)==1
s=s.replace(OLD,'<tr><td>Ta Sangi</td><td>4 Nov</td><td>7 Nov</td><td>res 6756773216; Booking Femme Girls (Old one 16840329); India; 1 adult; Bunk Bed in Female Dormitory Room; 3 nights; total €46.07, commission+charges €8.06, net ≈ €38.01 (≈ €12.67/night); payout due by 9 Nov; received 26 Oct; women\'s Airbnb closed 4–6 Nov</td></tr>')
now=datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Paris'))
utc=now.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
s,k=re.subn(r'(<meta name="calendar-version" content=")[0-9TZ:-]+(">)',r'\g<1>%s\g<2>'%utc,s); assert k==1
sh=now.astimezone(zoneinfo.ZoneInfo('Asia/Shanghai'))
stamp='%s Paris, %s Shanghai (%s)'%(now.strftime('%H:%M'),sh.strftime('%H:%M'),sh.strftime('%Y-%m-%d'))
s=re.sub(r'As of [^<]*?\(\d{4}-\d\d-\d\d\)\.','As of %s.'%stamp,s,count=1)
s=re.sub(r'Last refreshed [^<]*?\(\d{4}-\d\d-\d\d\)\.','Last refreshed %s.'%stamp,s,count=1)
for bad in ['<FORBIDDEN_1>','<FORBIDDEN_2>','<FORBIDDEN_3>','<FORBIDDEN_4>']: assert bad not in s
for must in ["Keti","IMFURAYACU","Ngango","Muhammad","Breakdown","chart-data"]: assert must in s
assert s.startswith('<!DOCTYPE html>') and 'name TBC, res 6756773216' not in s
open(OUT,'w',encoding='utf-8').write(s)
print(utc,hashlib.sha256(s.encode()).hexdigest(),len(s.encode()))
