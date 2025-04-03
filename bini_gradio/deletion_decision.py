import gradio as gr
import uuid
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ========== Storage ==========
archived_sessions = []
active_sessions = {}

# ========== Utils ==========
def convert_to_storage_format(gradio_history):
    """Convert Gradio format [(user, bot), ...] to internal format."""
    storage = []
    for msg in gradio_history:
        storage.append({"role": "user", "content": msg[0]})
        if msg[1]:
            storage.append({"role": "assistant", "content": msg[1]})
    return storage

def convert_to_gradio_format(storage_history):
    """Convert internal format to Gradio display format."""
    gradio_history = []
    for i in range(0, len(storage_history), 2):
        user_msg = storage_history[i]["content"]
        bot_msg = storage_history[i+1]["content"] if i+1 < len(storage_history) else None
        gradio_history.append((user_msg, bot_msg))
    return gradio_history

# ========== Chat Logic ==========
def process_message(msg, chat_history, session_id):
    """Send message to LLM and store history."""
    history = convert_to_storage_format(chat_history)
    messages = [{"role": "system", "content": "You are a helpful assistant."}] + history
    messages.append({"role": "user", "content": msg})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7
        )
        bot_reply = response.choices[0].message.content
    except Exception as e:
        bot_reply = f"Error: {e}"

    chat_history.append((msg, bot_reply))
    active_sessions[session_id] = convert_to_storage_format(chat_history)
    return chat_history, session_id

# ========== Deletion Logic ==========
def handle_decision(choice, session_id):
    history = active_sessions.get(session_id, [])
    chat_history = convert_to_gradio_format(history)

    if choice == "delete":
        active_sessions.pop(session_id, None)
        return [], str(uuid.uuid4()), gr.update(visible=False)
    elif choice == "archive":
        archived_sessions.append({
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "history": history
        })
        active_sessions.pop(session_id, None)
        return [], str(uuid.uuid4()), gr.update(visible=False)
    else:  # retain
        return chat_history, session_id, gr.update(visible=False)

def show_archived():
    if not archived_sessions:
        return "No archived sessions found."
    output = ""
    for item in archived_sessions:
        output += f"\nSession ID: {item['session_id']} ({item['timestamp']})\n"
        for msg in convert_to_gradio_format(item['history']):
            output += f"User: {msg[0]}\nAssistant: {msg[1]}\n"
        output += "\n"
    return output.strip()

# ========== Gradio Interface ==========
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Chatbot with Deletion Decision")

    with gr.Row():
        user_id = gr.Textbox(label="User ID", placeholder="e.g., user123", scale=3)
        archive_btn = gr.Button("Archived Sessions", scale=1)

    session_id = gr.State(str(uuid.uuid4()))
    chatbot = gr.Chatbot(label="Chat History")
    msg = gr.Textbox(placeholder="Type your message here...")

    with gr.Row():
        submit = gr.Button("Send", variant="primary")
        clear = gr.Button("Reset Chat", variant="secondary")

    with gr.Row(visible=False) as decision_panel:
        decision = gr.Radio(["retain", "delete", "archive"], label="What do you want to do with this chat?")
        confirm = gr.Button("Confirm Decision")

    archive_text = gr.Textbox(label="Archived Chats", lines=15, visible=False)

    # Event bindings
    submit.click(
        process_message,
        [msg, chatbot, session_id],
        [chatbot, session_id]
    ).then(lambda: "", None, [msg])

    clear.click(lambda: gr.update(visible=True), None, [decision_panel])

    confirm.click(
        handle_decision,
        [decision, session_id],
        [chatbot, session_id, decision_panel]
    )

    archive_btn.click(
        lambda: (show_archived(), gr.update(visible=True)),
        None,
        [archive_text]
    )

demo.launch(server_name="0.0.0.0", server_port=7860, share=True)