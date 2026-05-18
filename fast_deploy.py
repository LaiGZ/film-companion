#!/usr/bin/env python3
"""快速部署 — 简化 Dockerfile + scp + 启动"""
import pexpect, os, time

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

# 1. 先杀掉卡住的构建
print("=== 清理 ===")
out = ssh(f'sg docker -c "docker compose -f {BASE}/docker-compose.yml down 2>/dev/null; docker kill $(docker ps -q) 2>/dev/null; echo ok" 2>&1', timeout=10)
print(out)

# 2. SCP 新的 Dockerfile
print("\n=== 上传新 Dockerfile ===")
local_dockerfile = os.path.expanduser('~/projects/film-companion/Dockerfile')
child = pexpect.spawn(
    f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {local_dockerfile} {USER}@{HOST}:{BASE}/Dockerfile',
    timeout=30
)
i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
if i == 0:
    child.sendline(PASSWORD)
    child.expect(pexpect.EOF, timeout=30)
child.close()
print("✅ Dockerfile 已上传")

# 3. 启动
print("\n=== 构建并启动 ===")
out = ssh(f'sg docker -c "docker compose -f {BASE}/docker-compose.yml up -d --build" 2>&1', timeout=300)
print(out[-1000:])

# 4. 验证
print("\n=== 验证 ===")
out = ssh(f'sg docker -c "docker compose -f {BASE}/docker-compose.yml ps" 2>&1')
print(out)

out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1')
print(f"\nHTTP: {out}")

print(f"\n🎞 http://{HOST}:8080")
