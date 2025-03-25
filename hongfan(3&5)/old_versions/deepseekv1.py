import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime, timezone
import os
import asyncio
from dotenv import load_dotenv



# ================= 新增模块 1：敏感信息检测器 =================
SENSITIVITY_LEVELS = ["non-sensitive", "sensitive", "very-sensitive"]

async def detect_sensitive_info(text):
    """实时检测用户输入的敏感级别"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",  # 使用更高精度的模型
            messages=[{
                "role": "system",
                "content": """请分析以下文本的敏感级别，返回JSON格式：
                {
                    "sensitivity_level": "non-sensitive/sensitive/very-sensitive",
                    "flagged_content": ["检测到的敏感内容片段1", "片段2"]
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
            "content": result.get("flagged_content", [])
        }
    except Exception as e:
        print(f"Sensitivity detection error: {e}")
        return {"level": "non-sensitive", "content": []}

# ================= 新增模块 2：交互式处理流程 =================
class SessionState:
    """会话状态管理器"""
    def __init__(self):
        self.pending_actions = {}  # {session_id: {action: ..., original_message: ...}}

session_state = SessionState()

async def process_sensitive_interaction(user_id, session_id, user_choice, chat_history):
    """处理用户的选择"""
    pending = session_state.pending_actions.get(session_id)
    if not pending:
        return chat_history  # 无待处理操作
    
    if user_choice == "remove":
        # 插入占位符记录
        placeholder = {
            "role": "system",
            "content": f"[用户于{datetime.now().isoformat()}删除敏感信息]",
            "metadata": {
                "original_content": pending["original_message"],
                "action_timestamp": datetime.utcnow().isoformat()
            }
        }
        # 替换原始消息
        modified_history = [
            msg for msg in chat_history 
            if msg.get("content") != pending["original_message"]
        ]
        modified_history.append(placeholder)
    else:
        modified_history = chat_history
    
    # 清除待处理状态
    session_state.pending_actions.pop(session_id, None)
    
    # 更新数据库
    await save_to_dynamodb(user_id, session_id, modified_history)
    return modified_history

# ================= 修改后的聊天主逻辑 =================
async def enhanced_chatbot(user_id, session_id, user_message, chat_history):
    # 第一步：检测敏感信息
    detection_result = await detect_sensitive_info(user_message)
    
    # 记录原始消息（带时间戳）
    original_message = {
        "role": "user",
        "content": user_message,
        "timestamp": datetime.utcnow().isoformat(),
        "sensitivity": detection_result
    }
    
    # 第二步：根据敏感级别处理
    if detection_result["level"] != "non-sensitive":
        # 保存待处理状态
        session_state.pending_actions[session_id] = {
            "action": "sensitive_pending",
            "original_message": original_message,
            "detection_time": datetime.utcnow().isoformat()
        }
        
        # 生成提示消息
        warning_msg = {
            "role": "system",
            "content": f"⚠️ 检测到{detection_result['level']}信息: {', '.join(detection_result['content'])}",
            "buttons": ["remove", "keep"]
        }
        
        # 更新聊天记录（不保存原始敏感消息）
        chat_history.append(warning_msg)
        return chat_history, user_id, session_id
    
    # 正常处理流程
    messages = [{"role": "system", "content": "You are a helpful AI assistant."}] + chat_history
    messages.append(original_message)
    
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    
    # 添加助手的回复
    assistant_msg = {
        "role": "assistant",
        "content": response.choices[0].message.content,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    chat_history.extend([original_message, assistant_msg])
    await save_to_dynamodb(user_id, session_id, chat_history)
    return chat_history, user_id, session_id

# ================= 修改后的前端界面 =================
with gr.Blocks() as demo:
    # ... 原有组件 ...
    
    # 新增交互组件
    action_choice = gr.Radio(
        choices=["remove", "keep"],
        label="请选择处理方式",
        visible=False
    )
    confirm_button = gr.Button("确认", visible=False)
    
    # 修改后的交互逻辑
    def toggle_visibility(chat_history):
        last_msg = chat_history[-1] if chat_history else None
        if last_msg and "buttons" in last_msg:
            return gr.update(visible=True), gr.update(visible=True)
        return gr.update(visible=False), gr.update(visible=False)
    
    chatbot_ui.change(
        toggle_visibility,
        inputs=[chatbot_ui],
        outputs=[action_choice, confirm_button]
    )
    
    confirm_button.click(
        process_sensitive_interaction,
        inputs=[user_id_input, session_id, action_choice, chatbot_ui],
        outputs=[chatbot_ui]
    )