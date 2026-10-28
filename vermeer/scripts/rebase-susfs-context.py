#!/usr/bin/env python3
"""Rebase ONLY two include-context mismatches; no SUSFS semantic changes.
Requires git apply --check against the actual source after generating this file.
This does not port the separate KernelSU-side patch to SukiSU.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'patches/susfs/50_add_susfs_in_gki-android13-5.15.patch'
text=source.read_text()
for filename,changes in [
    ('fs/namespace.c',[('@@ -32,11 +32,21 @@','@@ -32,10 +32,20 @@'),(' #include <trace/hooks/blk.h>\n','')]),
    ('fs/proc/task_mmu.c',[('@@ -22,6 +22,9 @@','@@ -22,5 +22,8 @@'),(' #include <trace/hooks/mm.h>\n','')])]:
    start=text.index('diff --git a/'+filename+' ')
    end=text.find('\ndiff --git ',start+1)
    if end<0: end=len(text)
    section=text[start:end]
    for old,new in changes:
        if section.count(old)!=1: raise SystemExit('Unexpected upstream patch context: '+old)
        section=section.replace(old,new,1)
    text=text[:start]+section+text[end:]
(source.parent/'51_susfs_ack_context_rebased.patch').write_text(text,newline='\n')
print('Generated alternative full patch; apply 51 OR 50, never both. Not compile or ABI validation.')
