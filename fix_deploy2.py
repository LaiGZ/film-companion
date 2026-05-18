#!/usr/bin/env python3
"""修复部署 v2"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'

def ssh(cmd, timeout=60):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

def ssh_sudo(cmd, timeout=60):
    """SSH with sudo -S"""
    full_cmd = f"echo '{PASSWORD}' | sudo -S bash -c '{cmd}'"
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {full_cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. 检查实际目录结构
print("=== 1. 目录结构 ===")
out = ssh('find /home/aideploy/film-companion -maxdepth 3 -type f | head -20')
print(out)

print("\n=== 2. 修复目录（把文件从子目录移到顶层）===")
ssh('rm -f /home/aideploy/film-companion/film-companion/.env 2>/dev/null')
ssh('cp -r /home/aideploy/film-companion/film-companion/* /home/aideploy/film-companion/ 2>/dev/null')
ssh('cp -r /home/aideploy/film-companion/film-companion/.* /home/aideploy/film-companion/ 2>/dev/null')
ssh('rm -rf /home/aideploy/film-companion/film-companion')
print("  修复完成")
out = ssh('ls -la /home/aideploy/film-companion/ | head -20')
print(out)

print("\n=== 3. 添加 Docker 组 ===")
out = ssh_sudo('usermod -aG docker aideploy')
print(out)

print("\n=== 4. 设置 Docker socket 权限 ===")
out = ssh_sudo('chmod 666 /var/run/docker.sock')
print(out)

print("\n=== 5. 验证 Docker ===")
out = ssh('docker ps 2>&1')
print(out)

print("\n=== 6. 创建 .env ===")
# 从本地 .env 读取 DeepSeek key
local_key = ''
env_path = os.path.expanduser('~/projects/film-companion/.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                local_key = line.strip().split('=', 1)[1]
                break

env_content = f'DEEPSEEK_API_KEY={local_key}\nLLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-v4-flash\n'
ssh(f"printf '%s' '{env_content}' > /home/aideploy/film-companion/.env")
print(f"  KEY: {local_key[:10]}...{local_key[-4:]}")
print(ssh('cat /home/aideploy/film-companion/.env'))

print("\n=== 7. Docker compose 启动 ===")
out = ssh('cd /home/aideploy/film-companion && docker compose up -d 2>&1', timeout=120)
print(out)

print("\n=== 8. 验证 ===")
out = ssh('cd /home/aideploy/film-companion && docker compose ps 2>&1')
print(out)

out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>&1')
print(f"\nHTTP 状态码: {out}")
