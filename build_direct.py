#!/usr/bin/env python3
"""指定路径构建"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=30):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. 检查文件
print("=== 确认文件 ===")
out = ssh(f'ls -la {BASE}/Dockerfile {BASE}/requirements.txt {BASE}/main.py')
print(out)

# 2. 直接构建（显式指定 Dockerfile 路径）
print("\n=== 构建镜像 ===")
out = ssh(f'docker build -t film-companion -f {BASE}/Dockerfile {BASE}', timeout=120)
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['ERROR', 'Success', 'DONE', 'RUN', 'COPY', 'failed', 'exporting']):
        print(f"  {s[:150]}")
print(f"  (输出共 {len(out)} 字符)")

# 3. 检查结果
print("\n=== 检查镜像 ===")
out = ssh('docker images film-companion')
print(out)

# 4. 启动
if 'film-companion' in out and 'latest' in out:
    print("\n=== 启动容器 ===")
    out = ssh(f'docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion')
    print(f"  {out.strip()}")
    
    time.sleep(5)
    print("\n=== 验证 ===")
    out = ssh('docker ps')
    print(out)
    out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
    print(f"HTTP: {out.strip()}")
    
    if out.strip() == '200':
        print(f"\n🎉 http://{HOST}:8080")
    else:
        print("\n=== 日志 ===")
        print(ssh('docker logs film-companion --tail 20'))
else:
    print("❌ 构建失败")
