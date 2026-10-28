#!/usr/bin/env python3
"""Package source/evidence and an audit-only ZIP. Never packages a flashable Image."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def write_zip(path,entries):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
        for name,data,mode in entries:
            i=zipfile.ZipInfo(name,(2026,10,27,0,0,0)); i.create_system=3; i.external_attr=mode<<16; i.compress_type=zipfile.ZIP_DEFLATED
            out.writestr(i,data)
def main():
    release=ROOT/'release'; release.mkdir(exist_ok=True)
    readme=b'BootGuard AUDIT NOOP ONLY. No partition writes. Cannot restore a bootloop. Not device tested.\n'
    entries=[('META-INF/com/google/android/update-binary',(ROOT/'bootguard/recovery/update-binary').read_bytes(),0o100755),
             ('META-INF/com/google/android/updater-script',b'# BootGuard audit only; logic is in update-binary.\n',0o100644),('README.txt',readme,0o100644)]
    write_zip(release/'BootGuard-AUDIT-NOOP.zip',entries)
    allowed={'scripts','tests','configs','patches','bootguard','docs','evidence','ci'}
    files=[]
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if not p.is_file() or '__pycache__' in rel.parts: continue
        # Exclude reports that contain the ZIP's own hash: including them would
        # make repeated packaging change the archive through self-reference.
        if rel.as_posix() in ('evidence/packaging-result.json','evidence/package-verification.json'): continue
        if rel.parts[0] in allowed or rel.parts[:2]==('sources','research') or str(rel).replace('\\','/') in ['sources/upstream-lock.json','toolchains/lock.json','README.md','build.ps1','.gitignore','.gitattributes','LICENSE','NOTICE.md']:
            # No phone backups/images, compiled kernel/module binaries or keys.
            if p.suffix.lower() in ('.img','.ko','.pem','.key','.o','.pyc'): raise ValueError('Unexpected binary/key in devkit: '+str(rel))
            files.append(p)
    records={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    (release/'source-SHA256SUMS.txt').write_text(''.join(v+'  '+k+'\n' for k,v in records.items()),encoding='utf-8')
    payload=[(p.relative_to(ROOT).as_posix(),p.read_bytes(),0o100755 if p.suffix=='.sh' else 0o100644) for p in sorted(files)]
    payload.append(('source-SHA256SUMS.txt',(release/'source-SHA256SUMS.txt').read_bytes(),0o100644))
    write_zip(release/'Vermeer-Engineering-Devkit-NOT-FLASHABLE.zip',payload)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in release.glob('*.zip')}
    (release/'SHA256SUMS.txt').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(hashes.items())),encoding='utf-8')
    print(json.dumps({'source_files':len(files),'archives':hashes,'flashable_kernel_released':False},indent=2))
if __name__=='__main__': main()
