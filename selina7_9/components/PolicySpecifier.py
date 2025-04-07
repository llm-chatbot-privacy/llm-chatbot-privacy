
import gradio as gr

def policy_specifier():
    uses = gr.CheckboxGroup(
        ["Store conversations", "Personalize experience", "Usage analytics"],
        label="Allowable Uses of Your Data"
    )
    recipients = gr.Dropdown(
        ["OpenAI", "Government", "Public Dataset", "Partners"],
        label="Approved Recipients",
        multiselect=True
    )
    save_btn = gr.Button("Save Policy")
    confirm = gr.Markdown("")
    return uses, recipients, save_btn, confirm
