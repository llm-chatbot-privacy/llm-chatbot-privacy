import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime, timezone
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize AWS DynamoDB
session = boto3.Session(region_name=os.getenv("AWS_REGION"))
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= Business Value Assessment Module =================
BUSINESS_VALUE_LEVELS = ["non-valuable", "valuable", "very-valuable"]

async def assess_business_value(text: str) -> dict:
    """Analyze text for commercial value to businesses"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": """Analyze text for commercial value to businesses. Return JSON:
                {
                    "value_level": "non-valuable/valuable/very-valuable",
                    "valuable_items": ["detected items"],
                    "reason": "analysis rationale"
                }"""
            }, {
                "role": "user",
                "content": text
            }],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "level": result["value_level"],
            "items": result.get("valuable_items", []),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"Value assessment failed: {e}")
        return {"level": "non-valuable", "items": [], "reason": ""}

# ================= Value Alert System =================
class ValueAlertManager:
    def __init__(self):
        self.pending_alerts = {}  # {session_id: alert_data}

value_alert_manager = ValueAlertManager()

# ================= Enhanced Chat Logic =================
async def value_aware_chatbot(user_id: str, session_id: str, user_input: str, chat_history: list) -> tuple:
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Perform value assessment
    assessment = await assess_business_value(user_input)
    
    # Store original message with metadata
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value_assessment": assessment
    }
    
    if assessment["level"] != "non-valuable":
        # Store pending alert
        value_alert_manager.pending_alerts[session_id] = {
            "original_message": user_message,
            "assessment": assessment
        }
        
        # Create alert message
        alert_msg = {
            "role": "system",
            "content": f"⚠️ Commercial value detected [{assessment['level'].upper()}]: {', '.join(assessment['items'])}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        updated_history = chat_history + [user_message, alert_msg]
        await save_to_dynamodb(user_id, session_id, updated_history)
        return updated_history, session_id
    
    # Normal processing flow
    messages = [{"role": "system", "content": "You are a helpful assistant"}] + chat_history
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
    
    updated_history = chat_history + [user_message, assistant_msg]
    await save_to_dynamodb(user_id, session_id, updated_history)
    return updated_history, session_id

async def handle_value_acknowledgement(user_id: str, session_id: str, chat_history: list) -> tuple:
    """Process user acknowledgement of value alert"""
    pending = value_alert_manager.pending_alerts.get(session_id)
    if not pending:
        return chat_history, session_id
    
    # Remove alert messages and keep original
    new_history = [
        msg for msg in chat_history 
        if not ("⚠️ Commercial value detected" in msg.get("content", "") 
             and msg["role"] == "system")
    ]
    
    # Generate normal response
    messages = [{"role": "system", "content": "You are a helpful assistant"}] + new_history
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
    
    final_history = new_history + [assistant_msg]
    await save_to_dynamodb(user_id, session_id, final_history)
    
    del value_alert_manager.pending_alerts[session_id]
    return final_history, session_id

# ================= Enhanced Database Operations =================
async def save_to_dynamodb(user_id: str, session_id: str, history: list):
    """Save conversation with value metadata"""
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "value_metadata": {
            "total_alerts": sum(1 for msg in history if "value_assessment" in msg),
            "last_assessed": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
        print("Database updated:", data)
    except Exception as e:
        print("Database save failed:", str(e))
        raise

# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔍 Business Value Aware Chatbot")
    
    with gr.Row():
        user_id_input = gr.Textbox(label="User ID", placeholder="Enter unique identifier...")
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
    
    with gr.Row(visible=False) as alert_panel:
        ack_btn = gr.Button("Acknowledge & Continue", variant="secondary")
    
    def toggle_alert_panel(history):
        try:
            last_msg = history[-1][1] if history else ""
            return gr.update(visible="⚠️ Commercial value detected" in last_msg)
        except Exception:
            return gr.update(visible=False)
    
    submit_btn.click(
        value_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])
    
    ack_btn.click(
        handle_value_acknowledgement,
        [user_id_input, session_id, chatbot],
        [chatbot, session_id]
    )
    
    chatbot.change(
        toggle_alert_panel,
        [chatbot],
        [alert_panel]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )