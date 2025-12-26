# test_api.py
import requests
import json

API_KEY = "ms-01597560-bc5b-41c0-86ff-2466a31fc959"
URL = "https://api-inference.modelscope.cn/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json; charset=utf-8"
}

data = {
    "model": "deepseek-ai/DeepSeek-V3.1",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "max_tokens": 50,
    "temperature": 0.7
}

try:
    response = requests.post(URL, headers=headers,
                             data=json.dumps(data, ensure_ascii=False).encode('utf-8'))

    if response.status_code == 200:
        print("✅ API！")
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        print(f"模型回复：{reply}")
    else:
        print(f"❌ API请求失败，状态码：{response.status_code}")
        print(f"错误信息：{response.text}")

except Exception as e:
    print(f"❌ 连接异常：{str(e)}")