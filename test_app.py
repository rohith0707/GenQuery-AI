#!/usr/bin/env python3
"""
Test script to verify the application starts with the landing page.
Run this to test the app flow.
"""

import subprocess
import sys
import time

def test_app():
    print("🚀 Testing Generative SQL Intelligence App")
    print("=" * 50)
    
    print("\n1. Starting Streamlit app...")
    try:
        # Start the streamlit app
        cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port=8501"]
        print(f"Running: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for the server to start
        time.sleep(3)
        
        if process.poll() is None:
            print("✅ App started successfully!")
            print("🌐 Open your browser and go to: http://localhost:8501")
            print("\nExpected behavior:")
            print("- Should redirect to Landing page automatically")
            print("- Landing page should show 'Generative SQL Intelligence' title")
            print("- Should have animated background and particles")
            print("- Navigation buttons should work properly")
            print("\nPress Ctrl+C to stop the server...")
            
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping server...")
                process.terminate()
                process.wait()
                print("✅ Server stopped")
        else:
            stdout, stderr = process.communicate()
            print("❌ App failed to start")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_app()