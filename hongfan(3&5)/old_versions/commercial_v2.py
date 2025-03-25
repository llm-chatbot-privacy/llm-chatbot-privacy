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

# ================= Fixed Data Conversion =================
def convert_to_gradio_format(history):
    """Convert storage format to Gradio-compatible format"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            gradio_history.append((msg["content"], None))
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
                "content": user_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if bot_msg:
            storage_history.append({
                "role": "assistant",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage_history

# ================= Fixed Value Assessment =================
async def assess_business_value(text: str) -> dict:
    """Analyze text for commercial value (with error handling)"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo-1106",  # Use JSON-compatible model
            messages=[{
                "role": "system",
                "content": """Analyze text for commercial value. Respond in valid JSON:
                {
                    "value_level": "non-valuable/valuable/very-valuable",
                    "valuable_items": [],
                    "reason": "explanation"
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
            "level": result.get("value_level", "non-valuable"),
            "items": result.get("valuable_items", []),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"Value assessment error: {str(e)}")
        return {"level": "non-valuable", "items": [], "reason": ""}

# ================= Fixed Database Handling =================
async def save_to_dynamodb(user_id: str, session_id: str, history: list):
    """Save conversation with validation"""
    if not user_id or not session_id:
        raise ValueError("user_id and session_id cannot be empty")
    
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
        print("Database updated successfully")
    except Exception as e:
        print(f"Database error: {str(e)}")
        raise

# ================= Fixed Chat Logic =================
async def value_aware_chatbot(user_id: str, session_id: str, user_input: str, chat_history: list):
    # Validate user_id
    if not user_id.strip():
        raise gr.Error("User ID cannot be empty")
    
    # Initialize session
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Convert Gradio format to storage format
    storage_history = convert_to_storage_format(chat_history)
    
    # Perform value assessment
    assessment = await assess_business_value(user_input)
    
    # Create user message with metadata
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value_assessment": assessment
    }
    
    # Handle valuable content
    if assessment["level"] != "non-valuable":
        alert_msg = {
            "role": "system",
            "content": f"⚠️ Commercial value detected [{assessment['level'].upper()}]: {', '.join(assessment['items'])}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        storage_history.extend([user_message, alert_msg])
    else:
        # Normal processing
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
        storage_history.extend([user_message, assistant_msg])
    
    # Save to database
    await save_to_dynamodb(user_id, session_id, storage_history)
    
    # Convert back to Gradio format
    return convert_to_gradio_format(storage_history), session_id

# ================= Fixed Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔍 Business Value Aware Chatbot")
    
    with gr.Row():
        user_id_input = gr.Textbox(
            label="User ID",
            placeholder="Enter unique user ID...",
            info="Required field for session tracking"
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
    
    submit_btn.click(
        value_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )