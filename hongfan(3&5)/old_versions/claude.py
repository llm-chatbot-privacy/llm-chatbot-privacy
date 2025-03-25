import gradio as gr
import boto3
import uuid
import json
import openai
from datetime import datetime
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
AWS_REGION = os.getenv("AWS_REGION")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Connect to AWS DynamoDB
session = boto3.Session(region_name=AWS_REGION)
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# Initialize OpenAI Client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Function to classify sensitivity using LLM
async def classify_sensitivity(chat_history):
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Classify each message as Green (No risk), Yellow (Low), Orange (Medium), or Red (High). Respond in JSON format."},
                {"role": "user", "content": json.dumps(chat_history)}
            ],
            temperature=0.3,
        )

        # Ensure response is JSON
        classified_messages = json.loads(response.choices[0].message.content)

        # Validate the structure of classified_messages
        if not isinstance(classified_messages, list):
            raise ValueError("Invalid response format from LLM classification API")

        return classified_messages

    except Exception as e:
        print(f"Error classifying messages: {e}")
        # If classification fails, assign all as "unknown"
        return [{"content": msg["content"], "sensitivity": "unknown"} for msg in chat_history]


# Function to save chat history to DynamoDB
async def save_to_dynamodb(user_id, session_id, chat_history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    await asyncio.to_thread(table.put_item, Item=data)

# Function to retrieve chat history from DynamoDB
async def get_chat_history(user_id, session_id=None):
    if not session_id:
        # If no session_id provided, return list of all sessions for this user
        response = await asyncio.to_thread(
            table.query,
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
        )
        sessions = {}
        if 'Items' in response:
            for item in response['Items']:
                sessions[item['session_id']] = item['timestamp']
        return sessions
    
    # If session_id provided, return that specific session
    response = await asyncio.to_thread(
        table.get_item, 
        Key={"user_id": user_id, "session_id": session_id}
    )
    if "Item" in response:
        return json.loads(response["Item"]["history"]), session_id
    return [], session_id

# Function to filter messages based on sensitivity
def filter_messages_by_sensitivity(chat_history, level):
    levels = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    filtered_history = []
    
    for msg in chat_history:
        # Ensure the sensitivity key exists and is properly formatted
        if "sensitivity" in msg and msg["sensitivity"].lower() in levels:
            if levels[msg["sensitivity"].lower()] < levels[level.lower()]:
                filtered_history.append(msg)
        else:
            # Default to keeping messages with unknown sensitivity
            filtered_history.append(msg)
            
    return filtered_history

# Function to delete selected messages
async def delete_selected_messages(user_id, session_id, messages_to_delete):
    chat_history, _ = await get_chat_history(user_id, session_id)
    
    # Create a set of message contents for easier comparison
    contents_to_delete = {json.dumps(msg) for msg in messages_to_delete}
    
    # Keep messages not in the delete set
    updated_history = [msg for msg in chat_history 
                      if json.dumps(msg) not in contents_to_delete]
    
    await save_to_dynamodb(user_id, session_id, updated_history)
    return updated_history

# Function to generate LLM response and classify messages
async def chatbot(user_id, session_id, user_message, chat_history):
    if not user_id:
        return chat_history, "", session_id
        
    if not session_id:
        session_id = str(uuid.uuid4())
    if chat_history is None:
        chat_history = []

    messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
    for msg in chat_history:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Get AI-generated response
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.7,
    )
    llm_response_text = response.choices[0].message.content

    # Update chat history
    new_user_msg = {"role": "user", "content": user_message}
    new_assistant_msg = {"role": "assistant", "content": llm_response_text}
    
    chat_history.append(new_user_msg)
    chat_history.append(new_assistant_msg)

    # Classify messages for sensitivity
    try:
        sensitivity_results = await classify_sensitivity(chat_history)
        for i, msg in enumerate(chat_history):
            if i < len(sensitivity_results):
                msg["sensitivity"] = sensitivity_results[i]["sensitivity"].lower()
            else:
                msg["sensitivity"] = "green"  # Default if classification fails
    except Exception as e:
        print(f"Error classifying messages: {e}")
        # If classification fails, set default sensitivity
        for msg in chat_history:
            if "sensitivity" not in msg:
                msg["sensitivity"] = "green"

    # Save updated history
    await save_to_dynamodb(user_id, session_id, chat_history)

    return chat_history, user_id, session_id

# Gradio UI Setup
with gr.Blocks() as demo:
    gr.Markdown("# OpenAI LLM Chatbot with Private History Highlighter")

    user_id_input = gr.Textbox(label="Enter Your User ID")
    session_id = gr.State("")
    chatbot_ui = gr.Chatbot(type="messages", label="Chatbot")
    user_input = gr.Textbox(label="Your Message")
    submit_button = gr.Button("Send")
    session_dropdown = gr.Dropdown(label="Select a Session", choices=[])
    scan_button = gr.Button("Scan for Sensitive Content")
    delete_dropdown = gr.Dropdown(label="Delete messages rated", 
                               choices=["Orange & Red", "Red Only", "Manual Review"])
    review_area = gr.CheckboxGroup(label="Manually delete flagged messages")

    # Load chat history
    async def load_chat_history(user_id, session_id):
        if not session_id:
            return [], session_id
        
        history, session_id = await get_chat_history(user_id, session_id)
        return history, session_id

    session_dropdown.change(load_chat_history, [user_id_input, session_dropdown], [chatbot_ui, session_id])

    # Create a new session
    def create_new_session(user_id):
        return str(uuid.uuid4()), []

    new_session_button = gr.Button("New Chat Session")
    new_session_button.click(create_new_session, [user_id_input], [session_id, chatbot_ui])

    # Load user's chat sessions
    async def load_sessions(user_id):
        if not user_id:
            return []
            
        sessions_dict = await get_chat_history(user_id)
        # Sort sessions by timestamp (newest first)
        sorted_sessions = sorted(sessions_dict.items(), 
                                key=lambda x: x[1], 
                                reverse=True)
        return [session_id for session_id, _ in sorted_sessions]

    user_id_input.change(load_sessions, [user_id_input], [session_dropdown])

    # Bind chatbot function
    submit_button.click(chatbot, 
                      [user_id_input, session_id, user_input, chatbot_ui], 
                      [chatbot_ui, user_id_input, session_id])
    
    # Clear input after sending
    submit_button.click(lambda: "", inputs=[], outputs=[user_input])

    # Scan chat history for sensitive content
    async def scan_chat_history(user_id, session_id):
        if not user_id or not session_id:
            return chatbot_ui
            
        chat_history, _ = await get_chat_history(user_id, session_id)
        if not chat_history:
            return []
            
        try:
            sensitivity_results = await classify_sensitivity(chat_history)
            for i, msg in enumerate(chat_history):
                if i < len(sensitivity_results):
                    msg["sensitivity"] = sensitivity_results[i]["sensitivity"].lower()
                else:
                    msg["sensitivity"] = "green"
        except Exception as e:
            print(f"Error during sensitivity scan: {e}")
            # Set default sensitivity if scan fails
            for msg in chat_history:
                msg["sensitivity"] = "green"
                
        await save_to_dynamodb(user_id, session_id, chat_history)
        return chat_history

    scan_button.click(scan_chat_history, [user_id_input, session_id], [chatbot_ui])

    # Delete messages by sensitivity
    async def delete_messages(user_id, session_id, level_option):
        if not user_id or not session_id or not level_option:
            return chatbot_ui
            
        chat_history, _ = await get_chat_history(user_id, session_id)
        
        # Map dropdown options to actual sensitivity levels
        level_map = {
            "Red Only": "red",
            "Orange & Red": "orange",
            "Manual Review": None  # Special case
        }
        
        level = level_map.get(level_option)
        
        if level:
            # Automatic deletion based on level
            updated_history = filter_messages_by_sensitivity(chat_history, level)
            await save_to_dynamodb(user_id, session_id, updated_history)
            return updated_history
        else:
            # Manual review case - populate review area
            flagged_messages = [msg for msg in chat_history 
                              if "sensitivity" in msg and 
                                 msg["sensitivity"].lower() in ["orange", "red"]]
            
            message_texts = [f"{msg['role']}: {msg['content']} ({msg['sensitivity']})" 
                           for msg in flagged_messages]
            
            # Update review area with flagged messages
            return chat_history, message_texts

    # Bind to dropdown change
    delete_button = gr.Button("Apply Filtering")
    delete_button.click(delete_messages, 
                      [user_id_input, session_id, delete_dropdown], 
                      [chatbot_ui, review_area])

    # Manual deletion of selected messages
    async def delete_selected(user_id, session_id, selected_messages):
        if not user_id or not session_id or not selected_messages:
            return chatbot_ui
            
        chat_history, _ = await get_chat_history(user_id, session_id)
        
        # Parse selection back to messages
        to_delete = []
        for selection in selected_messages:
            parts = selection.split(": ", 1)
            if len(parts) == 2:
                role = parts[0]
                # Extract content (remove sensitivity info at the end)
                content = parts[1].rsplit(" (", 1)[0]
                
                # Find and mark messages to delete
                for msg in chat_history:
                    if msg["role"] == role and msg["content"] == content:
                        to_delete.append(msg)
        
        # Delete messages
        updated_history = [msg for msg in chat_history if msg not in to_delete]
        await save_to_dynamodb(user_id, session_id, updated_history)
        return updated_history

    apply_delete_button = gr.Button("Delete Selected Messages")
    apply_delete_button.click(delete_selected, 
                            [user_id_input, session_id, review_area], 
                            [chatbot_ui])

    # Clear chat history
    clear_button = gr.Button("Clear Chat")
    clear_button.click(lambda: ([], ""), inputs=[], outputs=[chatbot_ui, session_id])

# Launch Gradio App
demo.launch(share=True)