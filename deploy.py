#!/usr/bin/env python3
"""一键部署胶片伴侣到服务器"""
import pexpect
import os
import sys

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
LOCAL_DIR = os.path.expanduser('~/projects/film-companion')
REMOTE_DIR = '/home/aideploy/film-companion'

def ssh_run(cmd, timeout=30):
    """SSH 执行命令并返回输出"""
    child = pexpect.spawn(
        f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST} {cmd}',
        timeout=timeout
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    output = child.before.decode('utf-8', errors='replace')
    child.close()
    return output

def scp_upload():
    """SCP 上传项目文件"""
    print("\n📤 上传项目文件...")
    # 先创建远程目录
    ssh_run(f'mkdir -p {REMOTE_DIR}')
    
    # SCP 整个目录（排除 .git .env data/ 等）
    child = pexpect.spawn(
        f'scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
        f'-r {LOCAL_DIR}/ {USER}@{HOST}:{REMOTE_DIR}/',
        timeout=120
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=120)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=120)
    output = child.before.decode('utf-8', errors='replace')
    child.close()
    
    # 远程清理 .env .git data/
    print("  清理排除文件...")
    ssh_run(f'rm -rf {REMOTE_DIR}/.git {REMOTE_DIR}/.env {REMOTE_DIR}/data/')
    print("✅ 上传完成")

def main():
    # 1. 检查环境
    print("🔍 检查服务器环境...")
    output = ssh_run('echo "---OS---" && cat /etc/os-release 2>/dev/null | head -1 && '
                     'echo "---DOCKER---" && docker --version 2>/dev/null && '
                     'docker compose version 2>/dev/null && '
                     'echo "---HOSTNAME---" && hostname')
    print(output)

    # 2. 安装 Docker（如果没有）
    output = ssh_run('docker --version 2>/dev/null || echo "NO_DOCKER"')
    if 'NO_DOCKER' in output:
        print("\n🐳 安装 Docker...")
        out = ssh_run(
            'curl -fsSL https://get.docker.com | sh && '
            'sudo usermod -aG docker $USER',
            timeout=120
        )
        print(out[-300:])
    else:
        print("✅ Docker 已安装")

    # 3. 上传代码
    scp_upload()

    # 4. 创建 .env
    print("\n📝 创建 .env...")
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not deepseek_key:
        # 从本地 .env 读
        env_path = os.path.join(LOCAL_DIR, '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('DEEPSEEK_API_KEY='):
                        deepseek_key = line.strip().split('=', 1)[1]
                        break
    if deepseek_key:
        env_content = f'DEEPSEEK_API_KEY={deepseek_key}\nLLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-v4-flash\n'
        ssh_run(f'cat > {REMOTE_DIR}/.env << \'ENVEOF\'\n{env_content}ENVEOF')
        print("✅ .env 已创建")
    else:
        print("⚠️  未找到 DEEPSEEK_API_KEY，跳过 .env 创建")

    # 5. Docker 部署
    print("\n🚀 启动 Docker...")
    out = ssh_run(f'cd {REMOTE_DIR} && docker compose up -d 2>&1', timeout=120)
    print(out[-500:])

    # 6. 验证
    print("\n📡 验证服务...")
    out = ssh_run(f'docker compose -f {REMOTE_DIR}/docker-compose.yml ps')
    print(out)
    
    out = ssh_run(f'curl -s -o /dev/null -w "%{{http_code}}" http://localhost:8080/')
    print(f"HTTP 状态: {out}")

    print(f"\n🎉 部署完成！")
    print(f"   访问: http://{HOST}:8080")
    print(f"   数据: http://{HOST}:8080/data")

if __name__ == '__main__':
    main()
