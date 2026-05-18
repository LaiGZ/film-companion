#!/usr/bin/env python3
"""继续部署 v2 — 用 sg 解决组权限"""
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
    """以 docker 组身份执行命令"""
    return ssh(f"sg docker -c '{cmd}' 2>&1", timeout=timeout)

# 1. 验证 sg 工作
print("=== Docker 权限测试 ===")
out = sg('docker ps')
print(out)

# 2. 写 .env
print("\n=== 写 .env ===")
env_path = os.path.expanduser('~/projects/film-companion/.env')
local_key = ''
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                local_key = line.strip().split('=', 1)[1]
                break
ssh(f'cat > {BASE}/.env << \\ENVEOF\nDEEPSEEK_API_KEY={local_key}\nLLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-v4-flash\nENVEOF')
print(ssh(f'cat {BASE}/.env'))

# 3. 确认 compose 文件存在
print("\n=== 确认文件 ===")
out = ssh(f'ls -la {BASE}/docker-compose.yml {BASE}/Dockerfile {BASE}/requirements.txt {BASE}/main.py 2>&1')
print(out)

# 4. Docker compose 构建 + 启动
print("\n=== Docker compose up -d ===")
# 先改 .env 权限让 docker 可以读
ssh(f'chmod 644 {BASE}/.env')
out = sg(f'cd {BASE} && docker compose up -d --build', timeout=300)
print(out)

# 5. 验证
print("\n=== 容器状态 ===")
out = sg(f'cd {BASE} && docker compose ps')
print(out)

print("\n=== HTTP 测试 ===")
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1 || echo "fail"')
print(f"HTTP: {out}")

print(f"\n🎞 访问: http://{HOST}:8080")
print(f"📊 数据: http://{HOST}:8080/data")
