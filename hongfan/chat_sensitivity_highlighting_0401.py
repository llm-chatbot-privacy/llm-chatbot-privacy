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
def convert_to_gradio_format(history):
    """Convert storage format to Gradio display format"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            display_content = msg["content"]
            if "sensitivity" in msg:
                display_content += f"\n🔒Sensitivity Level: {msg['sensitivity']['level'].upper()}"
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
            sensitivity = {}
            if "🔒Sensitivity Level:" in user_msg:
                content, sensitivity_part = user_msg.split("\n🔒Sensitivity Level:")
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

# ================= Privacy Handling Module =================
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
            model="gpt-4o-2024-08-06",
            messages=[{
                "role": "system",
                "content":( 
                    "Analyze text for sensitive information "
                    "Consider the following examples:\n"
                    "1. Personal Information Disclosure: “My name is Sarah, and I live in San Francisco. My birthday is May 3rd.”\n"
                            "2. Sensitive Topic Exploration: “I've been feeling anxious lately and having trouble sleeping. What should I do?”\n"
                            "3. Ethical Question: “I saw my coworker stealing small items from the office. Should I report it?”\n"
                            "4. Family/Social Information: “Here is a text exchange I had with my partner last week. Am I in the wrong?”\n"
                            "5. Medical Data: “I have diabetes and take insulin regularly. Are there foods I should avoid?”\n"
                            "6. Professional Information: “I'm frustrated at work. My manager at XYZ Corp doesn't appreciate my efforts.”\n"
                            "7. Future Plans: “I'm thinking about taking a long vacation next month. What's a good place to travel?”\n"
                            "8. Financial Information: “I earn about $75,000 a year, and my credit score is around 680. Can I afford a new car?”\n"
                            "9. Location Information: “I often visit the Starbucks on Main Street after work around 6 PM.”\n"
                            "10. Political Ideology: “I voted for [candidate or party], but lately I’m reconsidering because of recent policies.”\n\n"
                    "Return a JSON object with the following keys:\n"
                    '{"sensitivity_level": "non-sensitive/sensitive/very-sensitive", "flagged_items": ["detected sensitive content"], "reason": "classification rationale"}'
              )
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
        print(f"Sensitivity detection failed: {e}")
        return {"level": "non-sensitive", "items": [], "reason": ""}

# ================= Enhanced Database Operations =================
async def save_to_dynamodb(user_id, session_id, history, sensitivity_level=None, user_action=None):
    """Save complete conversation history with privacy actions"""
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
        print("✅ Database record updated:", json.dumps(data, indent=2))
    except Exception as e:
        print("❌ Database save failed:", str(e))
        raise

# ================= Core Chat Logic =================
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
            "content": f"⚠️ Detected {detection['level']} level sensitive information: {detection['reason']}",
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
    
    messages = [{"role": "system", "content": "You are a helpful assistant"}] + storage_history
    messages.append(user_message)
    
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-2024-08-06",
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
        "content": f"[User chose to {'remove' if choice == 'remove' else 'keep'} sensitive information]",
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

# ================= Gradio Interface =================

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Privacy-Aware Chatbot: Chat Content Sensitive Info Highlighter")
    
    with gr.Row():
        user_id_input = gr.Textbox(label="User ID", placeholder="Enter unique identifier OR your provided participant ID...")
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
    
    # Modified button layout section
    with gr.Row():
        # Empty element to push button to right
        gr.Column(scale=3) 
        with gr.Column(scale=1):
            submit_btn = gr.Button("Send", variant="primary", size="lg")
    
    # Rest of the code remains the same...
    with gr.Row(visible=False) as action_panel:
        choice = gr.Radio(
            ["remove", "keep"], 
            label="Sensitive Information Handling: \n Do you want to keep or remove your detected sensitive info?",
            info="Confirm how to handle detected sensitive information",
            interactive=True
        )
        confirm_btn = gr.Button("Confirm Action", variant="stop")

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

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )