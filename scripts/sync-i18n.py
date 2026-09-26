"""Sync ro.json / ru.json with the keys in src/i18n/en.ts.

Existing translations are kept; new keys get "TODO" (shown in English until
translated). Locale-only plural variants (`_few`, `_many`) are preserved. Run after adding English strings:
    python3 scripts/sync-i18n.py
"""
import json, re, pathlib

root = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'i18n'
src = (root / 'en.ts').read_text()
body = src[src.index('{', src.index('export const en')):src.rindex('};') + 1]
body = re.sub(r'//.*', '', body)
body = re.sub(r"(\w+):", r'"\1":', body)
body = re.sub(r"'((?:[^'\\]|\\.)*)'", lambda m: json.dumps(m.group(1)), body)
body = re.sub(r',(\s*[}\]])', r'\1', body)
en = json.loads(body)

PLURAL = re.compile(r'_(zero|one|two|few|many|other)$')

def merge(ref, cur):
    out = {}
    # Keep locale-only plural variants (e.g. RU `_few`, `_many`) of keys that exist in English.
    for k, v in cur.items():
        base = PLURAL.sub('', k)
        if k != base and base in ref and isinstance(v, str):
            out[k] = v
    for k, v in ref.items():
        if isinstance(v, dict):
            out[k] = merge(v, cur.get(k, {}) if isinstance(cur.get(k), dict) else {})
        else:
            out[k] = cur.get(k, 'TODO') if isinstance(cur.get(k), str) else 'TODO'
    return out

for lang in ('ro', 'ru'):
    path = root / f'{lang}.json'
    cur = json.loads(path.read_text()) if path.exists() else {}
    out = merge(en, cur)
    out['lang'].update({'en': 'EN', 'ro': 'RO', 'ru': 'RU'})  # switch labels are universal
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    todo = json.dumps(out).count('"TODO"')
    print(f'{lang}.json: {todo} TODO keys')
