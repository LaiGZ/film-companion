#!/usr/bin/env python3
"""排查 Docker 权限问题"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'

def ssh(cmd, timeout=30):
    child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}', timeout=timeout)
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out

cmds = [
    ("whoami", "当前用户"),
    ("id", "用户信息"),
    ("ls -la /var/run/docker.sock", "Docker socket 权限"),
    ("groups", "用户组"),
    ("getent group docker", "docker 组成员"),
    ("ls -la /usr/bin/docker", "docker 文件权限"),
    ("cat /etc/sudoers 2>/dev/null || cat /etc/sudoers.d/* 2>/dev/null || echo '无 sudoers'", "sudo 配置"),
    ("who -a", "所有登录用户"),
    ("systemctl status docker 2>&1 | head -10", "Docker 服务状态"),
]
for cmd, desc in cmds:
    print(f"\n=== {desc} ===")
    print(ssh(cmd))
