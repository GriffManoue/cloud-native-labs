      
#!/bin/env python3
from flask import Flask, jsonify
import requests
import time
import logging
import os 
import sys 
import socket

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend service URL - using Kubernetes service discovery
BACKEND_BASE_URL = "http://svc-backend"

# Global variable to store backend config/code retrieved during startup
backend_response_data = None 

# --- Task 13: Graceful Shutdown ---
@app.route("/shutdown")
def shutdown():
    logger.info("Received shutdown request. Shutting down gracefully...")
    try:
        requests.get(f"{BACKEND_BASE_URL}/game-over", timeout=5)
        logger.info("Shutdown signal sent to backend.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send shutdown signal to backend: {str(e)}")
    finally:
        logger.info("Exiting application.")
        sys.exit(0)
# --- End Task 13 ---


@app.route("/hello")
def hello_world():
    return "<p>Hello, World!</p>"

# --- Task 11: /who-am-i Endpoint ---
@app.route("/who-am-i")
def who_am_i():
    pod_name = os.environ.get('POD_NAME', socket.gethostname())
    code = backend_response_data if backend_response_data else None
    
    return jsonify({
        'name': pod_name,
        'code': code
    })
# --- End Task 11 ---

# --- Task 8 & 10: /startup Endpoint ---
@app.route('/startup')
def startup():
    global backend_response_data 
    
    retry_count = 0
    retry_interval = 30  # Seconds between retries
    
    while True:
        try:
            backend_get_config_url = f"{BACKEND_BASE_URL}/get-config"
            logger.info(f"Attempt {retry_count + 1}: Connecting to backend at {backend_get_config_url}")
            response = requests.get(backend_get_config_url, timeout=30)
            response.raise_for_status()
            config_data = response.text
            backend_response_data = config_data
            logger.info("Successfully retrieved backend configuration and stored it.")
            return jsonify(config_data), 200  # OK status
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to connect to backend: {str(e)}")

        retry_count += 1
        logger.info(f"Retrying startup check in {retry_interval} seconds...")
        time.sleep(retry_interval)
# --- End Task 8 & 10 ---


# --- Task 12: /health Endpoint ---
@app.route("/health")
def health_check():
    try:
        ping_url = f"{BACKEND_BASE_URL}/ping"
        logger.debug(f"Performing liveness check: connecting to backend at {ping_url}")
        response = requests.get(ping_url, timeout=3)

        if response.status_code == 200:
            logger.debug("Liveness check successful: Backend is reachable.")
            return jsonify({"status": "healthy"}), 200 # OK status
        else:
            logger.warning(f"Liveness check failed: Backend returned non-200 status code: {response.status_code}")
            return jsonify({"status": "unhealthy", "reason": f"Backend returned status {response.status_code}"}), 503 # Service Unavailable

    except requests.exceptions.RequestException as e:
        logger.error(f"Liveness check failed: Cannot connect to backend: {str(e)}")
        return jsonify({"status": "unhealthy", "reason": "Cannot connect to backend"}), 503 # Service Unavailable
# --- End Task 12 ---


if __name__ == "__main__":
    app.run(debug=True) 

    