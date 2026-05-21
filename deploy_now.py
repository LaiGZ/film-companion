#!/usr/bin/env python3
"""一键部署 — rsync + docker build"""
import pexpect, os, sys, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=120):
    child = pexpect.spawn(
        f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}',
        timeout=timeout
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# Step 1: rsync 整个项目
print("=== 同步文件到服务器 ===")
child = pexpect.spawn(
    f'rsync -avz --delete -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" '
    f'--exclude=__pycache__ --exclude=.git --exclude=node_modules --exclude=.venv '
    f'--exclude=*.egg-info '
    f'./ {USER}@{HOST}:{BASE}/',
    timeout=120
)
i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=120)
if i == 0:
    child.sendline(PASSWORD)
    child.expect(pexpect.EOF, timeout=120)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n'):
    if l.strip() and not l.startswith('receiving') and not l.startswith('sent') and 'speedup' not in l:
        print(f"  {l.strip()[:120]}")
print("✅ 文件同步完成")

# Step 2: 构建并启动
print("\n=== 构建 Docker 镜像 ===")
out = ssh(f'cd {BASE} && docker rm -f film-companion 2>/dev/null; docker build -t film-companion . 2>&1', timeout=300)
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['Step', 'Success', 'exporting', 'DONE', 'RUN', 'CACHED', 'error', 'Error']):
        print(f"  {s[:150]}")
print("✅ 镜像构建完成")

print("\n=== 启动容器 ===")
out = ssh(
    f'docker run -d --name film-companion --restart unless-stopped -p 8080:8080 '
    f'-v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion',
    timeout=30
)
print(f"  {out.strip()}")

# Step 3: 验证
time.sleep(3)
print("\n=== 验证 ===")
out = ssh('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
print(out)
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP 状态: {out}")
print(f"\n🎞 http://{HOST}:8080")
