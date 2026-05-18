#!/usr/bin/env python3
"""排查网络问题"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}', timeout=10)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

def run(cmd, timeout=10):
    child.sendline(cmd)
    child.expect(r'\$', timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    for l in out.split('\n'):
        s = l.strip()
        if s and 'aideploy' not in s and '\\x1b' not in s and not s.startswith('['):
            print(f"  {s}")
    return out

print("=== 1. 容器是否在跑 ===")
run('docker ps | grep film-companion')

print("\n=== 2. 容器内端口监听 ===")
run('docker exec film-companion ss -tlnp 2>/dev/null || docker exec film-companion netstat -tlnp 2>/dev/null || echo "无工具"')

print("\n=== 3. 宿主机端口监听 ===")
run('ss -tlnp | grep 8080')

print("\n=== 4. 防火墙规则 ===")
run('iptables -L INPUT -n 2>/dev/null | head -15 || echo "无 iptables"')
run('firewall-cmd --list-all 2>/dev/null || ufw status 2>/dev/null || echo "无防火墙工具"')

print("\n=== 5. 从服务器本机访问 ===")
run('curl -s -o /dev/null -w "%{http_code} - %{content_type}" http://localhost:8080/')

print("\n=== 6. 从服务器公网 IP 访问 ===")
run(f'curl -s -o /dev/null -w "%{{http_code}}" http://{HOST}:8080/')

print("\n=== 7. 外网连通性 ===")
run('curl -s -o /dev/null -w "%{http_code}" https://api.deepseek.com')

child.sendline('exit')
child.close()
