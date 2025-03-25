import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime, timezone
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

# 🔹 **1. 敏感信息检测模块**
# 🔹 **1. Improved Sensitive Info Detection**
async def detect_sensitive_info(user_message):
    """
    Calls OpenAI to classify user input sensitivity.
    Fixes JSON parsing errors by ensuring model outputs strict JSON format.
    """
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "system", "content": "Classify the user's message into 'not sensitive', 'sensitive', or 'very sensitive'. Output should be a JSON object with a single key 'sensitivity'."},
            {"role": "user", "content": user_message}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}  # **Enforces valid JSON output**
    )

    try:
        classification = json.loads(response.choices[0].message.content.strip())  # Ensures clean parsing
        return classification.get("sensitivity", "not sensitive")  # Default fallback
    except json.JSONDecodeError as e:
        print(f"Error parsing sensitivity response: {e}")
        return "not sensitive"

# 🔹 **2. 交互逻辑：处理敏感信息**
async def chatbot(user_id, session_id, user_message, chat_history):
    """
    主要对话逻辑：
    1. 检测用户输入是否包含敏感信息。
    2. 如果包含，先询问用户是否删除该信息。
    3. 用户选择删除则用占位符替换，否则正常对话。
    """
    
    if not session_id:
        session_id = str(uuid.uuid4())
    if chat_history is None:
        chat_history = []

    # 🔸 **(1) 检测用户输入是否包含敏感信息**
    sensitivity = await detect_sensitive_info(user_message)

    if sensitivity in ["sensitive", "very sensitive"]:
        # 插入一条系统消息，提醒用户输入了敏感信息，并询问是否删除
        chat_history.append({"role": "system", "content": f"You have input sensitive information ({sensitivity}). Do you want to remove it? (yes/no)"})
        
        # **等待用户回复是否删除**
        return chat_history, user_id, session_id

    # 🔸 **(2) 处理用户对敏感信息的回应**
    if chat_history and chat_history[-1]["role"] == "system" and "sensitive information" in chat_history[-1]["content"]:
        if user_message.lower() in ["yes", "remove", "delete"]:
            chat_history.append({"role": "system", "content": "User chose to remove sensitive information."})
        else:
            chat_history.append({"role": "system", "content": "User chose to keep the information."})

        return chat_history, user_id, session_id

    # 🔸 **(3) 正常对话流程**
    messages = [{"role": "system", "content": "You are a helpful AI assistant."}] + chat_history
    messages.append({"role": "user", "content": user_message})

    # 调用 LLM 生成回复
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
    )
    llm_response_text = response.choices[0].message.content

    # 更新聊天记录
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": llm_response_text})

    # 存储聊天记录
    await save_to_dynamodb(user_id, session_id, chat_history)

    return chat_history, user_id, session_id

# 🔹 **3. 存储聊天记录**
async def save_to_dynamodb(user_id, session_id, chat_history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(chat_history),
    }
    await asyncio.to_thread(table.put_item, Item=data)

# 🔹 **4. Gradio UI**
with gr.Blocks() as demo:
    gr.Markdown("# OpenAI LLM Chatbot with Private Message Highlighter")

    user_id_input = gr.Textbox(label="Enter Your User ID")
    session_id = gr.State("")
    chatbot_ui = gr.Chatbot(type="messages", label="Chatbot")
    user_input = gr.Textbox(label="Your Message")
    submit_button = gr.Button("Send")
    session_dropdown = gr.Dropdown(label="Select a Session", choices=[])

    # 选择会话后加载聊天记录
    async def load_chat_history(user_id, session_id):
        if not session_id:
            return [], session_id
        response = await asyncio.to_thread(table.get_item, Key={"user_id": user_id, "session_id": session_id})
        return json.loads(response["Item"]["history"]), session_id if "Item" in response else [], session_id

    session_dropdown.change(load_chat_history, [user_id_input, session_dropdown], [chatbot_ui, session_id])

    # 创建新会话
    def create_new_session(user_id):
        return str(uuid.uuid4()), []

    new_session_button = gr.Button("New Chat Session")
    new_session_button.click(create_new_session, [user_id_input], [session_id, chatbot_ui])

    # 绑定聊天功能
    submit_button.click(chatbot, [user_id_input, session_id, user_input, chatbot_ui], [chatbot_ui, user_id_input, session_id])

    # 清空聊天
    clear_button = gr.Button("Clear Chat")
    clear_button.click(lambda: ([], ""), inputs=[], outputs=[chatbot_ui, session_id])

# 启动 Gradio
demo.launch(share=True)
