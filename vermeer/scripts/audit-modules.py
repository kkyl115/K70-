#!/usr/bin/env python3
"""Offline ELF/CRC inventory. Never equates matching CRCs with complete ABI."""
import argparse,gzip,json,lzma,struct,subprocess,zlib
from pathlib import Path
from kernel_audit import elf_module,compare_module

def audit(directory,symvers,vermagic):
    directory=Path(directory)
    if not directory.is_dir(): raise ValueError('module directory missing')
    report=[]
    for path in sorted(directory.rglob('*')):
        if not path.is_file() or not any(path.name.endswith(s) for s in ('.ko','.ko.gz','.ko.xz','.ko.zst')): continue
        try:
            if path.is_symlink(): raise ValueError('symlink module refused; supply an ordinary-file snapshot')
            data=path.read_bytes()
            if path.suffix=='.gz': data=gzip.decompress(data)
            elif path.suffix=='.xz': data=lzma.decompress(data)
            elif path.suffix=='.zst': data=subprocess.run(['zstd','-dc','--',str(path)],check=True,capture_output=True).stdout
            m=elf_module(data); result=compare_module(m,symvers,vermagic)
            report.append({'file':str(path.relative_to(directory)),'module':m,'check':result})
        except (OSError,ValueError,lzma.LZMAError,struct.error,zlib.error,subprocess.SubprocessError) as e:
            report.append({'file':str(path.relative_to(directory)),'error':str(e)})
    passes=sum(r.get('check',{}).get('symbol_crc_check')=='PASS' for r in report)
    return {'module_count':len(report),'crc_pass_count':passes,
            'all_supplied_modules_crc_pass':bool(report) and passes==len(report),
            'inventory_completeness_verified':False,'signature_verified':False,'full_abi_verified':False,
            'deployable':False,'results':report}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('directory'); p.add_argument('--symvers',required=True); p.add_argument('--vermagic',required=True); a=p.parse_args()
    try:
        r=audit(a.directory,Path(a.symvers).read_text(),a.vermagic); print(json.dumps(r,indent=2))
        raise SystemExit(0 if r['all_supplied_modules_crc_pass'] else 2)
    except (OSError,ValueError) as e: p.exit(2,str(e)+'\n')
