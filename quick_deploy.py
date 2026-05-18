#!/usr/bin/env python3
"""极简部署 — 一次性搞完"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

# 1. SCP 简化版 Dockerfile
child = pexpect.spawn(
    f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
    f'{os.path.expanduser("~/projects/film-companion/Dockerfile")} {USER}@{HOST}:{BASE}/Dockerfile',
    timeout=30
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(pexpect.EOF, timeout=30)
child.close()
print("✅ Dockerfile 已上传")

# 2. SSH 构建
child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}',
    timeout=10
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

# 2a. 验证 Dockerfile
child.sendline(f'head -5 {BASE}/Dockerfile')
child.expect(r'\$', timeout=5)

# 2b. 构建（只用 pip，没有 apt）
print("\n=== 🏗️ 构建镜像 ===")
child.sendline(f'newgrp docker <<< "docker build -t film-companion {BASE}"')
# 构建应该很快，只有 pip install
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=180)
out = child.before.decode('utf-8', errors='replace')
# 只看关键行
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['Success', 'Error', 'error', 'exporting', 'DONE', 'CACHED', 'RUN pip', 'COPY', 'failed']):
        print(f"  {s[:120]}")
print(f"  (构建输出共 {len(out)} 字符)")

# 2c. 启动
print("\n=== 🚀 启动容器 ===")
child.sendline(f'newgrp docker <<< "docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion"')
child.expect(r'\$', timeout=15)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n'):
    s = l.strip()
    if len(s) > 5 and 'aideploy' not in s:
        print(f"  {s}")

# 2d. 验证
time.sleep(3)
print("\n=== ✅ 验证 ===")
child.sendline('newgrp docker <<< "docker ps --format table{{.Names}}\\\\t{{.Status}}"')
child.expect(r'\$', timeout=10)
out = child.before.decode('utf-8', errors='replace')
for l in out.split('\n'):
    print(f"  {l.strip()}")

child.sendline('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
child.expect(r'\$', timeout=10)
out = child.before.decode('utf-8', errors='replace')
print(f"  HTTP: {out.split(chr(10))[1].strip() if chr(10) in out else out}")

child.sendline('exit')
child.close()
print(f"\n🎞 http://{HOST}:8080")
