from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import os
import requests
from datetime import datetime
from geopy.geocoders import Nominatim

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
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'

@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    reply_text = get_weather_forecast(user_text)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

def get_weather_forecast(city, target_date=None):
    try:
        geolocator = Nominatim(user_agent="line_weather_bot")
        location = geolocator.geocode(city + ", Taiwan")
        if not location:
            return f"找不到 {city} 的位置。請再確認地名。"

        lat, lon = location.latitude, location.longitude
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=zh_tw"
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            return f"{city} 的天氣查詢失敗：{data.get('message', '未知錯誤')}"

        forecast_list = data["list"]
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        matched = [f for f in forecast_list if f["dt_txt"].startswith(target_date)]
        if not matched:
            return f"{city} 在 {target_date} 查無天氣資料（僅提供未來5天）"

        result = f"{location.address}\n{target_date} 天氣預報：\n"
        for f in matched:
            time_str = f["dt_txt"][11:16]
            temp = f["main"]["temp"]
            desc = f["weather"][0]["description"]
            rain = f.get("pop", 0) * 100
            result += f"🕒{time_str} | {desc} | {temp:.1f}°C | 降雨機率 {rain:.0f}%\n"

        return result.strip()
    except Exception as e:
        return "天氣查詢時發生錯誤，請稍後再試。"

if __name__ == "__main__":
    app.run()
