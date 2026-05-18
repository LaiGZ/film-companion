#!/usr/bin/env python3
"""检查当前状态并继续构建"""
import pexpect, os

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
print("✅ 已登录")

def run(cmd, timeout=60):
    print(f"\n> {cmd}")
    child.sendline(cmd)
    child.expect(r'\$', timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    for l in out.strip().split('\n')[1:]:
        print(f"  {l.strip()}")
    return out

# 状态检查
run('sg docker -c "docker ps -a" 2>&1', timeout=10)
run(f'cat {BASE}/.env', timeout=5)
run(f'ls -la {BASE}/docker-compose.yml {BASE}/Dockerfile {BASE}/requirements.txt {BASE}/main.py', timeout=5)
run('sg docker -c "docker image ls python" 2>&1', timeout=10)

# 构建
print("\n=== 🚀 开始构建并启动 ===")
child.sendline(f'sg docker -c "docker compose -f {BASE}/docker-compose.yml up -d --build" 2>&1')
# 等最多 10 分钟构建
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=600)
out = child.before.decode('utf-8', errors='replace')
# 只打印关键部分
for line in out.split('\n'):
    if any(k in line for k in ['Step', 'RUN', 'COPY', 'Success', 'Error', 'error', 'WARN', 'failed', 'Layer']):
        print(f"  {line.strip()}")
print(f"\n--- 最后 500 字符 ---")
print(out[-500:])

# 验证
run('sg docker -c "docker compose -f {BASE}/docker-compose.yml ps" 2>&1', timeout=10)
run('curl -s -o /dev/null -w "%{{http_code}}" http://localhost:8080/', timeout=10)

child.sendline('exit')
child.close()
print(f"\n🎞 http://{HOST}:8080")
