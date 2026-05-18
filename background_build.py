#!/usr/bin/env python3
"""一次性构建+启动"""
import pexpect, os, sys

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=60):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# Step 1: 后台构建（nohup 避免 SSH 断开影响）
print("=== 1. 后台构建 ===")
ssh(f'nohup bash -c "cd {BASE} && docker build -t film-companion ." > {BASE}/build.log 2>&1 &', timeout=10)
print("   构建已在后台启动，等 60 秒...")

import time
time.sleep(60)

# Step 2: 查看构建日志
print("\n=== 2. 构建日志（最后 20 行）===")
log = ssh(f'tail -20 {BASE}/build.log', timeout=10)
print(log)

# Step 3: 检查镜像
print("\n=== 3. 检查镜像 ===")
out = ssh('docker images film-companion', timeout=10)
print(out)

# Step 4: 启动
if 'film-companion' in out:
    print("\n=== 4. 启动容器 ===")
    out = ssh(f'docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion', timeout=30)
    print(f"   {out.strip()}")
    
    time.sleep(5)
    print("\n=== 5. 验证 ===")
    out = ssh('docker ps --format "table {{.Names}}\\t{{.Status}}"', timeout=10)
    print(out)
    out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
    print(f"HTTP: {out.strip()}")
else:
    print("\n❌ 构建失败，看完整日志：")
    print(ssh(f'cat {BASE}/build.log', timeout=10))

print(f"\n🎞 http://{HOST}:8080")
