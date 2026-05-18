#!/usr/bin/env python3
"""最终部署 — 无 apt Dockerfile"""
import pexpect, os, time

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

def run(cmd, timeout=180):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

# 1. SCP 新 Dockerfile
print("📤 上传新 Dockerfile...")
child = pexpect.spawn(
    f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
    f'{os.path.expanduser("~/projects/film-companion/Dockerfile")} '
    f'{USER}@{HOST}:{BASE}/Dockerfile',
    timeout=30
)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(pexpect.EOF, timeout=30)
child.close()

# 确认上传成功
out = run(f'head -10 {BASE}/Dockerfile', timeout=10)
if 'RUN apt' not in out and 'RUN pip' in out:
    print("✅ 无 apt 版本已上传")
else:
    print("⚠️ Dockerfile 可能有问题，先看看:")
    print(out)

# 2. 构建
print("\n🏗️  构建镜像...")
out = run(f'cd {BASE} && docker build -t film-companion . 2>&1', timeout=300)
for l in out.split('\n'):
    s = l.strip()
    if any(k in s for k in ['Success', 'ERROR', 'failed', 'RUN pip', 'COPY']):
        print(f"  {s[:150]}")
print(f"  (共 {len(out)} 字符)")

# 3. 启动
print("\n🚀 启动容器...")
out = run(f'docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion', timeout=30)
container_id = out.strip()
print(f"  Container: {container_id[:20]}...")

# 4. 等待和验证
time.sleep(5)
print("\n✅ 验证:")
out = run('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
print(out)

out = run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
print(f"HTTP: {out.strip()}")

if out.strip() == '200':
    print(f"\n🎉 部署成功！")
    print(f"   访问: http://{HOST}:8080")
else:
    # 看日志
    print("\n⚠️ 服务未响应，查看日志...")
    logs = run(f'docker logs film-companion --tail 20', timeout=10)
    print(logs)
