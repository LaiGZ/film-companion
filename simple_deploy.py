#!/usr/bin/env python3
"""极简部署 v3 — 直接用 docker"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def run(cmd, timeout=180):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. 先确认 docker 已加入组（新 SSH 会话应该生效）
print("=== Docker 检查 ===")
out = run('docker ps', timeout=10)
print(out[:200])

# 2. 构建
print("\n=== 构建镜像 ===")
out = run(f'cd {BASE} && docker build -t film-companion . 2>&1', timeout=300)
# 只看最后几行
lines = out.strip().split('\n')
for l in lines[-10:]:
    print(f"  {l.strip()[:150]}")

# 3. 启动
print("\n=== 启动容器 ===")
out = run(f'docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion', timeout=30)
print(f"  {out.strip()}")

# 4. 验证
import time
time.sleep(3)
print("\n=== 验证 ===")
out = run('docker ps --format "table {{.Names}}\\t{{.Status}}"', timeout=10)
print(out)

out = run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"\nHTTP: {out.strip()}")

print(f"\n🎞 http://{HOST}:8080")
