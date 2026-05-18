#!/usr/bin/env python3
"""直接构建 — 修复 sg 参数"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def sg(cmd, timeout=60):
    """sg 语法: sg group command (不需要 -c 标志)"""
    child = pexpect.spawn(
        f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} sg docker "{cmd}"',
        timeout=timeout
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 验证 sg 正确
print("=== 验证 sg ===")
out = sg('docker ps')
print(out)

# 构建
print("\n=== 构建镜像 ===")
out = sg(f'docker build -t film-companion {BASE}', timeout=300)
print(out[-500:])

# 停止旧容器
print("\n=== 停止旧容器 ===")
sg('docker rm -f film-companion 2>/dev/null')

# 启动
print("\n=== 启动 ===")
out = sg(f'docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion', timeout=30)
print(out)

# 验证
print("\n=== 验证 ===")
out = sg('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')
print(out)

time.sleep(3)
out = sg('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
print(f"\nHTTP: {out}")

print(f"\n🎞 http://{HOST}:8080")
