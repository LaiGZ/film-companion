#!/usr/bin/env python3
"""检查当前部署状态"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=30):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

print("=== Docker 权限 ===")
print(ssh('sg docker -c "docker ps" 2>&1'))

print("\n=== 项目文件 ===")
print(ssh(f'ls -la {BASE}/docker-compose.yml {BASE}/.env {BASE}/Dockerfile 2>&1'))

print("\n=== .env 内容 ===")
print(ssh(f'cat {BASE}/.env'))

print("\n=== docker compose ps ===")
print(ssh(f'sg docker -c "cd {BASE} && docker compose ps" 2>&1'))

print("\n=== HTTP ===")
print(ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1'))
