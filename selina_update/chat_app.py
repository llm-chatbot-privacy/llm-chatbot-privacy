import boto3
import json
import asyncio
from datetime import datetime
import uuid
import gradio as gr
from components.ChatInput import chat_input_section
from components.ChatMessage import render_messages
from components.ChatSidebar import chat_sidebar
from components.ApiKeyModal import api_key_section
from components.DataHandlingModal import data_handling_selector
from components.PrincipleSelector import principle_selector
from components.state import (
    messages, add_message, set_mode,
    data_handling_mode, transmission_principle,
    set_principle, default_policy, set_default_policy
)
from services.openai_service import get_api_key, chat_with_gpt4
AWS_REGION = "us-east-2"
session = boto3.Session(region_name=AWS_REGION)
dynamodb = session.resource("dynamodb")
table = dynamodb.Table("chat_history")

async def save_to_dynamodb(user_id, session_id, chat_history, policy):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history, ensure_ascii=False),
        "policy": json.dumps(policy),
    }
    print("✅ Saving to DynamoDB:", data)
    await asyncio.to_thread(table.put_item, Item=data)

session_id = ""
user_id_state = ""
data_handling_mode_state = "private"  # NEW

def update_info(selected_mode):
    global data_handling_mode_state
    data_handling_mode_state = selected_mode
    desc = {
        "private": "🔒 Your conversation will not be stored. Perfect for sensitive discussions.",
        "sharing": "🌐 Your data may be shared with third parties. Be mindful of privacy."
    }
    return desc.get(selected_mode, "")

def update_principle_desc(selected):
    descs = {
        "Neutral Informant": "The assistant presents only neutral facts, avoiding opinions or suggestions.",
        "User Advocate": "The assistant acts in your best interest, suggesting helpful actions.",
        "Expert Advisor": "The assistant behaves like a qualified expert, but results may vary."
    }
    set_principle(selected)
    return descs.get(selected, "")

def store_policy(uses, recipients):
    set_default_policy({
        "uses": uses,
        "recipients": recipients
    })
    return "✅ Default policy saved!"

def set_user_id(uid):
    global user_id_state
    user_id_state = uid
    return "✅ User ID set to: **{}**".format(uid)

def start_chat(mode):
    set_mode(mode)
    messages.clear()

    mode_map = {
        "private": "🔒 Your conversation will not be stored. Perfect for sensitive discussions.",
        "sharing": "🌐 Your data may be shared with third parties. Be mindful of privacy."
    }
    add_message(mode_map.get(mode, ""), "system")

    principle_msg = {
        "Neutral Informant": "Assistant will stay factual and avoid making recommendations.",
        "User Advocate": " Assistant will try to recommend actions in your best interest.",
        "Expert Advisor": " Assistant behaves like an expert but may not be perfect."
    }
    add_message(principle_msg.get(transmission_principle, ""), "system")

    if not get_api_key():
        add_message("Please set your OpenAI API key by clicking the settings button above.", "assistant")
    else:
        add_message("Hello! I'm your privacy-focused AI assistant. How can I help you today?", "assistant")

    return render_messages()

async def handle_input(user_msg):
    global session_id
    if not session_id:
        session_id = "session_" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + str(uuid.uuid4())[:8]

    print("\n📥 handle_input triggered")
    print("🧾 Mode:", data_handling_mode_state)
    print("👤 User ID:", user_id_state)
    print("💬 Messages:", messages)

    add_message(user_msg, "user", default_policy.copy())
    reply = chat_with_gpt4(user_msg, data_handling_mode_state, transmission_principle)
    add_message(reply, "assistant", default_policy.copy())

    if data_handling_mode_state != "private" and user_id_state:
        await save_to_dynamodb(
            user_id=user_id_state,
            session_id=session_id,
            chat_history=[msg.copy() for msg in messages],
            policy=default_policy
        )

    return render_messages()

with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column(scale=1, min_width=200):
            chat_sidebar()

        with gr.Column(scale=4):
            gr.Markdown("## 🛡️ Chat Interface")

            chat_display = gr.Textbox(label="Chat", lines=20, interactive=False)
            user_input, send_btn = chat_input_section()
            data_radio, start_btn, info_box = data_handling_selector()
            principle_radio, principle_desc = principle_selector()
            principle_confirm = gr.Button("Confirm Advisory Role")
            key_input, key_btn, key_status = api_key_section()
            user_id_input = gr.Textbox(label="User ID", placeholder="Enter your user ID", value="test_user")
            user_id_confirm = gr.Button("Set User ID")
            user_id_status = gr.Markdown()

            send_btn.click(fn=handle_input, inputs=user_input, outputs=chat_display)
            data_radio.change(fn=update_info, inputs=data_radio, outputs=info_box)
            principle_radio.change(update_principle_desc, inputs=principle_radio, outputs=principle_desc)
            principle_confirm.click(
                fn=lambda val: f"✅ Advisory role set to: **{val}**",
                inputs=principle_radio,
                outputs=principle_desc)
            start_btn.click(start_chat, inputs=data_radio, outputs=chat_display)
            key_btn.click(fn=lambda k: "✅ Key set" if k else "❌ No key", inputs=key_input, outputs=key_status)
            user_id_confirm.click(fn=set_user_id, inputs=user_id_input, outputs=user_id_status)

if __name__ == "__main__":
    demo.launch()