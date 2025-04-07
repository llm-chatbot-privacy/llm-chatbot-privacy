import gradio as gr
def chat_input_section():
    return gr.Textbox(label='Your message'), gr.Button('Send')
