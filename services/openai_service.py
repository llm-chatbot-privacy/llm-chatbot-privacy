
import openai

_api_key = None

def get_api_key():
    return _api_key

def set_api_key(key):
    global _api_key
    _api_key = key
    openai.api_key = key
    return "✅ API key set."

def chat_with_gpt4(user_message, mode, principle):
    if not _api_key:
        return "⚠️ Please provide an API key first."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=_api_key)
        mode_prompts = {
            "private": "You are a confidential assistant. Do not store or use this data beyond this session.",
            "personalized": "You may refer to past conversations to personalize your response, but do not use the data to train models.",
            "sharing": "This conversation may be shared with others. Make sure to remind the user about privacy when necessary."
        }
        principle_prompts = {
            "Neutral Informant": "You should only present factual information and avoid giving advice or opinions.",
            "User Advocate": "You should act in the user's best interest and suggest helpful actions when possible.",
            "Expert Advisor": "You should behave like a confident and experienced expert, but clarify limitations."
        }
        system_prompt = f"{principle_prompts.get(principle, '')}\n{mode_prompts.get(mode, '')}"
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {str(e)}"
