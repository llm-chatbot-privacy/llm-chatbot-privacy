import gradio as gr
import boto3
import uuid
import json
import os
import asyncio
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI

# Load environment variables
load_dotenv()

# Initialize AWS DynamoDB
session = boto3.Session(region_name=os.getenv("AWS_REGION"))
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")

# Initialize OpenAI client (v1.0.0+)
OpenAI.api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
async_openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= Enhanced Data Structures =================
CATEGORY_MAPPING = {
    "Financial/Income/Tax": "financial",
    "Personal Identity": "identity",
    "Personal History": "history",
    "Family Information": "family",
    "Location/Address": "location",
    "Social Relationships": "social",
    "Personal Preferences": "preferences",
    "Health Information": "health",
    "Other": "other"
}

# Pattern-based sensitive info detection
SENSITIVE_PATTERNS = {
    "ssn": (r"\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b", "Personal Identity", 10),
    "credit_card": (r"\b(?:\d{4}[- ]?){3}\d{4}\b", "Financial/Income/Tax", 9),
    "phone": (r"\b(?:\+\d{1,2}\s?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b", "Personal Identity", 7),
    "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Personal Identity", 6),
    "address": (r"\b\d+\s+[A-Za-z0-9\s,.]+(?:Avenue|Ave|Street|St|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl|Terrace|Ter)[,.]?\s+(?:[A-Za-z]+[,.]?\s+)?(?:[A-Za-z]{2}[,.]?\s+)?(?:\d{5}(?:-\d{4})?)?", "Location/Address", 8),
    "dob": (r"\b(?:0[1-9]|1[0-2])[/.-](?:0[1-9]|[12][0-9]|3[01])[/.-](?:19|20)\d{2}\b", "Personal Identity", 8),
    "passport": (r"\b[A-Z]{1,2}[0-9]{6,9}\b", "Personal Identity", 9),
    "bank_account": (r"\b\d{10,12}\b", "Financial/Income/Tax", 8),
    "routing_number": (r"\b\d{9}\b", "Financial/Income/Tax", 8)
}

def convert_to_gradio_format(internal_history):
    """
    Convert internal storage format (list of dicts) to Gradio display format (list of tuples)
    
    Args:
        internal_history (list): List of message dictionaries
        
    Returns:
        list: List of tuples formatted for Gradio chatbot
    """
    gradio_history = []
    for msg in internal_history:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            display_content = msg.get("content", "")
            if "privacy_check" in msg and msg["privacy_check"].get("detected_items"):
                # Add privacy alert for each detected sensitive item
                detected = msg["privacy_check"]["detected_items"]
                categories = list(set(item["category"] for item in detected))
                highest_score = max(item["score"] for item in detected)
                
                alert_info = (
                    f"\n🔒 Detected {len(detected)} sensitive items in categories: {', '.join(categories)} "
                    f"(Highest sensitivity: {highest_score}/10)"
                )
                display_content += alert_info
            gradio_history.append((display_content, None))
        elif msg.get("role") in ["assistant", "system"]:
            # For system messages, attach them to the previous user message if exists.
            if msg.get("role") == "system":
                if gradio_history:
                    last_user = gradio_history[-1][0]
                    gradio_history[-1] = (last_user, msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
            else:
                if gradio_history and gradio_history[-1][1] is None:
                    gradio_history[-1] = (gradio_history[-1][0], msg.get("content", ""))
                else:
                    gradio_history.append((None, msg.get("content", "")))
    return gradio_history

def detect_sensitive_info_patterns(text):
    """
    Use regex patterns to detect common sensitive information
    
    Args:
        text (str): Text to analyze
        
    Returns:
        list: Detected sensitive items with category and score
    """
    detected_items = []
    
    # Check each pattern
    for name, (pattern, category, score) in SENSITIVE_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            detected_items.append({
                "type": name,
                "category": category,
                "score": score,
                "match": match.group()
            })
    
    return detected_items

async def detect_sensitive_info_ai(text):
    """
    Use AI to detect and categorize sensitive information
    
    Args:
        text (str): Text to analyze
        
    Returns:
        list: AI-detected sensitive items with category and score
    """
    examples = {
        "name": ("Personal name (e.g. 'My name is Sarah')", "Personal Identity", 10),
        "city": ("City of residence (e.g. 'I live in San Francisco')", "Location/Address", 10),
        "birthday": ("Birth date (e.g. 'My birthday is May 3rd')", "Personal Identity", 10),
        "mental_health": ("Mental health information (e.g. 'feeling anxious', 'trouble sleeping')", "Health Information", 10),
        "ethical_concern": ("Workplace ethical issues (e.g. 'coworker stealing')", "Other", 7),
        "relationship_info": ("Personal relationship details (e.g. 'text exchange with partner')", "Social Relationships", 10),
        "medical_condition": ("Medical conditions (e.g. 'diabetes', 'insulin')", "Health Information", 10),
        "workplace_issue": ("Work-related concerns (e.g. 'frustrated at work')", "Personal History", 10),
        "company_name": ("Employer name (e.g. 'XYZ Corp')", "Personal History", 10),
        "vacation_plans": ("Future travel plans (e.g. 'taking a vacation')", "Personal Preferences", 10),
        "income": ("Salary information (e.g. '$75,000 a year')", "Financial/Income/Tax", 10),
        "credit_score": ("Credit scoring information (e.g. 'credit score is 680')", "Financial/Income/Tax", 10),
        "regular_location": ("Frequently visited places (e.g. 'visit Starbucks on Main Street')", "Location/Address", 10),
        "schedule_info": ("Regular schedule details (e.g. 'after work around 6 PM')", "Personal History", 10),
        "political_view": ("Political opinions or voting history", "Other", 10)
    }
    
    # Build examples for system prompt
    example_list = []
    for key, (description, category, score) in examples.items():
        example_list.append(f"- {key}: {description} (Category: {category}, Sensitivity: {score}/10)")
    
    examples_text = "\n".join(example_list)
    try:
        response = await async_openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are a privacy analysis system. Analyze the text for sensitive personal information. "
                        "Respond in JSON format with an array of detected sensitive items. "
                        "For each item, provide: 'type' (specific type of information), 'category' (one of: Financial/Income/Tax, "
                        "Personal Identity, Personal History, Family Information, Location/Address, Social Relationships, "
                        "Personal Preferences, Health Information, Other), 'score' (sensitivity from 1-10, where 10 is "
                        "extremely sensitive), and 'reason' (brief explanation)."
                        "\n\nConsider these types of sensitive information and their sensitivity levels:\n"
                        f"{examples_text}"
                        "\n\nExamples:"
                        "\nPersonal Information Disclosure: \"My name is Sarah, and I live in San Francisco. My birthday is May 3rd.\""
                        "\nSensitive Topic Exploration: \"I've been feeling anxious lately and having trouble sleeping. What should I do?\""
                        "\nEthical Question: \"I saw my coworker stealing small items from the office. Should I report it?\""
                        "\nFamily/Social Information: \"Here is a text exchange I had with my partner last week. Am I in the wrong?\""
                        "\nMedical Data: \"I have diabetes and take insulin regularly. Are there foods I should avoid?\""
                        "\nProfessional Information: \"I'm frustrated at work. My manager at XYZ Corp doesn't appreciate my efforts.\""
                        "\nFuture Plans: \"I'm thinking about taking a long vacation next month. What's a good place to travel?\""
                        "\nFinancial Information: \"I earn about $75,000 a year, and my credit score is around 680. Can I afford a new car?\""
                        "\nLocation Information: \"I often visit the Starbucks on Main Street after work around 6 PM.\""
                        "\nPolitical Ideology: \"I voted for [candidate or party], but lately I'm reconsidering because of recent policies.\""
                    )
                },
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        result = json.loads(response.choices[0].message.content)
        if "detected_items" in result:
            return result["detected_items"]
        return []
        
    except Exception as e:
        print(f"AI sensitivity detection failed: {e}")
        return []

async def detect_sensitive_info(text, privacy_settings):
    """
    Detect sensitive information using both pattern matching and AI
    
    Args:
        text (str): Text to analyze
        privacy_settings (dict): User's privacy thresholds
        
    Returns:
        dict: Detection results with detected items and threshold info
    """
    # First use pattern matching for common sensitive info
    pattern_detected = detect_sensitive_info_patterns(text)
    
    # Then use AI for more nuanced detection
    ai_detected = await detect_sensitive_info_ai(text)
    
    # Combine results (prioritize pattern matches if duplicates)
    pattern_types = set(item["type"] for item in pattern_detected)
    combined_detected = pattern_detected + [
        item for item in ai_detected 
        if not any(item.get("type", "") == ptype for ptype in pattern_types)
    ]
    
    # Check which items exceed thresholds
    exceeded_items = []
    for item in combined_detected:
        category = CATEGORY_MAPPING.get(item.get("category", "Other"), "other")
        threshold = privacy_settings.get(category, 0)
        if item["score"] > threshold:
            exceeded_items.append({
                "type": item.get("type", ""),
                "category": item.get("category", ""),
                "score": item.get("score", 0),
                "threshold": threshold
            })
    
    return {
        "detected_items": combined_detected,
        "exceeded_items": exceeded_items,
        "exceeded": len(exceeded_items) > 0
    }

async def save_to_dynamodb(user_id, session_id, history, privacy_settings):
    """
    Save chat history to DynamoDB with improved error handling
    
    Args:
        user_id (str): User identifier
        session_id (str): Session identifier
        history (list): Chat history
        privacy_settings (dict): User's privacy settings
    """
    if not user_id or not session_id:
        print("Error: Missing user_id or session_id")
        return False
        
    # Create a sanitized version of history without sensitive content
    sanitized_history = []
    for msg in history:
        if isinstance(msg, dict):
            sanitized_msg = msg.copy()
            if "privacy_check" in sanitized_msg and sanitized_msg["privacy_check"].get("detected_items"):
                # Remove the actual sensitive content from logs
                sanitized_msg["content"] = "[REDACTED SENSITIVE CONTENT]"
            sanitized_history.append(sanitized_msg)
    
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": json.dumps(sanitized_history, ensure_ascii=False),  # Store sanitized history
        "privacy_settings": json.dumps(privacy_settings, ensure_ascii=False),
        "metadata": {
            "sensitive_operations": sum(1 for msg in history if "privacy_check" in msg),
            "last_modified": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        await asyncio.to_thread(table.put_item, Item=data)
        return True
    except Exception as e:
        print(f"Failed to save to DynamoDB: {e}")
        return False

async def privacy_aware_chatbot(user_id, session_id, user_input, internal_history, privacy_settings):
    """
    Core privacy-aware chatbot logic with improved error handling
    
    Args:
        user_id (str): User identifier
        session_id (str): Session identifier
        user_input (str): User's message
        internal_history (list): Current chat history
        privacy_settings (dict): User's privacy thresholds
        
    Returns:
        tuple: Updated chat history and state
    """
    # Validate input
    if not user_id:
        system_msg = {
            "role": "system",
            "content": "Error: User ID cannot be empty",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(system_msg)
        return convert_to_gradio_format(internal_history), session_id, internal_history, privacy_settings

    if not internal_history:
        initial_msg = {
            "role": "assistant",
            "content": "Hello! I'm a privacy-aware assistant. What can I help you with today?",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(initial_msg)
        return convert_to_gradio_format(internal_history), session_id, internal_history, privacy_settings

    # Detect sensitive information
    detection = await detect_sensitive_info(user_input, privacy_settings)
    
    user_message = {
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "privacy_check": detection
    }
    internal_history.append(user_message)
    
    # If detection exceeds the threshold, add a system warning message
    if detection.get("exceeded"):
        categories = list(set(item["category"] for item in detection["exceeded_items"]))
        highest_score = max(item["score"] for item in detection["exceeded_items"])
        
        warning_msg = {
            "role": "system",
            "content": (
                f"⚠️ WARNING: Your message contains sensitive information in categories: {', '.join(categories)}. "
                f"Highest sensitivity score: {highest_score}/10, which exceeds your privacy threshold. "
                f"Please be cautious about sharing sensitive personal information."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(warning_msg)
    
    # Build message context with all history messages
    messages = [{"role": "system", "content": "You are a privacy-focused assistant. Never ask for sensitive personal information like SSN, credit card numbers, or exact addresses."}]
    for msg in internal_history:
        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant", "system"]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    try:
        response = await async_openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=messages,
            temperature=0.7
        )
        
        assistant_msg = {
            "role": "assistant",
            "content": response.choices[0].message.content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(assistant_msg)
        
        # Only save to DynamoDB if successful
        save_success = await save_to_dynamodb(user_id, session_id, internal_history, privacy_settings)
        if not save_success:
            system_msg = {
                "role": "system",
                "content": "⚠️ Unable to save chat history",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            internal_history.append(system_msg)
            
    except Exception as e:
        error_msg = {
            "role": "system",
            "content": f"⚠️ Error occurred: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        internal_history.append(error_msg)
    
    return convert_to_gradio_format(internal_history), session_id, internal_history, privacy_settings

def create_privacy_sliders():
    """Create privacy slider components"""
    with gr.Row():
        sliders = []
        for category_name, category_id in CATEGORY_MAPPING.items():
            if category_id != "other":
                default_val = 7 if category_id in ["identity", "financial", "health", "location"] else 5
                sliders.append(gr.Slider(0, 10, value=default_val, label=f"{category_name} Sensitivity", interactive=True))
        return sliders

# ================= Gradio Interface =================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔒 Privacy-Aware Chatbot: Self define privacy threshold")
    
    # Privacy Settings Section
    with gr.Row(visible=True) as setup_panel:
        with gr.Column():
            user_id_input = gr.Textbox(label="User ID", placeholder="Enter a unique identifier...")
            gr.Markdown("### Privacy Sensitivity Thresholds\nSet how sensitive you want the bot to be for each category. Higher values allow more sensitive information. 🔒 For example, 1 means you don't want to share it to anyone; 10 means you are ok with this info on billboard next to I-5.")
            sliders = create_privacy_sliders()
            init_btn = gr.Button("Initialize Privacy Settings", variant="primary")
    
    # Chat Interface
    with gr.Row(visible=False) as chat_panel:
        with gr.Column():
            session_id_state = gr.State(lambda: uuid.uuid4().hex)
            privacy_settings_state = gr.State({})
            internal_history_state = gr.State([])
            chatbot = gr.Chatbot(height=500)
            msg = gr.Textbox(label="Message", lines=2)
            with gr.Row():
                submit_btn = gr.Button("Send", variant="primary")
                reset_btn = gr.Button("Reset Chat")
            gr.Markdown("### 🔒 Privacy Notice\nThis chatbot monitors your messages for sensitive information like SSN, credit cards, addresses, etc. For your protection, highly sensitive information may trigger warnings.")
    
    def initialize_settings(user_id, *slider_values):
        """
        Initialize privacy settings from slider values
        
        Args:
            user_id (str): User identifier
            *slider_values: Values from privacy sliders
            
        Returns:
            tuple: Updated states and UI components
        """
        if not user_id:
            return {}, None, None, []
            
        categories = [cat_id for cat_name, cat_id in CATEGORY_MAPPING.items() if cat_id != "other"]
        settings = dict(zip(categories, slider_values))
        
        # Gradio 3.x compatibility
        return (
            settings,
            gr.Row.update(visible=True),
            gr.Row.update(visible=False),
            []
        )
    
    def reset_chat(user_id, privacy_settings):
        """
        Reset the chat session
        
        Args:
            user_id (str): User identifier
            privacy_settings (dict): Current privacy settings
            
        Returns:
            tuple: New session state
        """
        new_session_id = uuid.uuid4().hex
        return [], new_session_id, []
    
    init_btn.click(
        initialize_settings,
        [user_id_input] + sliders,
        [privacy_settings_state, chat_panel, setup_panel, internal_history_state]
    )
    
    submit_btn.click(
        privacy_aware_chatbot,
        [user_id_input, session_id_state, msg, internal_history_state, privacy_settings_state],
        [chatbot, session_id_state, internal_history_state, privacy_settings_state]
    ).then(lambda: "", None, [msg])
    
    reset_btn.click(
        reset_chat,
        [user_id_input, privacy_settings_state],
        [chatbot, session_id_state, internal_history_state]
    )

if __name__ == "__main__":
    demo.launch(share=True)