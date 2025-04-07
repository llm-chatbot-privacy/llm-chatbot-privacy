import gradio as gr
def data_handling_selector():
    radio = gr.Radio(['private', 'personalized', 'sharing'], label='Choose Data Handling Mode')
    info = gr.Markdown('🔒 Your conversation will not be stored. Perfect for sensitive discussions.')
    button = gr.Button('Start Chat')
    return radio, button, info
