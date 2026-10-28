#!/usr/bin/env python3
"""Stop/continue only compiler processes whose cwd is this project's out directory."""
import argparse,os,pathlib,signal
p=argparse.ArgumentParser(); p.add_argument('action',choices=['pause','resume']); p.add_argument('output'); a=p.parse_args()
out=pathlib.Path(a.output).resolve(strict=True)
if out.name!='out-baseline' or out.parent.name!='vermeer-build': raise SystemExit('unexpected build output path')
for entry in pathlib.Path('/proc').iterdir():
    if not entry.name.isdigit(): continue
    try:
        cwd=(entry/'cwd').resolve(strict=True)
        comm=(entry/'comm').read_text().strip()
        if cwd.is_relative_to(out) and comm in ('ld.lld','clang','clang.real'):
            os.kill(int(entry.name),signal.SIGSTOP if a.action=='pause' else signal.SIGCONT)
            print(a.action,entry.name,comm,flush=True)
    except (FileNotFoundError,PermissionError,ProcessLookupError): pass
