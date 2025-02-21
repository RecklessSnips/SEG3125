import os
import gradio as gr
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

def groq_bot(message, history):
    """
    处理用户输入，调用 Groq API 生成回答
    """
    client = Groq(
        api_key=API_KEY,
    )

    # 构造聊天历史，保留前几轮对话
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert travel guide for Japan with 10+ years of experience. "
                "You provide detailed vacation plans, suggest popular attractions, local food, and affordable luxury hotels. "
                "Your recommendations are practical and budget-friendly."
            )
        }
    ]
    
    # 加入用户的历史对话，保持上下文
    for user_msg, ai_response in history[-3:]:  # 只保留最近3轮对话
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": ai_response})

    # 加入当前用户输入
    messages.append({"role": "user", "content": message})

    # 发送请求到 Groq API
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.5,
        max_completion_tokens=5000,
        stream=True  # 开启流式返回
    )

    # 处理流式返回结果
    response = ""
    for chunk in completion:
        content = chunk.choices[0].delta.content or ""
        response += content
        yield response  # Gradio 的 `yield` 实现流式响应

# 启动 Gradio Chat 界面
gr.ChatInterface(fn=groq_bot).launch()
