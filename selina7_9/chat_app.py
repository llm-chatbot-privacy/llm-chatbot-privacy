
import gradio as gr
from components.ChatInput import chat_input_section
from components.ChatMessage import render_messages
from components.ChatSidebar import chat_sidebar
from components.ApiKeyModal import api_key_section
from components.DataHandlingModal import data_handling_selector
from components.PrincipleSelector import principle_selector
from components.PolicySpecifier import policy_specifier
from components.state import (
    messages, add_message, set_mode,
    data_handling_mode, transmission_principle,
    set_principle, default_policy, set_default_policy
)
from services.openai_service import get_api_key, chat_with_gpt4

def start_chat(mode):
    set_mode(mode)
    messages.clear()

    mode_map = {
        "private": "🔒 Your conversation will not be stored. Perfect for sensitive discussions.",
        "personalized": "🧠 Your data will be stored for personalization but not used for training.",
        "sharing": "🌐 Your data may be shared with third parties. Be mindful of privacy."
    }
    add_message(mode_map.get(mode, ""), "system")

    if not get_api_key():
        add_message("Please set your OpenAI API key by clicking the settings button above.", "assistant")
    else:
        add_message("Hello! I'm your privacy-focused AI assistant. How can I help you today?", "assistant")

    return render_messages()

def handle_input(user_msg):
    add_message(user_msg, "user", default_policy.copy())
    reply = chat_with_gpt4(user_msg, data_handling_mode, transmission_principle)
    add_message(reply, "assistant", default_policy.copy())
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
            uses_check, recipients_drop, save_policy_btn, confirm_msg = policy_specifier()
            key_input, key_btn, key_status = api_key_section()

            def update_info(selected_mode):
                desc = {
                    "private": "🔒 Your conversation will not be stored. Perfect for sensitive discussions.",
                    "personalized": "🧠 Your data will be stored for personalization but not used for training.",
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

            data_radio.change(update_info, inputs=data_radio, outputs=info_box)
            principle_radio.change(update_principle_desc, inputs=principle_radio, outputs=principle_desc)
            start_btn.click(start_chat, inputs=data_radio, outputs=chat_display)
            send_btn.click(handle_input, inputs=user_input, outputs=chat_display)
            save_policy_btn.click(store_policy, inputs=[uses_check, recipients_drop], outputs=confirm_msg)
            key_btn.click(fn=lambda k: "✅ Key set" if k else "❌ No key", inputs=key_input, outputs=key_status)

demo.launch()
