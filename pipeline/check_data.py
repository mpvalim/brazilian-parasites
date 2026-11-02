#!/usr/bin/env python3
"""Confere se os dados gerados estão completos antes de publicar. Falha (código 1) se algo estiver fora do esperado."""
import sys, json, os
d = sys.argv[1]
L = lambda n: json.load(open(os.path.join(d, n), encoding='utf-8'))
meta = L('meta.json'); par = L('parasites.json'); hosts = L('hosts.json'); taxa = L('taxa.json')
problemas = []
if len(par) < 7000: problemas.append(f'poucos parasitos: {len(par)}')
if len(hosts) < 1500: problemas.append(f'poucos hospedeiros: {len(hosts)}')
if len(taxa) < 15000: problemas.append(f'poucos táxons na hierarquia: {len(taxa)}')
if any('parasitoide' in (p.get('lf') or '').lower() and not ({'endoparasito','ectoparasito'} & set((p.get('lf') or '').lower().split(';'))) for p in par if p.get('su') == 'válido'):
    problemas.append('há parasitoides sem endo/ectoparasito no resultado')
print(f"parasitos={len(par)} hospedeiros={len(hosts)} táxons={len(taxa)} novos={len(meta.get('addedByRule', []))} fora da lista antiga={len(meta.get('removedFromSeed', []))}")
if problemas:
    print('PROBLEMAS:', '; '.join(problemas)); sys.exit(1)
