from backboard import BackboardClient
import os
from dotenv import load_dotenv

load_dotenv()

try:
    client = BackboardClient(api_key=os.getenv("BACKBOARD_API_KEY", "dummy"))
    print("Client methods:")
    print([m for m in dir(client) if not m.startswith("_")])
except Exception as e:
    print(f"Error: {e}")
