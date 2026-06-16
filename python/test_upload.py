# -*- coding: utf-8 -*-

import os
import sys

# Add the parent directory to sys.path so we can locate .env or import helper files
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
sys.path.insert(0, _CURRENT_DIR)

# Try to load .env from the parent directory
_env_path = os.path.join(_PARENT_DIR, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        # Simple manual parser fallback if python-dotenv is not installed
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

import lazop

appKey = os.getenv("DARAZ_APPKEY")
appSecret = os.getenv("DARAZ_SECRET")

if not appKey or not appSecret:
    raise ValueError(
        "DARAZ_APPKEY and DARAZ_SECRET must be defined in your .env file or environment."
    )

client = lazop.LazopClient("https://api.daraz.com.np/rest", appKey, appSecret)

# create a api request
request = lazop.LazopRequest("/xiaoxuan/mockfileupload")

# simple type params ,Number ,String
request.add_api_param("file_name", "pom.xml")

# file params, value should be file content
_dummy_file = os.path.join(_CURRENT_DIR, "setup.py")
with open(_dummy_file, "r", encoding="utf-8") as f:
    file_content = f.read()

request.add_file_param("file_bytes", file_content)

response = client.execute(request)

# response type nil,ISP,ISV,SYSTEM
print("Response Type:", response.type)

# response code, 0 is no error
print("Response Code:", response.code)

# response error message
print("Response Message:", response.message)

# response unique id
print("Request ID:", response.request_id)

# full response
print("Body:", response.body)
