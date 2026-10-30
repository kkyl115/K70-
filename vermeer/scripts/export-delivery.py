#!/usr/bin/env python3
"""Export a reviewed snapshot to the user's existing delivery branch, no push."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def export(repo):
    repo=Path(repo).resolve()
    branch=subprocess.check_output(['git','-C',str(repo),'branch','--show-current'],text=True).strip()
    if branch!='codex/vermeer-engineering': raise ValueError('Unexpected delivery branch')
    origin=subprocess.check_output(['git','-C',str(repo),'remote','get-url','origin'],text=True).strip()
    if origin not in ('https://github.com/kkyl115/K70-.git','https://github.com/kkyl115/K70-'): raise ValueError('Unexpected repository')
    destination=repo/'vermeer'
    if destination.is_symlink() or not destination.resolve().is_relative_to(repo):
        raise ValueError('Delivery destination must stay inside the selected repository')
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0')
    included=[]
    for item in files:
        if not item: continue
        relative=Path(item)
        if relative.parts[:2]==('evidence','user-supplied'): continue
        source=ROOT/relative
        if not source.is_file() or source.is_symlink(): raise ValueError('Unexpected tracked file: '+item)
        target=destination/relative
        if not target.resolve().is_relative_to(repo): raise ValueError('Destination escapes repository')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.is_symlink(): raise ValueError('Destination symlink refused')
        shutil.copyfile(source,target)
        included.append({'path':relative.as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    result={'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
            'source_worktree_snapshot':True,'branch':branch,'files':included,
            'excluded':['evidence/user-supplied','untracked build outputs, backups, credentials'],
            'pushed':False}
    (destination/'delivery-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    return len(included)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('repository'); a=p.parse_args()
    print(json.dumps({'copied_files':export(a.repository),'pushed':False}))
