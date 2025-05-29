"""
Fixed GB28181 XML message formatting module.
This module handles formatting of messages according to the GB28181 standard.
"""

def format_catalog_response(device_id, channels):
    """Format a catalog response XML according to GB28181 standard"""
    from datetime import datetime
    import os
    now = datetime.now()
    items = []
    
    # Process all channels
    if isinstance(channels, dict):
        for channel_id, channel_info in channels.items():
            items.append(format_device_item(channel_id, channel_info))
    
    # Build the XML response
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