from flask import request, jsonify
import requests
from configs.config import Config


def send_message(message, phone_number):
    try:
        payload = {
            "to": phone_number,
            "message": message
        }

        response = requests.post(
            Config.CONNECT_URL, json=payload, headers={
                "x-presto-app-key": Config.CONNECT_APP_KEY})
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}