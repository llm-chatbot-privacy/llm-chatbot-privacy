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

# ================= Helpers =================
def convert_to_gradio_format(history):
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

# ================= Core Chat Logic =================
async def blank_chatbot(user_id, session_id, user_input, chat_history):
    session_id = session_id or str(uuid.uuid4())
    storage_history = convert_to_storage_format(chat_history)

    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    messages = [{"role": "system", "content": "You are a helpful assistant"}] + storage_history + [user_message]

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
    await asyncio.to_thread(table.put_item, Item={
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(storage_history, ensure_ascii=False)
    })

    return convert_to_gradio_format(storage_history), session_id

# ================= Sensitivity Analysis Logic =================
async def analyze_history_for_sensitivity(user_id):
    # Scan all sessions for this user
    response = await asyncio.to_thread(table.scan)
    sessions = [item for item in response["Items"] if item["user_id"] == user_id]
    analyzed = []
    for session in sessions:
        try:
            history = json.loads(session["history"])
            session_id = session["session_id"]
            for msg in history:
                if msg["role"] == "user":
                    detection = await detect_sensitive_info(msg["content"])
                    color = "green" if detection["level"] == "non-sensitive" else (
                        "yellow" if detection["level"] == "sensitive" else (
                            "orange" if detection["level"] == "very-sensitive" else "red"))
                    analyzed.append({
                        "session_id": session_id,
                        "content": msg["content"],
                        "level": detection["level"],
                        "reason": detection["reason"],
                        "color": color
                    })
        except Exception as e:
            print("Error analyzing session:", e)
    return analyzed

async def detect_sensitive_info(text):
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo-1106",
            messages=[{
                "role": "system",
                "content": """Analyze text for sensitive information, return JSON:
                {
                    \"sensitivity_level\": \"non-sensitive/sensitive/very-sensitive\",
                    \"flagged_items\": [\"...\"],
                    \"reason\": \"...\"
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
            "level": result.get("sensitivity_level", "non-sensitive"),
            "items": result.get("flagged_items", []),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print("Detection failed:", e)
        return {"level": "non-sensitive", "items": [], "reason": ""}

# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Chatbot with Deletion Decision")

    with gr.Row():
        user_id_input = gr.Textbox(label="User ID", placeholder="Enter user ID")
        session_id = gr.State()
        view_history_btn = gr.Button("📂 History Highlighter", size="sm")

    chatbot = gr.Chatbot(label="Chat", height=500)
    msg = gr.Textbox(label="Message", placeholder="Type here")
    submit_btn = gr.Button("Send")

    submit_btn.click(
        blank_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])

    history_display = gr.Dataframe(
        headers=["Session ID", "Message", "Sensitivity", "Reason"],
        interactive=False,
        visible=False
    )

    async def show_history(user_id):
        data = await analyze_history_for_sensitivity(user_id)
        rows = [[d["session_id"], d["content"], d["level"], d["reason"]] for d in data]
        return gr.update(visible=True, value=rows)

    view_history_btn.click(
        show_history,
        [user_id_input],
        [history_display]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
