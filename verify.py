#!/usr/bin/env python3
"""验证服务"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}', timeout=10)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

def run(cmd, timeout=10):
    child.sendline(cmd)
    child.expect(r'\$', timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    for l in out.split('\n'):
        s = l.strip()
        if s and 'aideploy' not in s and '\\x1b' not in s:
            print(f"  {s}")
    return out

run('docker ps')
run('docker logs film-companion --tail 10')
run('curl -s http://localhost:8080/ | head -5')
run('curl -s http://localhost:8080/data | head -3')

child.sendline('exit')
child.close()
print(f"\n🎞 http://{HOST}:8080")
