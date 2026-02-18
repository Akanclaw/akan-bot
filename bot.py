#!/opt/anon-bot/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Anon-chan QQ Bot v3 - WebSocket Server 模式
千早爱音 - 等待 NapCat 反向 WebSocket 连接
"""
import json
import asyncio
import websockets
import requests
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# MemoryStore 集成
sys.path.insert(0, '/opt/memorystore')
from MemoryStore import MemoryStore

# 配置
WS_SERVER_HOST = "0.0.0.0"
WS_SERVER_PORT = 8081
connected_clients = set()
memory = None

# ========== WebSocket 服务器处理器 ==========

async def handle_client(websocket):
    """处理单个 NapCat 客户端的消息"""
    connected_clients.add(websocket)
    print(f"✅ NapCat 连接 ({len(connected_clients)} 个)")
    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                msg_type = msg.get("post_type", "")
                if msg_type == "message":
                    user_id = str(msg.get("user_id", ""))
                    sender = msg.get("sender", {})
                    user_nickname = sender.get("card") or sender.get("nickname", user_id)
                    message_text = msg.get("raw_message", "")
                    group_id = msg.get("group_id")
                    print(f"📨 [{group_id}] {user_nickname}: {message_text[:50]}")
                    # 存储记忆
                    if memory and message_text:
                        try:
                            memory.add_memory(
                                text=f"{user_nickname}: {message_text}",
                                metadata={
                                    "user_id": user_id,
                                    "group_id": str(group_id) if group_id else None,
                                    "nickname": user_nickname,
                                    "timestamp": datetime.now().isoformat()
                                }
                            )
                        except Exception as e:
                            print(f"❌ 记忆存储失败: {e}")
                    # 生成回复
                    if group_id:
                        mention_keywords = ["爱音", "anon", "阿侬", "千早"]
                        is_mention = any(kw in message_text.lower() for kw in mention_keywords)
                        if is_mention:
                            response = get_response(user_nickname, message_text)
                            await send_group_msg(group_id, response)
                    else:
                        # 私聊：直接回复
                        response = get_response(user_nickname, message_text)
                        await send_private_msg(user_id, response)
                elif msg.get("meta_event_type") == "heartbeat":
                    print(f"💓 心跳: {msg.get('interval')}ms")
            except json.JSONDecodeError:
                print(f"⚠️ JSON 解析失败")
            except Exception as e:
                print(f"❌ 处理错误: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"⚠️ NapCat 断开 ({len(connected_clients)} 个剩余)")

# Placeholder to exit early
def __placeholder__(): pass

async def __old_handle_client(websocket):
    """OLD - 处理 WebSocket 消息"""
    async for message in websocket:
        try:
            msg = json.loads(message)
            msg_type = msg.get("post_type", "")
            
            if msg_type == "message":
                user_id = str(msg.get("user_id", ""))
                user_nickname = msg.get("sender", {}).get("nickname", user_id)
                message_text = msg.get("raw_message", "")
                group_id = msg.get("group_id")
                
                print(f"📨 [{group_id}] {user_nickname}: {message_text[:50]}")
                
                # 存储记忆
                if memory and message_text:
                    try:
                        memory.add(
                            text=f"{user_nickname}: {message_text}",
                            metadata={
                                "user_id": user_id,
                                "group_id": str(group_id) if group_id else None,
                                "nickname": user_nickname,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                    except Exception as e:
                        print(f"记忆存储失败: {e}")
                
                # 生成回复
                if group_id:
                    mention_keywords = ["爱音", "anon", "阿侬", "千早"]
                    is_mention = any(kw in message_text.lower() for kw in mention_keywords)
                    
                    if is_mention:
                        response = get_response(user_nickname, message_text)
                        await send_group_msg(group_id, response)
                        
            elif msg.get("meta_event_type") == "heartbeat":
                print(f"💓 心跳: {msg.get('interval')}ms")
                
        except json.JSONDecodeError:
            print(f"⚠️ JSON 解析失败")
        except Exception as e:
            print(f"❌ 处理错误: {e}")

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
【当前群友】{user_nickname}
【历史记忆】{context}
请用轻松可爱的语气回复。"""
        
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
