from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from datetime import datetime
import os
import requests
from dotenv import load_dotenv
from googletrans import Translator

# 載入 .env 環境變數
load_dotenv()

# 初始化
app = Flask(__name__)
configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))
line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Check access token/channel secret.")
        abort(400)

    return 'OK'


@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()

    if user_text.startswith("天氣 "):
        parts = user_text[3:].split()
        if len(parts) == 0:
            send_reply(event.reply_token, "請輸入地名，例如：天氣 台北 或 天氣 台北 6/15")
            return

        raw_city = parts[0]
        date_str = None

        # 日期處理
        if len(parts) > 1:
            try:
                mm, dd = parts[1].split("/")
                year = datetime.now().year
                date_str = f"{year}-{int(mm):02d}-{int(dd):02d}"
            except:
                send_reply(event.reply_token, "請輸入正確日期格式，例如：天氣 台北 6/15")
                return

        # 翻譯城市名稱
        translator = Translator()
        city = translator.translate(raw_city, dest="en").text

        reply_text = get_weather_forecast(city, raw_city, date_str)
    elif user_text.lower() == "hi":
        reply_text = "hello"
    else:
        reply_text = "你說的是：" + user_text

    send_reply(event.reply_token, reply_text)


def send_reply(token, message):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=token,
                messages=[TextMessage(text=message)]
            )
        )


def get_weather_forecast(city_en, city_zh, target_date=None):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_en}&appid={WEATHER_API_KEY}&units=metric&lang=zh_tw"
    try:
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            return f"查不到「{city_zh}」的天氣資料，請確認地名拼寫。"

        forecast_list = data["list"]
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        matched = [f for f in forecast_list if f["dt_txt"].startswith(target_date)]

        if not matched:
            return f"{city_zh} 在 {target_date} 查無天氣資料（僅提供未來5天）"

        result = f"{city_zh} {target_date} 的天氣預報：\n"
        for f in matched:
            time_str = f["dt_txt"][11:16]
            temp = f["main"]["temp"]
            desc = f["weather"][0]["description"]
            rain = f.get("pop", 0) * 100
            result += f"🕒{time_str} | {desc} | {temp:.1f}°C | 降雨機率 {rain:.0f}%\n"

        return result.strip()
    except Exception as e:
        return "天氣查詢失敗，請稍後再試。"


if __name__ == "__main__":
    app.run()
