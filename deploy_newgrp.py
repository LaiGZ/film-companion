#!/usr/bin/env python3
"""交互式 SSH 部署"""
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
print("✅ SSH 已登录")

def run(cmd, timeout=60):
    child.sendline(cmd)
    i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    # 只打印最后几行
    lines = [l.strip() for l in out.split('\n') if l.strip()]
    for l in lines[-5:]:
        if 'aideploy' not in l and '\\x1b' not in l:
            print(f"  {l}")
    return out

# 用 newgrp 进入 docker 组
print("=== 1. 构建镜像 ===")
child.sendline(f'newgrp docker <<EOF\ndocker build -t film-companion {BASE}\nEOF')
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=300)
out = child.before.decode('utf-8', errors='replace')
# 只打印构建关键行
for l in out.split('\n'):
    if any(k in l for k in ['Success', 'Error', 'error', 'exporting', 'DONE', 'BUILD']):
        print(f"  {l.strip()}")
print(f"  ...({len(out)} chars total)")

print("\n=== 2. 停止旧容器 ===")
run(f'newgrp docker <<< "docker rm -f film-companion 2>/dev/null"', timeout=10)

print("\n=== 3. 启动容器 ===")
run(f'newgrp docker <<< "docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion"', timeout=30)

print("\n=== 4. 验证 ===")
run('newgrp docker <<< "docker ps --format table{{.Names}}\\\\t{{.Status}}"', timeout=10)

time.sleep(3)
run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)

child.sendline('exit')
child.close()
print(f"\n🎞 http://{HOST}:8080")
