#!/usr/bin/env python3
"""直接构建不用 compose"""
import pexpect, os, time

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

# 直接用 docker (不用 compose)，手动指定参数
print("=== 构建镜像 ===")
out = ssh(f'sg docker -c "docker build -t film-companion {BASE}" 2>&1', timeout=300)
print(out[-500:])

print("\n=== 停止旧容器 ===")
ssh('sg docker -c "docker rm -f film-companion 2>/dev/null" 2>&1')

print("\n=== 启动容器 ===")
out = ssh(f'sg docker -c "docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion" 2>&1', timeout=30)
print(out)

print("\n=== 验证 ===")
out = ssh('sg docker -c "docker ps --format \\"table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\\"" 2>&1')
print(out)

time.sleep(3)
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1')
print(f"\nHTTP: {out}")

print(f"\n🎞 http://{HOST}:8080")
