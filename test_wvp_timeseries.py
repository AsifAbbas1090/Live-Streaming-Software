import requests
import sys
import json
import hashlib

# WVP-pro API credentials and endpoints
WVP_API = "https://safe-vision-wvp-web.x-stage.bull-b.com/api"
USERNAME = "freelancer"
PASSWORD = "freelancer"

# Device ID to test (update XX as needed)
DEVICE_ID = "81000000465001000001"

# Disable SSL warnings for demo purposes (not for production)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def md5_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def login():
    """Authenticate and return a session with accessToken set."""
    session = requests.Session()
    login_url = f"{WVP_API}/user/login"
    md5_pwd = md5_hash(PASSWORD)
    params = {"username": USERNAME, "password": md5_pwd}
    resp = session.get(login_url, params=params, verify=False)
    print(f"Login response: {resp.text}")
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print("✅ Login successful.")
        access_token = resp.json()["data"]["accessToken"]
        session.headers.update({"access-token": access_token})
        return session
    else:
        print(f"❌ Login failed: {resp.text}")
        sys.exit(1)

def check_device_status(session, device_id):
    """Check if the device is registered and its status."""
    url = f"{WVP_API}/device/query/devices"
    params = {
        "page": 1,
        "count": 10,
        "online": None,  # None to get both online and offline devices
        "deviceId": device_id
    }
    resp = session.get(url, params=params, verify=False)
    print(f"Device status response: {resp.text}")
    if resp.status_code == 200:
        print("✅ Device status query successful.")
        data = resp.json()
        if data.get("code") == 0 and data.get("data"):
            devices = data["data"].get("list", [])
            if devices:
                device = devices[0]
                print(f"Device status: {json.dumps(device, indent=2, ensure_ascii=False)}")
                return device
            else:
                print(f"❌ Device {device_id} not found in WVP system")
        else:
            print("❌ No device data returned")
    else:
        print(f"❌ Device status query failed: {resp.text}")
    return None

def query_recordings(session, device_id):
    """Query the time-series/recordings for the given device ID."""
    url = f"{WVP_API}/record/query"
    params = {
        "deviceId": device_id,
        "channelId": device_id,  # Often channelId == deviceId for main channel
        "startTime": "2025-05-01T00:00:00",
        "endTime": "2025-05-31T23:59:59"
    }
    resp = session.get(url, params=params, verify=False)
    print(f"Recordings query response: {resp.text}")
    if resp.status_code == 200:
        print("✅ Recordings query successful.")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Recordings query failed: {resp.text}")

def main():
    session = login()
    device = check_device_status(session, DEVICE_ID)
    if device and device.get("online"):
        query_recordings(session, DEVICE_ID)
    else:
        print("⚠️ Device is not online, skipping recordings query")

if __name__ == "__main__":
    main() 