import os
import uvicorn
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from .graph_client import graph_client

app = FastAPI()


# --- Pydantic Models for Webhook ---
class ResourceData(BaseModel):
    odata_type: str = Field(..., alias="@odata.type")
    id: str


class Notification(BaseModel):
    subscriptionId: str
    clientState: str
    resource: str
    lifecycleEvent: Optional[str] = None  # <-- เพิ่ม field นี้


class WebhookPayload(BaseModel):
    value: List[Notification]


# --- Global Cache for User ID ---
MY_USER_ID = None


# --- Webhook Endpoint ---
@app.post("/api/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # --- ส่วนที่ 1: จัดการ Validation Request ก่อนเสมอ ---
    # ตรวจสอบว่ามี validationToken ใน query params หรือไม่
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        # ถ้ามี ให้ตอบกลับด้วย token นั้นทันที พร้อม status 200 OK
        print("Received validation request. Responding with token.")
        return Response(
            content=validation_token, media_type="text/plain", status_code=200
        )

    # --- ส่วนที่ 2: ถ้าไม่ใช่ Validation Request ก็จะเป็น Notification จริง ---
    # เราจะพยายามอ่าน body เป็น JSON
    try:
        payload_json = await request.json()
        payload = WebhookPayload(**payload_json)

        # ส่งไปประมวลผลเบื้องหลังเพื่อตอบกลับ Microsoft ให้เร็วที่สุด
        background_tasks.add_task(process_notifications, payload)

        # ตอบกลับด้วย 202 Accepted เพื่อบอกว่า "ได้รับเรื่องแล้ว"
        return Response(status_code=202)

    except Exception as e:
        # ถ้าอ่าน JSON ไม่ได้ หรือมีปัญหาอื่นๆ
        print(f"Error processing notification payload: {e}")
        return Response(status_code=400)  # Bad Request


# --- Background Task ---
async def process_notifications(payload: WebhookPayload):
    for notif in payload.value:
        if notif.lifecycleEvent:
            print(f"Received lifecycle notification: {notif.lifecycleEvent}")
            continue  # ข้ามไป ไม่ต้องทำอะไรต่อ

        if notif.clientState != os.getenv("SUBSCRIPTION_CLIENT_STATE"):
            print("Invalid clientState received. Ignoring.")
            continue

        # Get full message details
        response = await graph_client.api_call("get", notif.resource)
        if response.status_code != 200:
            continue

        message_data = response.json()
        sender_id = message_data.get("from", {}).get("user", {}).get("id")

        # Prevent infinite loop by not mirroring self-sent messages
        if sender_id and sender_id == MY_USER_ID:
            print("Ignoring self-sent message.")
            continue

        # Mirror the message
        chat_id = message_data.get("chatId")
        content = message_data.get("body", {}).get("content")
        if chat_id and content:
            print(f"Mirroring message to chat {chat_id}")
            await graph_client.send_chat_message(chat_id, content)


# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    global MY_USER_ID
    print("Application starting up... Setting up Graph subscription.")

    # Get user's own ID to prevent infinite loops
    me_response = await graph_client.api_call("get", "/me")
    if me_response.status_code == 200:
        MY_USER_ID = me_response.json()["id"]
        print(f"Identified as user: {MY_USER_ID}")
        # Clean up old subscriptions and create a new one
        # await graph_client.delete_all_subscriptions()
        await graph_client.create_subscription(MY_USER_ID)
    else:
        print("CRITICAL: Could not get user info. Subscription setup failed.")


@app.get("/")
def health_check():
    return {"status": "ok", "user_id_identified": MY_USER_ID is not None}
