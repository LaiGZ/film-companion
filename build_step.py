#!/usr/bin/env python3
"""后台构建 + 日志轮询"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}',
    timeout=10
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)
print("✅ 登录成功")

# 1. 先试试 docker pull python:3.14-slim
print("\n=== 1. 拉取基础镜像（这步可能慢）===")
child.sendline(f'sg docker -c "docker pull python:3.14-slim" 2>&1')
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=180)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n'):
    print(f"  {l.strip()}")

# 2. 构建
print("\n=== 2. 构建镜像 ===")
child.sendline(f'sg docker -c "cd {BASE} && docker build -t film-companion ." 2>&1')
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=300)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n'):
    print(f"  {l.strip()}")

# 3. 启动
print("\n=== 3. 启动容器 ===")
child.sendline(f'sg docker -c "docker run -d --name film-companion -p 8080:8080 --restart unless-stopped -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion" 2>&1')
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
out = child.before.decode('utf-8', errors='replace')
print(out[-500:])

# 4. 验证
print("\n=== 4. 验证 ===")
child.sendline('sg docker -c "docker ps" 2>&1')
child.expect(r'\$', timeout=10)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n')[1:]:
    print(f"  {l.strip()}")

time.sleep(2)
child.sendline('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
child.expect(r'\$', timeout=10)
out = child.before.decode('utf-8', errors='replace')
print(f"\nHTTP: {out.split(chr(10))[1].strip() if chr(10) in out else out}")

child.sendline('exit')
child.close()
print(f"\n🎞 http://{HOST}:8080")
