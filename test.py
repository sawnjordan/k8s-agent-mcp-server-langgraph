from openai import OpenAI
import os

client = OpenAI(
    api_key="sk-d702b99edb1940d0bf68cf86aad97917",
    base_url="https://api.deepseek.com"
)

# List models
models = client.models.list()

for m in models.data:
    print(m.id)
