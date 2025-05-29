"""
GB28181 XML message formatting module.
This module handles formatting of messages according to the GB28181 standard.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import uuid
from datetime import datetime, timedelta
import re
from logger import log
import os

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def generate_xml_header(cmd_type, sn=None, device_id=None):
    """Generate standard GB28181 XML message header"""
    if sn is None:
        sn = str(int(time.time()))
    
    root = ET.Element("Message")
    
    # Create CmdType element
    cmd_type_elem = ET.SubElement(root, "CmdType")
    cmd_type_elem.text = cmd_type
    
    # Create SN (serial number) element
    sn_elem = ET.SubElement(root, "SN")
    sn_elem.text = sn
    
    # Create DeviceID if provided
    if device_id:
        device_id_elem = ET.SubElement(root, "DeviceID")
        device_id_elem.text = device_id
    
    return root

def format_catalog_response(device_id, channels):
    """Format a catalog response XML according to GB28181 standard"""
    now = datetime.now()
    items = []
    
    # Check if channels is a list of strings (file paths) or a dictionary
    if isinstance(channels, list):
        for i, item in enumerate(channels):
            if isinstance(item, str):
                # It's a file path, create channel_info
                channel_id = f"{device_id}{i+1:03d}"
                file_name = os.path.basename(item)
                
                # Create a simple channel info dictionary
                channel_info = {
                    'name': file_name,
                    'manufacturer': 'GB28181-Restreamer',
                    'model': 'Camera',
                    'owner': 'gb28181-restreamer',
                    'civil_code': '123456',
                    'block': '123456',
                    'address': f'Video-{i+1}',
                    'parental': '0',
                    'parent_id': device_id,
                    'safety_way': '0',
                    'register_way': '1',
                    'secrecy': '0',
                    'status': 'ON'
                }
                items.append(format_device_item(channel_id, channel_info))
            elif isinstance(item, dict):
                # It's already a dictionary with channel info
                channel_id = item.get('channel_id', f"{device_id}{i+1:03d}")
                items.append(format_device_item(channel_id, item))
    elif isinstance(channels, dict):
        # Original code for dictionary type
        for channel_id, channel_info in channels.items():
            # Format each device item according to GB/T 28181 standard
            items.append(format_device_item(channel_id, channel_info))
    
    # Properly format XML using the GB28181 standard
    xml_template = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{int(now.timestamp())}</SN>
  <DeviceID>{device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>{len(channels)}</SumNum>
  <DeviceList Num="{len(channels)}">
{"".join(items)}
  </DeviceList>
</Response>
"""
    return xml_template

def format_device_item(channel_id, channel_info):
    """Format a device item for catalog response"""
    # Ensure values are strings to avoid issues with None values
    name = str(channel_info.get('name', 'Channel'))
    manufacturer = str(channel_info.get('manufacturer', 'GB28181-Restreamer'))
    model = str(channel_info.get('model', 'Camera'))
    owner = str(channel_info.get('owner', 'gb28181-restreamer'))
    civil_code = str(channel_info.get('civil_code', '123456'))
    block = str(channel_info.get('block', '123456'))
    address = str(channel_info.get('address', 'Local'))
    parental = str(channel_info.get('parental', '0'))
    parent_id = str(channel_info.get('parent_id', '34020000002000000001'))
    safety_way = str(channel_info.get('safety_way', '0'))
    register_way = str(channel_info.get('register_way', '1'))
    secrecy = str(channel_info.get('secrecy', '0'))
    status = str(channel_info.get('status', 'ON'))
    
    # Return properly formatted XML with all required fields
    return f"""    <Item>
      <DeviceID>{channel_id}</DeviceID>
      <Name>{name}</Name>
      <Manufacturer>{manufacturer}</Manufacturer>
      <Model>{model}</Model>
      <Owner>{owner}</Owner>
      <CivilCode>{civil_code}</CivilCode>
      <Block>{block}</Block>
      <Address>{address}</Address>
      <Parental>{parental}</Parental>
      <ParentID>{parent_id}</ParentID>
      <SafetyWay>{safety_way}</SafetyWay>
      <RegisterWay>{register_way}</RegisterWay>
      <Secrecy>{secrecy}</Secrecy>
      <Status>{status}</Status>
    </Item>
"""

def format_device_info_response(device_info):
    """Format a device info response XML according to GB28181 standard"""
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <CmdType>DeviceInfo</CmdType>
  <SN>{int(datetime.now().timestamp())}</SN>
  <DeviceID>{device_info['device_id']}</DeviceID>
  <Result>OK</Result>
  <DeviceName>{device_info['device_name']}</DeviceName>
  <Manufacturer>{device_info.get('manufacturer', 'GB28181-Restreamer')}</Manufacturer>
  <Model>{device_info.get('model', 'Restreamer')}</Model>
  <Firmware>{device_info.get('firmware', '1.0')}</Firmware>
  <MaxCamera>{device_info.get('max_camera', '1')}</MaxCamera>
  <MaxAlarm>{device_info.get('max_alarm', '0')}</MaxAlarm>
</Response>
"""
    return xml_template

def format_device_status_response(device_id, status_info):
    """Format a device status response XML according to GB28181 standard"""
    # Build the current date and time in the required format
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <CmdType>DeviceStatus</CmdType>
  <SN>{int(now.timestamp())}</SN>
  <DeviceID>{device_id}</DeviceID>
  <Status>{status_info.get('status', 'OK')}</Status>
  <Online>{status_info.get('online', 'ONLINE')}</Online>
  <StatusTime>
    <Date>{date_str}</Date>
    <Time>{time_str}</Time>
  </StatusTime>
  <Result>OK</Result>
</Response>
"""
    return xml_template

def format_keepalive_response(device_id):
    """Format a keepalive response XML according to GB28181 standard"""
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <CmdType>Keepalive</CmdType>
  <SN>{int(datetime.now().timestamp())}</SN>
  <DeviceID>{device_id}</DeviceID>
  <Status>OK</Status>
  <Result>OK</Result>
</Response>
"""
    return xml_template

def format_media_status_response(device_id, stream_info):
    """Format a media status response XML according to GB28181 standard"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <CmdType>MediaStatus</CmdType>
  <SN>{int(now.timestamp())}</SN>
  <DeviceID>{device_id}</DeviceID>
  <NotifyType>121</NotifyType>
  <Status>{stream_info.get('status', 'OK')}</Status>
  <StatusTime>
    <Date>{date_str}</Date>
    <Time>{time_str}</Time>
  </StatusTime>
  <Result>OK</Result>
</Response>
"""
    return xml_template

def format_recordinfo_response(device_id, records, sn=None):
    """Format a RecordInfo response XML according to GB28181 standard"""
    if sn is None:
        sn = str(int(datetime.now().timestamp()))
        
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <CmdType>RecordInfo</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{device_id}</DeviceID>
  <Name>GB28181-Restreamer</Name>
  <SumNum>{len(records)}</SumNum>
  <RecordList>
    {"".join([format_record_item(record) for record in records])}
  </RecordList>
</Response>
"""
    return xml_template

def format_record_item(record):
    """Format a single record item for RecordInfo response"""
    # Get the recording timestamp
    if isinstance(record.get('date_time'), datetime):
        dt = record['date_time']
    else:
        try:
            dt = datetime.fromtimestamp(record['timestamp'])
        except (TypeError, ValueError):
            dt = datetime.now()
            
    # Format the start/end times
    start_time = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = (dt + timedelta(seconds=record.get('duration', 3600))).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return f"""    <Item>
      <DeviceID>{record.get('device_id', '')}</DeviceID>
      <Name>{record.get('filename', '')}</Name>
      <FilePath>{record.get('path', '')}</FilePath>
      <Address>{record.get('address', 'Local Recording')}</Address>
      <StartTime>{start_time}</StartTime>
      <EndTime>{end_time}</EndTime>
      <Secrecy>{record.get('secrecy', '0')}</Secrecy>
      <Type>{record.get('type', 'all')}</Type>
      <FileSize>{record.get('size', 0)}</FileSize>
    </Item>
"""

def parse_xml_message(message_text):
    """Parse a GB28181 XML message
    
    Args:
        message_text (str): XML message text
        
    Returns:
        dict: Parsed message content or None if parsing failed
    """
    try:
        # Extract XML content from SIP message
        xml_match = re.search(r'<\?xml.*<\/Response>', message_text, re.DOTALL)
        if not xml_match:
            log.warning("[XML] Could not extract XML from message")
            return None
            
        xml_content = xml_match.group(0)
        root = ET.fromstring(xml_content)
        
        # Parse common fields
        cmd_type = root.find('CmdType').text if root.find('CmdType') is not None else ""
        device_id = root.find('DeviceID').text if root.find('DeviceID') is not None else ""
        sn = root.find('SN').text if root.find('SN') is not None else ""
        
        # Create base result
        result = {
            'cmd_type': cmd_type,
            'device_id': device_id,
            'sn': sn
        }
        
        # Process based on command type
        if cmd_type == "Catalog":
            parse_catalog_query(result, root)
        elif cmd_type == "DeviceInfo":
            parse_device_info_query(result, root)
        elif cmd_type == "DeviceStatus":
            parse_device_status_query(result, root)
        elif cmd_type == "Keepalive":
            parse_keepalive(result, root)
        elif cmd_type == "RecordInfo":
            parse_record_info_query(result, root)
        
        return result
    except Exception as e:
        log.error(f"[XML] Error parsing XML message: {e}")
        return None

def parse_catalog_query(result, root):
    """Parse a catalog query"""
    # No special fields for catalog query
    return result

def parse_device_info_query(result, root):
    """Parse a device info query"""
    # No special fields for device info query
    return result

def parse_device_status_query(result, root):
    """Parse a device status query"""
    # No special fields for device status query
    return result

def parse_keepalive(result, root):
    """Parse a keepalive message"""
    # No special fields for keepalive
    return result

def parse_record_info_query(result, root):
    """Parse a record info query"""
    try:
        # Extract start/end times if present
        start_time_elem = root.find('.//StartTime')
        end_time_elem = root.find('.//EndTime')
        
        if start_time_elem is not None:
            result['start_time'] = start_time_elem.text
        
        if end_time_elem is not None:
            result['end_time'] = end_time_elem.text
    except Exception as e:
        log.error(f"[XML] Error parsing record info query: {e}")
        
    return result

def parse_recordinfo_query(message_text):
    """Parse a RecordInfo query from raw message text
    
    Args:
        message_text (str): Raw message text containing XML
        
    Returns:
        dict: Parsed query parameters or None if parsing failed
    """
    try:
        # Extract XML content from SIP message
        xml_match = re.search(r'<\?xml.*<\/Query>', message_text, re.DOTALL)
        if not xml_match:
            log.warning("[XML] Could not extract RecordInfo XML from message")
            return None

        xml_content = xml_match.group(0)
        
        # Fix potential XML issues (some implementations send malformed XML)
        xml_content = xml_content.replace('xmlns="http://www.chinamobile.com/wvmp"', '')
        
        root = ET.fromstring(xml_content)
        
        # Check if this is a RecordInfo query
        cmd_type_elem = root.find('CmdType')
        if cmd_type_elem is None or cmd_type_elem.text != 'RecordInfo':
            log.warning("[XML] Not a RecordInfo query")
            return None
        
        # Extract basic info
        device_id = root.find('DeviceID').text if root.find('DeviceID') is not None else ""
        sn = root.find('SN').text if root.find('SN') is not None else ""
        
        # Extract time range
        start_time = None
        end_time = None
        
        start_time_elem = root.find('.//StartTime')
        end_time_elem = root.find('.//EndTime')
        
        if start_time_elem is not None:
            start_time = start_time_elem.text
        
        if end_time_elem is not None:
            end_time = end_time_elem.text
        
        # Create result
        return {
            'cmd_type': 'RecordInfo',
            'device_id': device_id,
            'sn': sn,
            'start_time': start_time,
            'end_time': end_time
        }
    except Exception as e:
        log.error(f"[XML] Error parsing RecordInfo query: {e}")
        return None 