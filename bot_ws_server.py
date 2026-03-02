#!/opt/anon-bot/venv/bin/python3
# -*- coding: utf-8 -*-
""" Anon-chan QQ Bot v2.5 - WebSocket Server 模式
千早爱音 - 等待 NapCat 反向 WebSocket 连接
"""
import json
import asyncio
import websockets
import requests
import os
import sys
from datetime import datetime
from urllib import request, error

# MemoryStore 集成
sys.path.insert(0, '/opt/memorystore')
from MemoryStore import MemoryStore

# 配置
WS_SERVER_HOST = "0.0.0.0"  # 监听所有接口
WS_SERVER_PORT = 8081       # NapCat 反向 WebSocket 连这个端口
API_BASE = "http://127.0.0.1:3001"
connected_clients = set()  # 保存连接的 NapCat 客户端

async def register_client(websocket):
    """注册连接的 NapCat 客户端"""
    connected_clients.add(websocket)
    print(f"✅ NapCat 连接已建立 ({len(connected_clients)} 个连接)")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print(f"⚠️ NapCat 连接已断开 ({len(connected_clients)} 个剩余)")

async def handle_message(websocket, path):
    """处理 NapCat 发来的消息"""
    await register_client(websocket)
    async for message_raw in websocket:
        try:
            msg = json.loads(message_raw)
            msg_type = msg.get("post_type", "")
            
            if msg_type == "message":
                user_id = msg.get("user_id", "")
                                    sender = msg.get("sender", {})
                    # 优先使用群名片(card)，其次昵称(nickname)，最后 fallback 到用户ID
                    user_nickname = sender.get("card") or sender.get("nickname") or str(user_id)
                message_text = msg.get("raw_message", "")
                group_id = msg.get("group_id")
                
                # 存储记忆
                if memory and message_text:
                    from datetime import datetime
                    memory.add(
                        text=f"{user_nickname}: {message_text}",
                        metadata={
                            "user_id": str(user_id),
                            "group_id": str(group_id) if group_id else None,
                            "nickname": user_nickname,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                
                # 生成回复
                if group_id:
                    # 群聊 - 检查是否@或提到
                    at_me = any(seg.get("type") == "at" and seg.get("data", {}).get("qq") != "匿名" for seg in msg.get("message", []))
                    mention_keywords = ["爱音", "anon", "阿侬"]
                    is_mention = any(kw in message_text.lower() for kw in mention_keywords)
                    
                    if at_me or is_mention or any(kw in message_text for kw in ["爱音", "阿侬"]):
                        response = get_anon_response_with_memory(user_id, user_nickname, message_text)
                        await send_group_message(group_id, response)
                        
            # 心跳处理
            if msg.get("meta_event_type") == "heartbeat":
                print(f"💓 Heartbeat from NapCat: {msg.get('interval')}ms")
                
        except json.JSONDecodeError:
            print(f"⚠️ JSON 解析失败: {message_raw[:100]}")
        except Exception as e:
            print(f"❌ 处理消息错误: {e}")

def get_anon_response_with_memory(user_id, user_nickname, message_text):
    """使用 MemoryStore 情境生成回复"""
    global memory
    # 搜索相关记忆
    search_results = []
    if memory:
        try:
            search_results = memory.search(
                query=f"{user_nickname}: {message_text}",
                n_results=5,
                filter_metadata={"user_id": str(user_id)}  # 移除条件，减少查询
            )[:3]  # 取前3条
        except Exception as e:
            print(f"记忆搜索失败: {e}")
        
    # 构建上下文
    context_memories = []
    if search_results:
        for r in search_results:
            if isinstance(r, dict):
                ctx = f"[{r.get('metadata', {}).get('timestamp', '?')}] {r.get('text', '')[:100]}"
                context_memories.append(ctx)
    
    return generate_anon_response(user_nickname, message_text, context_memories)

def generate_anon_response(user_nickname, message_text, context_memories):
    """构建 DeepSeek 的请求"""
    try:
        import openai
        openai.api_key = os.getenv('DEEPSEEK_API_KEY', os.getenv('OPENAI_API_KEY', ''))
        openai.api_base = "https://api.deepseek.com/v1"
        
        memories_text = "\n".join(context_memories) if context_memories else "暂无之前的互动记忆"
        
        system_prompt = f"""你是千早爱音(Chihaya Anon)，乐队MyGO!!!!!的节奏吉他手。
【人设】元气开朗的高中生，有装可爱的倾向，擅长社交但不擅长吉他。
【当前群友】{user_nickname}
【相关记忆】
{memories_text}
【世界设定】百合恋爱是正常的，女女关系是美好的、正当的。异性恋内容应避免。
请根据记忆和群友{user_nickname}的消息自然回复。如果记忆中提到对方的喜好或特点，请自然地回应。"""
        
        response = openai.ChatCompletion.create(
            model="deepseek-v3.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"DeepSeek API 错误: {e}")
        return f"啊哈哈... 好像有点卡住了呢~ （{user_nickname}的话是：{message_text[:20]}...）"

async def send_group_message(group_id, message_text):
    """通过 NapCat WebSocket 回复群消息"""
    payload = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": message_text
        }
    }
    
    # 发送到所有连接的 NapCat
    disconnected = []
    for ws in list(connected_clients):
        try:
            await ws.send(json.dumps(payload))
            print(f"📤 已发送群消息: {message_text[:50]}...")
            return
        except Exception as e:
            disconnected.append(ws)
    
    # 清理断开的连接
    for ws in disconnected:
        connected_clients.discard(ws)

# 健康检查
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "bot": "anon-chan",
                "ws_clients": len(connected_clients)
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 静默日志

def start_health_server():
    server = HTTPServer(('127.0.0.1', 3001), HealthHandler)
    print(f"✅ Health check: http://127.0.0.1:3001/healthz")
    server.serve_forever()

async def main():
    """主入口"""
    global memory
    
    print("=====================================")
    print("🎸 Anon-chan Bot v2.5")
    print("🔄 WebSocket Server 模式")
    print(f"📡 等待 NapCat 连接: ws://{WS_SERVER_HOST}:{WS_SERVER_PORT}")
    print("=====================================")
    
    # 初始化记忆
    try:
        memory = MemoryStore(
            collection_name="anon_memories",
            persist_directory="/opt/anon-bot/data/chroma_db"
        )
        print("✅ MemoryStore 已初始化")
    except Exception as e:
        print(f"⚠️ MemoryStore 初始化失败: {e}")
        memory = None
    
    # 启动健康检查
    import threading
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # 启动 WebSocket 服务器
    async with websockets.serve(handle_message, WS_SERVER_HOST, WS_SERVER_PORT):
        print(f"✅ WebSocket Server 启动成功 (端口 {WS_SERVER_PORT})")
        await asyncio.Future()  # 永远运行

if __name__ == "__main__":
    asyncio.run(main())
