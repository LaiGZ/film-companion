#!/usr/bin/env python3
"""交互式部署 — 持久 SSH 会话"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'
YML = f'{BASE}/docker-compose.yml'

# 打开交互式 SSH 会话
child = pexpect.spawn(
    f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}',
    timeout=10
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)
print("✅ SSH 已登录")

def run(cmd, timeout=60, echo=True):
    if echo:
        print(f"\n> {cmd}")
    child.sendline(cmd)
    i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    if echo:
        # 去掉命令本身的回显
        lines = out.strip().split('\n')
        for l in lines[1:]:
            print(f"  {l.strip()}")
    return out

# 1. 写 .env
print("\n=== 写 .env ===")
env_path = os.path.expanduser('~/projects/film-companion/.env')
local_key = ''
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                local_key = line.strip().split('=', 1)[1]
                break
run(f"printf 'DEEPSEEK_API_KEY=%s\\nLLM_PROVIDER=deepseek\\nLLM_MODEL=deepseek-v4-flash\\n' '{local_key}' > {BASE}/.env")
run(f'cat {BASE}/.env')

# 2. 验证 docker
run('sg docker -c "docker ps" 2>&1', timeout=10)

# 3. 启动（用 sg，在交互式会话里不会超时）
print("\n=== 构建并启动 ===")
child.sendline(f'sg docker -c "docker compose -f {YML} up -d --build" 2>&1')
# 等最多 5 分钟
i = child.expect([r'\$', pexpect.EOF, pexpect.TIMEOUT], timeout=300)
out = child.before.decode('utf-8', errors='replace')
print(out[:2000])

# 4. 验证
run('sg docker -c "docker compose -f {YML} ps" 2>&1', timeout=10)
run('curl -s -o /dev/null -w "%{{http_code}}" http://localhost:8080/', timeout=10)

print(f"\n🎞 http://{HOST}:8080")
child.sendline('exit')
child.close()
