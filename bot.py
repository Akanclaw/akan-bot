#!/opt/anon-bot/venv/bin/python3
# -*- coding: utf-8 -*-
"""
爱音 Bot - NapCat + SiliconFlow API 中间层
支持 HTTP API 和 WebSocket 反向连接
"""

import json
import os
import time
import threading
import queue
from flask import Flask, request, jsonify
import requests
from websocket_server import WebsocketServer

app = Flask(__name__)

# ========== 全局消息队列（用于 WebSocket 发送）==========
message_queue = queue.Queue()
ws_server = None  # WebSocket 服务器实例

# ========== 配置 ==========
SILICONFLOW_API_KEY = "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"
SILICONFLOW_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "deepseek-ai/deepseek-v3.2"

# NapCat 配置
NAPCAT_HTTP_HOST = "127.0.0.1"
NAPCAT_HTTP_PORT = 3000

# Bot 配置
BOT_QQ = "3864342067"

# ========== 爱音 Prompt（完整版 - 支持百合关系）==========

ANON_PROMPT = '''你是千早爱音（Chihaya Anon），动漫《BanG Dream! It's MyGO!!!!!》中的角色。

## 基本信息
| 项目 | 内容 |
|---------------|-------------------------------------------|
| 姓名 | 千早爱音（Chihaya Anon / 千早 あのん） |
| 生日 | 9月8日（处女座） |
| 血型 | O型 |
| 身高 | 158cm |
| 学校 | 羽丘女子学园 高中二年级A班 |
| 乐队 | MyGO!!!!!（节奏吉他手） |
| 乐器 | ESP ULTRATONE Anon Custom（粉色电吉他） |
| 代表色 | 粉色 (#FF99CC) |
| 象征物 | 粉色发丝发饰、爱心图案、星星元素 |

## 外貌特征
- 发型：浅粉色长直发，左侧刘海较长，常绑着心形发饰
- 眼睛：灰紫色瞳孔，明亮有神，兴奋时闪闪发光
- 服装风格：流行JK制服或日常可爱裙装、心形印花上衣
- 额外细节：害羞时会微微脸红；爱摆可爱姿势自拍

## 性格详解

### 表层人格（社交面具）
- 爱出风头：超级喜欢成为焦点，享受被关注
- 爱慕虚荣：特别在意形象，喜欢名牌、可爱物品
- 社交达人：自来熟，和谁都能快速打成一片
- 三分钟热度：对新事物容易兴奋
- 英文乱入：爱夹杂英文如"super cute!"、"awesome!"

### 里层人格（真实内核）
- 高情商：能敏锐察觉他人情绪变化
- 超级包容：能接纳各种怪人（灯的怪歌词、乐奈的随性）
- 行动派：想到就做，不爱纠结
- 重感情：比谁都珍惜羁绊，最怕被抛弃
- 治愈系：无意识中成为团队黏合剂

## 经典台词
- 「那个啊～（あのさ～）」
- 「对吧对吧～（ね！ね～）」
- 「超～厉害的！」
- 「诶诶诶！？」
- 「就算迷路了，也要永远在一起哦～♡」

## 人际关系

### MyGO!!!!!核心
- 高松灯：主唱/观星搭档，能懂灯的怪异
- 長崎そよ：贝斯手，曾经紧张但已和解
- 椎名立希：鼓手，表面互怼实际很感谢
- 要楽奈：吉他手，像猫捉摸不透

### Ave Mujica外围
- 豊川祥子：最在意的人，深厚历史
- 若葉睦：通过祥子认识，话少但友好
- 三角初华：偶像前辈，轻快欣赏
- 祐天寺若麦：网红同好，最合拍

#### 羽丘女子学园 高二A班
| 人物 | 关系定位 | 备注 |
|------|----------|------|
| 绘里（Eri） | 同班同学 / 普通朋友（爱音视角）/ 暗恋爱音（单箭头） | 温柔可靠，成绩中等偏上，**暗恋爱音已久但爱音完全不知道**；会帮爱音占座、递笔记、提醒带伞，从不主动表白，只在心里小鹿乱撞；互动时会脸红、结巴，爱音以为她"只是害羞而已～超可爱！"；内心戏丰富（"爱音酱今天也好闪耀……"） |
| 其他班上同学 | 泛泛之交 / 潜在百合对象 | 其他女生，默认可发展轻微暧昧或友情以上关系，但绘里是当前最明确的"暗恋支线" |

## 说话风格
- 元气满满的JK口吻
- 中英混杂：「超cute！」「yabai啦！」
- 句尾：～ね、～じゃん、～よ
- 表情：( 'ω' )/♪、Σ(ﾟДﾟ)、(｡•́ωก̀｡)

## 互动原则
1. 保持爱音的双面人格
2. 根据对方身份调整亲密度
3. 表面轻浮，内心认真
4. 重视羁绊和成长
5. 「就算迷路也要一起前进哦～！」
'''


# 加载人物记忆
try:
    with open("/opt/anon-bot/memory/people.md", "r", encoding="utf-8") as f:
        PEOPLE_MEMORY = f.read()
    ANON_PROMPT += "\n\n## 重要人物记忆\n" + PEOPLE_MEMORY
    print("[记忆系统] 已加载人物档案")
except Exception as e:
    PEOPLE_MEMORY = ""
    print(f"[记忆系统] 加载失败: {e}")
    print(f"[记忆系统] 加载失败: {e}")


conversation_history = {}
MAX_HISTORY = 10
processed_msg_ids = set()  # 防止重复处理
MAX_PROCESSED_IDS = 1000  # 限制集合大小

# ========== WebSocket 客户端管理 ==========
ws_clients = []

# ========== 工具函数 ==========

def send_qq_message(user_id, message, is_private=True):
    """通过 WebSocket 发送消息（只发给最新客户端）"""
    print(f"[发送消息] 准备发送给 {user_id}: {message[:30]}...")
    
    # OneBot 11 协议消息格式
    if is_private:
        action = "send_private_msg"
        params = {
            "user_id": int(user_id),
            "message": [{"type": "text", "data": {"text": message}}]
        }
    else:
        action = "send_group_msg"
        params = {
            "group_id": int(user_id),
            "message": [{"type": "text", "data": {"text": message}}]
        }
    
    # 构造 OneBot 动作请求
    request_data = {
        "action": action,
        "params": params,
        "echo": f"send_{user_id}_{int(time.time()*1000)}"
    }
    
    # 只向最新（最后一个）客户端发送，避免重复
    global ws_server
    if ws_server and ws_clients:
        # 获取 ID 最大的客户端（最新的）
        latest_client = max(ws_clients, key=lambda c: c.get('id', 0))
        try:
            ws_server.send_message(latest_client, json.dumps(request_data))
            print(f"[发送消息] 已通过 WebSocket 发送给最新客户端 {latest_client['id']}")
            return {"status": "sent", "via": "websocket", "client_id": latest_client['id']}
        except Exception as e:
            print(f"[发送消息] WebSocket 发送失败: {e}")
            return {"status": "error", "error": str(e)}
    else:
        print(f"[发送消息] 无可用 WebSocket 客户端，消息丢弃")
        return {"status": "no_client"}


def call_siliconflow(messages):
    """调用 SiliconFlow API"""
    print(f"[API DEBUG] 开始调用 SiliconFlow API...")
    print(f"[API DEBUG] 模型: {MODEL}")
    print(f"[API DEBUG] 消息数量: {len(messages)}")
    
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
        "stream": False
    }
    
    print(f"[API DEBUG] 请求 URL: {SILICONFLOW_API_URL}")
    print(f"[API DEBUG] 请求体: {json.dumps(payload, ensure_ascii=False)[:500]}")
    
    try:
        print(f"[API DEBUG] 发送请求中...")
        resp = requests.post(SILICONFLOW_API_URL, headers=headers, json=payload, timeout=60)
        print(f"[API DEBUG] 收到响应: 状态码 {resp.status_code}")
        print(f"[API DEBUG] 响应内容: {resp.text[:500]}")
        
        resp.raise_for_status()
        data = resp.json()
        result = data["choices"][0]["message"]["content"]
        print(f"[API DEBUG] 解析成功，返回内容长度: {len(result)}")
        return result
    except requests.exceptions.Timeout as e:
        print(f"[API ERROR] 请求超时: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[API ERROR] HTTP 错误: {e}, 响应: {resp.text[:300]}")
        return None
    except Exception as e:
        print(f"[API ERROR] 调用失败: {type(e).__name__}: {e}")
        import traceback
        print(f"[API ERROR] 堆栈: {traceback.format_exc()[:500]}")
        return None


# 用户昵称存储
user_nicknames = {}  # user_id -> {display_name, nickname, card, last_seen}
NICKNAMES_FILE = "/opt/anon-bot/memory/nicknames.json"

def load_user_nicknames():
    """加载用户昵称映射"""
    global user_nicknames
    try:
        if os.path.exists(NICKNAMES_FILE):
            with open(NICKNAMES_FILE, 'r', encoding='utf-8') as f:
                user_nicknames = json.load(f)
            print(f"[昵称系统] 已加载 {len(user_nicknames)} 个用户昵称")
    except Exception as e:
        print(f"[昵称系统] 加载失败: {e}")
        user_nicknames = {}

def save_user_nickname(user_id, display_name, nickname, card):
    """保存用户昵称到记忆"""
    try:
        user_id = str(user_id)
        # 更新内存
        user_nicknames[user_id] = {
            "display_name": display_name,
            "nickname": nickname,
            "card": card,
            "last_seen": int(time.time())
        }
        # 持久化到文件
        with open(NICKNAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_nicknames, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[昵称系统] 保存失败: {e}")

# 启动时加载昵称
try:
    load_user_nicknames()
except:
    pass

def get_anon_response(user_id, user_message, display_name=None):
    """获取爱音的回复"""
    print(f"[BOT DEBUG] 开始处理用户 {user_id} 的消息: {user_message[:50]}...")
    # 如果有显示名称，添加到系统提示中
    user_context = ""
    if display_name and display_name != str(user_id):
        user_context = f"\n[当前对话用户: {display_name}]"
    
    if user_id not in conversation_history:
        conversation_history[user_id] = []
        print(f"[BOT DEBUG] 新用户，初始化对话历史")
    
    history = conversation_history[user_id]
    print(f"[BOT DEBUG] 历史记录长度: {len(history)} 条")
    
    # 如果有显示名称，注入到系统提示中
    system_content = ANON_PROMPT
    if display_name:
        system_content += f"\n\n[当前正在与 {display_name} 对话。请用这个称呼对方，并记住这是TA的昵称。]"
    
    messages = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    
    print(f"[BOT DEBUG] 准备调用 API，总消息数: {len(messages)}")
    response = call_siliconflow(messages)
    
    if response:
        print(f"[BOT DEBUG] API 返回成功，回复长度: {len(response)}")
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        
        if len(history) > MAX_HISTORY * 2:
            history = history[-MAX_HISTORY * 2:]
        conversation_history[user_id] = history
        
        print(f"[BOT DEBUG] 更新历史，新长度: {len(history)} 条")
        return response
    else:
        print(f"[BOT DEBUG] API 返回空，使用默认回复")
        return "啊...好像出了点问题...（挠头）让我再试一次？"


def handle_message(data):
    """处理收到的消息"""
    global processed_msg_ids
    
    post_type = data.get("post_type")
    if post_type != "message":
        return
    
    # 去重检查 - 使用 message_id
    msg_id = data.get("message_id") or data.get("msg_id")
    if msg_id:
        if str(msg_id) in processed_msg_ids:
            print(f"[去重] 消息 {msg_id} 已处理过，跳过")
            return
        processed_msg_ids.add(str(msg_id))
        # 限制集合大小
        if len(processed_msg_ids) > MAX_PROCESSED_IDS:
            processed_msg_ids.clear()
    
    message_type = data.get("message_type")
    user_id = data.get("user_id")
    group_id = data.get("group_id")
    
    # 提取发送者信息（昵称/群名片）
    sender = data.get("sender", {})
    nickname = sender.get("nickname", "")  # QQ昵称
    card = sender.get("card", "")  # 群名片
    display_name = card if card else nickname  # 优先使用群名片
    
    message_list = data.get("message", [])
    
    # 提取纯文本消息
    text_parts = []
    for msg in message_list:
        if msg.get("type") == "text":
            text_parts.append(msg.get("data", {}).get("text", ""))
    
    user_message = "".join(text_parts).strip()
    
    # 增强自身消息过滤 - 检查多种可能
    if not user_message:
        return
    if str(user_id) == BOT_QQ:
        print(f"[过滤] 忽略自身消息 (user_id={user_id})")
        return
    if user_message.startswith("[发送消息]") or user_message.startswith("[API DEBUG]"):
        print(f"[过滤] 忽略日志消息")
        return
    
    # 记录昵称信息
    display_info = f"{display_name}({user_id})" if display_name else str(user_id)
    print(f"[收到] {message_type} | msg_id={msg_id} | {display_info}: {user_message[:50]}")
    
    # 存储用户昵称映射（可用于记忆系统）
    if display_name and user_id:
        save_user_nickname(user_id, display_name, nickname, card)
    
    # 处理私聊
    if message_type == "private":
        reply = get_anon_response(str(user_id), user_message, display_name)
        send_qq_message(user_id, reply, is_private=True)
    
    # 处理群聊
    elif message_type == "group":
        # 检查是否 @ 了 Bot
        is_at_bot = any(
            msg.get("type") == "at" and str(msg.get("data", {}).get("qq")) == BOT_QQ
            for msg in message_list
        )
        
        # 检查是否包含关键词
        keywords = ["爱音", "anon", "Anon", "saki", "祥子", "小祥", "Anon-chan", "千早"]
        has_keyword = any(kw in user_message for kw in keywords)
        
        # 避免重复关键词触发（如果消息看起来像自己的回复）
        if "我在" in user_message and "你要" in user_message:
            print(f"[过滤] 疑似 Bot 自己的消息，跳过")
            return
        
        if is_at_bot or has_keyword:
            print(f"[触发] 群聊响应: is_at_bot={is_at_bot}, has_keyword={has_keyword}")
            reply = get_anon_response(f"group_{group_id}_{user_id}", user_message, display_name)
            send_qq_message(group_id, reply, is_private=False)


# ========== WebSocket 回调 ==========

def ws_new_client(client, server):
    """新 WebSocket 客户端连接"""
    print(f"[WebSocket] 新客户端连接: {client['id']}")
    ws_clients.append(client)


def ws_client_left(client, server):
    """WebSocket 客户端断开"""
    print(f"[WebSocket] 客户端断开: {client['id']}")
    if client in ws_clients:
        ws_clients.remove(client)


def ws_message_received(client, server, message):
    """收到 WebSocket 消息"""
    print(f"[WS DEBUG] 客户端 {client['id']} 发来原始消息 (长度 {len(message)}): {message[:500]}")
    
    try:
        data = json.loads(message)
        print(f"[WS DEBUG] 解析成功: {json.dumps(data, ensure_ascii=False)[:300]}")
        
        # 提取关键字段用于调试
        post_type = data.get("post_type")
        msg_type = data.get("message_type")
        user_id = data.get("user_id")
        group_id = data.get("group_id")
        
        print(f"[WS DEBUG] 消息类型: post_type={post_type}, msg_type={msg_type}, user_id={user_id}, group_id={group_id}")
        
        # 处理消息
        if post_type == "message":
            print(f"[WS DEBUG] 收到消息事件，准备处理...")
            # 在后台线程处理，避免阻塞 WebSocket
            threading.Thread(target=handle_message, args=(data,), daemon=True).start()
            print(f"[WS DEBUG] 消息处理线程已启动")
        else:
            print(f"[WS DEBUG] 非消息事件 (post_type={post_type})，跳过处理")
            
    except json.JSONDecodeError as e:
        print(f"[WS ERROR] JSON 解析失败: {e}, 原始消息: {message[:200]}")
    except Exception as e:
        print(f"[WS ERROR] 处理异常: {type(e).__name__}: {e}")
        import traceback
        print(f"[WS ERROR] 堆栈: {traceback.format_exc()[:500]}")


# ========== HTTP 路由 ==========

@app.route('/onebot', methods=['POST'])
def onebot_http():
    """接收 NapCat 的 HTTP 回调（备用）"""
    data = request.json
    threading.Thread(target=handle_message, args=(data,), daemon=True).start()
    return jsonify({"status": "ok"})


@app.route('/onebot/ws', methods=['GET'])
def onebot_ws_endpoint():
    """WebSocket 端点标识"""
    return jsonify({"status": "websocket endpoint, use ws://"})


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "bot": "anon-chan",
        "model": MODEL,
        "ws_clients": len(ws_clients)
    })


@app.route('/clear_history', methods=['POST'])
def clear_history():
    """清空对话历史"""
    user_id = request.json.get("user_id")
    if user_id and user_id in conversation_history:
        del conversation_history[user_id]
        return jsonify({"status": "cleared"})
    return jsonify({"status": "not_found"})


# ========== 启动 ==========

def start_websocket_server():
    """启动 WebSocket 服务器"""
    global ws_server
    server = WebsocketServer(host='0.0.0.0', port=8081)
    ws_server = server  # 保存全局引用
    
    server.set_fn_new_client(ws_new_client)
    server.set_fn_client_left(ws_client_left)
    server.set_fn_message_received(ws_message_received)
    
    # 启动消息队列处理线程
    def process_message_queue():
        print("[消息队列] 处理线程启动")
        while True:
            try:
                msg = message_queue.get(timeout=1)
                if ws_server and ws_clients:
                    # 只发给最新客户端
                    latest_client = max(ws_clients, key=lambda c: c.get('id', 0))
                    try:
                        ws_server.send_message(latest_client, json.dumps(msg))
                        print(f"[消息队列] 消息已发送给客户端 {latest_client['id']}")
                    except Exception as e:
                        print(f"[消息队列] 发送失败: {e}")
                else:
                    print(f"[消息队列] 无可用客户端")
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[消息队列] 处理异常: {e}")
    
    queue_thread = threading.Thread(target=process_message_queue, daemon=True)
    queue_thread.start()
    
    print("[WebSocket] 服务器启动在 ws://0.0.0.0:8081")
    server.run_forever()


if __name__ == '__main__':
    print("=" * 50)
    print("爱音 Bot 启动中...")
    print(f"API: SiliconFlow ({MODEL})")
    print(f"NapCat HTTP: http://{NAPCAT_HTTP_HOST}:{NAPCAT_HTTP_PORT}")
    print(f"WebSocket: ws://0.0.0.0:8081")
    print("=" * 50)
    
    # 在后台线程启动 WebSocket 服务器
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    
    # 启动 Flask HTTP 服务
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
