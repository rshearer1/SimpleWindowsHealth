"""
Hardware Scanner Module for Windows Health Checker Pro
Collects comprehensive hardware information via WMI, Registry, and ctypes.

Optimizations:
- Static data (BIOS, motherboard) cached for 5 minutes
- Timing instrumentation for profiling
- Separate functions for static vs dynamic data
"""

import subprocess
import re
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import winreg
from datetime import datetime

# Performance utilities - define fallbacks first, then override if import succeeds
def timed(operation_name: Optional[str] = None):
    def decorator(func):
        return func
    return decorator

def cached(key, ttl_seconds=300):
    def decorator(func):
        return func
    return decorator

class TimingContext:
    def __init__(self, name): pass
    def __enter__(self): return self
    def __exit__(self, *args): return False

try:
    from perf_utils import timed, cached, data_cache, TimingContext  # type: ignore
    PERF_UTILS_AVAILABLE = True
except ImportError:
    PERF_UTILS_AVAILABLE = False


class HealthStatus(Enum):
    """Health status levels for hardware components"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class CPUInfo:
    """CPU information"""
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    cores: int = 0
    threads: int = 0
    base_clock_mhz: int = 0
    max_clock_mhz: int = 0
    current_clock_mhz: int = 0
    architecture: str = "Unknown"
    socket: str = "Unknown"
    l2_cache_kb: int = 0
    l3_cache_kb: int = 0
    utilization_percent: float = 0.0
    temperature_c: Optional[float] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    device_id: str = ""
    processor_id: str = ""
    revision: str = ""
    stepping: str = ""
    family: str = ""
    voltage_caps: str = ""
    external_clock_mhz: int = 0
    l1_cache_kb: int = 0
    virtualization_enabled: bool = False
    address_width: int = 0
    data_width: int = 0
    status_info: str = ""
    cpu_status: str = ""
    power_management: List[str] = field(default_factory=list)
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GPUInfo:
    """GPU information"""
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    driver_version: str = "Unknown"
    driver_date: str = "Unknown"
    vram_mb: int = 0
    resolution: str = "Unknown"
    refresh_rate: int = 0
    temperature_c: Optional[float] = None
    utilization_percent: Optional[float] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    device_id: str = ""
    pnp_device_id: str = ""
    video_processor: str = ""
    video_architecture: str = ""
    video_memory_type: str = ""
    adapter_dac_type: str = ""
    min_refresh_rate: int = 0
    max_refresh_rate: int = 0
    bits_per_pixel: int = 0
    color_planes: int = 0
    inf_filename: str = ""
    inf_section: str = ""
    installed_display_drivers: str = ""
    monochrome: bool = False
    video_mode_description: str = ""
    availability: str = ""
    config_error_code: int = 0
    caption: str = ""
    description: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAMSlot:
    """Individual RAM slot information"""
    slot: str = "Unknown"
    manufacturer: str = "Unknown"
    part_number: str = "Unknown"
    capacity_gb: float = 0.0
    speed_mhz: int = 0
    form_factor: str = "Unknown"
    memory_type: str = "Unknown"
    # Extended properties
    serial_number: str = ""
    device_locator: str = ""
    configured_clock_speed: int = 0
    configured_voltage: float = 0.0
    min_voltage: float = 0.0
    max_voltage: float = 0.0
    data_width: int = 0
    total_width: int = 0
    type_detail: str = ""
    asset_tag: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAMInfo:
    """Overall RAM information"""
    total_gb: float = 0.0
    used_gb: float = 0.0
    available_gb: float = 0.0
    utilization_percent: float = 0.0
    slots_used: int = 0
    slots_total: int = 0
    slots: List[RAMSlot] = field(default_factory=list)
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    total_physical_memory: int = 0
    total_virtual_memory: int = 0
    available_virtual_memory: int = 0
    page_file_total: int = 0
    page_file_free: int = 0
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MotherboardInfo:
    """Motherboard and BIOS information"""
    manufacturer: str = "Unknown"
    product: str = "Unknown"
    version: str = "Unknown"
    serial_number: str = "Unknown"
    bios_vendor: str = "Unknown"
    bios_version: str = "Unknown"
    bios_date: str = "Unknown"
    bios_mode: str = "Unknown"  # UEFI or Legacy
    secure_boot: bool = False
    tpm_present: bool = False
    tpm_version: str = "Unknown"
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended motherboard properties
    baseboard_status: str = ""
    baseboard_hosting_board: bool = False
    baseboard_hot_swappable: bool = False
    baseboard_removable: bool = False
    baseboard_replaceable: bool = False
    baseboard_config_options: List[str] = field(default_factory=list)
    # Extended BIOS properties
    bios_release_date: str = ""
    smbios_version: str = ""
    smbios_major: int = 0
    smbios_minor: int = 0
    bios_characteristics: List[str] = field(default_factory=list)
    embedded_controller_major: int = 0
    embedded_controller_minor: int = 0
    primary_bios: bool = False
    # System info
    system_manufacturer: str = ""
    system_model: str = ""
    system_type: str = ""
    system_family: str = ""
    system_sku: str = ""
    # Chassis info
    chassis_manufacturer: str = ""
    chassis_type: str = ""
    chassis_serial: str = ""
    chassis_asset_tag: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageDrive:
    """Physical storage drive information"""
    model: str = "Unknown"
    serial_number: str = "Unknown"
    interface_type: str = "Unknown"
    media_type: str = "Unknown"  # SSD, HDD, etc.
    capacity_gb: float = 0.0
    firmware_version: str = "Unknown"
    smart_status: str = "Unknown"
    temperature_c: Optional[float] = None
    power_on_hours: Optional[int] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    device_id: str = ""
    pnp_device_id: str = ""
    caption: str = ""
    description: str = ""
    index: int = 0
    partitions: int = 0
    bytes_per_sector: int = 0
    sectors_per_track: int = 0
    total_heads: int = 0
    total_cylinders: int = 0
    total_sectors: int = 0
    total_tracks: int = 0
    compression_method: str = ""
    manufacturer: str = ""
    scsi_bus: int = 0
    scsi_port: int = 0
    scsi_lun: int = 0
    scsi_target_id: int = 0
    signature: str = ""
    # SMART attributes (if available)
    smart_attributes: Dict[str, Any] = field(default_factory=dict)
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageVolume:
    """Logical volume/partition information"""
    drive_letter: str = ""
    label: str = ""
    file_system: str = ""
    capacity_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    utilization_percent: float = 0.0
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    volume_serial: str = ""
    description: str = ""
    drive_type: str = ""
    compressed: bool = False
    supports_quotas: bool = False
    supports_disk_quotas: bool = False
    quotas_disabled: bool = False
    quotas_incomplete: bool = False
    quotas_rebuilding: bool = False
    block_size: int = 0
    maximum_component_length: int = 0
    supports_file_based_compression: bool = False
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageInfo:
    """Overall storage information"""
    physical_drives: List[StorageDrive] = field(default_factory=list)
    volumes: List[StorageVolume] = field(default_factory=list)
    total_capacity_gb: float = 0.0
    total_used_gb: float = 0.0


@dataclass
class NetworkAdapter:
    """Network adapter information"""
    name: str = "Unknown"
    description: str = "Unknown"
    adapter_type: str = "Unknown"  # Ethernet, Wi-Fi, etc.
    mac_address: str = "Unknown"
    speed_mbps: int = 0
    ipv4_address: str = "Not assigned"
    ipv6_address: str = "Not assigned"
    subnet_mask: str = ""
    gateway: str = ""
    dns_servers: List[str] = field(default_factory=list)
    link_state: str = "Unknown"  # Up, Down, Disconnected
    dhcp_enabled: bool = False
    status: HealthStatus = HealthStatus.UNKNOWN
    # Extended properties
    device_id: str = ""
    pnp_device_id: str = ""
    guid: str = ""
    index: int = 0
    interface_index: int = 0
    net_connection_id: str = ""
    manufacturer: str = ""
    service_name: str = ""
    time_of_last_reset: str = ""
    permanent_address: str = ""
    physical_adapter: bool = False
    # Connection info
    dhcp_server: str = ""
    dhcp_lease_obtained: str = ""
    dhcp_lease_expires: str = ""
    wins_primary: str = ""
    wins_secondary: str = ""
    # Statistics
    bytes_received: int = 0
    bytes_sent: int = 0
    packets_received: int = 0
    packets_sent: int = 0
    errors_received: int = 0
    errors_sent: int = 0
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorInfo:
    """Temperature and fan sensor information"""
    name: str = "Unknown"
    sensor_type: str = "Unknown"  # Temperature, Fan, Voltage
    value: float = 0.0
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioDevice:
    """Audio device information"""
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    device_id: str = ""
    pnp_device_id: str = ""
    status: str = "Unknown"
    driver_version: str = ""
    driver_date: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class USBDevice:
    """USB device information"""
    name: str = "Unknown"
    device_id: str = ""
    pnp_device_id: str = ""
    description: str = ""
    manufacturer: str = ""
    status: str = "Unknown"
    service: str = ""
    class_guid: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class USBController:
    """USB controller information"""
    name: str = "Unknown"
    manufacturer: str = ""
    device_id: str = ""
    pnp_device_id: str = ""
    protocol_supported: str = ""
    status: str = "Unknown"
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorInfo:
    """Monitor information"""
    name: str = "Unknown"
    manufacturer: str = ""
    device_id: str = ""
    pnp_device_id: str = ""
    screen_width: int = 0
    screen_height: int = 0
    pixels_per_x_logical_inch: int = 0
    pixels_per_y_logical_inch: int = 0
    monitor_type: str = ""
    availability: str = ""
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatteryInfo:
    """Battery information (for laptops)"""
    name: str = "Unknown"
    device_id: str = ""
    status: str = "Unknown"
    battery_status: int = 0  # 1=Discharging, 2=AC, etc.
    chemistry: str = ""
    design_capacity: int = 0
    full_charge_capacity: int = 0
    estimated_charge_remaining: int = 0
    estimated_run_time: int = 0
    expected_life: int = 0
    time_on_battery: int = 0
    time_to_full_charge: int = 0
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PrinterInfo:
    """Printer information"""
    name: str = "Unknown"
    device_id: str = ""
    driver_name: str = ""
    port_name: str = ""
    printer_status: str = ""
    print_processor: str = ""
    shared: bool = False
    share_name: str = ""
    local: bool = False
    network: bool = False
    default: bool = False
    raw_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HardwareSnapshot:
    """Complete hardware snapshot"""
    timestamp: str = ""
    cpu: CPUInfo = field(default_factory=CPUInfo)
    gpus: List[GPUInfo] = field(default_factory=list)
    ram: RAMInfo = field(default_factory=RAMInfo)
    motherboard: MotherboardInfo = field(default_factory=MotherboardInfo)
    storage: StorageInfo = field(default_factory=StorageInfo)
    network_adapters: List[NetworkAdapter] = field(default_factory=list)
    sensors: List[SensorInfo] = field(default_factory=list)
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    # Extended hardware collections
    audio_devices: List[AudioDevice] = field(default_factory=list)
    usb_devices: List[USBDevice] = field(default_factory=list)
    usb_controllers: List[USBController] = field(default_factory=list)
    monitors: List[MonitorInfo] = field(default_factory=list)
    batteries: List[BatteryInfo] = field(default_factory=list)
    printers: List[PrinterInfo] = field(default_factory=list)


def _run_wmic(wmic_class: str, properties: List[str], timeout: int = 10) -> List[Dict[str, str]]:
    """Run WMIC command and parse output"""
    try:
        props = ",".join(properties)
        cmd = f'wmic {wmic_class} get {props} /format:csv'
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return []
        
        # First non-empty line is headers
        headers = [h.strip() for h in lines[0].split(',')]
        results = []
        
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split(',')
            if len(values) >= len(headers):
                # Handle case where Node is first column in CSV
                if headers[0] == 'Node':
                    row = {headers[i]: values[i].strip() for i in range(1, len(headers))}
                else:
                    row = {headers[i]: values[i].strip() for i in range(len(headers))}
                results.append(row)
        
        return results
    except Exception:
        return []


def _run_wmic_list(wmic_class: str, properties: List[str], timeout: int = 10) -> List[Dict[str, str]]:
    """Run WMIC command with /format:list and parse output.
    
    This is more reliable than CSV format when fields contain commas.
    """
    try:
        props = ",".join(properties)
        cmd = f'wmic {wmic_class} get {props} /format:list'
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Parse list format: Key=Value, records separated by double blank lines
        results = []
        current_record: Dict[str, str] = {}
        blank_count = 0
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                blank_count += 1
                # Two or more blank lines = definite record separator
                if blank_count >= 2 and current_record:
                    results.append(current_record)
                    current_record = {}
            elif '=' in line:
                blank_count = 0
                key, _, value = line.partition('=')
                current_record[key.strip()] = value.strip()
        
        # Don't forget last record
        if current_record:
            results.append(current_record)
        
        return results
    except Exception:
        return []


def _run_powershell(command: str, timeout: int = 15) -> str:
    """Run PowerShell command and return output"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_registry_value(key_path: str, value_name: str, hive=winreg.HKEY_LOCAL_MACHINE) -> Optional[str]:
    """Read a value from Windows Registry"""
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
    except Exception:
        return None


def _parse_size_to_gb(size_bytes: str) -> float:
    """Convert bytes string to GB"""
    try:
        return round(int(size_bytes) / (1024 ** 3), 2)
    except (ValueError, TypeError):
        return 0.0


def _parse_size_to_mb(size_bytes: str) -> int:
    """Convert bytes string to MB"""
    try:
        return int(int(size_bytes) / (1024 ** 2))
    except (ValueError, TypeError):
        return 0


@timed("collect_cpu_info")
def collect_cpu_info() -> CPUInfo:
    """Collect comprehensive CPU information"""
    cpu = CPUInfo()
    
    try:
        # Get CPU details from WMI - only use valid Win32_Processor properties
        # Note: L1InstructionCacheSize, L1DataCacheSize, VirtualizationFirmwareEnabled don't exist
        results = _run_wmic(
            "cpu",
            ["Name", "Manufacturer", "NumberOfCores", "NumberOfLogicalProcessors",
             "MaxClockSpeed", "CurrentClockSpeed", "Architecture", "SocketDesignation",
             "L2CacheSize", "L3CacheSize", "LoadPercentage", "DeviceID", "ProcessorId",
             "Revision", "Stepping", "Family", "VoltageCaps", "ExtClock",
             "AddressWidth", "DataWidth", "Status", "CpuStatus", "PowerManagementSupported",
             "Caption", "Description", "AssetTag", "PartNumber", "SerialNumber",
             "SecondLevelAddressTranslationExtensions", "VMMonitorModeExtensions"]
        )
        
        if results:
            r = results[0]
            # Store all raw properties
            cpu.raw_properties = r.copy()
            
            # Basic properties
            cpu.name = r.get("Name", "Unknown").strip()
            cpu.manufacturer = r.get("Manufacturer", "Unknown")
            cpu.cores = int(r.get("NumberOfCores", 0) or 0)
            cpu.threads = int(r.get("NumberOfLogicalProcessors", 0) or 0)
            cpu.max_clock_mhz = int(r.get("MaxClockSpeed", 0) or 0)
            cpu.current_clock_mhz = int(r.get("CurrentClockSpeed", 0) or 0)
            cpu.base_clock_mhz = cpu.max_clock_mhz  # Base often equals max in WMI
            cpu.socket = r.get("SocketDesignation", "Unknown")
            cpu.l2_cache_kb = int(r.get("L2CacheSize", 0) or 0)
            cpu.l3_cache_kb = int(r.get("L3CacheSize", 0) or 0)
            cpu.utilization_percent = float(r.get("LoadPercentage", 0) or 0)
            
            # Extended properties
            cpu.device_id = r.get("DeviceID", "")
            cpu.processor_id = r.get("ProcessorId", "")
            cpu.revision = r.get("Revision", "")
            cpu.stepping = r.get("Stepping", "")
            cpu.family = r.get("Family", "")
            cpu.voltage_caps = r.get("VoltageCaps", "")
            cpu.external_clock_mhz = int(r.get("ExtClock", 0) or 0)
            
            # Check virtualization via VMMonitorModeExtensions instead
            cpu.virtualization_enabled = r.get("VMMonitorModeExtensions", "").upper() == "TRUE"
            cpu.address_width = int(r.get("AddressWidth", 0) or 0)
            cpu.data_width = int(r.get("DataWidth", 0) or 0)
            cpu.status_info = r.get("Status", "")
            cpu.cpu_status = r.get("CpuStatus", "")
            
            # Architecture mapping
            arch_map = {"0": "x86", "5": "ARM", "9": "x64", "12": "ARM64"}
            cpu.architecture = arch_map.get(r.get("Architecture", ""), "Unknown")
        
        # Get L1 cache from Win32_CacheMemory (not available in Win32_Processor)
        try:
            cache_results = _run_wmic(
                "path Win32_CacheMemory",
                ["Purpose", "InstalledSize", "Level"]
            )
            l1_total = 0
            for cache in cache_results:
                purpose = cache.get("Purpose", "")
                if "L1" in purpose:
                    l1_total += int(cache.get("InstalledSize", 0) or 0)
            cpu.l1_cache_kb = l1_total
        except Exception:
            pass
        
        # Determine health status
        if cpu.utilization_percent > 90:
            cpu.status = HealthStatus.WARNING
        elif cpu.name != "Unknown":
            cpu.status = HealthStatus.HEALTHY
            
    except Exception:
        pass
    
    return cpu


@timed("collect_gpu_info")
def collect_gpu_info() -> List[GPUInfo]:
    """Collect comprehensive GPU information"""
    gpus = []
    
    try:
        # Use list format because InstalledDisplayDrivers can contain commas
        # which breaks CSV parsing
        results = _run_wmic_list(
            "path win32_videocontroller",
            ["Name", "AdapterCompatibility", "DriverVersion", "DriverDate",
             "AdapterRAM", "CurrentHorizontalResolution", "CurrentVerticalResolution",
             "CurrentRefreshRate", "Status", "DeviceID", "PNPDeviceID",
             "VideoProcessor", "VideoArchitecture", "VideoMemoryType",
             "AdapterDACType", "MinRefreshRate", "MaxRefreshRate",
             "CurrentBitsPerPixel", "CurrentNumberOfColors",
             "InfFilename", "InfSection", "InstalledDisplayDrivers",
             "Monochrome", "VideoModeDescription", "Availability",
             "ConfigManagerErrorCode", "Caption", "Description",
             "AcceleratorCapabilities", "SystemName", "SpecificationVersion"]
        )
        
        for r in results:
            gpu = GPUInfo()
            # Store all raw properties
            gpu.raw_properties = r.copy()
            
            # Basic properties
            gpu.name = r.get("Name", "Unknown")
            gpu.manufacturer = r.get("AdapterCompatibility", "Unknown")
            gpu.driver_version = r.get("DriverVersion", "Unknown")
            
            # Parse driver date (format: YYYYMMDDHHMMSS.MMMMMM+ZZZ)
            driver_date_raw = r.get("DriverDate", "")
            if driver_date_raw and len(driver_date_raw) >= 8:
                try:
                    dt = datetime.strptime(driver_date_raw[:8], "%Y%m%d")
                    gpu.driver_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    gpu.driver_date = driver_date_raw[:10]
            
            # VRAM
            vram_raw = r.get("AdapterRAM", "0")
            gpu.vram_mb = _parse_size_to_mb(vram_raw)
            
            # Resolution
            h_res = r.get("CurrentHorizontalResolution", "")
            v_res = r.get("CurrentVerticalResolution", "")
            if h_res and v_res:
                gpu.resolution = f"{h_res} x {v_res}"
            
            gpu.refresh_rate = int(r.get("CurrentRefreshRate", 0) or 0)
            
            # Extended properties
            gpu.device_id = r.get("DeviceID", "")
            gpu.pnp_device_id = r.get("PNPDeviceID", "")
            gpu.video_processor = r.get("VideoProcessor", "")
            gpu.video_architecture = r.get("VideoArchitecture", "")
            gpu.video_memory_type = r.get("VideoMemoryType", "")
            gpu.adapter_dac_type = r.get("AdapterDACType", "")
            gpu.min_refresh_rate = int(r.get("MinRefreshRate", 0) or 0)
            gpu.max_refresh_rate = int(r.get("MaxRefreshRate", 0) or 0)
            gpu.bits_per_pixel = int(r.get("CurrentBitsPerPixel", 0) or 0)
            gpu.color_planes = 0  # ColorPlanes is not a valid Win32_VideoController property
            gpu.inf_filename = r.get("InfFilename", "")
            gpu.inf_section = r.get("InfSection", "")
            gpu.installed_display_drivers = r.get("InstalledDisplayDrivers", "")
            gpu.monochrome = r.get("Monochrome", "").lower() == "true"
            gpu.video_mode_description = r.get("VideoModeDescription", "")
            gpu.availability = r.get("Availability", "")
            gpu.config_error_code = int(r.get("ConfigManagerErrorCode", 0) or 0)
            gpu.caption = r.get("Caption", "")
            gpu.description = r.get("Description", "")
            
            # Status
            status_str = r.get("Status", "")
            if status_str.lower() == "ok":
                gpu.status = HealthStatus.HEALTHY
            elif status_str:
                gpu.status = HealthStatus.WARNING
            
            gpus.append(gpu)
            
    except Exception:
        pass
    
    return gpus if gpus else [GPUInfo()]


@timed("collect_ram_info")
def collect_ram_info() -> RAMInfo:
    """Collect comprehensive RAM information"""
    ram = RAMInfo()
    
    try:
        # Get overall memory status
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        
        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
        
        ram.total_gb = round(mem_status.ullTotalPhys / (1024 ** 3), 2)
        ram.available_gb = round(mem_status.ullAvailPhys / (1024 ** 3), 2)
        ram.used_gb = round(ram.total_gb - ram.available_gb, 2)
        ram.utilization_percent = mem_status.dwMemoryLoad
        
        # Extended memory stats
        ram.total_physical_memory = mem_status.ullTotalPhys
        ram.total_virtual_memory = mem_status.ullTotalVirtual
        ram.available_virtual_memory = mem_status.ullAvailVirtual
        ram.page_file_total = mem_status.ullTotalPageFile
        ram.page_file_free = mem_status.ullAvailPageFile
        
        # Get per-slot details with ALL properties
        results = _run_wmic(
            "memorychip",
            ["BankLabel", "Manufacturer", "PartNumber", "Capacity",
             "Speed", "FormFactor", "MemoryType", "SMBIOSMemoryType",
             "SerialNumber", "DeviceLocator", "ConfiguredClockSpeed",
             "ConfiguredVoltage", "MinVoltage", "MaxVoltage",
             "DataWidth", "TotalWidth", "TypeDetail", "Tag", "AssetTag"]
        )
        
        form_factor_map = {
            "0": "Unknown", "1": "Other", "2": "SIP", "3": "DIP", "4": "ZIP",
            "5": "SOJ", "6": "Proprietary", "7": "SIMM", "8": "DIMM", "9": "TSOP",
            "10": "PGA", "11": "RIMM", "12": "SODIMM", "13": "SRIMM", "14": "SMD",
            "15": "SSMP", "16": "QFP", "17": "TQFP", "18": "SOIC", "19": "LCC",
            "20": "PLCC", "21": "BGA", "22": "FPBGA", "23": "LGA"
        }
        
        memory_type_map = {
            "20": "DDR", "21": "DDR2", "22": "DDR2 FB-DIMM", "24": "DDR3",
            "26": "DDR4", "34": "DDR5"
        }
        
        for r in results:
            slot = RAMSlot()
            # Store all raw properties
            slot.raw_properties = r.copy()
            
            # Basic properties
            slot.slot = r.get("BankLabel", "Unknown")
            slot.manufacturer = r.get("Manufacturer", "Unknown").strip()
            slot.part_number = r.get("PartNumber", "Unknown").strip()
            slot.capacity_gb = _parse_size_to_gb(r.get("Capacity", "0"))
            slot.speed_mhz = int(r.get("Speed", 0) or 0)
            slot.form_factor = form_factor_map.get(r.get("FormFactor", "0"), "Unknown")
            
            # Try SMBIOSMemoryType first (more accurate for DDR4/DDR5)
            mem_type = r.get("SMBIOSMemoryType", "")
            if mem_type in memory_type_map:
                slot.memory_type = memory_type_map[mem_type]
            else:
                slot.memory_type = memory_type_map.get(r.get("MemoryType", ""), "Unknown")
            
            # Extended properties
            slot.serial_number = r.get("SerialNumber", "")
            slot.device_locator = r.get("DeviceLocator", "")
            slot.configured_clock_speed = int(r.get("ConfiguredClockSpeed", 0) or 0)
            try:
                slot.configured_voltage = float(r.get("ConfiguredVoltage", 0) or 0) / 1000  # mV to V
                slot.min_voltage = float(r.get("MinVoltage", 0) or 0) / 1000
                slot.max_voltage = float(r.get("MaxVoltage", 0) or 0) / 1000
            except (ValueError, TypeError):
                pass
            slot.data_width = int(r.get("DataWidth", 0) or 0)
            slot.total_width = int(r.get("TotalWidth", 0) or 0)
            slot.type_detail = r.get("TypeDetail", "")
            slot.asset_tag = r.get("AssetTag", "")
            
            ram.slots.append(slot)
        
        ram.slots_used = len([s for s in ram.slots if s.capacity_gb > 0])
        ram.slots_total = len(ram.slots) if ram.slots else ram.slots_used
        
        # Status based on utilization
        if ram.utilization_percent > 90:
            ram.status = HealthStatus.CRITICAL
        elif ram.utilization_percent > 75:
            ram.status = HealthStatus.WARNING
        else:
            ram.status = HealthStatus.HEALTHY
            
    except Exception:
        pass
    
    return ram


@timed("collect_motherboard_info")
@cached("hw_motherboard", ttl_seconds=300)  # Cache for 5 min - static data
def collect_motherboard_info() -> MotherboardInfo:
    """Collect comprehensive motherboard and BIOS information (cached - static data)"""
    mb = MotherboardInfo()
    
    try:
        # Motherboard info - get ALL properties
        results = _run_wmic(
            "baseboard",
            ["Manufacturer", "Product", "Version", "SerialNumber",
             "Status", "HostingBoard", "HotSwappable", "Removable", "Replaceable",
             "ConfigOptions", "Tag", "Model", "Name", "SKU", "PoweredOn"]
        )
        
        if results:
            r = results[0]
            mb.raw_properties["baseboard"] = r.copy()
            mb.manufacturer = r.get("Manufacturer", "Unknown")
            mb.product = r.get("Product", "Unknown")
            mb.version = r.get("Version", "")
            mb.serial_number = r.get("SerialNumber", "Unknown")
            mb.baseboard_status = r.get("Status", "")
            mb.baseboard_hosting_board = r.get("HostingBoard", "").lower() == "true"
            mb.baseboard_hot_swappable = r.get("HotSwappable", "").lower() == "true"
            mb.baseboard_removable = r.get("Removable", "").lower() == "true"
            mb.baseboard_replaceable = r.get("Replaceable", "").lower() == "true"
        
        # BIOS info - get ALL properties
        bios_results = _run_wmic(
            "bios",
            ["Manufacturer", "SMBIOSBIOSVersion", "ReleaseDate",
             "SMBIOSMajorVersion", "SMBIOSMinorVersion", "BIOSVersion",
             "EmbeddedControllerMajorVersion", "EmbeddedControllerMinorVersion",
             "PrimaryBIOS", "Name", "Caption", "Description", "SerialNumber",
             "SoftwareElementID", "Status", "Version", "CurrentLanguage",
             "InstallableLanguages"]
        )
        
        if bios_results:
            r = bios_results[0]
            mb.raw_properties["bios"] = r.copy()
            mb.bios_vendor = r.get("Manufacturer", "Unknown")
            mb.bios_version = r.get("SMBIOSBIOSVersion", "Unknown")
            
            # Parse BIOS date
            bios_date_raw = r.get("ReleaseDate", "")
            if bios_date_raw and len(bios_date_raw) >= 8:
                try:
                    dt = datetime.strptime(bios_date_raw[:8], "%Y%m%d")
                    mb.bios_date = dt.strftime("%Y-%m-%d")
                    mb.bios_release_date = bios_date_raw
                except Exception:
                    mb.bios_date = bios_date_raw[:10]
            
            mb.smbios_major = int(r.get("SMBIOSMajorVersion", 0) or 0)
            mb.smbios_minor = int(r.get("SMBIOSMinorVersion", 0) or 0)
            mb.smbios_version = f"{mb.smbios_major}.{mb.smbios_minor}"
            mb.embedded_controller_major = int(r.get("EmbeddedControllerMajorVersion", 0) or 0)
            mb.embedded_controller_minor = int(r.get("EmbeddedControllerMinorVersion", 0) or 0)
            mb.primary_bios = r.get("PrimaryBIOS", "").lower() == "true"
        
        # System info
        system_results = _run_wmic(
            "computersystem",
            ["Manufacturer", "Model", "SystemType", "SystemFamily", "SystemSKUNumber",
             "TotalPhysicalMemory", "NumberOfProcessors", "NumberOfLogicalProcessors",
             "Domain", "Workgroup", "UserName", "PrimaryOwnerName"]
        )
        
        if system_results:
            r = system_results[0]
            mb.raw_properties["system"] = r.copy()
            mb.system_manufacturer = r.get("Manufacturer", "")
            mb.system_model = r.get("Model", "")
            mb.system_type = r.get("SystemType", "")
            mb.system_family = r.get("SystemFamily", "")
            mb.system_sku = r.get("SystemSKUNumber", "")
        
        # Chassis info
        chassis_results = _run_wmic(
            "systemenclosure",
            ["Manufacturer", "ChassisTypes", "SerialNumber", "SMBIOSAssetTag",
             "Tag", "Version", "LockPresent", "SecurityStatus"]
        )
        
        chassis_type_map = {
            "1": "Other", "2": "Unknown", "3": "Desktop", "4": "Low Profile Desktop",
            "5": "Pizza Box", "6": "Mini Tower", "7": "Tower", "8": "Portable",
            "9": "Laptop", "10": "Notebook", "11": "Hand Held", "12": "Docking Station",
            "13": "All in One", "14": "Sub Notebook", "15": "Space-Saving",
            "16": "Lunch Box", "17": "Main Server Chassis", "18": "Expansion Chassis",
            "19": "SubChassis", "20": "Bus Expansion Chassis", "21": "Peripheral Chassis",
            "22": "RAID Chassis", "23": "Rack Mount Chassis", "24": "Sealed-Case PC",
            "30": "Tablet", "31": "Convertible", "32": "Detachable"
        }
        
        if chassis_results:
            r = chassis_results[0]
            mb.raw_properties["chassis"] = r.copy()
            mb.chassis_manufacturer = r.get("Manufacturer", "")
            mb.chassis_serial = r.get("SerialNumber", "")
            mb.chassis_asset_tag = r.get("SMBIOSAssetTag", "")
            
            chassis_type_raw = r.get("ChassisTypes", "")
            # ChassisTypes is typically {number} format
            chassis_num = re.search(r'\d+', chassis_type_raw)
            if chassis_num:
                mb.chassis_type = chassis_type_map.get(chassis_num.group(), chassis_type_raw)
        
        # Check UEFI/Secure Boot via registry
        firmware_type = _get_registry_value(
            r"SYSTEM\CurrentControlSet\Control\SecureBoot\State",
            "UEFISecureBootEnabled"
        )
        if firmware_type is not None:
            mb.bios_mode = "UEFI"
            mb.secure_boot = firmware_type == "1"
        else:
            # Check via bcdedit
            bcdedit_out = _run_powershell("bcdedit | Select-String 'path.*efi'")
            mb.bios_mode = "UEFI" if "efi" in bcdedit_out.lower() else "Legacy"
        
        # TPM check
        tpm_results = _run_wmic("path Win32_Tpm", ["IsEnabled_InitialValue", "SpecVersion"])
        if tpm_results:
            r = tpm_results[0]
            mb.tpm_present = r.get("IsEnabled_InitialValue", "").lower() == "true"
            mb.tpm_version = r.get("SpecVersion", "Unknown").split(",")[0] if r.get("SpecVersion") else "Unknown"
        
        mb.status = HealthStatus.HEALTHY
        
    except Exception:
        pass
    
    return mb


@timed("collect_storage_info")
def collect_storage_info() -> StorageInfo:
    """Collect comprehensive storage information"""
    storage = StorageInfo()
    
    try:
        # Physical drives - get ALL properties
        drive_results = _run_wmic(
            "diskdrive",
            ["Model", "SerialNumber", "InterfaceType", "MediaType",
             "Size", "FirmwareRevision", "Status", "DeviceID", "PNPDeviceID",
             "Caption", "Description", "Index", "Partitions", "BytesPerSector",
             "SectorsPerTrack", "TotalHeads", "TotalCylinders", "TotalSectors",
             "TotalTracks", "CompressionMethod", "Manufacturer", "SCSIBus",
             "SCSIPort", "SCSILogicalUnit", "SCSITargetId", "Signature",
             "Name", "SystemName", "Capabilities"]
        )
        
        for r in drive_results:
            drive = StorageDrive()
            # Store all raw properties
            drive.raw_properties = r.copy()
            
            # Basic properties
            drive.model = r.get("Model", "Unknown")
            drive.serial_number = r.get("SerialNumber", "Unknown").strip()
            drive.interface_type = r.get("InterfaceType", "Unknown")
            
            media = r.get("MediaType", "").lower()
            if "ssd" in media or "solid" in media:
                drive.media_type = "SSD"
            elif "hdd" in media or "hard" in media or "fixed" in media:
                drive.media_type = "HDD"
            else:
                drive.media_type = r.get("MediaType", "Unknown")
            
            drive.capacity_gb = _parse_size_to_gb(r.get("Size", "0"))
            drive.firmware_version = r.get("FirmwareRevision", "Unknown")
            
            # Extended properties
            drive.device_id = r.get("DeviceID", "")
            drive.pnp_device_id = r.get("PNPDeviceID", "")
            drive.caption = r.get("Caption", "")
            drive.description = r.get("Description", "")
            drive.index = int(r.get("Index", 0) or 0)
            drive.partitions = int(r.get("Partitions", 0) or 0)
            drive.bytes_per_sector = int(r.get("BytesPerSector", 0) or 0)
            drive.sectors_per_track = int(r.get("SectorsPerTrack", 0) or 0)
            drive.total_heads = int(r.get("TotalHeads", 0) or 0)
            drive.total_cylinders = int(r.get("TotalCylinders", 0) or 0)
            drive.total_sectors = int(r.get("TotalSectors", 0) or 0)
            drive.total_tracks = int(r.get("TotalTracks", 0) or 0)
            drive.compression_method = r.get("CompressionMethod", "")
            drive.manufacturer = r.get("Manufacturer", "")
            drive.scsi_bus = int(r.get("SCSIBus", 0) or 0)
            drive.scsi_port = int(r.get("SCSIPort", 0) or 0)
            drive.scsi_lun = int(r.get("SCSILogicalUnit", 0) or 0)
            drive.scsi_target_id = int(r.get("SCSITargetId", 0) or 0)
            drive.signature = r.get("Signature", "")
            
            status = r.get("Status", "")
            if status.lower() == "ok":
                drive.smart_status = "Healthy"
                drive.status = HealthStatus.HEALTHY
            else:
                drive.smart_status = status or "Unknown"
                drive.status = HealthStatus.WARNING if status else HealthStatus.UNKNOWN
            
            storage.physical_drives.append(drive)
        
        # Try to get SMART data via PowerShell (requires admin)
        smart_cmd = "Get-PhysicalDisk | Select-Object FriendlyName, HealthStatus, OperationalStatus | ConvertTo-Csv -NoTypeInformation"
        smart_out = _run_powershell(smart_cmd)
        if smart_out:
            lines = smart_out.strip().split('\n')
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.replace('"', '').split(',')
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        health = parts[1].strip()
                        for drive in storage.physical_drives:
                            if name.lower() in drive.model.lower():
                                drive.smart_status = health
                                if health.lower() == "healthy":
                                    drive.status = HealthStatus.HEALTHY
                                elif health.lower() == "warning":
                                    drive.status = HealthStatus.WARNING
                                elif health.lower() in ["unhealthy", "critical"]:
                                    drive.status = HealthStatus.CRITICAL
        
        # Logical volumes - get ALL properties
        vol_results = _run_wmic(
            "logicaldisk where DriveType=3",
            ["DeviceID", "VolumeName", "FileSystem", "Size", "FreeSpace",
             "VolumeSerialNumber", "Description", "DriveType", "Compressed",
             "SupportsQuotas", "SupportsDiskQuotas", "QuotasDisabled",
             "QuotasIncomplete", "QuotasRebuilding", "BlockSize",
             "MaximumComponentLength", "SupportsFileBasedCompression", "MediaType"]
        )
        
        for r in vol_results:
            vol = StorageVolume()
            # Store all raw properties
            vol.raw_properties = r.copy()
            
            # Basic properties
            vol.drive_letter = r.get("DeviceID", "")
            vol.label = r.get("VolumeName", "") or "Local Disk"
            vol.file_system = r.get("FileSystem", "")
            vol.capacity_gb = _parse_size_to_gb(r.get("Size", "0"))
            vol.free_gb = _parse_size_to_gb(r.get("FreeSpace", "0"))
            vol.used_gb = round(vol.capacity_gb - vol.free_gb, 2)
            
            if vol.capacity_gb > 0:
                vol.utilization_percent = round((vol.used_gb / vol.capacity_gb) * 100, 1)
            
            # Extended properties
            vol.volume_serial = r.get("VolumeSerialNumber", "")
            vol.description = r.get("Description", "")
            vol.drive_type = r.get("DriveType", "")
            vol.compressed = r.get("Compressed", "").lower() == "true"
            vol.supports_quotas = r.get("SupportsQuotas", "").lower() == "true"
            vol.supports_disk_quotas = r.get("SupportsDiskQuotas", "").lower() == "true"
            vol.quotas_disabled = r.get("QuotasDisabled", "").lower() == "true"
            vol.quotas_incomplete = r.get("QuotasIncomplete", "").lower() == "true"
            vol.quotas_rebuilding = r.get("QuotasRebuilding", "").lower() == "true"
            vol.block_size = int(r.get("BlockSize", 0) or 0)
            vol.maximum_component_length = int(r.get("MaximumComponentLength", 0) or 0)
            vol.supports_file_based_compression = r.get("SupportsFileBasedCompression", "").lower() == "true"
            
            # Status based on free space
            if vol.utilization_percent > 95:
                vol.status = HealthStatus.CRITICAL
            elif vol.utilization_percent > 85:
                vol.status = HealthStatus.WARNING
            else:
                vol.status = HealthStatus.HEALTHY
            
            storage.volumes.append(vol)
            storage.total_capacity_gb += vol.capacity_gb
            storage.total_used_gb += vol.used_gb
            
    except Exception:
        pass
    
    return storage


@timed("collect_network_info")
def collect_network_info() -> List[NetworkAdapter]:
    """Collect network adapter information"""
    adapters = []
    
    try:
        # Get adapter configuration
        config_results = _run_wmic(
            "nicconfig where IPEnabled=TRUE",
            ["Description", "MACAddress", "IPAddress", "IPSubnet",
             "DefaultIPGateway", "DNSServerSearchOrder", "DHCPEnabled"]
        )
        
        config_map = {}
        for r in config_results:
            desc = r.get("Description", "")
            if desc:
                config_map[desc.lower()] = r
        
        # Get adapter details
        adapter_results = _run_wmic(
            "nic where NetEnabled=TRUE",
            ["Name", "Description", "AdapterType", "MACAddress", "Speed", "NetConnectionStatus"]
        )
        
        status_map = {
            "0": "Disconnected", "1": "Connecting", "2": "Connected",
            "3": "Disconnecting", "4": "Hardware not present", "5": "Hardware disabled",
            "6": "Hardware malfunction", "7": "Media disconnected", "8": "Authenticating",
            "9": "Authentication succeeded", "10": "Authentication failed",
            "11": "Invalid address", "12": "Credentials required"
        }
        
        for r in adapter_results:
            adapter = NetworkAdapter()
            adapter.name = r.get("Name", "Unknown")
            adapter.description = r.get("Description", "Unknown")
            adapter.adapter_type = r.get("AdapterType", "Unknown")
            adapter.mac_address = r.get("MACAddress", "Unknown")
            
            # Speed in bps, convert to Mbps
            speed_bps = r.get("Speed", "0")
            try:
                adapter.speed_mbps = int(int(speed_bps) / 1_000_000)
            except (ValueError, TypeError):
                adapter.speed_mbps = 0
            
            status_code = r.get("NetConnectionStatus", "")
            adapter.link_state = status_map.get(status_code, "Unknown")
            
            # Get IP configuration
            desc_lower = adapter.description.lower()
            if desc_lower in config_map:
                cfg = config_map[desc_lower]
                
                # Parse IP addresses (WMI returns as tuple string)
                ip_str = cfg.get("IPAddress", "")
                if ip_str and ip_str != "()":
                    ips = re.findall(r'[\d\.]+|[\da-f:]+', ip_str, re.IGNORECASE)
                    for ip in ips:
                        if '.' in ip and adapter.ipv4_address == "Not assigned":
                            adapter.ipv4_address = ip
                        elif ':' in ip and adapter.ipv6_address == "Not assigned":
                            adapter.ipv6_address = ip
                
                subnet_str = cfg.get("IPSubnet", "")
                if subnet_str:
                    subnets = re.findall(r'[\d\.]+', subnet_str)
                    if subnets:
                        adapter.subnet_mask = subnets[0]
                
                gw_str = cfg.get("DefaultIPGateway", "")
                if gw_str:
                    gws = re.findall(r'[\d\.]+', gw_str)
                    if gws:
                        adapter.gateway = gws[0]
                
                dns_str = cfg.get("DNSServerSearchOrder", "")
                if dns_str:
                    adapter.dns_servers = re.findall(r'[\d\.]+', dns_str)
                
                adapter.dhcp_enabled = cfg.get("DHCPEnabled", "").lower() == "true"
            
            # Determine status
            if adapter.link_state == "Connected":
                adapter.status = HealthStatus.HEALTHY
            elif adapter.link_state in ["Disconnected", "Media disconnected"]:
                adapter.status = HealthStatus.WARNING
            else:
                adapter.status = HealthStatus.UNKNOWN
            
            adapters.append(adapter)
            
    except Exception:
        pass
    
    return adapters


def collect_sensor_info() -> List[SensorInfo]:
    """
    Collect temperature and fan sensor information.
    Note: Windows doesn't expose most sensors natively without third-party tools.
    This attempts to get what's available via WMI.
    """
    sensors = []
    
    try:
        # Try MSAcpi_ThermalZoneTemperature (limited availability)
        temp_results = _run_wmic(
            "path MSAcpi_ThermalZoneTemperature -namespace root/WMI",
            ["InstanceName", "CurrentTemperature"]
        )
        
        for r in temp_results:
            sensor = SensorInfo()
            sensor.raw_properties = r.copy()
            sensor.name = r.get("InstanceName", "Thermal Zone")
            sensor.sensor_type = "Temperature"
            
            # Temperature is in tenths of Kelvin
            try:
                temp_kelvin = int(r.get("CurrentTemperature", 0)) / 10
                sensor.value = round(temp_kelvin - 273.15, 1)  # Convert to Celsius
                sensor.unit = "°C"
                
                if sensor.value > 85:
                    sensor.status = HealthStatus.CRITICAL
                elif sensor.value > 70:
                    sensor.status = HealthStatus.WARNING
                else:
                    sensor.status = HealthStatus.HEALTHY
                    
                sensors.append(sensor)
            except (ValueError, TypeError):
                pass
        
        # TODO: Fan sensors typically require vendor-specific WMI classes or 
        # hardware monitoring tools like OpenHardwareMonitor/LibreHardwareMonitor
        # which expose data via their own WMI namespace.
        
    except Exception:
        pass
    
    return sensors


@timed("collect_audio_devices")
def collect_audio_devices() -> List[AudioDevice]:
    """Collect audio device information"""
    devices = []
    
    try:
        results = _run_wmic(
            "sounddev",
            ["Name", "Manufacturer", "DeviceID", "PNPDeviceID", "Status",
             "Caption", "Description", "ProductName", "StatusInfo"]
        )
        
        for r in results:
            device = AudioDevice()
            device.raw_properties = r.copy()
            device.name = r.get("Name", "Unknown")
            device.manufacturer = r.get("Manufacturer", "Unknown")
            device.device_id = r.get("DeviceID", "")
            device.pnp_device_id = r.get("PNPDeviceID", "")
            device.status = r.get("Status", "Unknown")
            devices.append(device)
            
    except Exception:
        pass
    
    return devices


@timed("collect_usb_devices")
def collect_usb_devices() -> List[USBDevice]:
    """Collect USB device information"""
    devices = []
    
    try:
        # Get USB hub/controller info
        results = _run_wmic(
            "path Win32_USBHub",
            ["Name", "DeviceID", "PNPDeviceID", "Description", "Manufacturer",
             "Status", "Service", "ClassGuid", "Caption"]
        )
        
        for r in results:
            device = USBDevice()
            device.raw_properties = r.copy()
            device.name = r.get("Name", "Unknown")
            device.device_id = r.get("DeviceID", "")
            device.pnp_device_id = r.get("PNPDeviceID", "")
            device.description = r.get("Description", "")
            device.manufacturer = r.get("Manufacturer", "")
            device.status = r.get("Status", "Unknown")
            device.service = r.get("Service", "")
            device.class_guid = r.get("ClassGuid", "")
            devices.append(device)
            
    except Exception:
        pass
    
    return devices


@timed("collect_usb_controllers")
def collect_usb_controllers() -> List[USBController]:
    """Collect USB controller information"""
    controllers = []
    
    try:
        results = _run_wmic(
            "path Win32_USBController",
            ["Name", "Manufacturer", "DeviceID", "PNPDeviceID", "ProtocolSupported",
             "Status", "Caption", "Description", "StatusInfo"]
        )
        
        protocol_map = {
            "0": "Unknown", "1": "Other", "16": "USB 1.0", "17": "USB 1.1",
            "18": "USB 2.0", "19": "USB 3.0"
        }
        
        for r in results:
            controller = USBController()
            controller.raw_properties = r.copy()
            controller.name = r.get("Name", "Unknown")
            controller.manufacturer = r.get("Manufacturer", "")
            controller.device_id = r.get("DeviceID", "")
            controller.pnp_device_id = r.get("PNPDeviceID", "")
            controller.protocol_supported = protocol_map.get(
                r.get("ProtocolSupported", "0"), r.get("ProtocolSupported", "Unknown")
            )
            controller.status = r.get("Status", "Unknown")
            controllers.append(controller)
            
    except Exception:
        pass
    
    return controllers


@timed("collect_monitors")
def collect_monitors() -> List[MonitorInfo]:
    """Collect monitor/display information"""
    monitors = []
    
    try:
        results = _run_wmic(
            "desktopmonitor",
            ["Name", "MonitorManufacturer", "DeviceID", "PNPDeviceID",
             "ScreenWidth", "ScreenHeight", "PixelsPerXLogicalInch",
             "PixelsPerYLogicalInch", "MonitorType", "Availability",
             "Caption", "Description", "Status"]
        )
        
        for r in results:
            monitor = MonitorInfo()
            monitor.raw_properties = r.copy()
            monitor.name = r.get("Name", "Unknown")
            monitor.manufacturer = r.get("MonitorManufacturer", "")
            monitor.device_id = r.get("DeviceID", "")
            monitor.pnp_device_id = r.get("PNPDeviceID", "")
            monitor.screen_width = int(r.get("ScreenWidth", 0) or 0)
            monitor.screen_height = int(r.get("ScreenHeight", 0) or 0)
            monitor.pixels_per_x_logical_inch = int(r.get("PixelsPerXLogicalInch", 0) or 0)
            monitor.pixels_per_y_logical_inch = int(r.get("PixelsPerYLogicalInch", 0) or 0)
            monitor.monitor_type = r.get("MonitorType", "")
            monitor.availability = r.get("Availability", "")
            monitors.append(monitor)
            
    except Exception:
        pass
    
    return monitors


@timed("collect_batteries")
def collect_batteries() -> List[BatteryInfo]:
    """Collect battery information (for laptops)"""
    batteries = []
    
    try:
        results = _run_wmic(
            "path Win32_Battery",
            ["Name", "DeviceID", "Status", "BatteryStatus", "Chemistry",
             "DesignCapacity", "FullChargeCapacity", "EstimatedChargeRemaining",
             "EstimatedRunTime", "ExpectedLife", "TimeOnBattery", "TimeToFullCharge",
             "Caption", "Description", "Availability"]
        )
        
        chemistry_map = {
            "1": "Other", "2": "Unknown", "3": "Lead Acid", "4": "Nickel Cadmium",
            "5": "Nickel Metal Hydride", "6": "Lithium-ion", "7": "Zinc Air",
            "8": "Lithium Polymer"
        }
        
        for r in results:
            battery = BatteryInfo()
            battery.raw_properties = r.copy()
            battery.name = r.get("Name", "Unknown")
            battery.device_id = r.get("DeviceID", "")
            battery.status = r.get("Status", "Unknown")
            battery.battery_status = int(r.get("BatteryStatus", 0) or 0)
            battery.chemistry = chemistry_map.get(
                r.get("Chemistry", "2"), r.get("Chemistry", "Unknown")
            )
            battery.design_capacity = int(r.get("DesignCapacity", 0) or 0)
            battery.full_charge_capacity = int(r.get("FullChargeCapacity", 0) or 0)
            battery.estimated_charge_remaining = int(r.get("EstimatedChargeRemaining", 0) or 0)
            battery.estimated_run_time = int(r.get("EstimatedRunTime", 0) or 0)
            battery.expected_life = int(r.get("ExpectedLife", 0) or 0)
            battery.time_on_battery = int(r.get("TimeOnBattery", 0) or 0)
            battery.time_to_full_charge = int(r.get("TimeToFullCharge", 0) or 0)
            batteries.append(battery)
            
    except Exception:
        pass
    
    return batteries


@timed("collect_printers")
def collect_printers() -> List[PrinterInfo]:
    """Collect printer information"""
    printers = []
    
    try:
        results = _run_wmic(
            "printer",
            ["Name", "DeviceID", "DriverName", "PortName", "PrinterStatus",
             "PrintProcessor", "Shared", "ShareName", "Local", "Network",
             "Default", "Caption", "Description", "Status"]
        )
        
        for r in results:
            printer = PrinterInfo()
            printer.raw_properties = r.copy()
            printer.name = r.get("Name", "Unknown")
            printer.device_id = r.get("DeviceID", "")
            printer.driver_name = r.get("DriverName", "")
            printer.port_name = r.get("PortName", "")
            printer.printer_status = r.get("PrinterStatus", "")
            printer.print_processor = r.get("PrintProcessor", "")
            printer.shared = r.get("Shared", "").lower() == "true"
            printer.share_name = r.get("ShareName", "")
            printer.local = r.get("Local", "").lower() == "true"
            printer.network = r.get("Network", "").lower() == "true"
            printer.default = r.get("Default", "").lower() == "true"
            printers.append(printer)
            
    except Exception:
        pass
    
    return printers


@timed("collect_hardware_snapshot")
def collect_hardware_snapshot() -> HardwareSnapshot:
    """
    Collect a complete hardware snapshot.
    This is the main entry point for the hardware scanner.
    Uses cached data for static components (motherboard/BIOS).
    """
    snapshot = HardwareSnapshot()
    snapshot.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Collect all hardware information
    # Note: motherboard_info is cached (static data doesn't change)
    snapshot.cpu = collect_cpu_info()
    snapshot.gpus = collect_gpu_info()
    snapshot.ram = collect_ram_info()
    snapshot.motherboard = collect_motherboard_info()  # Cached
    snapshot.storage = collect_storage_info()
    snapshot.network_adapters = collect_network_info()
    snapshot.sensors = collect_sensor_info()
    
    # Extended hardware collections
    snapshot.audio_devices = collect_audio_devices()
    snapshot.usb_devices = collect_usb_devices()
    snapshot.usb_controllers = collect_usb_controllers()
    snapshot.monitors = collect_monitors()
    snapshot.batteries = collect_batteries()
    snapshot.printers = collect_printers()
    
    # Determine overall health status
    all_statuses = [snapshot.cpu.status, snapshot.ram.status, snapshot.motherboard.status]
    all_statuses.extend([g.status for g in snapshot.gpus])
    all_statuses.extend([d.status for d in snapshot.storage.physical_drives])
    all_statuses.extend([v.status for v in snapshot.storage.volumes])
    all_statuses.extend([a.status for a in snapshot.network_adapters])
    all_statuses.extend([s.status for s in snapshot.sensors])
    
    if HealthStatus.CRITICAL in all_statuses:
        snapshot.overall_status = HealthStatus.CRITICAL
    elif HealthStatus.WARNING in all_statuses:
        snapshot.overall_status = HealthStatus.WARNING
    elif all(s == HealthStatus.HEALTHY for s in all_statuses if s != HealthStatus.UNKNOWN):
        snapshot.overall_status = HealthStatus.HEALTHY
    else:
        snapshot.overall_status = HealthStatus.UNKNOWN
    
    return snapshot


def get_hardware_summary() -> dict:
    """Get a quick summary of hardware for UI display"""
    snapshot = collect_hardware_snapshot()
    
    # Format GPU info - prefer real GPU over virtual adapters
    primary_gpu = None
    for gpu in snapshot.gpus:
        # Skip virtual/mirror adapters - prefer GPUs with VRAM
        if gpu.vram_mb > 0:
            primary_gpu = gpu
            break
        # Also skip by name patterns for virtual adapters
        name_lower = gpu.name.lower()
        if 'mirror' not in name_lower and 'virtual' not in name_lower and 'remote' not in name_lower:
            if primary_gpu is None:
                primary_gpu = gpu
    
    # Fall back to first GPU if no real one found
    if primary_gpu is None and snapshot.gpus:
        primary_gpu = snapshot.gpus[0]
    
    gpu_name = primary_gpu.name if primary_gpu else "Unknown"
    gpu_vram = primary_gpu.vram_mb if primary_gpu else 0
    
    # Format storage
    total_storage = sum(d.capacity_gb for d in snapshot.storage.physical_drives)
    
    return {
        "cpu": {
            "name": snapshot.cpu.name,
            "cores": snapshot.cpu.cores,
            "threads": snapshot.cpu.threads,
            "clock_mhz": snapshot.cpu.max_clock_mhz,
            "utilization": snapshot.cpu.utilization_percent,
            "status": snapshot.cpu.status.value
        },
        "gpu": {
            "name": gpu_name,
            "vram_mb": gpu_vram,
            "driver": primary_gpu.driver_version if primary_gpu else "Unknown",
            "status": primary_gpu.status.value if primary_gpu else "unknown"
        },
        "ram": {
            "total_gb": snapshot.ram.total_gb,
            "used_gb": snapshot.ram.used_gb,
            "utilization": snapshot.ram.utilization_percent,
            "slots": f"{snapshot.ram.slots_used}/{snapshot.ram.slots_total}",
            "status": snapshot.ram.status.value
        },
        "storage": {
            "total_gb": total_storage,
            "drives": len(snapshot.storage.physical_drives),
            "volumes": len(snapshot.storage.volumes),
            "status": "healthy" if all(d.status == HealthStatus.HEALTHY for d in snapshot.storage.physical_drives) else "warning"
        },
        "motherboard": {
            "manufacturer": snapshot.motherboard.manufacturer,
            "model": snapshot.motherboard.product,
            "bios": snapshot.motherboard.bios_version,
            "secure_boot": snapshot.motherboard.secure_boot,
            "tpm": snapshot.motherboard.tpm_present,
            "status": snapshot.motherboard.status.value
        },
        "network": {
            "adapters": len(snapshot.network_adapters),
            "connected": sum(1 for a in snapshot.network_adapters if a.link_state == "Connected"),
            "status": "healthy" if any(a.status == HealthStatus.HEALTHY for a in snapshot.network_adapters) else "warning"
        },
        "overall_status": snapshot.overall_status.value,
        "timestamp": snapshot.timestamp,
        "snapshot": snapshot  # Include full snapshot for detailed view
    }


# Test the module
if __name__ == "__main__":
    print("Collecting hardware snapshot...")
    summary = get_hardware_summary()
    
    print(f"\n=== Hardware Summary ===")
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Overall Status: {summary['overall_status']}")
    
    print(f"\n--- CPU ---")
    print(f"  {summary['cpu']['name']}")
    print(f"  {summary['cpu']['cores']} cores / {summary['cpu']['threads']} threads @ {summary['cpu']['clock_mhz']} MHz")
    print(f"  Utilization: {summary['cpu']['utilization']}%")
    
    print(f"\n--- GPU ---")
    print(f"  {summary['gpu']['name']}")
    print(f"  VRAM: {summary['gpu']['vram_mb']} MB")
    print(f"  Driver: {summary['gpu']['driver']}")
    
    print(f"\n--- RAM ---")
    print(f"  {summary['ram']['total_gb']} GB total, {summary['ram']['used_gb']} GB used ({summary['ram']['utilization']}%)")
    print(f"  Slots: {summary['ram']['slots']}")
    
    print(f"\n--- Storage ---")
    print(f"  {summary['storage']['drives']} physical drive(s), {summary['storage']['total_gb']:.0f} GB total")
    print(f"  {summary['storage']['volumes']} volume(s)")
    
    print(f"\n--- Motherboard ---")
    print(f"  {summary['motherboard']['manufacturer']} {summary['motherboard']['model']}")
    print(f"  BIOS: {summary['motherboard']['bios']}")
    print(f"  Secure Boot: {'Enabled' if summary['motherboard']['secure_boot'] else 'Disabled'}")
    print(f"  TPM: {'Present' if summary['motherboard']['tpm'] else 'Not detected'}")
    
    print(f"\n--- Network ---")
    print(f"  {summary['network']['adapters']} adapter(s), {summary['network']['connected']} connected")
    
    # Print detailed storage info
    snapshot = summary['snapshot']
    print(f"\n--- Storage Details ---")
    for drive in snapshot.storage.physical_drives:
        print(f"  {drive.model}: {drive.capacity_gb:.0f} GB ({drive.media_type}) - {drive.smart_status}")
    for vol in snapshot.storage.volumes:
        print(f"  {vol.drive_letter} ({vol.label}): {vol.used_gb:.1f}/{vol.capacity_gb:.1f} GB ({vol.utilization_percent}%)")
    
    print(f"\n--- Network Details ---")
    for adapter in snapshot.network_adapters:
        print(f"  {adapter.name}: {adapter.link_state}")
        if adapter.ipv4_address != "Not assigned":
            print(f"    IPv4: {adapter.ipv4_address}")
