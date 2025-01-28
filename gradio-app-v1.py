


import gradio as gr
import boto3
import uuid
import json
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import os


# In[ ]:


os.environ["AWS_ACCESS_KEY_ID"] = "keyid"
os.environ["AWS_SECRET_ACCESS_KEY"] = "accesskey"
os.environ["AWS_REGION"] = "us-west-2"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


# In[ ]:


# AWS DynamoDB setup
dynamodb_resource = boto3.resource('dynamodb', region_name="us-west-2")
table = dynamodb_resource.Table('chat_history')


# In[ ]:


# Load the LLM model
model_name = "distilgpt2"  # Example open-source model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto", torch_dtype="auto")
llm_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer, max_length=512)


# In[ ]:


# Function to save conversation history to DynamoDB
def save_to_dynamodb(session_id, chat_history):
    data = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    print("Saving to DynamoDB:", data)  # Debugging log
    table.put_item(Item=data)


# In[ ]:


# Function to query DynamoDB
def get_from_dynamodb(session_id):
    response = table.get_item(Key={"session_id": session_id})
    if "Item" in response:
        return json.loads(response["Item"]["history"])
    return []


# In[ ]:


# Function to generate a response from the LLM
def chatbot(session_id, user_message, chat_history):
    # Generate the LLM response
    prompt = " ".join([msg["content"] for msg in chat_history if msg["role"] == "user"]) + f" {user_message}"
    llm_response = llm_pipeline(prompt, num_return_sequences=1, do_sample=True)[0]["generated_text"]

    # Append user and LLM messages in the correct format
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": llm_response})

    save_to_dynamodb(session_id, chat_history)
    return chat_history, session_id

# Gradio app
with gr.Blocks() as demo:
    gr.Markdown("# Chatbot with LLM Response")
    session_id = gr.State(str(uuid.uuid4()))  # Generate unique session ID

    # Single Chatbot component
    chatbot_ui = gr.Chatbot(type='messages', label="Chatbot")
    user_input = gr.Textbox(label="Your Message")
    submit_button = gr.Button("Send")

    # Link the components
    submit_button.click(chatbot, [session_id, user_input, chatbot_ui], [chatbot_ui, session_id])
    
    # Option to clear the chat
    clear_button = gr.Button("Clear Chat")
    clear_button.click(lambda: ([], str(uuid.uuid4())), inputs=[], outputs=[chatbot_ui, session_id])

# Launch app with sharing enabled
demo.launch(share=True)




