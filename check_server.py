#!/usr/bin/env python3
"""检查服务器状态"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
REMOTE_DIR = '/home/aideploy/film-companion'

def ssh(cmd):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=30)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=30)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

print("=== 远程目录 ===")
print(ssh(f'ls -la {REMOTE_DIR}/'))

print("\n=== 查找 docker-compose ===")
print(ssh(f'find {REMOTE_DIR} -name "docker-compose*" -o -name "Dockerfile" 2>/dev/null'))

print("\n=== 当前 docker 状态 ===")
print(ssh('docker ps -a 2>&1'))
