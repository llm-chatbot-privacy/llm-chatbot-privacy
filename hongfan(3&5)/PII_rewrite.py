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

# ================= Data Conversion Functions =================
def convert_to_gradio_format(history):
    """Convert storage format to Gradio display format"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            display_content = msg["content"]
            if "metadata" in msg:
                pii_info = "\n".join([f"{k}: {v}" for k,v in msg["metadata"].get("removed_pii", {}).items()])
                display_content += f"\n🔒 Removed PII:\n{pii_info}"
            gradio_history.append((display_content, None))
        elif msg["role"] == "assistant":
            if gradio_history and gradio_history[-1][1] is None:
                gradio_history[-1] = (gradio_history[-1][0], msg["content"])
            else:
                gradio_history.append((None, msg["content"]))
    return gradio_history

def convert_to_storage_format(gradio_history):
    """Convert Gradio format to storage format"""
    storage_history = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            storage_history.append({
                "role": "user",
                "content": user_msg.split("\n🔒")[0],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if bot_msg:
            storage_history.append({
                "role": "system" if "⚠️" in bot_msg else "assistant",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage_history

# ================= Privacy Management =================
class PrivacyManager:
    def __init__(self):
        self.pending_rewrites = {}  # {session_id: {original: ..., revised: ..., removed_pii: ...}}

privacy_manager = PrivacyManager()

async def detect_and_rewrite_pii(text):
    """Detect and rewrite PII using GPT-4"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo-1106",
            messages=[{
                "role": "system",
                "content": """Perform the following tasks:
1. Identify PII (Personally Identifiable Information) including: age, address, phone numbers, ID numbers, race, income, etc.
2. Generate revised text with PII removed/obfuscated
3. Return JSON format:
{
    "original": "original text",
    "revised": "revised text",
    "removed_pii": {
        "pii_type": ["specific content"],
        "age": ["35"],
        "address": ["123 Main St"]
    }
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
            "original": result["original"],
            "revised": result["revised"],
            "removed_pii": result.get("removed_pii", {})
        }
    except Exception as e:
        print(f"PII rewriting failed: {e}")
        return {"original": text, "revised": text, "removed_pii": {}}

# ================= Database Operations =================
async def save_to_dynamodb(user_id, session_id, history, user_action=None):
    """Enhanced data storage with PII audit"""
    pii_audit = {
        "total_pii": 0,
        "details": {},
        "decisions": []
    }
    
    for msg in history:
        if msg.get("role") == "user" and "metadata" in msg:
            pii_audit["details"].update(msg["metadata"].get("removed_pii", {}))
            pii_audit["decisions"].append(msg["metadata"].get("user_choice"))
    
    pii_audit["total_pii"] = len(pii_audit["details"])
    
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "pii_audit": json.dumps(pii_audit),
        "user_action": user_action or "none",
        "metadata": {
            "sensitive_operations": len(pii_audit["decisions"]),
            "last_modified": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
        print("✅ Database record updated")
    except Exception as e:
        print(f"❌ Database save failed: {e}")
        raise

# ================= Core Chat Logic =================
async def privacy_aware_chatbot(user_id, session_id, user_input, chat_history):
    storage_history = convert_to_storage_format(chat_history)
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # PII Detection and Rewriting
    rewrite_result = await detect_and_rewrite_pii(user_input)
    
    if rewrite_result["revised"] != rewrite_result["original"]:
        privacy_manager.pending_rewrites[session_id] = {
            "original": rewrite_result["original"],
            "revised": rewrite_result["revised"],
            "removed_pii": rewrite_result["removed_pii"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Create warning message
        pii_list = "\n".join(
            [f"{k}: {', '.join(v)}" 
             for k, v in rewrite_result["removed_pii"].items() if v]
        )
        
        warning_msg = {
            "role": "system",
            "content": f"""⚠️ PII Detected - Suggested Revision:
{rewrite_result["revised"]}

Removed PII:
{pii_list}""",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        storage_history.append(warning_msg)
        await save_to_dynamodb(user_id, session_id, storage_history, "pending")
        return convert_to_gradio_format(storage_history), session_id
    
    # Normal processing if no PII detected
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    messages = [{"role": "system", "content": "You are a privacy-conscious assistant"}] + [
        {k:v for k,v in msg.items() if k in ["role", "content"]} 
        for msg in storage_history 
        if msg["role"] != "system"
    ]
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

async def handle_rewrite_choice(user_id, session_id, choice, chat_history):
    storage_history = convert_to_storage_format(chat_history)
    
    pending = privacy_manager.pending_rewrites.get(session_id)
    if not pending:
        return chat_history, session_id
    
    # Create user message with metadata
    user_message = {
        "role": "user",
        "content": pending["revised"] if choice == "accept" else pending["original"],
        "metadata": {
            "original_text": pending["original"],
            "user_choice": choice,
            "removed_pii": pending["removed_pii"]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Create confirmation message
    confirmation_msg = {
        "role": "system",
        "content": f"User chose to {choice} revision",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    storage_history.extend([user_message, confirmation_msg])
    await save_to_dynamodb(user_id, session_id, storage_history, choice)
    del privacy_manager.pending_rewrites[session_id]
    
    return convert_to_gradio_format(storage_history), session_id

# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Privacy-Conscious Chatbot")
    
    with gr.Row():
        user_id_input = gr.Textbox(label="User ID", placeholder="Enter unique identifier...")
        session_id = gr.State()
    
    chatbot = gr.Chatbot(
        label="Conversation History",
        height=500
    )
    
    msg = gr.Textbox(
        label="Your Message",
        placeholder="Type your message here...",
        lines=2
    )
    
    with gr.Row():
        submit_btn = gr.Button("Send", variant="primary")
        clear_btn = gr.Button("Clear Chat", variant="secondary")
    
    with gr.Row(visible=False) as rewrite_panel:
        with gr.Column():
            gr.Markdown("### PII Detected - Review Suggested Changes")
            with gr.Row():
                accept_btn = gr.Button("Accept Changes", variant="primary")
                reject_btn = gr.Button("Keep Original", variant="secondary")

    def toggle_rewrite_panel(history):
        try:
            if history and history[-1][1]:
                return gr.update(visible="Suggested Revision:" in history[-1][1])
            return gr.update(visible=False)
        except Exception:
            return gr.update(visible=False)
    
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])
    
    accept_btn.click(
        handle_rewrite_choice,
        [user_id_input, session_id, gr.State("accept"), chatbot],
        [chatbot, session_id]
    )
    
    reject_btn.click(
        handle_rewrite_choice,
        [user_id_input, session_id, gr.State("reject"), chatbot],
        [chatbot, session_id]
    )
    
    chatbot.change(
        toggle_rewrite_panel,
        [chatbot],
        [rewrite_panel]
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