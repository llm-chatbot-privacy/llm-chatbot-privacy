import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime, timezone
import os
import asyncio
from dotenv import load_dotenv
import hashlib

# 加载环境变量
load_dotenv()

# 初始化 AWS DynamoDB
session = boto3.Session(region_name=os.getenv("AWS_REGION"))
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# 初始化 OpenAI 客户端
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= 增强型数据结构 =================
def convert_to_gradio_format(history):
    """将存储格式转换为Gradio显示格式"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            display_content = msg["content"]
            if "sensitivity" in msg:
                display_content += f"\n🔒敏感级别: {msg['sensitivity']['level'].upper()}"
            gradio_history.append((display_content, None))
        elif msg["role"] == "assistant":
            if gradio_history and gradio_history[-1][1] is None:
                gradio_history[-1] = (gradio_history[-1][0], msg["content"])
            else:
                gradio_history.append((None, msg["content"]))
        elif msg["role"] == "system":
            gradio_history.append((None, msg["content"]))
    return gradio_history

def convert_to_storage_format(gradio_history):
    """将Gradio格式转换为存储格式"""
    storage_history = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            sensitivity = {}
            if "🔒敏感级别:" in user_msg:
                content, sensitivity_part = user_msg.split("\n🔒敏感级别:")
                sensitivity = {"level": sensitivity_part.strip().lower()}
            else:
                content = user_msg
            
            storage_history.append({
                "role": "user",
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **({"sensitivity": sensitivity} if sensitivity else {})
            })
        
        if bot_msg:
            storage_history.append({
                "role": "system" if "⚠️" in bot_msg else "assistant",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage_history

# ================= 敏感信息处理模块 =================
class PrivacyManager:
    def __init__(self):
        self.pending_actions = {}  # {session_id: {message: ..., detection: ...}}

    def generate_message_hash(self, message):
        return hashlib.sha256(message.encode()).hexdigest()

privacy_manager = PrivacyManager()

async def detect_sensitive_info(text):
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo-1106",
            messages=[{
                "role": "system",
                "content": """分析文本敏感信息，返回JSON格式：
                {
                    "sensitivity_level": "non-sensitive/sensitive/very-sensitive",
                    "flagged_items": ["检测到的敏感内容"],
                    "reason": "分类依据说明"
                }"""
            }, {
                "role": "user", 
                "content": text
            }],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "level": result["sensitivity_level"],
            "items": result.get("flagged_items", []),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"敏感信息检测失败: {e}")
        return {"level": "non-sensitive", "items": [], "reason": ""}

# ================= 增强版数据库操作 =================
async def save_to_dynamodb(user_id, session_id, history, sensitivity_level=None, user_action=None):
    """保存完整对话记录和隐私操作"""
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "sensitivity_level": sensitivity_level or "none",
        "user_action": user_action or "none",
        "metadata": {
            "sensitive_operations": sum(1 for msg in history if "sensitivity" in msg),
            "last_modified": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
        print("✅ 数据库记录已更新:", json.dumps(data, indent=2))
    except Exception as e:
        print("❌ 数据库保存失败:", str(e))
        raise

# ================= 核心聊天逻辑 =================
async def privacy_aware_chatbot(user_id, session_id, user_input, chat_history):
    storage_history = convert_to_storage_format(chat_history)
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    detection = await detect_sensitive_info(user_input)
    message_hash = privacy_manager.generate_message_hash(user_input)
    
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sensitivity": detection,
        "hash": message_hash
    }
    
    if detection["level"] != "non-sensitive":
        privacy_manager.pending_actions[session_id] = {
            "message": user_message,
            "detection": detection
        }
        
        warning_msg = {
            "role": "system",
            "content": f"⚠️ 检测到 {detection['level']} 级敏感信息: {detection['reason']}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        storage_history.extend([user_message, warning_msg])
        await save_to_dynamodb(
            user_id, session_id, 
            storage_history,
            sensitivity_level=detection["level"],
            user_action="pending"
        )
        return convert_to_gradio_format(storage_history), session_id
    
    messages = [{"role": "system", "content": "你是一个有用的助手"}] + storage_history
    messages.append(user_message)
    
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    
    assistant_msg = {
        "role": "assistant",
        "content": response.choices[0].message.content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    storage_history.extend([user_message, assistant_msg])
    await save_to_dynamodb(user_id, session_id, storage_history)
    return convert_to_gradio_format(storage_history), session_id

async def handle_user_choice(user_id, session_id, choice, chat_history):
    storage_history = convert_to_storage_format(chat_history)
    
    pending = privacy_manager.pending_actions.get(session_id)
    if not pending:
        return chat_history, session_id
    
    action_record = {
        "action": choice,
        "original_hash": pending["message"]["hash"],
        "detection_level": pending["detection"]["level"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    placeholder = {
        "role": "system",
        "content": f"[用户选择{'删除' if choice == 'remove' else '保留'}敏感信息]",
        "action_record": action_record,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if choice == "remove":
        new_history = [
            msg for msg in storage_history 
            if not (msg.get("hash") == pending["message"]["hash"] or 
                   "⚠️" in msg.get("content", ""))
        ]
    else:
        new_history = [
            msg for msg in storage_history 
            if "⚠️" not in msg.get("content", "")
        ]
    
    new_history.append(placeholder)
    
    await save_to_dynamodb(
        user_id, session_id, 
        new_history,
        sensitivity_level=pending["detection"]["level"],
        user_action=choice
    )
    
    del privacy_manager.pending_actions[session_id]
    return convert_to_gradio_format(new_history), session_id

# ================= Gradio界面 =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 隐私保护聊天机器人")
    
    with gr.Row():
        user_id_input = gr.Textbox(label="用户ID", placeholder="输入唯一标识...")
        session_id = gr.State()
    
    chatbot = gr.Chatbot(
        label="对话记录",
        bubble_full_width=False,
        height=500
    )
    
    msg = gr.Textbox(
        label="输入消息",
        lines=2
    )
    
    with gr.Row():
        submit_btn = gr.Button("发送", variant="primary")
        clear_btn = gr.Button("清空对话", variant="secondary")
    
    with gr.Row(visible=False) as action_panel:
        choice = gr.Radio(
            ["remove", "keep"], 
            label="敏感信息操作选择",
            info="请确认如何处理检测到的敏感信息",
            interactive=True
        )
        confirm_btn = gr.Button("确认操作", variant="stop")

    def toggle_action_panel(history):
        try:
            if history and history[-1][1]:
                return gr.update(visible="⚠️" in history[-1][1])
            return gr.update(visible=False)
        except Exception:
            return gr.update(visible=False)
    
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])
    
    confirm_btn.click(
        handle_user_choice,
        [user_id_input, session_id, choice, chatbot],
        [chatbot, session_id]
    )
    
    chatbot.change(
        toggle_action_panel,
        [chatbot],
        [action_panel]
    )
    
    clear_btn.click(
        lambda: ([], str(uuid.uuid4())),
        outputs=[chatbot, session_id]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )