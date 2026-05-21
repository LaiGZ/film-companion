#!/usr/bin/env python3
"""直接 docker cp 注入新前端文件 — 无需重构镜像"""
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

# 1. 先在服务器上创建临时目录，接收新文件
print("=== 创建临时目录 ===")
out = ssh(f'mkdir -p {BASE}/web/dist/assets', timeout=10)
print(out)

# 2. rsync 只传 dist 文件到服务器 tmp
print("\n=== 同步 dist 文件 ===")
child = pexpect.spawn(
    f'rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" '
    f'web/dist/ {USER}@{HOST}:{BASE}/web/dist/',
    timeout=60
)
i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=60)
if i == 0:
    child.sendline(PASSWORD)
    child.expect(pexpect.EOF, timeout=60)
out = child.before.decode('utf-8', errors='replace')
print(out[-300:] if len(out) > 300 else out)

# 3. docker cp 注入到容器
print("\n=== docker cp 注入容器 ===")
out = ssh(
    f'docker cp {BASE}/web/dist/index.html film-companion:/app/web/dist/ && '
    f'docker cp {BASE}/web/dist/assets film-companion:/app/web/dist/',
    timeout=30
)
print(out)
print("✅ 前端文件已注入容器")

# 4. 重启容器生效
print("\n=== 重启容器 ===")
out = ssh('docker restart film-companion', timeout=30)
print(out.strip())

# 5. 验证
time.sleep(3)
print("\n=== 验证 ===")
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP 状态: {out.strip()}")
out = ssh('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
print(out.strip())
print(f"\n🎞 http://{HOST}:8080")
