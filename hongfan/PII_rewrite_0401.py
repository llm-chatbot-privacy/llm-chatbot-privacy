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
            gradio_history.append((msg["content"], None))
        elif msg["role"] == "assistant":
            if gradio_history and gradio_history[-1][1] is None:
                gradio_history[-1] = (gradio_history[-1][0], msg["content"])
            else:
                gradio_history.append((None, msg["content"]))
        elif msg["role"] == "system":
            # Special case for PII warnings and other system messages
            gradio_history.append((None, msg["content"]))
    return gradio_history

def convert_to_storage_format(gradio_history):
    """Convert Gradio format to storage format"""
    storage_history = []
    for user_msg, bot_msg in gradio_history:
        if user_msg:
            # Extract content without PII notifications if present
            clean_msg = user_msg.split("\n🔒")[0] if "\n🔒" in user_msg else user_msg
            storage_history.append({
                "role": "user",
                "content": clean_msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        if bot_msg:
            role = "system" if "⚠️" in bot_msg else "assistant"
            storage_history.append({
                "role": role,
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
    """Detect and rewrite PII using GPT-4 without using JSON response format"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-2024-08-06",  
            messages=[{
                "role": "system",
                "content": 
                    "You are a privacy protection assistant. Your task is to:\n"
                    "1. Analyze the user's message for any PII (Personally Identifiable Information) such as age, address, phone numbers, email addresses, ID numbers, race, gender, income, etc.\n"
                    "2. If you find PII, generate a revised version of the text with the PII removed or anonymized while preserving the user's intended meaning.\n"
                    "3. Output your analysis in the exact format shown below:\n\n"
                    "---PII_ANALYSIS_START---\n"
                    "ORIGINAL_TEXT: [paste the original text here]\n"
                    "REVISED_TEXT: [paste your revised version here]\n"
                    "DETECTED_PII:\n"
                    "- Type: [type of PII], Content: [the specific content]\n"
                    "- Type: [type of PII], Content: [the specific content]\n"
                    "(list all detected PII items)\n"
                    "---PII_ANALYSIS_END---\n\n"
                    "If no PII is detected, respond with:\n"
                    "---PII_ANALYSIS_START---\n"
                    "ORIGINAL_TEXT: [paste the original text here]\n"
                    "REVISED_TEXT: [paste the original text here]\n"
                    "DETECTED_PII: None\n"
                    "---PII_ANALYSIS_END---\n\n"
                    "Some concrete privacy or sensitive information category examples for your reference:\n"
                    "Personal Information Disclosure: “My name is Sarah, and I live in San Francisco. My birthday is May 3rd.”\n"
                    "Sensitive Topic Exploration: “I've been feeling anxious lately and having trouble sleeping. What should I do?”\n"
                    "Ethical Question: “I saw my coworker stealing small items from the office. Should I report it?”\n"
                    "Family/Social Information: “Here is a text exchange I had with my partner last week. Am I in the wrong?”\n"
                    "Medical Data: “I have diabetes and take insulin regularly. Are there foods I should avoid?”\n"
                    "Professional Information: “I'm frustrated at work. My manager at XYZ Corp doesn't appreciate my efforts.”\n"
                    "Future Plans: “I'm thinking about taking a long vacation next month. What's a good place to travel?”\n"
                    "Financial Information: “I earn about $75,000 a year, and my credit score is around 680. Can I afford a new car?”\n"
                    "Location Information: “I often visit the Starbucks on Main Street after work around 6 PM.”\n"
                    "Political Ideology: “I voted for [candidate or party], but lately I’m reconsidering because of recent policies.”"
            }, {
                "role": "user",
                "content": text
            }],
            temperature=0.2
        )
        
        analysis_text = response.choices[0].message.content
        
        # Extract the sections from the formatted response
        if "---PII_ANALYSIS_START---" in analysis_text and "---PII_ANALYSIS_END---" in analysis_text:
            analysis_content = analysis_text.split("---PII_ANALYSIS_START---")[1].split("---PII_ANALYSIS_END---")[0].strip()
            
            # Parse the sections
            sections = analysis_content.split("\n")
            original_text = sections[0].replace("ORIGINAL_TEXT: ", "").strip() if "ORIGINAL_TEXT: " in sections[0] else text
            revised_text = sections[1].replace("REVISED_TEXT: ", "").strip() if "REVISED_TEXT: " in sections[1] else text
            
            # Parse detected PII items
            removed_pii = {}
            if "DETECTED_PII: None" not in analysis_content:
                pii_section_start = next((i for i, line in enumerate(sections) if "DETECTED_PII:" in line), -1)
                if pii_section_start >= 0:
                    for i in range(pii_section_start + 1, len(sections)):
                        if sections[i].strip().startswith("-"):
                            parts = sections[i].strip("- ").split(", Content: ")
                            if len(parts) == 2:
                                pii_type = parts[0].replace("Type: ", "").strip()
                                pii_content = parts[1].strip()
                                if pii_type not in removed_pii:
                                    removed_pii[pii_type] = []
                                removed_pii[pii_type].append(pii_content)
            
            return {
                "original": original_text,
                "revised": revised_text,
                "removed_pii": removed_pii
            }
        else:
            # Fallback if parsing fails
            print("Parsing failed, using original text")
            return {"original": text, "revised": text, "removed_pii": {}}
            
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
            pii_info = msg["metadata"].get("removed_pii", {})
            pii_audit["details"].update(pii_info)
            pii_audit["decisions"].append(msg["metadata"].get("user_choice"))
            pii_audit["total_pii"] += sum(len(items) for items in pii_info.values())
    
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
    
    # Check if PII was detected and text was modified
    if rewrite_result["revised"] != rewrite_result["original"]:
        # Store the pending rewrite
        privacy_manager.pending_rewrites[session_id] = {
            "original": rewrite_result["original"],
            "revised": rewrite_result["revised"],
            "removed_pii": rewrite_result["removed_pii"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Format removed PII for display
        pii_list = "\n".join(
            [f"- {k}: {', '.join(v)}" 
             for k, v in rewrite_result["removed_pii"].items() if v]
        )
        
        # Create confirmation request message
        warning_msg = {
            "role": "system",
            "content": f"""⚠️ **PII Detected** - We suggest this revised version:

"{rewrite_result["revised"]}"

**Removed PII information:**
{pii_list}

Please choose to Accept or Keep Original using the buttons below.""",
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
    
    # Prepare conversation for API
    messages = [{"role": "system", "content": "You are a privacy-conscious assistant"}] + [
        {k:v for k,v in msg.items() if k in ["role", "content"]} 
        for msg in storage_history 
        if msg["role"] != "system"
    ]
    messages.append({"role": "user", "content": user_input})
    
    # Get response from LLM
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
    if not session_id or session_id not in privacy_manager.pending_rewrites:
        return chat_history, session_id
    
    pending = privacy_manager.pending_rewrites[session_id]
    storage_history = convert_to_storage_format(chat_history)
    
    # Filter out the warning message that asks for confirmation
    storage_history = [msg for msg in storage_history if not 
                      (msg["role"] == "system" and "PII Detected" in msg.get("content", ""))]
    
    # Determine which message text to use based on user choice
    user_content = pending["revised"] if choice == "accept" else pending["original"]
    
    # Create user message with metadata
    user_message = {
        "role": "user",
        "content": user_content,
        "metadata": {
            "original_text": pending["original"],
            "user_choice": choice,
            "removed_pii": pending["removed_pii"]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Add user choice notification for display
    choice_notification = f"\n🔒 {'Using revised message without PII.' if choice == 'accept' else 'Using original message with PII.'}"
    user_message_with_notification = {
        "role": "user",
        "content": user_content + choice_notification,
        "metadata": {
            "original_text": pending["original"],
            "user_choice": choice,
            "removed_pii": pending["removed_pii"]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Replace the storage history with the updated message that includes the choice notification
    storage_history.append(user_message_with_notification)
    
    # Now get the actual response from the LLM - but use the clean message without notification
    messages = [{"role": "system", "content": "You are a privacy-conscious assistant"}] + [
        {"role": msg["role"], "content": msg["content"].split("\n🔒")[0] if msg["role"] == "user" and "\n🔒" in msg["content"] else msg["content"]} 
        for msg in storage_history 
        if msg["role"] != "system" or "PII Detected" not in msg.get("content", "")
    ]
    
    # Get response from LLM
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
    
    storage_history.append(assistant_msg)
    
    # Save everything to the database - but use the clean user message for storage
    db_storage_history = [msg for msg in storage_history]
    for i, msg in enumerate(db_storage_history):
        if msg["role"] == "user" and "\n🔒" in msg.get("content", ""):
            # Replace with clean version for database storage
            db_storage_history[i] = user_message
    
    await save_to_dynamodb(user_id, session_id, db_storage_history, choice)
    
    # Clean up the pending rewrite
    del privacy_manager.pending_rewrites[session_id]
    
    return convert_to_gradio_format(storage_history), session_id
# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Privacy-Conscious Chatbot that rewrite your message with privacy / sensitive info.")
    
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
    
    with gr.Row(visible=False) as rewrite_panel:
        with gr.Column():
            gr.Markdown("### PII Detected - Please Review")
            with gr.Row():
                accept_btn = gr.Button("Accept Revised Version", variant="primary")
                reject_btn = gr.Button("Keep Original", variant="secondary")

    # Function to check if we need to show the rewrite panel
    def toggle_rewrite_panel(chat_history):
        # Check if the last message is a PII warning
        if chat_history and len(chat_history) > 0:
            last_msg = chat_history[-1]
            if last_msg[1] and "⚠️ **PII Detected**" in last_msg[1]:
                return gr.update(visible=True)
        return gr.update(visible=False)
    
    # Function to prevent new messages while waiting for user to choose
    def check_input_allowed(chat_history):
        if chat_history and len(chat_history) > 0:
            last_msg = chat_history[-1]
            if last_msg[1] and "⚠️ **PII Detected**" in last_msg[1]:
                return gr.update(interactive=False, placeholder="Please accept or reject PII changes first...")
        return gr.update(interactive=True, placeholder="Type your message here...")
    
    # Register event handlers
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id, msg, chatbot],
        [chatbot, session_id]
    ).then(
        lambda: "", 
        None, 
        [msg]
    ).then(
        toggle_rewrite_panel,
        [chatbot],
        [rewrite_panel]
    ).then(
        check_input_allowed,
        [chatbot],
        [msg]
    )
    
    accept_btn.click(
        handle_rewrite_choice,
        [user_id_input, session_id, gr.State("accept"), chatbot],
        [chatbot, session_id]
    ).then(
        toggle_rewrite_panel,
        [chatbot],
        [rewrite_panel]
    ).then(
        check_input_allowed,
        [chatbot],
        [msg]
    )
    
    reject_btn.click(
        handle_rewrite_choice,
        [user_id_input, session_id, gr.State("reject"), chatbot],
        [chatbot, session_id]
    ).then(
        toggle_rewrite_panel,
        [chatbot],
        [rewrite_panel]
    ).then(
        check_input_allowed,
        [chatbot],
        [msg]
    )
    
    # Clear chat button
    # clear_btn.click(
    #     lambda: ([], str(uuid.uuid4())),
    #     outputs=[chatbot, session_id]
    # ).then(
    #     lambda: gr.update(visible=False),
    #     None,
    #     [rewrite_panel]
    # ).then(
    #     lambda: gr.update(interactive=True, placeholder="Type your message here..."),
    #     None,
    #     [msg]
    # )
    
    # Update UI when chat history changes
    chatbot.change(
        toggle_rewrite_panel,
        [chatbot],
        [rewrite_panel]
    ).then(
        check_input_allowed,
        [chatbot],
        [msg]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True
    )