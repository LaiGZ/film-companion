#!/usr/bin/env python3
"""网络排查 v2"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}', timeout=10)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

# 逐个运行
child.sendline('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/')
child.expect(r'\$', timeout=10)
print("本机 localhost:", child.before.decode().strip().split('\n')[-1].strip())

child.sendline(f'curl -s -o /dev/null -w "%{{http_code}}" http://{HOST}:8080/')
child.expect(r'\$', timeout=10)
print("公网 IP:", child.before.decode().strip().split('\n')[-1].strip())

child.sendline('which iptables 2>/dev/null && iptables -L -n --line-numbers 2>&1 | head -30 || echo "无 iptables"')
child.expect(r'\$', timeout=10)
print("\n防火墙:\n", child.before.decode().strip())

child.sendline('cat /etc/hostname && cat /etc/resolv.conf | head -3')
child.expect(r'\$', timeout=10)
print("\n系统信息:\n", child.before.decode().strip())

child.sendline('ip addr show | grep "inet "')
child.expect(r'\$', timeout=10)
print("\nIP 地址:\n", child.before.decode().strip())

child.sendline('exit')
child.close()
