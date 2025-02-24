import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime
import os
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 连接 AWS DynamoDB
session = boto3.Session(region_name=os.getenv("AWS_REGION"))
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# 初始化 OpenAI 客户端
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 异步存储聊天记录到 DynamoDB
async def save_to_dynamodb(user_id, session_id, chat_history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    print("Saving to DynamoDB:", data)
    await asyncio.to_thread(table.put_item, Item=data)

# 异步获取用户的所有聊天会话
async def get_sessions_by_user(user_id):
    response = await asyncio.to_thread(
        table.scan,
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user_id}
    )
    sessions = {item["session_id"]: json.loads(item["history"]) for item in response.get("Items", [])}
    return sessions

# 异步获取指定会话的聊天记录
async def get_chat_history(user_id, session_id):
    if not session_id:
        session_id = str(uuid.uuid4())
        return [], session_id

    response = await asyncio.to_thread(table.get_item, Key={"user_id": user_id, "session_id": session_id})
    if "Item" in response:
        return json.loads(response["Item"]["history"]), session_id
    return [], session_id

# 使用 OpenAI 生成聊天回复
async def chatbot(user_id, session_id, user_message, chat_history):
    if not session_id:
        session_id = str(uuid.uuid4())
    if chat_history is None:
        chat_history = []

    # 组织对话历史
    messages = [{"role": "system", "content": "You are a helpful AI assistant."}] + chat_history
    messages.append({"role": "user", "content": user_message})

    # 调用 OpenAI API
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
    )
    llm_response_text = response.choices[0].message.content

    # 更新聊天历史
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": llm_response_text})

    # 存储聊天记录
    await save_to_dynamodb(user_id, session_id, chat_history)
    return chat_history, user_id, session_id

# Gradio 前端
with gr.Blocks() as demo:
    gr.Markdown("# OpenAI LLM Chatbot with DynamoDB Storage (User ID + Sessions)")

    user_id_input = gr.Textbox(label="Enter Your User ID")
    session_id = gr.State("")
    chatbot_ui = gr.Chatbot(type="messages", label="Chatbot")
    user_input = gr.Textbox(label="Your Message")
    submit_button = gr.Button("Send")
    session_dropdown = gr.Dropdown(label="Select a Session", choices=[])

    # 加载用户所有会话
    async def load_sessions(user_id):
        sessions = await get_sessions_by_user(user_id)
        return list(sessions.keys())

    # 选择会话后加载聊天记录
    async def load_chat_history(user_id, session_id):
        history, session_id = await get_chat_history(user_id, session_id)
        return history, session_id

    session_dropdown.change(load_chat_history, [user_id_input, session_dropdown], [chatbot_ui, session_id])

    # 创建新会话
    def create_new_session(user_id):
        new_session_id = str(uuid.uuid4())
        return new_session_id, []

    new_session_button = gr.Button("New Chat Session")
    new_session_button.click(create_new_session, [user_id_input], [session_id, chatbot_ui])

    # 绑定聊天功能
    submit_button.click(chatbot, [user_id_input, session_id, user_input, chatbot_ui], [chatbot_ui, user_id_input, session_id])

    # 清空聊天
    clear_button = gr.Button("Clear Chat")
    clear_button.click(lambda: ([], ""), inputs=[], outputs=[chatbot_ui, session_id])

# 启动 Gradio
demo.launch(share=True)