import gradio as gr
from services.openai_service import set_api_key
def api_key_section():
    key_input = gr.Textbox(label='Set OpenAI API Key', type='password')
    key_button = gr.Button('Set API Key')
    key_status = gr.Textbox(label='API Status', interactive=False)
    key_button.click(fn=set_api_key, inputs=key_input, outputs=None)
    return key_input, key_button, key_status
