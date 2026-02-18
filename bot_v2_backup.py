#!/opt/anon-bot/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Anon-chan QQ Bot v2 - 千早爱音 (MemoryStore 集成版)
"""

import json
import asyncio
import websockets
import requests
import os
import sys
from datetime import datetime

# MemoryStore 集成
sys.path.insert(0, '/opt/memorystore')
from MemoryStore import MemoryStore

WEBSOCKET_URI = "ws://127.0.0.1:8082"
API_BASE = "http://127.0.0.1:8081"

# 初始化 MemoryStore - 爱音的记忆
memory = None

def init_memory():
    """初始化记忆存储"""
    global memory
    memory = MemoryStore(
        collection_name="anon_memories",
        persist_directory="/opt/anon-bot/data/chroma_db"
    )
    return memory

def get_anon_response_with_memory(user_id, user_nickname, message_text):
    """使用 MemoryStore 语境生成回复"""
    global memory
    
    # 搜索相关记忆
    search_results = []
    if memory:
        search_results = memory.search(
            query=f"{user_nickname}: {message_text}",
            n_results=5,
            filter_metadata={"user_id": user_id} if user_id else None
        )[:3]  # 取前3条
    
    # 构建系统提示
    context_memories = []
    if search_results:
        for r in search_results:
            ctx = f"[{r.get('metadata', {}).get('timestamp', '?')}] {r.get('text', '')[:100]}"
            context_memories.append(ctx)
    
    return generate_anon_response(user_nickname, message_text, context_memories)

def generate_anon_response(user_nickname, message_text, context_memories):
    """构建 DeepSeek 的请求"""
    import openai
    openai.api_key = os.getenv('DEEPSEEK_API_KEY', os.getenv('OPENAI_API_KEY', ''))
    openai.api_base = "https://api.deepseek.com/v1"
    
    # 爱音人设 + 记忆上下文
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

async def bot_event_loop():
    """主事件循环"""
    print("🎸 Anon-chan Bot v2 (MemoryStore) 启动")
    
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URI) as ws:
                print(f"✅ WebSocket 已连接到 {WEBSOCKET_URI}")
                
                async for message_raw in ws:
                    try:
                        msg = json.loads(message_raw)
                        
                        if msg.get('post_type') != 'message':
                            continue
                        if msg.get('message_type') != 'group':
                            continue
                        
                        user_id = str(msg.get('user_id', ''))
                        group_id = str(msg.get('group_id', ''))
                        message_text = ''.join(
                            seg['data']['text'] for seg in msg.get('message', [])
                            if seg.get('type') == 'text'
                        )
                        
                        # 获取用户昵称
                        user_nickname = msg.get('sender', {}).get('card') or \
                                       msg.get('sender', {}).get('nickname') or \
                                       str(user_id)
                        
                        print(f"[{group_id}] {user_nickname}({user_id}): {message_text}")
                        
                        # 生成回复（带记忆）
                        response = get_anon_response_with_memory(
                            user_id, user_nickname, message_text
                        )
                        
                        # 存储互动
                        if memory:
                            memory.add_memory(
                                text=f"群友{user_nickname}({user_id})说：'{message_text}'",
                                metadata={
                                    "user_id": user_id,
                                    "nickname": user_nickname,
                                    "group_id": group_id,
                                    "type": "chat_received",
                                    "resolved": True
                                }
                            )
                            memory.add_memory(
                                text=f"爱音回复{user_nickname}：'{response}'",
                                metadata={
                                    "user_id": user_id,
                                    "nickname": user_nickname,
                                    "type": "anon_response",
                                    "resolved": True
                                }
                            )
                        
                        # 发送回复
                        send_url = f"{API_BASE}/send_group_msg"
                        payload = {
                            "group_id": group_id,
                            "message": response,
                            "auto_escape": False
                        }
                        
                        try:
                            r = requests.post(send_url, json=payload, timeout=10)
                            print(f"✅ Sent: {r.status_code}")
                        except Exception as e:
                            print(f"❌ Send failed: {e}")
                            
                    except Exception as e:
                        print(f"❌ Message handling error: {e}")
                        
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    init_memory()
    asyncio.run(bot_event_loop())
