#!/usr/bin/env python3
# src/stream_config.py

import os
import json
import copy
from logger import log

class StreamConfig:
    """
    Handles stream configuration and presets for GB28181 video streams
    """
    def __init__(self, config_path=None):
        self.default_preset = {
            "encoder": "x264enc",
            "width": 704,
            "height": 576,
            "framerate": 25,
            "bitrate": 1024,
            "keyframe_interval": 50,
            "speed_preset": "medium",
            "profile": "baseline",
            "tune": "zerolatency"
        }
        
        # Default GB28181 format mapping
        self.gb28181_formats = {
            "1:1": {"width": 176, "height": 144},  # QCIF
            "1:2": {"width": 352, "height": 288},  # CIF
            "1:3": {"width": 704, "height": 576},  # 4CIF
            "1:4": {"width": 720, "height": 576}   # D1
        }
        
        self.presets = {"default": self.default_preset}
        
        # Load presets from config file if available
        if not config_path:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
            config_path = os.path.join(config_dir, "streaming_presets.json")
        
        self.load_config(config_path)
        
    def load_config(self, config_path):
        """
        Load configuration from a JSON file
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "presets" in config:
                    self.presets.update(config["presets"])
                    log.info(f"[CONFIG] Loaded {len(config['presets'])} stream presets")
                
                if "gb28181_format_profiles" in config:
                    self.gb28181_formats.update(config["gb28181_format_profiles"])
                    log.info(f"[CONFIG] Loaded {len(config['gb28181_format_profiles'])} GB28181 format profiles")
            else:
                log.warning(f"[CONFIG] Stream config file not found: {config_path}")
        except Exception as e:
            log.error(f"[CONFIG] Error loading stream config: {e}")
    
    def get_preset(self, preset_name="default"):
        """
        Get a preset by name
        """
        if preset_name in self.presets:
            return copy.deepcopy(self.presets[preset_name])
        else:
            log.warning(f"[CONFIG] Preset '{preset_name}' not found, using default")
            return copy.deepcopy(self.default_preset)
    
    def get_format_params(self, format_id):
        """
        Get format parameters for a GB28181 format ID
        Format IDs are typically in the form of "codec_id:resolution_id"
        """
        if format_id in self.gb28181_formats:
            return copy.deepcopy(self.gb28181_formats[format_id])
        else:
            log.warning(f"[CONFIG] Format '{format_id}' not found, using 4CIF")
            return copy.deepcopy(self.gb28181_formats["1:3"])  # Default to 4CIF
    
    def create_encoder_params(self, preset_name=None, format_id=None, **kwargs):
        """
        Create encoder parameters based on preset and/or format ID
        Additional parameters can be provided as kwargs to override preset values
        """
        # Start with default preset
        params = copy.deepcopy(self.default_preset)
        
        # Apply preset if specified
        if preset_name and preset_name in self.presets:
            params.update(self.presets[preset_name])
        
        # Apply format if specified
        if format_id and format_id in self.gb28181_formats:
            format_params = self.gb28181_formats[format_id]
            
            # If format refers to another preset, load that preset first
            if "preset" in format_params and format_params["preset"] in self.presets:
                base_preset = self.presets[format_params["preset"]]
                params.update(base_preset)
            
            # Apply format parameters (overrides preset)
            params.update({k: v for k, v in format_params.items() if k != "preset"})
        
        # Apply any additional parameters
        params.update(kwargs)
        
        return params
    
    def list_presets(self):
        """
        List all available presets
        """
        return list(self.presets.keys())
    
    def list_formats(self):
        """
        List all available GB28181 formats
        """
        return list(self.gb28181_formats.keys())


# Helper functions
def get_stream_config():
    """
    Get a stream configuration instance (singleton)
    """
    if not hasattr(get_stream_config, "instance"):
        get_stream_config.instance = StreamConfig()
    return get_stream_config.instance


def create_encoder_params(preset=None, format_id=None, **kwargs):
    """
    Create encoder parameters using the stream configuration
    """
    config = get_stream_config()
    return config.create_encoder_params(preset, format_id, **kwargs)


# Simple test if run directly
if __name__ == "__main__":
    config = StreamConfig()
    print("Available presets:", config.list_presets())
    print("Available formats:", config.list_formats())
    
    # Test creating parameters for different scenarios
    print("\nDefault preset:", config.get_preset())
    print("\nHigh quality preset:", config.get_preset("high"))
    print("\nGB28181 4CIF format:", config.get_format_params("1:3"))
    print("\nCustom parameters:", config.create_encoder_params(
        preset="medium", 
        width=800,
        height=600,
        bitrate=1500
    ))
    print("\nFormat-based parameters:", config.create_encoder_params(
        format_id="1:3",
        bitrate=1800
    )) 