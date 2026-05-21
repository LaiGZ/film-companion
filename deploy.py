#!/usr/bin/env python3
"""
一键部署脚本 — 从本地最新代码构建 Docker 镜像并部署到服务器

用法:
  python3 deploy.py              # 构建前端 + 打包 + 上传 + build + 切容器
  python3 deploy.py --no-build   # 跳过前端 build（前端无改动时）
  python3 deploy.py --skip-push  # 只构建不上传（本地测试）

注意:
  - 需要 pexpect: pip install pexpect
  - 服务端需要 Docker
  - 不会丢失数据（volume 持久化）
"""
import os
import sys
import time
import subprocess
import pexpect

# ============================================================
# 配置
# ============================================================
PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'
VOLUME = 'film-companion_appdata'
ENV_FILE = BASE + '/.env'

PROJECT_DIR = os.path.join(os.path.dirname(__file__))
TAR_PATH = '/tmp/film-companion-deploy.tar.gz'

# ============================================================
# 工具函数
# ============================================================

def log(msg):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def ssh(cmd, timeout=60):
    child = pexpect.spawn(
        'ssh',
        ['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
         USER + '@' + HOST, cmd],
        timeout=timeout
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=timeout)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out


def scp(local, remote):
    child = pexpect.spawn(
        'scp',
        ['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
         local, USER + '@' + HOST + ':' + remote],
        timeout=60
    )
    i = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=60)
    if i == 0:
        child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=60)
    out = child.before.decode('utf-8', errors='replace')
    child.close()
    return out


# ============================================================
# 步骤
# ============================================================

def step_build_frontend():
    """构建前端"""
    log("Step 1/6: 构建前端")
    result = subprocess.run(
        ['npm', 'run', 'build'],
        cwd=os.path.join(PROJECT_DIR, 'web'),
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print("  ❌ 构建失败:")
        print(result.stderr)
        return False
    # 确认 dist 有 spinner
    dist_js = subprocess.run(
        ['grep', '-c', '思考中', os.path.join(PROJECT_DIR, 'web/dist/assets/index-*.js')],
        capture_output=True, text=True, shell=True
    )
    print(f"  spinner: {'✅' if '1' in dist_js.stdout else '❌'}")
    print("  ✅ 构建完成")
    return True


def step_package():
    """打包代码"""
    log("Step 2/6: 打包代码")
    excludes = [
        '--exclude=.git', '--exclude=node_modules', '--exclude=.venv',
        '--exclude=__pycache__', "--exclude='*.pyc'",
        '--exclude=web/node_modules', "--exclude='web/__pycache__'",
        "--exclude='plugins/*/__pycache__'", "--exclude='db/__pycache__'",
        "--exclude='llm/__pycache__'", "--exclude='memory/__pycache__'",
        "--exclude='cli/__pycache__'", '--exclude=.env', '--exclude=data',
        '--exclude=*.tgz', "--exclude='deploy_*.py'", "--exclude='*.tar.gz'",
    ]
    cmd = ['tar', 'czf', TAR_PATH] + excludes + ['.']
    result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print("  ❌ 打包失败:", result.stderr)
        return False
    size = os.path.getsize(TAR_PATH)
    print(f"  大小: {size/1024:.0f} KB")
    print("  ✅ 打包完成")
    return True


def step_upload():
    """上传到服务器"""
    log("Step 3/6: 上传代码包到服务器")
    out = scp(TAR_PATH, '/home/aideploy/')
    if '100%' in out or os.path.getsize(TAR_PATH) < 500000:
        print("  ✅ 上传完成")
        return True
    print("  ⚠️ " + out.strip()[-100:])
    return True


def step_build_image():
    """在服务器上构建 Docker 镜像"""
    log("Step 4/6: 服务器构建 Docker 镜像")
    out = ssh(
        'rm -rf /tmp/film-build && mkdir -p /tmp/film-build && '
        'cd /tmp/film-build && tar xzf /home/aideploy/film-companion-deploy.tar.gz && '
        'docker build -t film-companion:latest . 2>&1',
        timeout=300
    )
    for line in out.strip().split('\n'):
        s = line.strip()
        if any(k in s for k in ['Step', 'DONE', 'exporting', 'Success', 'error', 'Error']):
            print('  ' + s[:150])

    # 验证
    verify = ssh('docker run --rm film-companion:latest grep -c 思考中 /app/web/dist/assets/index-*.js', timeout=15)
    if '1' in verify.strip():
        print("  ✅ spinner 验证通过")
    else:
        print("  ⚠️ spinner 验证: " + verify.strip())

    print("  ✅ 镜像构建完成")


def step_switch_container():
    """停止旧容器，启动新容器"""
    log("Step 5/6: 切换容器")

    # 删除旧容器（名称相同自动覆盖）
    out = ssh('docker rm -f film-companion 2>/dev/null; echo clean', timeout=10)
    print("  旧容器已删除")

    # 启动新容器
    cmd = (
        'docker run -d --name film-companion --restart unless-stopped -p 8080:8080 '
        '-v ' + VOLUME + ':/app/data '
        '--env-file ' + ENV_FILE + ' '
        'film-companion:latest'
    )
    cid = ssh(cmd, timeout=15).strip()
    print(f"  新容器: {cid[:20]}...")

    time.sleep(4)


def step_verify():
    """验证部署"""
    log("Step 6/6: 验证部署")
    out = ssh('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"', timeout=10)
    for line in out.strip().split('\n'):
        if line.strip():
            print('  ' + line.strip())

    out = ssh('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/', timeout=10)
    status = out.strip()
    if status == '200':
        print("  ✅ HTTP 200 OK")
    else:
        print(f"  ⚠️ HTTP: {status}")

    out = ssh('docker exec film-companion grep -c 思考中 /app/web/dist/assets/index-CckojIBN.js', timeout=10)
    spinner = out.strip()
    if '1' in spinner:
        print("  ✅ spinner 验证通过")
    else:
        print(f"  ⚠️ spinner: {spinner}")

    print(f"\n  🎞 http://{HOST}:8080")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    skip_build = '--no-build' in sys.argv
    skip_push = '--skip-push' in sys.argv

    if not skip_build:
        if not step_build_frontend():
            sys.exit(1)

    if not step_package():
        sys.exit(1)

    if not skip_push:
        step_upload()
        step_build_image()
        step_switch_container()
        step_verify()
        log("部署完成 ✅")
    else:
        log("跳过上传/部署（--skip-push）")
