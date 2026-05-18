#!/usr/bin/env python3
"""一步到位 — 直接执行"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=120):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 先写个部署脚本到服务器上
script = f'''#!/bin/bash
cd {BASE}
docker rm -f film-companion 2>/dev/null
docker build -t film-companion .
docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion
'''

# 上传脚本
child = pexpect.spawn(
    f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -',
    timeout=30
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(pexpect.EOF, timeout=30)
child.close()

# 用 heredoc 写到服务器
print("=== 创建部署脚本 ===")
ssh(f'cat > {BASE}/deploy.sh << \'SCRIPTEOF\'\n{script}\nSCRIPTEOF\nchmod +x {BASE}/deploy.sh')
print("✅ 脚本已创建")

# 执行
print("\n=== 执行构建 ===")
out = ssh(f'cd {BASE} && bash deploy.sh 2>&1', timeout=300)
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['Success', 'Error', 'error', 'exporting', 'DONE', 'RUN', 'CACHED', 'failed', 'dead', 'container']):
        print(f"  {s[:150]}")

# 验证
print("\n=== 验证 ===")
out = ssh('docker ps --format "table {{.Names}}\\t{{.Status}}"', timeout=10)
print(out)

import time
time.sleep(2)
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"\nHTTP: {out}")
print(f"\n🎞 http://{HOST}:8080")
