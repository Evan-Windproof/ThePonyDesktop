#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib, importlib.util, json, subprocess, sys, tempfile, unittest, shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
HOST=Path(sys.argv.pop(1)).resolve()
spec=importlib.util.spec_from_file_location('manager',ROOT/'integration/manage.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tpd test ');self.addCleanup(self.tmp.cleanup)
        self.h=Path(self.tmp.name)/'HoofTTY'
        subprocess.run(['git','clone','-q','--shared',str(HOST),str(self.h)],check=True)
        m.git(self.h,'checkout','-q','--detach',m.BASE)
    def install(self,ok=True,check=False):
        r=subprocess.run([sys.executable,str(ROOT/'integration/manage.py'),str(self.h)]+(['--check'] if check else []),capture_output=True,text=True)
        self.assertEqual(r.returncode==0,ok,r.stdout+r.stderr)
        return r
    def snapshot(self):
        return {str(p.relative_to(self.h)):p.read_bytes() for p in self.h.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.h).parts}
    def legacy(self,v):
        m.git(self.h,'apply',str(ROOT/f'integration/hooftty-v{v}.patch'))
        (self.h/'apps/tpd.c').write_bytes((ROOT/f'tests/fixtures/tpd-{v}.c').read_bytes())
    def test_fresh_repeat_check(self):
        before=self.snapshot();self.install(check=True);self.assertEqual(before,self.snapshot())
        self.install();after=self.snapshot();self.install();self.assertEqual(after,self.snapshot())
    def test_upgrade_both(self):
        for v in ('0.1.0','0.1.1'):
            with self.subTest(v=v):
                profiles,target=m.plans(self.h)
                # restore only test fixture's managed paths between cases
                for n in target:(self.h/n).unlink(missing_ok=True)
                for n,b in profiles['base'].items():
                    if b is not None:(self.h/n).write_bytes(b)
                self.legacy(v);self.install()
                self.assertTrue(all((self.h/n).read_bytes()==b for n,b in target.items()))
    def test_unknown_sources_preserved(self):
        self.legacy('0.1.1');(self.h/'apps/tpd.c').write_text('local edit\n')
        before=self.snapshot();self.install(ok=False);self.assertEqual(before,self.snapshot())
    def test_unknown_kernel_preserved(self):
        p=self.h/'kernel/drivers/framebuffer.c';p.write_text(p.read_text()+'\n/* edit */\n')
        before=self.snapshot();self.install(ok=False);self.assertEqual(before,self.snapshot())
    def test_unrelated_edits_preserved(self):
        p=self.h/'README.md';p.write_text('local readme');self.install();self.assertEqual(p.read_text(),'local readme')
    def test_symlink_refused(self):
        p=self.h/'apps/tpd.c';p.symlink_to('/tmp/tpd-no-overwrite')
        self.install(ok=False);self.assertTrue(p.is_symlink())
    def test_abi_refused(self):
        (self.h/'apps/abi.h').write_text('unknown');before=self.snapshot()
        self.install(ok=False);self.assertEqual(before,self.snapshot())
    def test_partial_interface_refused(self):
        self.legacy('0.1.1');(self.h/'include/kernseed/pixels.h').unlink()
        before=self.snapshot();self.install(ok=False);self.assertEqual(before,self.snapshot())
    def test_write_failure_rolls_back(self):
        before=self.snapshot();real=m.os.replace;calls=0
        def fail_once(*args):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected failure')
            return real(*args)
        with patch.object(sys,'argv',['manage',str(self.h)]),patch.object(m.os,'replace',side_effect=fail_once):
            with self.assertRaises(OSError):m.main()
        self.assertEqual(before,self.snapshot())
    def test_version_header_dependency(self):
        self.install();p=self.h/'Makefile'
        self.assertIn(b'$(BUILD)/apps/tpd.elf: apps/tpd_version.h',p.read_bytes())
        self.assertIn((ROOT/'VERSION').read_text().strip(),(self.h/'apps/tpd_version.h').read_text())
    def test_staged_changes_preserved(self):
        (self.h/'README.md').write_text('staged local edit')
        m.git(self.h,'add','README.md');before=m.git(self.h,'diff','--cached','--binary')
        self.install();self.assertEqual(before,m.git(self.h,'diff','--cached','--binary'))
    def test_version_only_bump(self):
        self.install();source=(self.h/'apps/tpd.c').read_bytes()
        package=Path(self.tmp.name)/'package';package.mkdir()
        for name in ('integration','src'):shutil.copytree(ROOT/name,package/name)
        (package/'VERSION').write_text('0.1.3\n')
        with patch.object(m,'ROOT',package),patch.object(sys,'argv',['manage',str(self.h)]):m.main()
        self.assertEqual(source,(self.h/'apps/tpd.c').read_bytes())
        self.assertIn(b'0.1.3',(self.h/'apps/tpd_version.h').read_bytes())
    def test_fixture_hashes(self):
        known=json.loads((ROOT/'integration/legacy-apps.json').read_text())
        for v,d in known.items():self.assertEqual(hashlib.sha256((ROOT/f'tests/fixtures/tpd-{v}.c').read_bytes()).hexdigest(),d)
if __name__=='__main__':unittest.main()
