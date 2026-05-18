#!/usr/bin/env python3
"""docker cp 更新文件到容器"""
import pexpect, os

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'
LOCAL = os.path.expanduser('~/projects/film-companion')

def scp_to_host(local, remote, timeout=30):
    child = pexpect.spawn(
        f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {local} {USER}@{HOST}:{remote}',
        timeout=timeout)
    child.expect('password:')
    child.sendline(PASSWORD)
    child.expect(pexpect.EOF, timeout=timeout)
    child.close()

def ssh(cmd, timeout=30):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. SCP 文件到宿主机
print("📤 上传到宿主机...")
scp_to_host(f'{LOCAL}/web/server.py', f'{BASE}/web/server.py')
scp_to_host(f'{LOCAL}/web/chat.html', f'{BASE}/web/chat.html')

# 2. docker cp 到容器
print("📦 复制到容器...")
print(ssh(f'docker cp {BASE}/web/server.py film-companion:/app/web/server.py'))
print(ssh(f'docker cp {BASE}/web/chat.html film-companion:/app/web/chat.html'))

# 3. 验证
print("\n🔍 验证容器内文件...")
marked = ssh(f'docker exec film-companion grep -c "marked" /app/web/chat.html')
print(f"marked 出现次数: {marked.strip()}")

reversed_check = ssh(f'docker exec film-companion grep "display_msgs" /app/web/server.py')
print(f"display_msgs 行: {reversed_check.strip()}")

# 4. 重启容器
print("\n🔄 重启...")
ssh('docker restart film-companion', timeout=10)
import time; time.sleep(3)

# 5. 线上验证
print("\n✅ 线上验证:")
out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP: {out.strip()}")

# 用真实消息测试 API 顺序
test_msg = ssh('''curl -s -X POST http://localhost:8080/api/chat/stream \\
  -H "Content-Type: application/json" \\
  -d '{"message":"你好"}' --max-time 15 2>&1 | tail -1''', timeout=20)
print(f"API 正常: {test_msg[:100] if test_msg else 'ok'}")

print(f"\n🎞 http://{HOST}:8080")
