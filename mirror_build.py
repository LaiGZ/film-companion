#!/usr/bin/env python3
"""带清华镜像的构建"""
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

# 用清华镜像写一个新的 requirements.txt 写法
# 最简单的方法：在 Dockerfile 里加 pip config
print("=== 1. 给 Dockerfile 加清华源 ===")
ssh(f"sed -i 's/RUN pip install/RUN pip config set global.index-url https:\\/\\/pypi.tuna.tsinghua.edu.cn\\/simple \\&\\& pip install/' {BASE}/Dockerfile")
print(ssh(f'cat {BASE}/Dockerfile'))

# 2. 后台构建（不阻塞）
print("\n=== 2. 启动后台构建 ===")
ssh(f'docker build -t film-companion -f {BASE}/Dockerfile {BASE} > {BASE}/build.log 2>&1 &', timeout=10)

# 3. 等 30 秒后检查进度
print("   等待 30 秒...")
time.sleep(30)

print("\n=== 3. 构建进度 ===")
print(ssh(f'tail -5 {BASE}/build.log'))

# 4. 持续轮询，最多等 5 分钟
for i in range(10):
    time.sleep(30)
    out = ssh(f'tail -3 {BASE}/build.log')
    if 'Successfully built' in out or 'ERROR' in out:
        print(f"\n=== 构建完成（{i*30+30}秒）===")
        print(out)
        break
    print(f"  正在构建... ({i*30+60}秒)")

# 5. 检查结果
print("\n=== 4. 检查镜像 ===")
out = ssh('docker images film-companion')
print(out)

if 'film-companion' in out and 'latest' in out:
    print("\n=== 5. 启动 ===")
    out = ssh(f'docker rm -f film-companion 2>/dev/null; docker run -d --name film-companion --restart unless-stopped -p 8080:8080 -v {BASE}/.env:/app/.env -v {BASE}/data:/app/data film-companion')
    print(f"  {out.strip()}")
    
    time.sleep(5)
    print("\n=== 6. 验证 ===")
    print(ssh('docker ps --format "table {{.Names}}\t{{.Status}}"'))
    http = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
    print(f"HTTP: {http.strip()}")
    
    if http.strip() == '200':
        print(f"\n🎉 http://{HOST}:8080")
    else:
        print(ssh('docker logs film-companion --tail 20'))
else:
    print(f"\n❌ 镜像构建失败，日志：")
    print(ssh(f'cat {BASE}/build.log'))
