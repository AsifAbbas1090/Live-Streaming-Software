import platform
import os
import sys

def get_system_architecture():
    """
    Get the system architecture in a standardized format.
    Returns: tuple (arch, is_64bit)
    """
    machine = platform.machine().lower()
    is_64bit = sys.maxsize > 2**32
    
    # Map common architecture names to standardized ones
    arch_map = {
        'x86_64': 'amd64',
        'amd64': 'amd64',
        'aarch64': 'arm64',
        'arm64': 'arm64',
        'armv8l': 'arm64',
        'armv7l': 'arm',
        'armv6l': 'arm'
    }
    
    normalized_arch = arch_map.get(machine, machine)
    return normalized_arch, is_64bit

def is_arm_architecture():
    """
    Check if the system is running on ARM architecture.
    Returns: bool
    """
    arch, _ = get_system_architecture()
    return arch in ['arm64', 'arm']

def get_go_arch():
    """
    Get the appropriate GOARCH value for the current system.
    Returns: str
    """
    arch, _ = get_system_architecture()
    if arch in ['arm64', 'arm']:
        return 'arm64'
    return 'amd64' 