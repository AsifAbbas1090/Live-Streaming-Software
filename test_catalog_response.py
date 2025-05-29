import argparse
import logging
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from sip_handler_pjsip import SIPClient
from gb28181_sip_sender import GB28181SIPSender
from gb28181_xml import format_catalog_response
from file_scanner import get_video_catalog, scan_video_files
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def simulate_catalog_query(device_id):
    return (
        f"MESSAGE sip:{device_id}@127.0.0.1 SIP/2.0\r\n"
        f"From: <sip:test@127.0.0.1>\r\n"
        f"To: <sip:{device_id}@127.0.0.1>\r\n"
        f"Call-ID: testcallid123\r\n"
        f"CSeq: 1 MESSAGE\r\n"
        f"Content-Type: Application/MANSCDP+xml\r\n"
        f"Content-Length: 154\r\n\r\n"
        f"<?xml version=\"1.0\" encoding=\"GB2312\"?>\n"
        f"<Query>\n<CmdType>Catalog</CmdType>\n<SN>123456</SN>\n<DeviceID>{device_id}</DeviceID>\n</Query>"
    )

def main():
    parser = argparse.ArgumentParser(description="Test GB28181 Catalog Response")
    parser.add_argument('--config', '-c', default='gb28181-restreamer/config/config.json', help='Path to config file')
    parser.add_argument('--sip-uri', default=None, help='Target SIP URI for catalog response (overrides config)')
    parser.add_argument('--transport', default='udp', choices=['udp', 'tcp'], help='SIP transport protocol')
    parser.add_argument('--notify', action='store_true', help='Also send NOTIFY (for SUBSCRIBE)')
    args = parser.parse_args()

    config = load_config(args.config)
    if args.transport:
        config['sip']['transport'] = args.transport

    # Ensure stream_directory is absolute
    config['stream_directory'] = os.path.abspath(os.path.join(os.path.dirname(__file__), config['stream_directory']))

    # Scan for video files before generating catalog
    scan_video_files(config['stream_directory'])
    video_catalog = get_video_catalog()

    device_id = config['sip']['device_id']
    logging.info(f"Loaded config for device_id: {device_id}")

    # Simulate a catalog query MESSAGE
    catalog_query = simulate_catalog_query(device_id)
    logging.info("Simulating catalog query MESSAGE:")
    print(catalog_query)

    # Prepare SIP handler and sender
    sip_sender = GB28181SIPSender(config)
    sip_sender.start()

    # Generate catalog XML
    catalog_dict = {}
    for i, video_path in enumerate(video_catalog):
        video_name = os.path.basename(video_path)
        channel_id = f"{device_id}{i+1:03d}"
        catalog_dict[channel_id] = {
            "device_id": channel_id,
            "name": video_name,
            "path": video_path,
            "channel_id": channel_id,
            "status": "ON",
            "manufacturer": "GB28181-Restreamer",
            "model": "Video-File",
            "owner": "gb28181-restreamer",
            "civil_code": "123456",
            "address": f"Video-{i+1}",
            "parental": "0",
            "parent_id": device_id,
            "safety_way": "0",
            "register_way": "1",
            "secrecy": "0",
        }
    catalog_xml = format_catalog_response(device_id, catalog_dict)
    logging.info(f"Generated catalog XML (length {len(catalog_xml)}):\n{catalog_xml[:300]}...\n")

    # Determine target SIP URI
    target_uri = args.sip_uri or f"sip:{device_id}@{config['sip']['server']}:{config['sip']['port']}"
    logging.info(f"Sending catalog as SIP MESSAGE to: {target_uri}")
    sip_sender.send_catalog(catalog_xml, target_uri)
    time.sleep(2)

    if args.notify:
        logging.info(f"Sending catalog as SIP NOTIFY to: {target_uri}")
        # Simulate NOTIFY (using send_notify_catalog)
        sip_sender.send_notify_catalog(
            call_id="testcallid123",
            from_uri=f"sip:{device_id}@{config['sip']['server']}",
            to_uri=target_uri,
            via_header=f"SIP/2.0/{args.transport.upper()} {config['sip']['server']}:{config['sip']['port']};branch=z9hG4bK-testbranch",
            cseq="1",
            target_uri=target_uri
        )
        time.sleep(2)

    sip_sender.stop()
    logging.info("Test complete.")

if __name__ == "__main__":
    main() 