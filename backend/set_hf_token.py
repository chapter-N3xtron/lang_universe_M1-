import os
import sys

token = input("Paste your HuggingFace token (get it from https://huggingface.co/settings/tokens): ").strip()

# Save to environment file
with open(".env", "a") as f:
    f.write(f"\nHF_TOKEN={token}\n")

# Also set for current session
os.environ["HF_TOKEN"] = token

print(f"\n✓ Token saved to .env file")
print("✓ Please also accept the license at: https://huggingface.co/kyutai/pocket-tts")
print("\nThen restart the backend server.")
