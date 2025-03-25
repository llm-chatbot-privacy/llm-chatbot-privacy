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

# ================= Privacy Configuration =================
PRIVACY_CATEGORIES = {
    "financial": "Financial/Income/Tax Information",
    "career": "Career/Education Background",
    "family": "Family Information",
    "social": "Social Relationships",
    "preferences": "Personal Preferences"
}

class PrivacyConfig:
    def __init__(self):
        self.configs = {}
    
    def update_config(self, user_id, config):
        self.configs[user_id] = config
    
    def get_config(self, user_id):
        return self.configs.get(user_id, {})
    
privacy_config = PrivacyConfig()

# ================= Enhanced Data Structures =================
def convert_to_gradio_format(history):
    """Convert storage format to Gradio display format"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            display_content = msg["content"]
            if "privacy_alert" in msg:
                display_content += f"\n🚨 Privacy Alert: {msg['privacy_alert']}"
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
    """Convert Gradio format to storage format"""
    storage_history = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            alert = None
            if "🚨 Privacy Alert:" in user_msg:
                content, alert_part = user_msg.split("\n🚨 Privacy Alert:")
                alert = alert_part.strip()
            else:
                content = user_msg
            
            entry = {
                "role": "user",
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if alert:
                entry["privacy_alert"] = alert
            storage_history.append(entry)
        
        if bot_msg:
            storage_history.append({
                "role": "system" if "⚠️" in bot_msg else "assistant",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage_history

# ================= Privacy Detection Module =================
class PrivacyManager:
    def __init__(self):
        self.pending_actions = {}
    
    async def detect_privacy_issues(self, text, user_id):
        """Detect privacy issues based on user configuration"""
        try:
            config = privacy_config.get_config(user_id)
            if not config:
                return None
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4",
                messages=[{
                    "role": "system",
                    "content": f"""Analyze text for privacy issues in these categories: {', '.join(PRIVACY_CATEGORIES.values())}. 
                    For each detected category, estimate sensitivity level 1-10. 
                    Return JSON format: {{
                        "issues": [{{
                            "category": "category_key",
                            "sensitivity": 1-10,
                            "content": "detected content",
                            "explanation": "reason for detection"
                        }}]
                    }}"""
                }, {
                    "role": "user",
                    "content": text
                }],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            alerts = []
            
            for issue in result.get("issues", []):
                category = issue.get("category")
                sensitivity = issue.get("sensitivity", 0)
                user_threshold = config.get(category, 0)
                
                if sensitivity > user_threshold:
                    alerts.append({
                        "category": PRIVACY_CATEGORIES.get(category, "Unknown"),
                        "user_threshold": user_threshold,
                        "detected_level": sensitivity,
                        "content": issue.get("content"),
                        "explanation": issue.get("explanation")
                    })
            
            return alerts if alerts else None
            
        except Exception as e:
            print(f"Privacy detection failed: {str(e)}")
            return None

privacy_manager = PrivacyManager()

# ================= Enhanced Database Operations =================
async def save_to_dynamodb(user_id, session_id, history):
    """Save conversation with privacy metadata"""
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "privacy_config": privacy_config.get_config(user_id),
        "metadata": {
            "privacy_alerts": sum(1 for msg in history if "privacy_alert" in msg),
            "last_modified": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
        print("✅ Database record updated")
    except Exception as e:
        print(f"❌ Database save failed: {str(e)}")
        raise

# ================= Core Chat Logic =================
async def privacy_aware_chatbot(user_id, session_id, user_input, chat_history):
    storage_history = convert_to_storage_format(chat_history)
    
    # Initialize session
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Detect privacy issues
    alerts = await privacy_manager.detect_privacy_issues(user_input, user_id)
    
    # Build user message
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Add alerts if any
    if alerts:
        alert_text = " | ".join([
            f"{alert['category']} (Your threshold: {alert['user_threshold']}/10, Detected: {alert['detected_level']}/10)"
            for alert in alerts
        ])
        user_message["privacy_alert"] = alert_text
        
        # Add system warning
        warning_msg = {
            "role": "system",
            "content": "⚠️ Your input contains sensitive information exceeding your privacy preferences. Please be cautious.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        storage_history.append(warning_msg)
    
    # Generate assistant response
    messages = [{"role": "system", "content": "You are a helpful assistant"}] + storage_history
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
    
    # Update history
    storage_history.extend([user_message, assistant_msg])
    await save_to_dynamodb(user_id, session_id, storage_history)
    
    return convert_to_gradio_format(storage_history), session_id

# ================= Gradio Interface =================
def create_privacy_settings_ui():
    with gr.Blocks() as settings_ui:
        gr.Markdown("## 🔐 Set Your Privacy Preferences (1-10)")
        sliders = {}
        for category_key, category_label in PRIVACY_CATEGORIES.items():
            sliders[category_key] = gr.Slider(
                minimum=1,
                maximum=10,
                step=1,
                label=category_label,
                info=f"How careful do you want to be about sharing {category_label.lower()}?",
                value=5
            )
        save_btn = gr.Button("Save Preferences", variant="primary")
    
    return settings_ui, sliders, save_btn

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Privacy-Aware Chatbot with Personalized Settings")
    
    # User configuration section
    settings_ui, privacy_sliders, save_btn = create_privacy_settings_ui()
    
    # Chat section
    with gr.Tab("Chat"):
        with gr.Row():
            user_id_input = gr.Textbox(
                label="User ID",
                placeholder="Enter unique identifier...",
                info="Required to save your preferences"
            )
            session_id = gr.State()
        
        chatbot = gr.Chatbot(
            label="Conversation History",
            bubble_full_width=False,
            height=500
        )
        
        msg = gr.Textbox(
            label="Input Message",
            placeholder="Type your message here...",
            lines=2
        )
        
        with gr.Row():
            gr.Column(scale=3)
            with gr.Column(scale=1):
                submit_btn = gr.Button("Send", variant="primary")
    
    # Event handling
    def save_preferences(user_id, **slider_values):
        if not user_id.strip():
            raise gr.Error("Please enter a User ID first")
        privacy_config.update_config(user_id, slider_values)
        return "Preferences saved successfully!"
    
    save_btn.click(
        save_preferences,
        inputs=[user_id_input] + list(privacy_sliders.values()),
        outputs=gr.Textbox(visible=False)
    )
    
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )