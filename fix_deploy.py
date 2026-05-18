#!/usr/bin/env python3
"""修复部署"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE_DIR = '/home/aideploy/film-companion'

def ssh(cmd, timeout=60):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

print("=== 1. 修复目录结构 ===")
if os.path.exists(os.path.join(BASE_DIR, 'film-companion')):
    print(ssh(f'mv {BASE_DIR}/film-companion/* {BASE_DIR}/ && rm -rf {BASE_DIR}/film-companion'))
print(ssh(f'ls {BASE_DIR}/'))

print("\n=== 2. 修复 Docker 权限 ===")
# 添加用户到 docker 组
print(ssh('sudo usermod -aG docker aideploy 2>&1'))
print(ssh('id aideploy | grep docker'))

print("\n=== 3. 重启 Docker 服务（让组生效）===")
print(ssh('sudo systemctl restart docker 2>&1'))

print("\n=== 4. 验证 Docker ===")
print(ssh('docker ps 2>&1'))

print("\n=== 5. 启动服务 ===")
print(ssh(f'cd {BASE_DIR} && docker compose up -d 2>&1', timeout=120))

print("\n=== 6. 检查状态 ===")
print(ssh(f'cd {BASE_DIR} && docker compose ps'))
print(ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "服务启动中..."'))
