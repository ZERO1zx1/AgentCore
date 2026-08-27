"""Simple alerts helper: sends notifications via webhook (Slack, Teams, or custom) or prints to stdout in demo.

Configure ALERT_WEBHOOK_URL env var to send POST {json: {project_id, message}}
"""
import os
import json
import requests

ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL', '')


def send_alert(project_id: str, message: str):
    payload = {'project_id': project_id, 'message': message}
    if ALERT_WEBHOOK_URL:
        try:
            requests.post(ALERT_WEBHOOK_URL, json=payload, timeout=5)
            return True
        except Exception as e:
            print('Failed to send alert to webhook:', e)
            print('Alert payload:', payload)
            return False
    # fallback: print
    print(f'ALERT [{project_id}]: {message}')
    return True
