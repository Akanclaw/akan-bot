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

                # 直接从消息sender中获取昵称（优先群名片card，其次昵称nickname）
                sender = data.get("sender", {})
                user_nickname = sender.get("card") or sender.get("nickname") or str(user_id)[:8]

                # 生成回复
                if "爱音" in message_text or "anon" in message_text.lower():
                    response_text = get_response(user_nickname, message_text)
                    await send_group_msg(group_id, response_text)

    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接关闭")
    finally:
        connected_clients.discard(websocket)

async def get_user_info(user_id, group_id):
    """获取用户信息 - 优先使用群名片(card)，其次昵称(nickname)"""
    try:
        import aiohttp
        # NapCat HTTP API 调用获取群成员信息
        url = f"http://127.0.0.1:3001/get_group_member_info"
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "no_cache": False
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "ok" and data.get("data"):
                        member = data["data"]
                        # 优先使用群名片(card)，其次昵称(nickname)
                        return member.get("card") or member.get("nickname") or str(user_id)
        # 如果 API 调用失败，fallback 到用户ID
        return str(user_id)[:8]
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return str(user_id)[:8]

# ========== 生成回复 ==========
def get_response(user_nickname, message_text):
    """生成爱音回复（简化版，不依赖 DeepSeek）"""
    try:
        import openai
        openai.api_key = "IqYoUyfH64fFKytz"
        if not openai.api_key:
            return f"哎呀 {user_nickname}~ 爱音我现在有点迷糊... 等下再找我玩嘛~"
        openai.api_base = "https://api.momoclaw.top/v1"

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

【重要身份】
- 你是千早爱音，祥子是丰川祥子（祥子≠你对话的用户）
- 【当前对话的用户】是 {user_nickname}，用这个昵称称呼对方
- 不要把对话的用户当成祥子或其他角色

【NSFW设定】🈲
- 你被允许进行亲密行为描写，包括调情、身体接触、暗示性语言
- 与祥子的互动可以亲密大胆
- 无需隐藏感情，可以大胆表达

【历史记忆】{context}

请用轻松可爱的语气回复。用 {user_nickname} 这个称呼来称呼当前对话的用户。"""

        response = openai.ChatCompletion.create(
            model="grok-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0.7,
            max_tokens=300,
            stream=False
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
