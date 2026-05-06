import sys
import os
import json

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from agent.vision import VisionAI

def test_ai():
    print(f"--- Testing AI Provider: {Config.AI_PROVIDER.upper()} ---")
    print(f"Model: {getattr(Config, f'{Config.AI_PROVIDER.upper()}_MODEL', 'Unknown')}")
    
    vision = VisionAI()
    
    # Text only test
    print("\n[1] Testing Text-Only Analysis (UIA/Lesson Logic)...")
    try:
        response = vision.analyze_text_only("Hello! This is a test. Reply with 'DeepSeek is online'.")
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"❌ Text-only failed: {e}")
        
    # Analyze screen test (will fallback since it's deepseek)
    print("\n[2] Testing Multimodal Fallback...")
    try:
        # Pass a fake base64 string to trigger the fallback logic
        fake_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        task = "Test the system."
        
        res = vision.analyze_screen(fake_b64, task)
        print(f"Thought: {res.get('thought')}")
        print(f"Action: {res.get('action')}")
    except Exception as e:
        print(f"❌ Multimodal fallback failed: {e}")

if __name__ == "__main__":
    test_ai()
