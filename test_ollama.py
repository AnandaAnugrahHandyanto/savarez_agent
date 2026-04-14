import sys
sys.path.insert(0, ".")
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
response = client.chat.completions.create(
    model="llama3:8b",
    messages=[{"role": "user", "content": "Say hello in exactly 3 words"}],
    max_tokens=20,
    stream=False,
)
print("Response:", response.choices[0].message.content)
print("Model:", response.model)
print("Usage:", response.usage)
