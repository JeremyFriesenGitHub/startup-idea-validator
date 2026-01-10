import asyncio
import os
from dotenv import load_dotenv
try:
    from backboard import BackboardClient
except ImportError:
    print("Backboard SDK not installed")
    exit(1)

load_dotenv()

async def main():
    client = BackboardClient(api_key=os.getenv("BACKBOARD_API_KEY"))
    
    print("Creating assistant...")
    asst = await client.create_assistant(name="Debug Asst", description="Debug")
    asst_id = getattr(asst, "id", None) or asst.get("id")
    print(f"Assistant ID: {asst_id}")
    
    print("Creating thread...")
    thread = await client.create_thread(assistant_id=asst_id)
    thread_id = getattr(thread, "id", None) or thread.get("id")
    print(f"Thread ID: {thread_id}")
    
    print("Sending message...")
    resp = await client.add_message(
        thread_id=thread_id,
        content="Say 'Hello World'",
        model_name="gpt-4o-mini"
    )
    
    print("\n--- Raw Response Type ---")
    print(type(resp))
    print("\n--- Raw Response Dict ---")
    try:
        if hasattr(resp, "__dict__"):
            print(resp.__dict__)
        else:
            print(resp)
    except Exception as e:
        print(f"Could not print dict: {e}")

if __name__ == "__main__":
    asyncio.run(main())
