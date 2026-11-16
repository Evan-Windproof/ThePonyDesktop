#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real guest keyboard/mouse input and VGA pixel checks. Usage: script HOOFTTY."""
import sys,os,time,subprocess,tempfile,re
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT/'tests'))
from boot import QMP,wait_for
OUT=Path(__file__).resolve().parents[1]/'test-results'
OUT.mkdir(exist_ok=True)
serial=OUT/'serial.log'; serial.write_text('')
with tempfile.TemporaryDirectory(prefix='tpd-') as d:
    sock=Path(d)/'qmp'; gdbsock=Path(d)/'gdb'
    args=[os.environ.get('QEMU','qemu-system-x86_64'),'-L',os.environ.get('QEMU_DATA','/usr/share/qemu'),'-machine','pc,accel=tcg','-m','128','-smp','1','-vga','std','-display','none','-nic','none','-cdrom',str(ROOT/'build/kernseed.iso'),'-serial',f'file:{serial}','-qmp',f'unix:{sock},server=on,wait=off','-monitor','none','-no-reboot','-gdb',f'unix:{gdbsock},server=on,wait=off']
    if os.environ.get('QEMU_BIOS'):args+=['-bios',os.environ['QEMU_BIOS']]
    with (OUT/'qemu.stderr').open('w') as err:
        p=subprocess.Popen(args,stderr=err,stdout=subprocess.DEVNULL)
        q=None
        try:
            wait_for(sock.exists,p,'QMP');q=QMP(sock)
            wait_for(lambda:'hoof> ' in serial.read_text(),p,'HoofTTY Shell')
            def key(c):
                q.command('send-key',{'keys':[{'type':'qcode','data':{' ':'spc','\n':'ret'}.get(c,c)}],'hold-time':20});time.sleep(.06)
            def cmd(s,expected):
                n=len(serial.read_text())
                for c in s+'\n':key(c)
                wait_for(lambda:expected in serial.read_text()[n:],p,s)
            def move(dx,dy):
                q.command('input-send-event',{'events':[{'type':'rel','data':{'axis':'x','value':dx}},{'type':'rel','data':{'axis':'y','value':dy}}]});time.sleep(.4)
            def button(down):
                q.command('input-send-event',{'events':[{'type':'btn','data':{'down':down,'button':'left'}}]});time.sleep(.3)
            def screen(name):
                time.sleep(.3);path=OUT/(name+'.ppm');q.command('screendump',{'filename':str(path)})
                with path.open('rb') as f:
                    assert f.readline().strip()==b'P6';w,h=map(int,f.readline().split());assert f.readline().strip()==b'255';data=f.read()
                assert (w,h)==(800,600)
                return lambda x,y:data[(y*w+x)*3:(y*w+x+1)*3]
            cmd('echo baseline','baseline\n');cmd('run hello','hoof> ')
            def memory():
                n=len(serial.read_text());cmd('meminfo','hoof> ')
                m=re.search(r'allocated=(\d+) tables=(\d+) mapped=(\d+)',serial.read_text()[n:])
                assert m,serial.read_text()[n:]
                return tuple(map(int,m.groups()))
            baseline=memory()
            for cycle in range(2):
                cmd('run tpd','Ring 3 desktop ready')
                if cycle==0:
                    # Read actual guest diagnostics while stopped, without modifying state.
                    q.command('stop')
                    r=subprocess.run([os.environ.get('GDB','gdb'),'-nx','-batch',
                        '-ex',f'file {ROOT}/build/kernseed.elf','-ex',f'target remote {gdbsock}',
                        '-ex','p/x user_state','-ex','p graphics_owned','-ex','detach'],capture_output=True,text=True,timeout=15)
                    (OUT/'gdb.log').write_text(r.stdout+r.stderr)
                    assert r.returncode==0 and 'last_cs = 0x2b' in r.stdout and 'active = 0x1' in r.stdout and '= true' in r.stdout,r.stdout+r.stderr
                    q.command('cont')
                px=screen('desktop'+str(cycle));assert px(10,200)==bytes.fromhex('244754');assert px(65,65)==bytes.fromhex('345c80')
                if cycle==0:
                    # Break movement into PS/2-range packets. Title starts at 60,60.
                    move(-100,-100);move(-100,-100);move(-100,-25)
                    button(True);wait_for(lambda:'TPD: drag begin' in serial.read_text(),p,'title drag')
                    move(100,80);button(False)
                    px=screen('dragged');assert px(65,65)==bytes.fromhex('244754');assert px(165,145)==bytes.fromhex('345c80')
                    move(100,0);move(100,0);move(40,0) # cursor now 440,155; close at 432..454
                    button(True);button(False)
                    wait_for(lambda:'TPD: window closed' in serial.read_text(),p,'close button')
                    px=screen('closed');assert px(165,145)==bytes.fromhex('244754')
                n=len(serial.read_text());key('q')
                wait_for(lambda:'hoof> ' in serial.read_text()[n:],p,'Shell restore')
                cmd('echo restored','restored\n');assert memory()==baseline,'user pages or task stack not reclaimed'
            # Third session exits through the taskbar, independently of Q.
            cmd('run tpd','Ring 3 desktop ready');move(100,100);move(100,100);move(100,85);move(45,0)
            n=len(serial.read_text());button(True);button(False)
            wait_for(lambda:'hoof> ' in serial.read_text()[n:],p,'taskbar exit')
            assert memory()==baseline
            cmd('run privileged','User fault: task terminated')
            cmd('echo healthy','healthy\n')
            assert 'PANIC' not in serial.read_text()
            (OUT/'result.txt').write_text('PASS: boot, Shell, hello, desktop three times, CPL3 GDB evidence, resource reclamation, taskbar exit, pixels, mouse drag/close, q exit, Shell recovery, privileged fault containment.\n')
            print((OUT/'result.txt').read_text())
        finally:
            if q:q.close()
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
