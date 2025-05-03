# src/sip_handler.py

import time
import threading

class MockSIPClient:
    def __init__(self, config):
        self.sip_server_ip = config.get("sip_server_ip", "127.0.0.1")
        self.sip_server_port = config.get("sip_server_port", 5060)
        self.device_id = config.get("device_id", "UnknownDevice")
        self.registered = False
        self.running = False

    def register(self):
        """
        Simulate SIP registration with server.
        """
        print(f"[SIP] Attempting registration to SIP Server {self.sip_server_ip}:{self.sip_server_port}")
        time.sleep(1)  # simulate network delay
        self.registered = True
        print(f"[SIP] Registration successful with Device ID: {self.device_id}")

    def listen_for_invites(self):
        """
        Simulate listening for INVITE messages and responding.
        """
        print("[SIP] Listening for INVITE requests...")
        self.running = True

        # Simulate receiving an INVITE after a few seconds
        def simulate_invite():
            time.sleep(3)  # wait 3 seconds
            if self.running and self.registered:
                print("[SIP] Received INVITE request from SIP server.")
                self.start_media_session()

        threading.Thread(target=simulate_invite).start()

    def start_media_session(self):
        """
        Simulate starting a media session (RTP stream) after INVITE.
        """
        print("[SIP] Media session established. Streaming media via RTP now.")

    def unregister(self):
        """
        Simulate unregistering from the SIP server.
        """
        if self.running:
            self.running = False
            print("[SIP] Unregistered from SIP Server.")

# High-level functions to integrate with your main.py

def register_to_sip_server(config):
    global sip_client
    sip_client = MockSIPClient(config)
    sip_client.register()
    sip_client.listen_for_invites()

def handle_invite_request(stream_source):
    """
    This stays here for now but will be real SIP media control later.
    """
    print(f"[SIP] Handling INVITE for stream: {stream_source}")
    # In real SIP, we would start media RTP streaming here
