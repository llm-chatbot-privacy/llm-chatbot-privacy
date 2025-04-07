
messages = []
data_handling_mode = "private"
transmission_principle = "Neutral Informant"
default_policy = {"uses": [], "recipients": []}

def set_mode(mode):
    global data_handling_mode
    data_handling_mode = mode

def set_principle(p):
    global transmission_principle
    transmission_principle = p

def set_default_policy(policy):
    global default_policy
    default_policy = policy

def add_message(content, role, policy=None):
    messages.append({ "role": role, "content": content, "policy": policy or {} })
