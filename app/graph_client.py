import os
import httpx
from datetime import datetime, timedelta
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

load_dotenv()


class GraphClient:
    def __init__(self):
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self.refresh_token = os.getenv("AZURE_REFRESH_TOKEN")
        self.scope = [
            "https://graph.microsoft.com/Chat.ReadWrite",
            "https://graph.microsoft.com/User.Read",
        ]
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

    def get_token(self):
        result = self.app.acquire_token_by_refresh_token(
            self.refresh_token, scopes=self.scope
        )
        if "access_token" in result:
            if "refresh_token" in result:
                self.refresh_token = result["refresh_token"]
                print("Refreshed token and got a new refresh_token.")
            return result["access_token"]
        else:
            raise Exception(
                f"Could not acquire token: {result.get('error_description')}"
            )

    async def api_call(self, method: str, endpoint: str, json_data=None):
        access_token = self.get_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = f"https://graph.microsoft.com/v1.0{endpoint}"
        async with httpx.AsyncClient() as client:
            if method.lower() == "get":
                response = await client.get(url, headers=headers)
            elif method.lower() == "post":
                response = await client.post(url, headers=headers, json=json_data)
            elif method.lower() == "delete":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
        return response

    async def create_subscription(self, user_id: str):
        expiration_time = (
            datetime.utcnow() + timedelta(hours=70)
        ).isoformat() + "Z"  # Max is ~71 hours
        payload = {
            "changeType": "created",
            "notificationUrl": f"{os.getenv('WEBHOOK_BASE_URL')}/api/webhook",
            "lifecycleNotificationUrl": f"{os.getenv('WEBHOOK_BASE_URL')}/api/webhook",
            "resource": f"/users/{user_id}/chats/getAllMessages",
            "expirationDateTime": expiration_time,
            "clientState": os.getenv("SUBSCRIPTION_CLIENT_STATE"),
            "includeResourceData": False,
        }
        response = await self.api_call("post", "/subscriptions", json_data=payload)
        if response.status_code == 201:
            print(f"Subscription created successfully: {response.json()['id']}")
            return response.json()
        print(f"Error creating subscription: {response.text}")
        return None

    async def delete_all_subscriptions(self):
        response = await self.api_call("get", "/subscriptions")
        if response.status_code == 200:
            subs = response.json().get("value", [])
            for sub in subs:
                sub_id = sub["id"]
                await self.api_call("delete", f"/subscriptions/{sub_id}")
                print(f"Deleted subscription: {sub_id}")

    async def send_chat_message(self, chat_id: str, content: str):
        payload = {"body": {"content": content}}
        response = await self.api_call(
            "post", f"/chats/{chat_id}/messages", json_data=payload
        )
        return response.status_code == 201


graph_client = GraphClient()
