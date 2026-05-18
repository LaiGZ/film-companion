#!/usr/bin/env python3
"""最终 — 清华源 + 长超时"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def ssh(cmd, timeout=300):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. SCP 新 Dockerfile
print("📤 上传 Dockerfile（清华源版）...")
child = pexpect.spawn(
    f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
    f'{os.path.expanduser("~/projects/film-companion/Dockerfile")} '
    f'{USER}@{HOST}:{BASE}/Dockerfile', timeout=30)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(pexpect.EOF, timeout=30)
child.close()
print("✅ 已上传")

# 验证
out = ssh(f'cat {BASE}/Dockerfile', timeout=10)
print(out)

# 2. 构建（给 5 分钟）
print("\n=== 构建镜像 ===")
out = ssh(f'docker build -t film-companion -f {BASE}/Dockerfile {BASE}', timeout=300)
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['Success', 'ERROR', 'DONE', 'RUN', 'error', 'failed']):
        print(f"  {s[:150]}")
print(f"  (共 {len(out)} 字符)")

# 3. 检查
print("\n=== 检查 ===")
out = ssh('docker images film-companion', timeout=10)
print(out)

if 'film-companion' in out and 'latest' in out:
    print("✅ 镜像构建成功！")
    print("\n=== 启动 ===")
    ssh(f'docker rm -f film-companion 2>/dev/null', timeout=10)
    out = ssh(f'docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion', timeout=10)
    print(f"  Container: {out.strip()[:20]}")
    
    time.sleep(5)
    print("\n=== 验证 ===")
    print(ssh('docker ps --format "table {{.Names}}\t{{.Status}}"'))
    http = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
    print(f"HTTP: {http.strip()}")
    
    if http.strip() == '200':
        print(f"\n🎉 http://{HOST}:8080")
    else:
        print("\n日志:")
        print(ssh('docker logs film-companion --tail 20'))
else:
    print("❌ 构建失败")
