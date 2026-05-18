#!/usr/bin/env python3
"""继续部署"""
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

# 1. 验证 docker 权限
print("=== 验证 Docker 权限 ===")
out = ssh('newgrp docker <<< "docker ps" 2>&1')
print(out)

# 2. 重新写 .env（确保有内容）
print("\n=== 检查 .env ===")
env_path = os.path.expanduser('~/projects/film-companion/.env')
local_key = ''
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                local_key = line.strip().split('=', 1)[1]
                break
env_content = f'DEEPSEEK_API_KEY={local_key}\nLLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-v4-flash\n'
ssh(f"printf '%s' '{env_content}' > {BASE}/.env")
print(ssh(f'cat {BASE}/.env'))

# 3. Docker compose 启动（用 newgrp 让组生效）
print("\n=== 启动 Docker compose ===")
out = ssh(f"newgrp docker <<< 'cd {BASE} && docker compose up -d' 2>&1", timeout=120)
print(out)

time.sleep(3)

# 4. 验证
print("\n=== 容器状态 ===")
out = ssh(f"newgrp docker <<< 'cd {BASE} && docker compose ps' 2>&1")
print(out)

print("\n=== HTTP 测试 ===")
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1')
print(f"HTTP: {out}")

print(f"\n🎉 访问地址: http://{HOST}:8080")
