#!/usr/bin/env python3
"""验证线上是否已更新"""
import pexpect

PASSWORD = 'Aa120958.'
HOST = '101.34.205.172'
USER = 'aideploy'
BASE = '/home/aideploy/film-companion'

child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {USER}@{HOST}', timeout=10)
child.expect('password:')
child.sendline(PASSWORD)
child.expect(r'\$', timeout=10)

# 1. 检查容器内文件
child.sendline(f'docker exec film-companion grep -c "marked" /app/web/chat.html')
child.expect(r'\$', timeout=10)
print("chat.html 含 marked 次数:", child.before.decode().strip().split('\n')[-1])

child.sendline(f'docker exec film-companion grep -c "marked.parse" /app/web/chat.html')
child.expect(r'\$', timeout=10)
print("marked.parse 调用次数:", child.before.decode().strip().split('\n')[-1])

child.sendline(f'docker exec film-companion grep "display_msgs" /app/web/server.py')
child.expect(r'\$', timeout=10)
print("server.py display_msgs:", child.before.decode().strip().split('\n')[-1])

# 2. 真实对话测试
child.sendline('''curl -s -X POST http://localhost:8080/api/chat/stream \\
  -H "Content-Type: application/json" \\
  -d '{"message":"测试，请用 **加粗** 和 `代码` 回复"}' \\
  --max-time 15 | grep -o '"content":"[^"]*"' | head -5''')
child.expect(r'\$', timeout=20)
print("\n对话测试响应片段:", child.before.decode().strip()[-200:])

child.sendline('exit')
child.close()
