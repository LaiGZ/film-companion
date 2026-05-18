#!/usr/bin/env python3
"""推送前端+后端改动到服务器"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'
LOCAL = os.path.expanduser('~/projects/film-companion')

def ssh(cmd, timeout=30):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

def scp(local, remote, timeout=30):
    child = pexpect.spawn(
        f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {local} {USER}@{HOST}:{remote}',
        timeout=timeout)
    child.expect('password:')
    child.sendline(PASSWORD)
    child.expect(pexpect.EOF, timeout=timeout)
    child.close()

# 1. SCP 两个改动的文件
print("📤 上传 server.py...")
scp(f'{LOCAL}/web/server.py', f'{BASE}/web/server.py')

print("📤 上传 chat.html...")
scp(f'{LOCAL}/web/chat.html', f'{BASE}/web/chat.html')

# 2. 重启容器
print("\n🔄 重启容器...")
ssh(f'docker restart film-companion', timeout=10)
time.sleep(3)

# 3. 验证
print("\n✅ 验证:")
out = ssh('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
print(out)

out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP: {out.strip()}")

if out.strip() == '200':
    print(f"\n🎉 http://{HOST}:8080")
else:
    print(ssh('docker logs film-companion --tail 10'))
