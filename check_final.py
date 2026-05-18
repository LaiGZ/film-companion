#!/usr/bin/env python3
"""检查服务器状态"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}', timeout=10)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

def run(cmd, timeout=30):
    child.sendline(cmd)
    child.expect(r'\$', timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    for l in out.split('\n'):
        s = l.strip()
        if s and 'aideploy' not in s and '\\x1b' not in s and not s.startswith('['):
            print(f"  {s[:120]}")
    return out

print("=== Docker 镜像 ===")
run('docker images')

print("\n=== Docker 容器 ===")
run('docker ps -a')

print("\n=== Dockerfile 内容 ===")
run(f'cat {BASE}/Dockerfile')

print("\n=== 本地直接启动（如果镜像存在） ===")
# 如果 film-companion 镜像存在就直接启动
run('docker inspect film-companion 2>/dev/null && echo "镜像存在" || echo "无镜像"')

child.sendline('exit')
child.close()
