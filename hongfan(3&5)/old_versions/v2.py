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

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= Enhanced Data Structures =================
CATEGORY_MAPPING = {
    "个人金融/收入/税务": "financial",
    "个人履历": "career",
    "家庭信息": "family",
    "个人社会关系": "social_relations",
    "个人喜好": "preferences",
    "其他": "other"
}

# def convert_to_gradio_format(history):
#     """Convert storage format to Gradio display format"""
#     gradio_history = []
#     for msg in history:
#         if msg["role"] == "user":
#             display_content = msg["content"]
#             if "privacy_check" in msg:
#                 display_content += f"\n🔒 Privacy Alert: {msg['privacy_check']['message']}"
#             gradio_history.append((display_content, None))
#         elif msg["role"] == "assistant":
#             if gradio_history and gradio_history[-1][1] is None:
#                 gradio_history[-1] = (gradio_history[-1][0], msg["content"])
#             else:
#                 gradio_history.append((None, msg["content"]))
#     return gradio_history

def convert_to_gradio_format(storage_history):
    """将存储格式（字典列表）转换为Gradio显示格式（元组列表）"""
    gradio_history = []
    for msg in storage_history:
        # 确保处理的是字典类型
        if not isinstance(msg, dict):
            continue
            
        if msg.get("role") == "user":
            display_content = msg.get("content", "")
            
            # 添加隐私警告信息
            if "privacy_check" in msg:
                alert_info = (
                    f"\n🔒 检测到 {msg['privacy_check']['category']} 信息 "
                    f"(敏感度 {msg['privacy_check']['score']}/10)"
                )
                display_content += alert_info
                
            gradio_history.append((display_content, None))
            
        elif msg.get("role") in ["assistant", "system"]:
            # 处理系统警告消息
            if msg.get("role") == "system":
                if gradio_history:
                    # 将系统消息附加到上一条用户消息
                    last_user = gradio_history[-1][0]
                    gradio_history[-1] = (last_user, msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
            else:
                # 正常助手消息
                if gradio_history and gradio_history[-1][1] is None:
                    gradio_history[-1] = (gradio_history[-1][0], msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
    
    return gradio_history

# ================= Privacy Detection Module =================
async def detect_sensitive_info(text, privacy_settings):
    """Detect sensitive information with category classification"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo-1106",
            messages=[{
                "role": "system",
                "content": f"""Analyze text for sensitive information. Respond in JSON:
                {{
                    "category": "{'/'.join(CATEGORY_MAPPING.keys())}",
                    "score": 1-10,
                    "reason": "explanation"
                }}
                Categories:
                - 个人金融/收入/税务: Financial information
                - 个人履历: Career/education background
                - 家庭信息: Family details
                - 个人社会关系: Social relationships
                - 个人喜好: Personal preferences
                - 其他: Other non-sensitive"""
            }, {
                "role": "user", 
                "content": text
            }],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        category = CATEGORY_MAPPING.get(result["category"], "other")
        score = int(result["score"])
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

# ================= Core Chat Logic =================
async def privacy_aware_chatbot(user_id, session_id, user_input, chat_history, privacy_settings):
    """Main chatbot handler with privacy checks"""
    # 转换Gradio格式的历史记录到内部存储格式
    storage_history = convert_to_gradio_format(chat_history)
    
    # 首次消息初始化
    if not storage_history:
        storage_history.append({
            "role": "assistant",
            "content": "您好！请告诉我一些关于您的基本情况。",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return convert_to_gradio_format(storage_history), session_id, privacy_settings
    
    # 敏感信息检测
    detection = await detect_sensitive_info(user_input, privacy_settings)
    
    # 添加用户消息（带隐私检查）
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "privacy_check": detection
    }
    storage_history.append(user_message)
    
    # 添加隐私警告（如果超过阈值）
    if detection["exceeded"]:
        warning_msg = {
            "role": "system",
            "content": f"⚠️ 您提供的信息涉及 [{detection['category']}]，敏感度评分 {detection['score']} 超过您设置的阈值 {detection['threshold']}。请注意隐私安全！",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        storage_history.append(warning_msg)
    
    # 构建消息时确保正确的字典访问
    messages = [{"role": "system", "content": "你是一个注重隐私保护的助手"}]
    for msg in storage_history:
        if isinstance(msg, dict):  # 确保是字典类型
            if msg.get("role") != "system":
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
    
    # 生成助手响应
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7
    )
    
    # 添加助手消息
    assistant_msg = {
        "role": "assistant",
        "content": response.choices[0].message.content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    storage_history.append(assistant_msg)
    
    # Save to database
    async def save_to_dynamodb(user_id, session_id, history, privacy_settings):
        """更新后的保存函数"""
        data = {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "history": json.dumps(history, ensure_ascii=False),
            "privacy_settings": json.dumps(privacy_settings),
            "metadata": {
                "sensitive_operations": sum(1 for msg in history if "privacy_check" in msg),
                "last_modified": datetime.now(timezone.utc).isoformat()
            }
        }
    
    return convert_to_gradio_format(storage_history), session_id, privacy_settings

# ================= Gradio Interface =================
def create_privacy_sliders():
    """Create privacy slider components"""
    with gr.Row():
        return [
            gr.Slider(1, 10, value=5, label=cn, interactive=True)
            for cn in CATEGORY_MAPPING.keys() if cn != "其他"
        ]

# ================= Gradio Interface =================
def create_privacy_sliders():
    """Create privacy slider components"""
    with gr.Row():
        return [
            gr.Slider(1, 10, value=5, label=cn, interactive=True)
            for cn in CATEGORY_MAPPING.keys() if cn != "其他"
        ]

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
            session_id = gr.State()
            privacy_settings = gr.State()
            chatbot = gr.Chatbot(height=500)
            msg = gr.Textbox(label="输入消息", lines=2)
            submit_btn = gr.Button("发送", variant="primary")
    
    # Initialize privacy settings
    def initialize_settings(user_id, *slider_values):
        # 返回三个值：privacy_settings, chat_panel状态, setup_panel状态
        settings = dict(zip([v for k,v in CATEGORY_MAPPING.items() if k != "其他"], slider_values))
        return (
            settings,  # 对应privacy_settings State组件
            gr.update(visible=True),  # 对应chat_panel
            gr.update(visible=False)  # 对应setup_panel
        )
    
    init_btn.click(
        initialize_settings,
        [user_id_input] + sliders,
        [privacy_settings, chat_panel, setup_panel]  # 三个输出目标
    )
    
    # Chat interaction
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, chatbot, privacy_settings],
        [chatbot, session_id, privacy_settings]
    ).then(lambda: "", None, [msg])

if __name__ == "__main__":
    demo.launch(share=True)