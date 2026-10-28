#!/usr/bin/env python3
"""Pin candidate upstream sources for read-only review. Never run setup scripts."""
import json
from collect_upstream import api, fetch, EVIDENCE

REPOS = {
    'bbg': ('vc-teahouse/Baseband-guard', 'main', ['README.md', 'Kconfig', 'Makefile', 'LICENSE', 'baseband_guard.c', 'baseband_guard.h', 'blkdev_helper.c', 'blkdev_helper.h', 'kernel_compat.h']),
    'droidspaces': ('ravindu644/Droidspaces-OSS', 'main', ['README.md', 'LICENSE']),
    'bbr3': ('google/bbr', 'v3', ['README.md', 'Makefile', 'net/ipv4/tcp_bbr.c']),
    'ntsync': ('torvalds/linux', 'v6.14', ['drivers/misc/ntsync.c', 'include/uapi/linux/ntsync.h', 'tools/testing/selftests/drivers/ntsync/ntsync.c']),
}

def main():
    records={}
    for name,(repo,ref,files) in REPOS.items():
        commit=api('candidates/'+name+'/commit.json',f'https://api.github.com/repos/{repo}/commits/{ref}')
        pin=commit['sha']
        records[name]={'repository':'https://github.com/'+repo,'ref':ref,'commit':pin,'committer_date':commit['commit']['committer']['date'],'status':'source_review_only'}
        if name in ('bbg','droidspaces'):
            tree=api('candidates/'+name+'/tree.json',f'https://api.github.com/repos/{repo}/git/trees/{pin}?recursive=1')
            records[name]['tree_truncated']=tree.get('truncated')
            if name=='bbg':
                files=sorted(set(files)|{x['path'] for x in tree['tree'] if x['type']=='blob' and (x['path'].startswith('tracing/') or x['path'].startswith('docs/'))})
            else:
                files=sorted(set(files)|{x['path'] for x in tree['tree'] if x['type']=='blob' and 'kernel-patches/GKI/below-kernel-6.12' in x['path']})
        records[name]['files']=[]
        for path in files:
            try:
                fetch('candidates/'+name+'/'+path,f'https://raw.githubusercontent.com/{repo}/{pin}/{path}')
                records[name]['files'].append(path)
            except Exception as e:
                records[name].setdefault('fetch_errors',[]).append({'path':path,'error':str(e)})
        print(name,pin,flush=True)
    (EVIDENCE/'candidates'/'lock.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
