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

# ================= 消息格式转换工具 =================
def convert_to_gradio_format(history):
    """将内部存储格式转换为Gradio需要的格式"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            gradio_history.append((msg["content"], None))
        elif msg["role"] == "assistant":
            if gradio_history and gradio_history[-1][1] is None:
                gradio_history[-1] = (gradio_history[-1][0], msg["content"])
            else:
                gradio_history.append((None, msg["content"]))
        elif msg["role"] == "system":
            gradio_history.append((None, msg["content"]))
    return gradio_history

def convert_to_storage_format(gradio_history):
    """将Gradio格式转换为内部存储格式"""
    storage_history = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            storage_history.append({
                "role": "user",
                "content": user_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if bot_msg:
            storage_history.append({
                "role": "assistant" if "assistant" in bot_msg else "system",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage_history

# ================= 敏感信息处理模块 =================
class PrivacyManager:
    def __init__(self):
        self.pending_actions = {}

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
                "content": """分析以下文本的敏感信息，返回JSON格式：
                {
                    "sensitivity_level": "non-sensitive/sensitive/very-sensitive",
                    "flagged_items": [],
                    "reason": "说明"
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

# ================= 核心聊天逻辑 =================
async def privacy_aware_chatbot(user_id, session_id, user_input, chat_history):
    # 转换Gradio格式为内部存储格式
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
        privacy_manager.pending_actions[session_id] = user_message
        
        warning_msg = {
            "role": "system",
            "content": f"⚠️ 检测到 {detection['level']} 级敏感信息: {detection['reason']}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        storage_history.extend([user_message, warning_msg])
        await save_to_dynamodb(user_id, session_id, storage_history)
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
    
    if choice == "remove":
        placeholder = {
            "role": "system",
            "content": "[用户选择删除敏感信息]",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 移除原始敏感消息和警告消息
        new_history = [
            msg for msg in storage_history 
            if msg.get("content") != pending["content"]
            and not msg.get("content", "").startswith("⚠️")
        ]
        new_history.append(placeholder)
    else:
        new_history = [
            msg for msg in storage_history 
            if not msg.get("content", "").startswith("⚠️")
        ]
    
    await save_to_dynamodb(user_id, session_id, new_history)
    return convert_to_gradio_format(new_history), session_id

# ================= 数据库操作 =================
async def save_to_dynamodb(user_id, session_id, history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history)
    }
    await asyncio.to_thread(table.put_item, Item=data)

# ================= Gradio界面 =================
with gr.Blocks() as demo:
    gr.Markdown("# 隐私保护聊天机器人")
    
    user_id_input = gr.Textbox(label="用户ID")
    session_id = gr.State()
    
    chatbot = gr.Chatbot(label="对话记录")
    msg = gr.Textbox(label="输入消息")
    
    with gr.Row():
        submit_btn = gr.Button("发送", variant="primary")
        clear_btn = gr.Button("清空对话")
    
    with gr.Row(visible=False) as action_panel:
        choice = gr.Radio(["remove", "keep"], label="请选择操作")
        confirm_btn = gr.Button("确认")

    def toggle_action_panel(history):
        last_msg = history[-1][1] if history else ""
        return gr.update(visible="⚠️" in last_msg)
    
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
    demo.launch(share=True)