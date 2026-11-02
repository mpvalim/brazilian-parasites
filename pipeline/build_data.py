#!/usr/bin/env python3
"""Brazilian Parasites — gera os JSON do app a partir do CSV mv_planilha_extendida do CTFB.
Uso: python build_data.py CSV_ENTRADA PASTA_SAIDA [lista_semente.json]
Saídas: parasites.json (schema compacto do app), hosts.json, meta.json
"""
import sys, json, re, datetime, pandas as pd

BIOMES = {'MATA_ATLANTICA':'Mata Atlântica','CERRADO':'Cerrado','AMAZONIA':'Amazônia','PANTANAL':'Pantanal','PAMPA':'Pampa','CAATINGA':'Caatinga'}
HYDRO = {'BACIA_AMAZONICA':'AM','BACIA_TOCANTINS_ARAGUAIA':'TA','BACIA_ATLANTICO_SUDESTE':'SEA','BACIA_PARANA':'PR_H','BACIA_URUGUAI':'UR','BACIA_ATLANTICO_SUL':'SA','BACIA_ATLANTICO_NORDESTE_ORIENTAL':'NAOR','BACIA_SAO_FRANCISCO':'SF','BACIA_PARAGUAI':'PG','BACIA_ATLANTICO_NORDESTE_OCIDENTAL':'NAOC'}
MARINE = {'SUDESTE_BRASILEIRO':'SE','ILHAS_DE_SAO_PEDRO_E_SAO_PAULO':'SPSP','AMAZONIA':'AMZ','RIO_GRANDE':'RG','ATLANTICO_SUDOESTE_TROPICAL':'ASWT','NORDESTE_BRASILEIRO':'NE','ATLANTICO_SUDOESTE_TEMPERADO_QUENTE':'ASWTQ','PLATAFORMA_CONTINENTAL_BRASILEIRA_NORTE':'PCN','LESTE_BRASILEIRO':'LE','ILHAS_OCEANICAS':'ILHAS'}
ORIGIN = {'native':'nativa','introduced':'exotica','uncertain':'incerto'}
TIPO = {'TIPO_HOLOTIPO':'Holótipo'}
TT = lambda lf: ('Ecto/Endoparasito' if ('ectoparasito' in lf and 'endoparasito' in lf and 'ectoparasitoide' not in lf) else 'Ectoparasito' if 'ectoparasito' in lf else 'Endoparasito' if 'endoparasito' in lf else None)

NAME = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+"; PART = r"(?:de|da|do|dos|das|van|von|der|di|del|du|le|la|Le|La|De|Da|Van|Von)"
AUTH = r"(?:" + PART + r" )?" + NAME + r"(?: " + NAME + r")?(?: " + PART + r")? [A-Z]{1,4}(?:-[A-Z]{1,4})?(?: (?:de|da|do|dos) [A-Z]{1,3})?(?: Jr\.?| Filho| Neto)?"
CITE = re.compile(r"(?<=[\.\)])\s*(?=" + AUTH + r"(?:(?:, ?|,? ?& ?|; ?)" + AUTH + r")*,? ?\(\d{4}[a-z]?\))")
def split_refs(raw):
    out = []
    for line in re.split(r'\r?\n', raw or ''):
        line = line.strip()
        if line: out += [x.strip() for x in CITE.split(line) if x and x.strip()]
    return out

def split_list(s): return [x for x in (s or '').split(';') if x.strip()]

def canon(r, sg_on=True):
    if r['taxonRank'] == 'subgenus' and r['genus']:
        return f"{r['genus']} ({r['subGenus'] or r['genus']})"
    sg = f"({r['subGenus']})" if sg_on and r['subGenus'] and r['specificEpithet'] else ''
    parts = [r['genus'], sg, r['specificEpithet'], r['infraspecificEpithet']]
    return ' '.join(p for p in parts if p).strip() or re.sub(r'\s+\(?[^\s]*\d{4}.*$', '', r['scientificName'])

TYPE_LABEL = {'HOLOTIPO':'Holótipo','PARATIPO':'Parátipo','LECTOTIPO':'Lectótipo','PARALECTOTIPO':'Paralectótipo','NEOTIPO':'Neótipo','SINTIPO':'Síntipo','ALOTIPO':'Alótipo'}
def typology_text(js):
    try: d = json.loads(js)
    except Exception: return ''
    if not isinstance(d, dict): return ''
    pri = d.get('primario') or {}
    out = ''
    tp = (pri.get('tipo_primario') or '').strip().upper()
    if tp:
        reg = (pri.get('registro_primario') or '').strip(); rep = (pri.get('repositorio_primario') or '').strip(); loc = (pri.get('localidade_primario') or '')
        head = ', '.join(x for x in [reg, rep] if x)
        out = TYPE_LABEL.get(tp, tp.capitalize()) + ': ' + head + (' — ' + loc if loc else '')
    sec = d.get('secundario') or []
    if isinstance(sec, dict): sec = [sec]
    n = len(sec) if isinstance(sec, list) else 0
    if out and n:
        kinds = {TYPE_LABEL.get((s.get('tipo_secudario') or s.get('tipo_secundario') or '').strip().upper(), '') for s in sec if isinstance(s, dict)} - {''}
        out += f". {n} espécime{'s' if n>1 else ''} adiciona{'is' if n>1 else 'l'}" + (f" ({'/'.join(sorted(kinds))})" if kinds else '')
    return out

def main(csv, outdir, seed_path=None, seed_dir=None):
    df = pd.read_csv(csv, dtype=str, na_filter=False, encoding='utf-8-sig')
    idx = df.set_index('taxonID', drop=False)
    sp = df[df.taxonRank.isin(['species','subspecies'])]
    seed = set(json.load(open(seed_path))) if seed_path else set()
    # Regra do app: só endoparasitos e ectoparasitos (forma de vida do CTFB). Parasitoides ficam de fora.
    PAR_TOKENS = {'endoparasito', 'ectoparasito'}
    is_par = sp.lifeForm.str.lower().apply(lambda v: bool(PAR_TOKENS & set(x.strip() for x in v.split(';'))))
    chosen = set(sp[is_par & (sp.taxonomicStatus == 'accepted')].taxonID)
    # sinônimos cujo nome aceito é um parasito escolhido
    syn = set(sp[(sp.taxonomicStatus != 'accepted') & sp.acceptedNameUsageID.isin(chosen)].taxonID)
    ids = chosen | syn
    added = sorted(chosen - seed) if seed else []
    removed = sorted(seed - chosen) if seed else []
    def host_rec(hid):
        if hid not in idx.index: return None
        h = idx.loc[hid]
        return {'n': canon(h, False) if h.taxonRank in ('species','subspecies') else '', 'a': h.scientificNameAuthorship, 'cl': h['class'], 'o': h['order'], 'f': h.family}
    out = []
    for tid in sorted(ids, key=lambda x: int(x) if x.isdigit() else 0):
        r = idx.loc[tid]
        rec = {'i':'ctfb-'+tid, 'n':canon(r, False), 'a':r.scientificNameAuthorship, 'phy':r.phylum, 'cl':r['class'], 'o':r['order'], 'so':r.subOrder, 'sf':r.superFamily, 'sfam':r.subFamily, 'f':r.family}
        if r.taxonomicStatus == 'accepted':
            rec['su'] = 'válido'
            l = r.lifeForm
            if TT(l): rec['tt'] = TT(l)
            if l: rec['lf'] = l.upper()
            if r.habitat: rec['h'] = r.habitat
            st = sorted({x.split('-')[1] for x in split_list(r.locationID) if x.startswith('BR-')})
            if st: rec['st'] = st
            if r.establishmentMeans in ORIGIN: rec['os'] = ORIGIN[r.establishmentMeans]
            oc = sorted(set(split_list(r.countryCode)) | {'BR'})
            rec['oc'] = oc
            ed = split_list(r.epicontinentalDomain)
            bm = [BIOMES[x] for x in ed if x in BIOMES]; hr = [HYDRO[x] for x in ed if x in HYDRO]
            if bm: rec['bm'] = sorted(bm)
            if hr: rec['hr'] = sorted(hr)
            mr = [MARINE[x] for x in split_list(r.marineDomain) if x in MARINE]
            if mr: rec['mr'] = sorted(mr)
            rf = split_refs(r.bibliographicReference)
            if rf: rec['rf'] = rf
            if r.endemicBrazil: rec['eb'] = r.endemicBrazil
            hos = [host_rec(h) for h in split_list(r.animalHostIds)]
            hos = [h for h in hos if h]
            if hos: rec['ho'] = hos
            ty = typology_text(r.typology)
            if ty: rec['ty'] = ty
            rec['env'] = {'EPICONTINENTAL':'epicontinental','MARINHO':'marinho'}.get(r.environment,'indefinido')
            if r.vernacularName: rec['p'] = r.vernacularName.split(';')[0].strip()
        else:
            rec['su'] = 'sinônimo'
            if r.acceptedNameUsage: rec['sy'] = r.acceptedNameUsage
            if r.acceptedNameUsageID: rec['ai'] = 'ctfb-'+r.acceptedNameUsageID
        out.append({k:v for k,v in rec.items() if v not in ('', None, [])})

    # ---------- hospedeiros ----------
    parasites = [o for o in out if o['su']=='válido']
    host_parasites = {}
    for o in parasites:
        tid = o['i'][5:]
        for hid in split_list(idx.loc[tid].animalHostIds):
            host_parasites.setdefault(hid, []).append(o)
    TT_SHORT = lambda tt: 'ecto' if (tt or '').startswith('Ecto') else 'endo'
    hosts = []
    for hid, plist in host_parasites.items():
        if hid not in idx.index: continue
        h = idx.loc[hid]
        if h.taxonRank not in ('species','subspecies'): continue
        v = [x.strip() for x in h.vernacularName.split(';') if x.strip()]
        hosts.append({'id':hid,'n':canon(h),'a':h.scientificNameAuthorship,'phy':h.phylum,'cl':h['class'],'o':h['order'],'f':h.family,'sf':h.subFamily,'tr':h.tribe,'str_':h.subTribe,'g':h.genus,'eb':h.endemicBrazil,'v':v,
                      'p':[{'id':o['i'][5:],'n':o['n'],'a':o.get('a',''),'cl':o.get('cl',''),'o':o.get('o',''),'so':o.get('so',''),'f':o.get('f',''),'t':TT_SHORT(o.get('tt')),'linked':True} for o in sorted(plist,key=lambda q:q['n'])],
                      'scientificName':canon(h),'authorship':h.scientificNameAuthorship,'popularName':'; '.join(v)})
    hosts.sort(key=lambda q:int(q['id']))
    # ---------- hierarquia ampliada (ALL_PARASITE_TAXA) ----------
    fams = {o['f'] for o in out if o.get('f')}
    RK = ['species','genus','subspecies','subgenus','family','subfamily','tribe','subtribe']
    cand = df[df.family.isin(fams) & df.taxonRank.isin(RK) & (df.taxonomicStatus=='accepted')]
    taxa = [{'id':r.taxonID,'n':(canon(r) if r.taxonRank in ('species','subspecies') else (r[{'genus':'genus','subgenus':'subGenus','family':'family','subfamily':'subFamily','tribe':'tribe','subtribe':'subTribe'}[r.taxonRank]] or canon(r))),'a':r.scientificNameAuthorship,'rk':r.taxonRank,'phylum':r.phylum,'classe':r['class'],'ordem':r['order'],'subordem':r.subOrder,'superfamilia':r.superFamily,'familia':r.family,'subfamilia':r.subFamily} for r in cand.itertuples(index=False) ] if False else None
    taxa = []
    for r in cand.to_dict('records'):
        nm = canon(r) if r['taxonRank'] in ('species','subspecies','subgenus') else (r[{'genus':'genus','subgenus':'subGenus','family':'family','subfamily':'subFamily','tribe':'tribe','subtribe':'subTribe'}[r['taxonRank']]] or canon(r))
        taxa.append({'id':r['taxonID'],'n':nm,'a':r['scientificNameAuthorship'],'rk':r['taxonRank'],'phylum':r['phylum'],'classe':r['class'],'ordem':r['order'],'subordem':r['subOrder'],'superfamilia':r['superFamily'],'familia':r['family'],'subfamilia':r['subFamily']})
    # ---------- nome -> ID (supraespecíficos) ----------
    FIELD = {'subgenus':'subGenus','phylum':'phylum','class':'class','order':'order','suborder':'subOrder','superfamily':'superFamily','family':'family','subfamily':'subFamily','tribe':'tribe','subtribe':'subTribe','genus':'genus','subgenus':'subGenus','superclass':'superClass','subclass':'subClass','infraclass':'infraClass','superorder':'superOrder','infraorder':'infraOrder'}
    ids_by_name = {}
    sub = df[df.taxonRank.isin(list(FIELD))].copy()
    sub['_acc'] = (sub.taxonomicStatus=='accepted')
    for r in sub.sort_values('_acc', ascending=False, kind='stable').to_dict('records'):
        nm = canon(r) if r['taxonRank']=='subgenus' else r[FIELD[r['taxonRank']]]
        if nm and nm not in ids_by_name: ids_by_name[nm] = r['taxonID']
    # ---------- dicionário de gêneros ----------
    genus_dict = sorted(set(df.genus) - {''})
    # ---------- autoria por nível ----------
    def auth(rank, col):
        d = df[(df.taxonRank==rank) & (df.taxonomicStatus=='accepted')]
        return {r[col]: r['scientificNameAuthorship'] for r in d.to_dict('records') if r[col] and r['scientificNameAuthorship']}
    auths = {'PHYLUM_AUTH':auth('phylum','phylum'),'CLASS_AUTH':auth('class','class'),'ORDER_AUTH':auth('order','order'),'SUBORDER_AUTH':auth('suborder','subOrder'),'SUPERFAMILY_AUTH':auth('superfamily','superFamily'),'FAMILY_AUTH':auth('family','family'),'SUBFAMILY_AUTH':auth('subfamily','subFamily'),'GENUS_AUTH':auth('genus','genus')}
    # só o que os parasitos usam, para manter o arquivo enxuto
    used = {'PHYLUM_AUTH':{o['phy'] for o in out}, 'CLASS_AUTH':{o['cl'] for o in out if o.get('cl')}, 'ORDER_AUTH':{o['o'] for o in out if o.get('o')}, 'SUBORDER_AUTH':{o['so'] for o in out if o.get('so')}, 'SUPERFAMILY_AUTH':{o['sf'] for o in out if o.get('sf')}, 'FAMILY_AUTH':{t['familia'] for t in taxa if t['familia']}, 'SUBFAMILY_AUTH':{t['subfamilia'] for t in taxa if t['subfamilia']}, 'GENUS_AUTH':{t['n'] for t in taxa if t['rk']=='genus'}}
    auths = {k:{n:a for n,a in v.items() if n in used[k]} for k,v in auths.items()}
    import os; os.makedirs(outdir, exist_ok=True)
    _seed = json.load(open(seed_dir, encoding='utf-8')) if seed_dir and os.path.exists(seed_dir) else {}
    def seed(name, default):
        return _seed.get(name.replace('.json', ''), default)
    # a semente nunca perde nada: o que o app já tinha continua, o CTFB atual prevalece nos conflitos
    sa = seed('authorship.json', {}); auths = {k: {**sa.get(k, {}), **auths.get(k, {})} for k in set(sa) | set(auths)}
    ids_by_name = {**seed('taxon_ids.json', {}), **ids_by_name}
    genus_dict = sorted(set(seed('genus_dict.json', [])) | set(genus_dict))
    HAB_AQUATIC = {'Actinopterygii','Chondrichthyes','Dipnoi','Sarcopterygii','Cephalaspidomorphi','Myxini','Elasmobranchii','Holocephali'}
    sh = seed('host_habitat.json', {})
    hab = {}
    for h in hosts:
        if h['id'] in sh: hab[h['id']] = sh[h['id']]; continue
        r = idx.loc[h['id']]
        if r.environment == 'MARINHO' or r.marineDomain: hab[h['id']] = 'marine'
        elif r.environment == 'EPICONTINENTAL' and r['class'] in HAB_AQUATIC and r.epicontinentalDomain: hab[h['id']] = 'freshwater'
        else: hab[h['id']] = 'terrestrial'
    json.dump(out, open(os.path.join(outdir,'parasites.json'),'w',encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
    W = lambda name, obj: json.dump(obj, open(os.path.join(outdir,name),'w',encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
    W('hosts.json', hosts); W('taxa.json', taxa); W('taxon_ids.json', ids_by_name); W('genus_dict.json', genus_dict); W('authorship.json', auths); W('host_habitat.json', hab)
    json.dump({'generatedAt': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat()+'Z', 'source':'mv_planilha_extendida', 'nParasites': len(out), 'nHosts': len(hosts), 'nTaxa': len(taxa), 'nAccepted': sum(1 for o in out if o['su']=='válido'), 'addedByRule': added, 'removedFromSeed': removed}, open(os.path.join(outdir,'meta.json'),'w',encoding='utf-8'), ensure_ascii=False)
    print('parasitos:', len(out), '| novos pela regra:', len(added))

if __name__ == '__main__':
    main(*sys.argv[1:5])
