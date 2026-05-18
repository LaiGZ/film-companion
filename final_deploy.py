#!/usr/bin/env python3
"""修复并启动"""
import pexpect, os

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

def sg(cmd, timeout=120):
    return ssh(f"sg docker -c 'sh -c \"{cmd}\"' 2>&1", timeout=timeout)

# 1. 写 .env（用 printf，百分百可靠）
print("=== 写 .env ===")
env_path = os.path.expanduser('~/projects/film-companion/.env')
local_key = ''
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                local_key = line.strip().split('=', 1)[1]
                break
ssh(f"printf 'DEEPSEEK_API_KEY=%s\nLLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-v4-flash\n' '{local_key}' > {BASE}/.env")
print(ssh(f'cat {BASE}/.env'))

# 2. Docker 构建启动（用全路径指定 compose 文件）
print("\n=== Docker compose build + up ===")
YML = f'{BASE}/docker-compose.yml'
out = sg(f'docker compose -f {YML} up -d --build 2>&1', timeout=300)
print(out)

# 3. 验证
print("\n=== 容器 ===")
out = sg(f'docker compose -f {YML} ps')
print(out)

print("\n=== HTTP ===")
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1')
print(f"HTTP: {out}")

print(f"\n🎞 http://{HOST}:8080")
