from openai import OpenAI

# 填入你的 API Key（或设置环境变量 ARK_API_KEY）
API_KEY = "ark-9c63f23c-39f4-46b7-a299-84226416d11c-4f6f3"
ENDPOINT_ID = "ep-20260423222827-6lcn6"

client = OpenAI(
    api_key=API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

def test_chat():
    print("Testing chat completion...")
    response = client.chat.completions.create(
        model=ENDPOINT_ID,
        messages=[
            {"role": "user", "content": "你好，请简单介绍一下你自己。"},
        ],
    )
    print(f"Model: {response.model}")
    print(f"Response: {response.choices[0].message.content}")
    print(f"Usage: {response.usage}")

def test_stream():
    print("\nTesting streaming...")
    stream = client.chat.completions.create(
        model=ENDPOINT_ID,
        messages=[
            {"role": "user", "content": "用一句话介绍人工智能。"},
        ],
        stream=True,
    )
    print("Stream response: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()

if __name__ == "__main__":
    test_chat()
    test_stream()
