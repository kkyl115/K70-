#!/usr/bin/env python3
"""Read-only upstream metadata/file collection. Never executes fetched content."""
import base64
import hashlib
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'evidence' / 'upstream-research'
EVIDENCE.mkdir(parents=True, exist_ok=True)

def fetch(name, url, gitiles=False):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Vermeer-Upstream-Audit/1.0'})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
            if gitiles:
                data = base64.b64decode(data, validate=True)
            path = EVIDENCE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            record = {'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                      'retrieved_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'gitiles_base64_decoded': gitiles}
            path.with_name(path.name + '.provenance.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            return data
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)

def api(name, url):
    data = fetch(name, url)
    if data.startswith(b")]}'"):
        data = data.split(b'\n', 1)[1]
    return json.loads(data)

if __name__ == '__main__':
    gh = 'https://api.github.com/repos/'
    micode = api('micode-branch.json', gh + 'MiCode/Xiaomi_Kernel_OpenSource/branches/bsp-vermeer-t-oss')
    suki = api('sukisu-release.json', gh + 'SukiSU-Ultra/SukiSU-Ultra/releases/tags/v4.2.1-r2')
    suki_commit = api('sukisu-commit.json', gh + 'SukiSU-Ultra/SukiSU-Ultra/commits/v4.2.1-r2')
    suki_tree = api('sukisu-tree.json', gh + 'SukiSU-Ultra/SukiSU-Ultra/git/trees/' + suki_commit['sha'] + '?recursive=1')
    bsp_tree = api('micode-tree.json', gh + 'MiCode/Xiaomi_Kernel_OpenSource/git/trees/' + micode['commit']['sha'] + '?recursive=1')
    susfs = api('susfs-branch.json', 'https://gitlab.com/api/v4/projects/simonpunk%2Fsusfs4ksu/repository/branches/gki-android13-5.15')
    api('ack-commit.json', 'https://android.googlesource.com/kernel/common/+/6f2f96be86b9?format=JSON')
    fetch('micode-README.md', 'https://raw.githubusercontent.com/MiCode/Xiaomi_Kernel_OpenSource/README/README.md')
    print('SukiSU commit:', suki_commit['sha'])
    for label, tree in [('sukisu', suki_tree), ('micode', bsp_tree)]:
        print(label, 'truncated:', tree.get('truncated'))
        print('\n'.join(x['path'] for x in tree['tree'] if any(w in x['path'].lower() for w in ['kpm', 'kernelpatch', 'license', 'readme', 'susfs', 'vermeer_user_defconfig'])))
