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

# Load environment variables
load_dotenv()

# Initialize AWS DynamoDB
session = boto3.Session(region_name=os.getenv("AWS_REGION"))
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# Initialize OpenAI client (v1.0.0+)
openai.api_key = os.getenv("OPENAI_API_KEY")

# ================= Enhanced Data Structures =================
CATEGORY_MAPPING = {
    "个人金融/收入/税务": "financial",
    "个人履历": "career",
    "家庭信息": "family",
    "个人社会关系": "social_relations",
    "个人喜好": "preferences",
    "其他": "other"
}

def convert_to_gradio_format(internal_history):
    """Convert internal storage format (list of dicts) to Gradio display format (list of tuples)"""
    gradio_history = []
    for msg in internal_history:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            display_content = msg.get("content", "")
            if "privacy_check" in msg:
                alert_info = (
                    f"\n🔒 检测到 {msg['privacy_check']['category']} 信息 "
                    f"(敏感度 {msg['privacy_check']['score']}/10)"
                )
                display_content += alert_info
            gradio_history.append((display_content, None))
        elif msg.get("role") in ["assistant", "system"]:
            # For system messages, attach them to the previous user message if exists.
            if msg.get("role") == "system":
                if gradio_history:
                    last_user = gradio_history[-1][0]
                    gradio_history[-1] = (last_user, msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
            else:
                if gradio_history and gradio_history[-1][1] is None:
                    gradio_history[-1] = (gradio_history[-1][0], msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
    return gradio_history

async def detect_sensitive_info(text, privacy_settings):
    """Detect sensitive info using the new async OpenAI ChatCompletion API"""
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo-1106",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze text for sensitive information. Respond in JSON with keys: "
                        "category, score, reason. Categories: 个人金融/收入/税务, 个人履历, 家庭信息, 个人社会关系, 个人喜好, 其他."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.2
        )
        result = json.loads(response.choices[0].message.content)
        category = CATEGORY_MAPPING.get(result.get("category", "其他"), "other")
        score = int(result.get("score", 0))
        threshold = privacy_settings.get(category, 0)
        
        return {
            "category": category,
            "score": score,
            "threshold": threshold,
            "exceeded": score > threshold,
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"Sensitivity detection failed: {e}")
        return {"category": "other", "exceeded": False}

async def save_to_dynamodb(user_id, session_id, history, privacy_settings):
    """Save chat history to DynamoDB"""
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "privacy_settings": json.dumps(privacy_settings, ensure_ascii=False),
        "metadata": {
            "sensitive_operations": sum(1 for msg in history if "privacy_check" in msg),
            "last_modified": datetime.now(timezone.utc).isoformat()
        }
    }
    await asyncio.to_thread(table.put_item, Item=data)

async def privacy_aware_chatbot(user_id, session_id, user_input, internal_history, privacy_settings):
    """Core privacy-aware chatbot logic"""
    if not internal_history:
        initial_msg = {
            "role": "assistant",
            "content": "您好！请告诉我一些关于您的基本情况。",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(initial_msg)
        return convert_to_gradio_format(internal_history), session_id, internal_history, privacy_settings

    # Detect sensitive information
    detection = await detect_sensitive_info(user_input, privacy_settings)
    
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "privacy_check": detection
    }
    internal_history.append(user_message)
    
    # If detection exceeds the threshold, add a system warning message
    if detection.get("exceeded"):
        warning_msg = {
            "role": "system",
            "content": f"⚠️ 您提供的信息涉及 [{detection['category']}]，敏感度评分 {detection['score']} 超过您设置的阈值 {detection['threshold']}。请注意隐私安全！",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(warning_msg)
    
    # Build message context with all history messages
    messages = [{"role": "system", "content": "你是一个注重隐私保护的助手。"}]
    for msg in internal_history:
        if isinstance(msg, dict):
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    
    assistant_msg = {
        "role": "assistant",
        "content": response.choices[0].message.content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    internal_history.append(assistant_msg)
    
    await save_to_dynamodb(user_id, session_id, internal_history, privacy_settings)
    
    return convert_to_gradio_format(internal_history), session_id, internal_history, privacy_settings

def create_privacy_sliders():
    """Create privacy slider components"""
    with gr.Row():
        return [
            gr.Slider(1, 10, value=5, label=cn, interactive=True)
            for cn in CATEGORY_MAPPING.keys() if cn != "其他"
        ]

# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 隐私感知聊天机器人")
    
    # Privacy Settings Section
    with gr.Row(visible=True) as setup_panel:
        with gr.Column():
            user_id_input = gr.Textbox(label="用户ID", placeholder="输入唯一标识符...")
            sliders = create_privacy_sliders()
            init_btn = gr.Button("初始化隐私设置", variant="primary")
    
    # Chat Interface
    with gr.Row(visible=False) as chat_panel:
        with gr.Column():
            session_id = gr.State(uuid.uuid4().hex)
            privacy_settings = gr.State()
            internal_history = gr.State([])
            chatbot = gr.Chatbot(height=500)
            msg = gr.Textbox(label="输入消息", lines=2)
            submit_btn = gr.Button("发送", variant="primary")
    
    def initialize_settings(user_id, *slider_values):
        settings = dict(zip([k for k in CATEGORY_MAPPING.keys() if k != "其他"], slider_values))
        return (
            settings,
            gr.update(visible=True),
            gr.update(visible=False),
            []
        )
    
    init_btn.click(
        initialize_settings,
        [user_id_input] + sliders,
        [privacy_settings, chat_panel, setup_panel, internal_history]
    )
    
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, internal_history, privacy_settings],
        [chatbot, session_id, internal_history, privacy_settings]
    ).then(lambda: "", None, [msg])

if __name__ == "__main__":
    demo.launch(share=True)
