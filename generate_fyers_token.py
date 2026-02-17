"""Generate and save Fyers API token manually.

Usage:
    python generate_fyers_token.py
"""

import os
from dotenv import load_dotenv
from src.fyers_auth import get_session, generate_token, save_token

def main():
    load_dotenv()

    client_id = os.environ.get("FYERS_APP_ID")
    secret_key = os.environ.get("FYERS_SECRET_KEY")
    redirect_uri = os.environ.get("FYERS_REDIRECT_URI")

    if not client_id or not secret_key or not redirect_uri:
        print("❌ Missing Fyers credentials in .env file")
        print("\nRequired variables:")
        print("  FYERS_APP_ID=your_app_id_here")
        print("  FYERS_SECRET_KEY=your_secret_key_here")
        print("  FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/abc123")
        print("\nSee .env.example for template")
        return

    print("🔐 Generating Fyers API Token")
    print("="*80)

    # Step 1: Generate auth URL
    session = get_session(client_id, secret_key, redirect_uri)
    auth_url = session.generate_authcode()

    print("\n📋 Step 1: Visit this URL to authorize:")
    print("-"*80)
    print(auth_url)
    print("-"*80)

    print("\n📋 Step 2: After authorizing, you'll be redirected to a URL like:")
    print("https://trade.fyers.in/api-login/redirect-uri/abc123?auth_code=XXXXXXXXXXXXX&state=sample_state")
    print("\n📋 Step 3: Copy the 'auth_code' value from the URL")

    # Step 2: Get auth code from user
    auth_code = input("\n🔑 Paste the auth_code here: ").strip()

    if not auth_code:
        print("❌ No auth_code provided. Exiting.")
        return

    # Step 3: Generate access token
    print("\n⏳ Generating access token...")
    try:
        access_token = generate_token(session, auth_code)
        save_token(access_token)
        print("✅ Access token generated and saved to .fyers_token")
        print(f"✅ Token valid for 24 hours")
        print(f"\n📁 Token saved to: .fyers_token")
        print("\n✨ You can now use fetch_market_data.py or main.py fetch commands!")
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure you copied the entire auth_code")
        print("  2. Try generating a fresh auth URL (run this script again)")
        print("  3. Check your .env credentials are correct")

if __name__ == "__main__":
    main()
