import gradio as gr
import requests
import uuid  # For generating unique session IDs

# API endpoint for the back-end
API_URL = "https://<your-api-gateway-endpoint>/chatbot"  # Replace with your API Gateway URL

# Function to handle user interaction
def chat_with_bot(user_message, chat_history, session_id, user_id):
    if not user_id:
        return "Please provide a user ID before starting the chat.", chat_history, session_id, user_id

    # Prepare the payload for the back-end
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "user_message": user_message,
        "chat_history": chat_history
    }

    # Send the POST request to the back-end
    response = requests.post(API_URL, json=payload)
    response_data = response.json()

    # Extract the updated chat history from the response
    updated_chat_history = response_data.get("chat_history", [])
    return updated_chat_history, session_id, user_id

# Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# Chatbot with OpenAI Backend")

    # Collect user ID first
    user_id = gr.Textbox(label="Enter your User ID", placeholder="Enter your user ID here", value="")
    session_id = gr.Textbox(label="Session ID", value=str(uuid.uuid4()), visible=False)  # Generate a unique session ID

    # Chatbot UI
    chatbot_ui = gr.Chatbot(label="Chatbot")
    user_input = gr.Textbox(label="Your Message", placeholder="Type your message...", visible=False)
    submit_button = gr.Button("Send", visible=False)

    # Function to initialize chat
    def initialize_chat(user_id):
        if not user_id:
            return "User ID is required to proceed.", [], session_id.value, user_id
        # Show chat UI after user ID is entered
        user_input.visible = True
        submit_button.visible = True
        return "", [], session_id.value, user_id

    # Connect initialization logic
    user_id.submit(fn=initialize_chat, inputs=[user_id], outputs=["message", chatbot_ui, session_id, user_id])

    # Connect chat function to chatbot UI
    submit_button.click(
        fn=chat_with_bot,
        inputs=[user_input, chatbot_ui, session_id, user_id],
        outputs=[chatbot_ui, session_id, user_id]
    )

# Launch the Gradio app
demo.launch(share=True)
