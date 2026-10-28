#!/usr/bin/env python3
"""Stage a pinned, offline SukiSU LKM source experiment; never install anything."""
import argparse,difflib,hashlib,json,pathlib,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
COMMIT='d6b36700f3bd0a4c1585549b470dd30bb8774534'

def prepare(destination):
    destination=pathlib.Path(destination).absolute()
    if destination.exists(): raise ValueError('Destination exists; refusing overwrite or double integration')
    archive=ROOT/'evidence/upstream-research/sukisu-source.tar.gz'
    provenance=json.loads(archive.with_name(archive.name+'.provenance.json').read_text())
    expected_url='https://codeload.github.com/SukiSU-Ultra/SukiSU-Ultra/tar.gz/'+COMMIT
    if provenance['url']!=expected_url or hashlib.sha256(archive.read_bytes()).hexdigest()!=provenance['sha256']:
        raise ValueError('Pinned source archive mismatch')
    destination.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        prefix='SukiSU-Ultra-'+COMMIT+'/'
        for m in tar.getmembers():
            if not m.name.startswith(prefix) and m.name.rstrip('/')!=prefix.rstrip('/'):
                raise ValueError('Unexpected archive path')
        tar.extractall(destination,filter='data')
    source=destination/('SukiSU-Ultra-'+COMMIT)
    kbuild=source/'kernel/Kbuild'; original=kbuild.read_text()
    first=original.index('GIT_BIN  :='); last=original.index('$(info -- $(REPO_NAME) version:',first)
    replacement='''# Vermeer offline reproducibility patch: no network or parent Git lookup.
KSU_VERSION := 41068
KSU_VERSION_FULL := v4.2.1-r2-d6b36700@vermeer-lab
'''
    changed=original[:first]+replacement+original[last:]
    kbuild.write_text(changed)
    patch=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/kernel/Kbuild',tofile='b/kernel/Kbuild'))
    (ROOT/'patches/sukisu/0001-pin-offline-version.patch').write_text(patch)
    manifest={'source_commit':COMMIT,'archive_sha256':provenance['sha256'],
              'kbuild_sha256':hashlib.sha256(changed.encode()).hexdigest(),'mode':'lkm_compile_experiment',
              'KPM':False,'SUSFS':False,'device_installation_allowed':False}
    (destination/'stage-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return source

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('destination'); a=p.parse_args()
    try: print(prepare(a.destination))
    except (OSError,ValueError,KeyError) as e: p.exit(2,str(e)+'\n')
