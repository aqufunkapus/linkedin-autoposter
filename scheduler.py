#!/usr/bin/env python3
"""
Scheduler - Runs the LinkedIn auto-poster every hour
This is what Railway will execute continuously
"""

import time
import subprocess
from datetime import datetime

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def run_autoposter():
    """Execute the auto-poster script"""
    try:
        log("🔄 Running LinkedIn auto-poster...")
        result = subprocess.run(
            ['python', 'linkedin_auto_poster.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
            
        if result.returncode == 0:
            log("✅ Auto-poster completed successfully")
        else:
            log(f"⚠️  Auto-poster exited with code {result.returncode}")
            
    except subprocess.TimeoutExpired:
        log("⏱️  Auto-poster timed out after 5 minutes")
    except Exception as e:
        log(f"❌ Error running auto-poster: {e}")

def main():
    """Run auto-poster every hour"""
    log("🚀 Scheduler started - will check for new posts every hour")
    
    while True:
        run_autoposter()
        
        # Wait 1 hour before next check
        log("⏳ Sleeping for 1 hour until next check...")
        time.sleep(3600)  # 3600 seconds = 1 hour

if __name__ == "__main__":
    main()
