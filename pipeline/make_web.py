#!/usr/bin/env python3
"""Converte o HTML do app (dados embutidos) na versão web: dados lidos de ./data/*.json.
Uso: python make_web.py APP_ENTRADA.html APP_SAIDA.html"""
import sys, re, json
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
dec = json.JSONDecoder()

def literal_end(text, start):
    _, end = dec.raw_decode(text[start:]); return start + end

def replace_const(name, expr, set_wrap=False):
    global s
    m = re.search(r'\bconst ' + name + r' = ', s)
    assert m, name
    st = m.end()
    if set_wrap:                       # new Set([...])
        assert s[st:st+8] == 'new Set(', name
        en = literal_end(s, st + 8)
        assert s[en] == ')', name
        en += 1
    else:
        en = literal_end(s, st)
    s = s[:m.start()] + 'const ' + name + ' = ' + expr + s[en:]

replace_const('REAL_HOSTS', 'window.BP_DATA.hosts')
replace_const('REAL_PARASITES_MIN', 'window.BP_DATA.parasites')
replace_const('ALL_PARASITE_TAXA', 'window.BP_DATA.taxa')
replace_const('CTFB_TAXON_ID_BY_NAME', 'window.BP_DATA.taxonIds')
replace_const('HOST_HABITAT_MAP', 'window.BP_DATA.hostHabitat')
replace_const('GENUS_DICT', 'new Set(window.BP_DATA.genus)', set_wrap=True)

# mapas de autoria: uma única declaração const A = {...}, B = {...}, ...;
m = re.search(r'\bconst PHYLUM_AUTH = ', s); st = m.start(); pos = m.end(); names = ['PHYLUM_AUTH']
en = literal_end(s, pos)
while True:
    mm = re.match(r',\s*([A-Z_]+_AUTH) = ', s[en:])
    if not mm: break
    names.append(mm.group(1)); en = literal_end(s, en + mm.end())
assert s[en] == ';', repr(s[en:en+20])
s = s[:st] + 'const ' + ', '.join(f'{n} = window.BP_DATA.auth.{n}' for n in names) + s[en:]
print('mapas de autoria:', names)

# scripts embutidos -> text/plain, executados depois do carregamento dos dados
parts = re.split(r'(<script(?![^>]*\bsrc=)[^>]*>)', s)
out = []; n_wrapped = 0
for i, p in enumerate(parts):
    if re.fullmatch(r'<script(?![^>]*\bsrc=)[^>]*>', p) and 'application/ld+json' not in p:
        tag = p[:-1] + ' type="text/plain" data-bp-script="1">' if 'type=' not in p else p
        out.append(tag); n_wrapped += 1
    else: out.append(p)
s = ''.join(out)
print('scripts adiados:', n_wrapped)

LOADER = r'''
<style>
#bp-loading{position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff;color:#2b4a3a;font-family:system-ui,sans-serif;text-align:center;padding:24px}
#bp-loading .bar{width:min(320px,70vw);height:8px;border-radius:4px;background:#e3eee7;overflow:hidden;margin-top:14px}
#bp-loading .bar i{display:block;height:100%;width:0;background:#2e7d4f;transition:width .2s}
#bp-loading.err{color:#8a2d1f}
</style>
<div id="bp-loading"><div id="bp-loading-msg">Carregando dados do CTFB…</div><div class="bar"><i id="bp-loading-bar"></i></div></div>
<script>
(function(){
  var FILES = {hosts:'hosts.json',parasites:'parasites.json',taxa:'taxa.json',taxonIds:'taxon_ids.json',genus:'genus_dict.json',auth:'authorship.json',hostHabitat:'host_habitat.json',meta:'meta.json'};
  var base = (document.currentScript && document.currentScript.dataset.base) || 'data/';
  var keys = Object.keys(FILES), done = 0, el = document.getElementById('bp-loading');
  function step(){ done++; var b = document.getElementById('bp-loading-bar'); if(b) b.style.width = Math.round(100*done/keys.length)+'%'; }
  function fail(e){ el.className = 'err'; document.getElementById('bp-loading-msg').textContent = 'Não foi possível carregar os dados do CTFB. Tente novamente em instantes. (' + e + ')'; }
  var data = {};
  Promise.all(keys.map(function(k){
    return fetch(base + FILES[k], {cache:'no-cache'}).then(function(r){ if(!r.ok) throw new Error(FILES[k]+' '+r.status); return r.json(); }).then(function(j){ data[k] = j; step(); });
  })).then(function(){
    window.BP_DATA = data;
    var scripts = Array.prototype.slice.call(document.querySelectorAll('script[data-bp-script]'));
    scripts.forEach(function(old){
      var n = document.createElement('script'); if(old.id) n.id = old.id;
      n.textContent = old.textContent; old.parentNode.replaceChild(n, old);
    });
    try{ document.dispatchEvent(new Event('DOMContentLoaded', {bubbles:true})); }catch(_){}
    if(el) el.remove();
    try{
      var m = data.meta && data.meta.generatedAt ? new Date(data.meta.generatedAt) : null;
      if(m && !isNaN(m)){
        var d = document.createElement('div'); d.id = 'bp-data-stamp';
        d.style.cssText = 'text-align:center;font:12px system-ui,sans-serif;color:#6b7a70;padding:10px 0 18px';
        d.textContent = 'Dados do CTFB atualizados em ' + m.toLocaleDateString('pt-BR') + ' · ' + data.meta.nParasites.toLocaleString('pt-BR') + ' registros de parasitos';
        document.body.appendChild(d);
      }
    }catch(_){}
  }).catch(function(e){ fail(e && e.message ? e.message : e); });
})();
</script>
'''
i = s.index('<body')
j = s.index('>', i) + 1
s = s[:j] + LOADER + s[j:]
open(dst, 'w', encoding='utf-8').write(s)
print('ok', len(s)/1e6, 'MB')
