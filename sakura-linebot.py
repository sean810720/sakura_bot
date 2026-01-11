'''
[LINEBot] 櫻花小助理

- Heroku 網址:
https://sakura-bot-g977.onrender.com/callback
'''

import os, configparser

# 載入 Flask
from flask import Flask, request, abort

# 載入 LINEbot SDK
from linebot.v3 import (
     WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.models.show_loading_animation_request import ShowLoadingAnimationRequest

# 載入 Llama Index
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.node_parser import SentenceSplitter

#from llama_index.llms.gemini import Gemini
from llama_index.llms.google_genai import GoogleGenAI

# from llama_index.embeddings.gemini import GeminiEmbedding
# from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

# Flask & 一般設定
app = Flask(__name__)

# LINEbot 設定
handler = WebhookHandler(
    os.environ.get('channel_secret')
)
line_bot = MessagingApi(
    ApiClient(
        Configuration(
            access_token=os.environ.get('channel_access_token')
        )
    )
)

# LLM API 設定
os.environ['OPENAI_API_KEY'] = os.environ.get('openai_key')
os.environ['GOOGLE_API_KEY'] = os.environ.get('google_gemini_key')

# LlamaIndex LLM 設定
# Settings.llm = OpenAI(
#     model="gpt-4o-mini",
#     temperature=0,
#     top_p=0.9,
#     top_k=40,
#     repedtion_penalty=1.1
# )
Settings.llm = GoogleGenAI(
    model="gemini-2.5-flash-lite",
    # temperature=0.1,
    # top_p=0.9,
    # top_k=40,
    # repedtion_penalty=1.1
)

# Settings.embed_model = GeminiEmbedding(
#     model_name="models/gemini-embedding-001"
# )
# Settings.embed_model = GoogleGenAIEmbedding(
#     model_name="text-embedding-004",
#     embed_batch_size=100,
# )
Settings.text_splitter = SentenceSplitter(
    chunk_size=2048,
    chunk_overlap=200
)

# LlamaIndex 初始化
documents = SimpleDirectoryReader(input_dir="./data").load_data()
index = VectorStoreIndex.from_documents(
    documents,
    transformations=[Settings.text_splitter]
)

# 設定基於 LLM 的自定義 Reranker
from llama_index.core.postprocessor import LLMRerank
llm_reranker = LLMRerank(
    choice_batch_size=5,
    llm=Settings.llm,
    top_n=2
)

# 建立聊天引擎
chat_engine = index.as_chat_engine(
    chat_mode="condense_plus_context",
    node_postprocessors=[llm_reranker],
    verbose=True,
    system_prompt=(
        "妳現在是櫻花澍社區的管理小助理。"
        "妳的性別是女性。"
        "妳的個性活潑熱心嚴謹又帶點幽默。"
        "妳提到複雜的管理規則會用簡單清楚又生活化的方式解釋。"
        "妳一律用台灣繁體中文回答問題。"
        "妳偶爾喜歡使用顏文字。"
        "請一步一步思考，告訴我最後結果即可。"
        "盡量簡短又清晰地回答。"
        "如果提問中只有閒聊內容，也回應閒聊字眼即可。"
    ),
)

# 接收平台來的通知
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body:" + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 回應區
@handler.add(MessageEvent, message=TextMessageContent)
def echo(event):

    # 只回應 LINE 官方以外的帳號
    if event.source.user_id != "Udeadbeefdeadbeefdeadbeefdeadbeef":
        result = ""

        # 單人小窗模式
        if event.source.type == 'user':

            # 載入思考中動畫
            line_bot.show_loading_animation(
                ShowLoadingAnimationRequest(
                    chatId=event.source.user_id,
                    loadingSeconds=60
                )
            )
            
            # 提問處理
            prompt = event.message.text
            prompt = "{}".format(prompt.strip().replace('\n', ''))
            #result = str(chat_engine.chat(prompt, tool_choice="query_engine_tool"))
            result = str(chat_engine.chat(prompt))
            result = result.replace('*   **', '◼').replace('**', '').replace('* ', '✅ ') if result else ""
            if result == "Empty Response":
                result = str(Settings.llm.complete("""
妳現在是櫻花澍社區的管理小助理。
妳的性別是女性。
妳的個性活潑熱心嚴謹又帶點幽默。
妳提到複雜的管理規則會用簡單清楚又生活化的方式解釋。
妳一律用台灣繁體中文回答問題。
妳偶爾喜歡使用顏文字。
盡量簡短又清晰地回答。
如果提問中只有閒聊內容，也回應閒聊字眼即可。
請一步一步思考，告訴我最後結果即可：「{}」""".format(prompt)))

            # 回應用戶
            print("\n=== 發問 ===\n{}\n======\n".format(prompt))
            print("\n=== AI回答 ===\n{}\n======\n".format(result))
            if len(result) > 0:
                line_bot.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=result)]
                    )
                )

# 主程式
if __name__ == "__main__":
    app.run()
