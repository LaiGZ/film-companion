#!/usr/bin/env python3
"""快速检查服务器状态"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}',
    timeout=10
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

def run(cmd, timeout=10):
    child.sendline(cmd)
    child.expect(r'\$', timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    for l in out.split('\n'):
        l = l.strip()
        if l and 'aideploy' not in l and not l.startswith('\\x1b'):
            print(f"  {l}")

print("=== Docker 容器 ===")
run('newgrp docker <<< "docker ps -a"')

print("\n=== 文件 ===")
run(f'ls -la {BASE}/Dockerfile {BASE}/.env {BASE}/main.py')

print("\n=== .env ===")
run(f'cat {BASE}/.env')

print("\n=== Docker 镜像 ===")
run('newgrp docker <<< "docker images film-companion"')

child.sendline('exit')
child.close()
