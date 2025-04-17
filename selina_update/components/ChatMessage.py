from components.state import messages
def render_messages():
    return '\n\n'.join([f"**{m['role'].capitalize()}**: {m['content']}" for m in messages])
