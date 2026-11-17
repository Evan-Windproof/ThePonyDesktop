#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight complete managed file sets before installation; never reset Git."""
import argparse, hashlib, json, os, re, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='8d2951186df48773d6014290f08be9ebf0df8257'
def git(where,*args):
    return subprocess.run(['git','-C',str(where),*args],capture_output=True,check=True).stdout

def plans(host):
    paths=set()
    for v in ('0.1.0','0.1.1'):
        paths.update(re.findall(r'^diff --git a/\S+ b/(\S+)$',(ROOT/f'integration/hooftty-v{v}.patch').read_text(),re.M))
    profiles={}
    with tempfile.TemporaryDirectory(prefix='tpd-plan-') as tmp:
        tree=Path(tmp)
        git(tree,'init','-q')
        baseline={}
        additions={'include/kernseed/graphics.h','include/kernseed/pixels.h','kernel/drivers/graphics.c'}
        for name in sorted(paths):
            if name in additions:baseline[name]=None;continue
            baseline[name]=git(host,'show',f'{BASE}:{name}')
        profiles['base']=baseline
        for v in ('0.1.0','0.1.1'):
            for name,data in baseline.items():
                p=tree/name;p.parent.mkdir(parents=True,exist_ok=True)
                if data is None:p.unlink(missing_ok=True)
                else:p.write_bytes(data)
            git(tree,'apply',str(ROOT/f'integration/hooftty-v{v}.patch'))
            profiles[v]={name:(tree/name).read_bytes() if (tree/name).exists() else None for name in paths}
    target=dict(profiles['0.1.1'])
    target['Makefile']+=b'\n# TPD version header must invalidate the application image.\n$(BUILD)/apps/tpd.elf: apps/tpd_version.h\n'
    profiles['0.1.2']=dict(target)
    version=(ROOT/'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid VERSION')
    target['apps/tpd.c']=(ROOT/'src/tpd.c').read_bytes()
    target['apps/tpd_version.h']=f'/* Generated from TPD VERSION. */\n#define TPD_VERSION "{version}"\n'.encode()
    return profiles,target

def read_safe(host,name):
    p=host/name
    for ancestor in (p,*p.parents):
        if ancestor==host:break
        if ancestor.is_symlink():raise ValueError(f'Symlink is not managed: {name}')
    if p.exists() and not p.is_file():raise ValueError(f'Not a regular file: {name}')
    return p.read_bytes() if p.exists() else None

def main():
    a=argparse.ArgumentParser();a.add_argument('host',type=Path);a.add_argument('--check',action='store_true');args=a.parse_args()
    host=args.host.resolve(strict=True)
    if Path(git(host,'rev-parse','--show-toplevel').decode().strip()).resolve()!=host:raise ValueError('Pass the HoofTTY checkout root')
    # The ABI must remain the original one, even when no managed files need changes.
    if read_safe(host,'apps/abi.h')!=(ROOT/'src/abi.h').read_bytes():raise ValueError('Unknown apps/abi.h; refusing changes')
    profiles,target=plans(host)
    current={name:read_safe(host,name) for name in target}
    oldapp=current['apps/tpd.c'];oldheader=current['apps/tpd_version.h']
    known=json.loads((ROOT/'integration/legacy-apps.json').read_text())
    if oldapp is not None and oldapp!=target['apps/tpd.c'] and hashlib.sha256(oldapp).hexdigest() not in known.values():
        raise ValueError('Unknown apps/tpd.c; refusing all changes')
    if oldheader is not None:
        match=re.fullmatch(rb'/\* Generated from TPD VERSION\. \*/\n#define TPD_VERSION "(\d+\.\d+\.\d+)"\n',oldheader)
        if not match or tuple(map(int,match[1].split(b'.')))>tuple(map(int,(ROOT/'VERSION').read_text().strip().split('.'))):
            raise ValueError('Unknown header or unsupported version downgrade')
    matches=[v for v,files in profiles.items() if all(current[n]==b for n,b in files.items())]
    if not matches:raise ValueError('Unknown or mixed kernel interface files; refusing all changes')
    if oldheader is not None and oldapp!=target['apps/tpd.c']:raise ValueError('Mixed application version')
    changed=[n for n in target if current[n]!=target[n]]
    print(f'Interface: {matches[-1]}; target TPD {(ROOT/"VERSION").read_text().strip()}; {len(changed)} file(s) to update')
    if args.check or not changed:return
    # Back up all affected files before writing. Store outside the checkout.
    backup=Path(tempfile.mkdtemp(prefix='tpd-backup-'))
    (backup/'absent.json').write_text(json.dumps([n for n in changed if current[n] is None]))
    for n in changed:
        if current[n] is not None:
            p=backup/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(current[n])
    print(f'Recovery backup: {backup}',flush=True)
    def replace(n,data):
        p=host/n
        if data is None:p.unlink(missing_ok=True);return
        p.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.tpd-',dir=p.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(data)
            os.chmod(tmp,(p.stat().st_mode & 0o777) if p.exists() else 0o644)
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    if any(read_safe(host,n)!=current[n] for n in current):raise ValueError('Checkout changed during preflight; backup retained')
    try:
        for n in changed:replace(n,target[n])
    except BaseException:
        for n in changed:replace(n,current[n])
        raise
    print('TPD integrated; run make iso check in HoofTTY')
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as e:raise SystemExit(str(e))
