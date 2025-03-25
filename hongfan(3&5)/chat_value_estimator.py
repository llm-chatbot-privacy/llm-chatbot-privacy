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

# ================= Core Business Logic =================
class ValueAssessmentSystem:
    def __init__(self):
        self.alert_history = {}
    
    async def assess_value(self, text: str) -> dict:
        """Analyze commercial value of user input"""
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[{
                    "role": "system",
                    "content": """Analyze text for commercial value. Return JSON:
                    {
                        "value_level": "non-valuable/valuable/very-valuable",
                        "valuable_items": [],
                        "reason": "assessment rationale"
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
            print(f"Assessment failed: {str(e)}")
            return {"level": "non-valuable", "items": [], "reason": ""}

value_system = ValueAssessmentSystem()

# ================= Data Conversion =================
def convert_to_gradio_format(history: list) -> list:
    """Convert storage format to Gradio display format"""
    gradio_history = []
    for msg in history:
        if msg["role"] == "user":
            display = msg["content"]
            if "value_assessment" in msg:
                display += f"\n🔍Commercial Value: {msg['value_assessment']['level'].upper()}"
            gradio_history.append((display, None))
        elif msg["role"] == "system":
            gradio_history.append((None, msg["content"]))
        elif msg["role"] == "assistant":
            if gradio_history and gradio_history[-1][1] is None:
                gradio_history[-1] = (gradio_history[-1][0], msg["content"])
            else:
                gradio_history.append((None, msg["content"]))
    return gradio_history

def convert_to_storage_format(gradio_history: list) -> list:
    """Convert Gradio format to storage format"""
    storage = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            storage.append({
                "role": "user",
                "content": user_msg.split("\n🔍Commercial Value:")[0],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if bot_msg:
            storage.append({
                "role": "system" if "⚠️" in bot_msg else "assistant",
                "content": bot_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return storage

# ================= Chat Flow Control =================
async def process_message(user_id: str, session_id: str, user_input: str, chat_history: list) -> tuple:
    """Process message with commercial value detection"""
    # Input validation
    if not user_id.strip():
        raise gr.Error("User ID cannot be empty")
    
    # Initialize session ID
    session_id = session_id or str(uuid.uuid4())
    
    # Convert data format
    storage_history = convert_to_storage_format(chat_history)
    
    # Commercial value assessment
    assessment = await value_system.assess_value(user_input)
    
    # Build user message
    user_msg = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value_assessment": assessment
    }
    
    # Add alert message if valuable
    alert_msg = None
    if assessment["level"] != "non-valuable":
        alert_msg = {
            "role": "system",
            "content": f"⚠️ Commercial value detected [{assessment['level'].upper()}]: {', '.join(assessment['items'])}. "
                      f"Note: The information you provide might be used for commercial value extraction.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # Generate assistant response
    messages = [{"role": "system", "content": "You are a helpful assistant"}] + storage_history
    messages.append(user_msg)
    
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
    
    # Build final history
    final_history = storage_history.copy()
    final_history.append(user_msg)
    if alert_msg:
        final_history.append(alert_msg)
    final_history.append(assistant_msg)
    
    # Save to database
    await save_to_dynamodb(user_id, session_id, final_history)
    
    return convert_to_gradio_format(final_history), session_id

# ================= Database Module =================
async def save_to_dynamodb(user_id: str, session_id: str, history: list):
    """Save data to DynamoDB"""
    if not user_id or not session_id:
        raise ValueError("user_id and session_id cannot be empty")
    
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(history, ensure_ascii=False),
        "value_metadata": {
            "total_alerts": sum(1 for msg in history if "value_assessment" in msg),
            "last_alert": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
    except Exception as e:
        print(f"Database save failed: {str(e)}")
        raise

# ================= User Interface =================
def create_interface():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🔍 Commercial Value Aware Chatbot")
        
        # User identification
        with gr.Row():
            user_id_input = gr.Textbox(
                label="User ID",
                placeholder="Enter unique user identifier...",
                info="Required field",
                min_width=300
            )
            session_id = gr.State()
        
        # Chat interface
        chatbot = gr.Chatbot(
            label="Conversation History",
            bubble_full_width=False,
            height=500
        )
        
        # Input components
        msg = gr.Textbox(
            label="Input Message",
            placeholder="Type your message here...",
            lines=2,
            max_lines=5
        )
        
        # Submit button
        with gr.Row():
            gr.Column(scale=3)
            with gr.Column(scale=1):
                submit_btn = gr.Button("Send", variant="primary")

        # Event binding
        submit_btn.click(
            process_message,
            [user_id_input, session_id, msg, chatbot],
            [chatbot, session_id]
        ).then(lambda: "", None, [msg])
        
    return demo

# ================= Launch Application =================
if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )