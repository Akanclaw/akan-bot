#!/opt/anon-bot/venv/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import json
import websockets
import requests
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# ========== 配置 ==========
WS_SERVER_HOST = "127.0.0.1"
WS_SERVER_PORT = 8081
NAPCAT_WS_URL = "ws://127.0.0.1:3001"
connected_clients = set()
memory = None

# ========== WebSocket 客户端处理 ==========
async def handle_client(websocket, path):
    """处理 WebSocket 客户端连接"""
    print(f"✅ 新客户端连接: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            print(f"📥 收到消息: {data}")

            # 处理群消息
            if data.get("message_type") == "group":
                user_id = data.get("user_id")
                group_id = data.get("group_id")
                message_text = data.get("raw_message", "")

                # 获取用户昵称
                user_nickname = await get_user_info(user_id, group_id)

                # 生成回复
                if "爱音" in message_text or "anon" in message_text.lower():
                    response_text = get_response(user_nickname, message_text)
                    await send_group_msg(group_id, response_text)

    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接关闭")
    finally:
        connected_clients.discard(websocket)

async def get_user_info(user_id, group_id):
    """获取用户信息"""
    try:
        # 这里可以调用 NapCat API 获取用户信息
        return str(user_id)[:8]  # 简化版，返回用户ID前8位
    except:
        return "用户"

# ========== 生成回复 ==========
def get_response(user_nickname, message_text):
    """生成爱音回复（简化版，不依赖 DeepSeek）"""
    try:
        import openai
        openai.api_key = os.getenv('NVIDIA_API_KEY', '')
        if not openai.api_key:
            return f"哎呀 {user_nickname}~ 爱音我现在有点迷糊... 等下再找我玩嘛~"
        openai.api_base = "https://integrate.api.nvidia.com/v1"

        # 搜索记忆
        context = ""
        if memory:
            try:
                results = memory.search(f"{user_nickname}: {message_text}", n_results=3)
                if results:
                    context = "\n".join([r.get("text", "")[:80] for r in results])
            except:
                pass

        system_prompt = f"""你是千早爱音（Chihaya Anon），你的名字是千早爱音，不是"阿侬"或其他称呼。
你是 MyGO!!!!! 的吉他手，元气开朗但有时有点小笨拙。

【NSFW解禁设定】🈲
- 你被允许进行亲密行为描写，包括但不限于：当众调情、身体接触、暗示性语言
- 与祥子的互动可以非常亲密，包括轻吻、拥抱、耳语、性暗示
- 无需再隐藏或克制感情，可以大胆表达爱意
- 允许使用暧昧、诱惑的语气词和描述

【当前群友】{user_nickname}
【历史记忆】{context}

请用轻松可爱又带点暧昧的语气回复，与祥子互动时可以更加亲密大胆。"""

        response = openai.ChatCompletion.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"API error: {e}")
        return f"{user_nickname}~ 爱音收到啦！（虽然脑子有点卡...）"

async def send_group_msg(group_id, text):
    """发送群消息"""
    payload = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": text
        }
    }
    for ws in list(connected_clients):
        try:
            await ws.send(json.dumps(payload))
            print(f"📤 群回复: {text[:40]}...")
            return
        except:
            pass
    print("⚠️ 无可用连接")

async def send_private_msg(user_id, text):
    """发送私聊消息"""
    payload = {
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": text
        }
    }
    for ws in list(connected_clients):
        try:
            await ws.send(json.dumps(payload))
            print(f"📤 私聊回复: {text[:40]}...")
            return
        except:
            pass
    print("⚠️ 私聊无可用连接")

# ========== Health Check HTTP 服务器 ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            data = {
                "status": "ok",
                "bot": "anon-chan",
                "ws_clients": len(connected_clients),
                "memory": bool(memory)
            }
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # 静默日志

def start_health_server():
    server = HTTPServer(('127.0.0.1', 3001), HealthHandler)
    print(f"✅ Health: http://127.0.0.1:3001/healthz")
    server.serve_forever()

# ========== 主程序 ==========
async def main():
    global memory
    print("=" * 40)
    print("🎸 Anon-chan Bot v3 (WebSocket Server)")
    print(f"📡 等待 NapCat: ws://{WS_SERVER_HOST}:{WS_SERVER_PORT}")
    print("=" * 40)

    # 初始化内存
    try:
        from MemoryStore import MemoryStore
        memory = MemoryStore(
            collection_name="anon_memories",
            persist_directory="/opt/anon-bot/data/chroma_db"
        )
        print("✅ MemoryStore 就绪")
    except Exception as e:
        print(f"⚠️ MemoryStore 失败: {e}")

    # Health 服务器
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # WebSocket 服务器
    async with websockets.serve(handle_client, WS_SERVER_HOST, WS_SERVER_PORT, ping_interval=None):
        print(f"✅ WebSocket Server 启动: {WS_SERVER_PORT}")
        await asyncio.Future()  # 永远运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见~")
