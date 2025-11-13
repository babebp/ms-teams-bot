import msal
import os
from dotenv import load_dotenv

load_dotenv(override=True)

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORIZATION_CODE = "CODE FROM URL"

# URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri=http://localhost:8000/callback&response_mode=query&scope=https://graph.microsoft.com/Chat.ReadWrite%20https://graph.microsoft.com/User.Read%20offline_access&state=12345"
# print(URL)

authority = f"https://login.microsoftonline.com/{TENANT_ID}"
app = msal.ConfidentialClientApplication(
    client_id=CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
)
result = app.acquire_token_by_authorization_code(
    AUTHORIZATION_CODE,
    scopes=["https://graph.microsoft.com/Chat.ReadWrite"],
    redirect_uri="http://localhost:8000/callback",
)
if "refresh_token" in result:
    print("SUCCESS! Your Refresh Token:")
    print(result["refresh_token"])
else:
    print("ERROR:", result.get("error_description"))
