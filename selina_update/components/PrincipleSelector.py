import gradio as gr
def principle_selector():
    radio = gr.Radio(['Neutral Informant', 'User Advocate', 'Expert Advisor'], label='Choose Chatbot Advisory Role')
    desc = gr.Markdown('The assistant presents only neutral facts, avoiding opinions or suggestions.')
    return radio, desc
