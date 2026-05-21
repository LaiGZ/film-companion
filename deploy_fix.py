#!/usr/bin/env python3
"""修复部署 — 停旧启新 + 验证"""
import pexpect, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=60):
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

# 1. 停旧容器
print("=== 停旧容器 ===")
out = ssh('docker stop film-companion && docker rm film-companion', timeout=30)
print(out)
print("✅ 旧容器已移除")

# 2. 确认镜像已是最新
print("\n=== 检查镜像 ===")
out = ssh('docker images film-companion --format "{{.CreatedAt}}"', timeout=10)
print(f"  镜像创建时间: {out.strip()}")

# 3. 启动新容器
print("\n=== 启动新容器 ===")
out = ssh(
    f'docker run -d --name film-companion --restart unless-stopped -p 8080:8080 '
    f'-v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion',
    timeout=30
)
print(f"  {out.strip()}")

# 4. 验证
time.sleep(3)
print("\n=== 验证 ===")
out = ssh('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
print(out)
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP 状态: {out.strip()}")
print(f"\n🎞 http://{HOST}:8080")
