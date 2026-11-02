#!/usr/bin/env python3
"""Confere se os dados gerados estão completos antes de publicar. Falha (código 1) se algo estiver fora do esperado."""
import sys, json, os
d = sys.argv[1]
L = lambda n: json.load(open(os.path.join(d, n), encoding='utf-8'))
meta = L('meta.json'); par = L('parasites.json'); hosts = L('hosts.json'); taxa = L('taxa.json')
seed = set(json.load(open(os.path.join(os.path.dirname(__file__), 'lista_semente.json'))))
got = {p['i'][5:] for p in par}
cob = len(seed & got) / max(1, len(seed))
problemas = []
if len(par) < 9000: problemas.append(f'poucos parasitos: {len(par)}')
if len(hosts) < 1500: problemas.append(f'poucos hospedeiros: {len(hosts)}')
if len(taxa) < 20000: problemas.append(f'poucos táxons na hierarquia: {len(taxa)}')
if cob < 0.95: problemas.append(f'só {cob:.1%} da lista-semente continua no CTFB')
print(f"parasitos={len(par)} hospedeiros={len(hosts)} táxons={len(taxa)} cobertura da semente={cob:.1%} novos pela regra={len(meta.get('addedByRule', []))}")
if problemas:
    print('PROBLEMAS:', '; '.join(problemas)); sys.exit(1)
