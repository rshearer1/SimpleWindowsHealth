"""
Driver Update Scanner & Installer
A Python GUI application to scan for and install driver updates
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import subprocess
import json
import os
import sys
import ctypes
import re
import urllib.request
import urllib.error
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import webbrowser

# Try to import requests for better HTTP handling
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class DriverInfo:
    """Represents information about a device driver"""
    device_name: str
    device_id: str
    manufacturer: str
    driver_version: str
    driver_date: str
    status: str
    inf_name: str = ""
    update_available: bool = False
    update_version: str = ""
    update_source: str = ""
    hardware_id: str = ""
    device_class: str = ""


@dataclass
class OnlineDriverInfo:
    """Represents driver information from online sources"""
    name: str
    version: str
    date: str
    download_url: str
    source: str
    size: str = ""
    description: str = ""
    requires_restart: bool = False


class OnlineDriverChecker:
    """Handles online driver version checking from various sources"""
    
    # Known driver database - maps hardware IDs to driver info URLs
    DRIVER_DATABASE = {
        # NVIDIA GPUs
        'nvidia': {
            'vendor_id': '10DE',
            'api_url': 'https://www.nvidia.com/Download/processFind.aspx',
            'support_url': 'https://www.nvidia.com/Download/index.aspx'
        },
        # AMD GPUs
        'amd': {
            'vendor_id': '1002',
            'api_url': 'https://www.amd.com/en/support',
            'support_url': 'https://www.amd.com/en/support'
        },
        # Intel
        'intel': {
            'vendor_id': '8086',
            'api_url': 'https://www.intel.com/content/www/us/en/download-center/home.html',
            'support_url': 'https://www.intel.com/content/www/us/en/download-center/home.html'
        },
        # Realtek
        'realtek': {
            'vendor_id': '10EC',
            'support_url': 'https://www.realtek.com/en/downloads'
        }
    }
    
    def __init__(self, callback=None):
        self.callback = callback
        self.session = None
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
    
    def log(self, message: str):
        if self.callback:
            self.callback(message)
    
    def http_get(self, url: str, timeout: int = 30) -> Optional[str]:
        """Perform HTTP GET request"""
        try:
            if HAS_REQUESTS and self.session:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.text
            else:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read().decode('utf-8')
        except Exception as e:
            self.log(f"HTTP error: {e}")
            return None
    
    def parse_version(self, version_str: str) -> Tuple[int, ...]:
        """Parse version string into comparable tuple"""
        try:
            # Extract numbers from version string
            numbers = re.findall(r'\d+', version_str)
            return tuple(int(n) for n in numbers[:4])  # Take up to 4 parts
        except:
            return (0,)
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns: -1 if v1<v2, 0 if equal, 1 if v1>v2"""
        t1 = self.parse_version(v1)
        t2 = self.parse_version(v2)
        
        # Pad shorter tuple
        max_len = max(len(t1), len(t2))
        t1 = t1 + (0,) * (max_len - len(t1))
        t2 = t2 + (0,) * (max_len - len(t2))
        
        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        return 0
    
    def detect_gpu_vendor(self, device_id: str) -> Optional[str]:
        """Detect GPU vendor from device ID"""
        device_id_upper = device_id.upper()
        if 'VEN_10DE' in device_id_upper:
            return 'nvidia'
        elif 'VEN_1002' in device_id_upper:
            return 'amd'
        elif 'VEN_8086' in device_id_upper:
            return 'intel'
        return None
    
    def check_nvidia_driver(self, device_id: str, current_version: str) -> Optional[OnlineDriverInfo]:
        """Check for NVIDIA driver updates"""
        self.log("Checking NVIDIA for driver updates...")
        
        try:
            # Extract device ID components
            match = re.search(r'DEV_([0-9A-F]{4})', device_id.upper())
            if not match:
                return None
            
            dev_id = match.group(1)
            
            # NVIDIA driver lookup - we'll check their latest driver page
            # In production, this would use NVIDIA's actual API
            nvidia_url = f"https://www.nvidia.com/Download/API/lookupValueSearch.aspx?TypeID=3"
            
            # For now, provide the download page URL
            return OnlineDriverInfo(
                name="NVIDIA Graphics Driver",
                version="Check Online",
                date="",
                download_url="https://www.nvidia.com/Download/index.aspx",
                source="NVIDIA",
                description=f"Check for updates for device {dev_id}"
            )
        except Exception as e:
            self.log(f"NVIDIA check error: {e}")
            return None
    
    def check_amd_driver(self, device_id: str, current_version: str) -> Optional[OnlineDriverInfo]:
        """Check for AMD driver updates"""
        self.log("Checking AMD for driver updates...")
        
        try:
            match = re.search(r'DEV_([0-9A-F]{4})', device_id.upper())
            if not match:
                return None
            
            dev_id = match.group(1)
            
            # AMD Adrenalin drivers page
            return OnlineDriverInfo(
                name="AMD Radeon Software",
                version="Check Online",
                date="",
                download_url="https://www.amd.com/en/support",
                source="AMD",
                description=f"Check for updates for device {dev_id}"
            )
        except Exception as e:
            self.log(f"AMD check error: {e}")
            return None
    
    def check_intel_driver(self, device_id: str, device_class: str, current_version: str) -> Optional[OnlineDriverInfo]:
        """Check for Intel driver updates"""
        self.log("Checking Intel for driver updates...")
        
        try:
            # Intel Driver & Support Assistant download
            intel_dsa_url = "https://www.intel.com/content/www/us/en/support/detect.html"
            
            # Determine driver type based on device class
            if 'display' in device_class.lower():
                url = "https://www.intel.com/content/www/us/en/download/785597/intel-arc-iris-xe-graphics-windows.html"
                name = "Intel Graphics Driver"
            elif 'net' in device_class.lower():
                url = "https://www.intel.com/content/www/us/en/download/18293/intel-network-adapter-driver-for-windows-10.html"
                name = "Intel Network Driver"
            else:
                url = intel_dsa_url
                name = "Intel Driver"
            
            return OnlineDriverInfo(
                name=name,
                version="Check Online",
                date="",
                download_url=url,
                source="Intel",
                description="Use Intel Driver & Support Assistant for automatic detection"
            )
        except Exception as e:
            self.log(f"Intel check error: {e}")
            return None
    
    def check_realtek_driver(self, device_id: str, device_class: str) -> Optional[OnlineDriverInfo]:
        """Check for Realtek driver updates"""
        self.log("Checking Realtek for driver updates...")
        
        try:
            if 'audio' in device_class.lower() or 'sound' in device_class.lower():
                url = "https://www.realtek.com/en/component/zoo/category/pc-audio-codecs-high-definition-audio-codecs-software"
                name = "Realtek HD Audio Driver"
            elif 'net' in device_class.lower():
                url = "https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software"
                name = "Realtek Network Driver"
            else:
                url = "https://www.realtek.com/en/downloads"
                name = "Realtek Driver"
            
            return OnlineDriverInfo(
                name=name,
                version="Check Online",
                date="",
                download_url=url,
                source="Realtek",
                description="Download from Realtek website"
            )
        except Exception as e:
            self.log(f"Realtek check error: {e}")
            return None
    
    def check_driver_online(self, driver: DriverInfo) -> Optional[OnlineDriverInfo]:
        """Check a single driver against online sources"""
        device_id = driver.device_id.upper()
        device_class = driver.device_class.lower() if driver.device_class else ""
        manufacturer = driver.manufacturer.lower() if driver.manufacturer else ""
        
        # Check by vendor ID in device ID
        if 'VEN_10DE' in device_id:  # NVIDIA
            return self.check_nvidia_driver(device_id, driver.driver_version)
        elif 'VEN_1002' in device_id:  # AMD
            return self.check_amd_driver(device_id, driver.driver_version)
        elif 'VEN_8086' in device_id:  # Intel
            return self.check_intel_driver(device_id, device_class, driver.driver_version)
        elif 'VEN_10EC' in device_id:  # Realtek
            return self.check_realtek_driver(device_id, device_class)
        
        # Check by manufacturer name
        if 'nvidia' in manufacturer:
            return self.check_nvidia_driver(device_id, driver.driver_version)
        elif 'amd' in manufacturer or 'advanced micro' in manufacturer:
            return self.check_amd_driver(device_id, driver.driver_version)
        elif 'intel' in manufacturer:
            return self.check_intel_driver(device_id, device_class, driver.driver_version)
        elif 'realtek' in manufacturer:
            return self.check_realtek_driver(device_id, device_class)
        
        return None
    
    def scan_all_drivers_online(self, drivers: List[DriverInfo]) -> List[Dict]:
        """Scan all drivers against online sources"""
        self.log("Scanning drivers against online databases...")
        results = []
        
        # Group drivers by vendor to avoid duplicate checks
        checked_vendors = set()
        
        for driver in drivers:
            device_id = driver.device_id.upper()
            
            # Extract vendor ID
            vendor_match = re.search(r'VEN_([0-9A-F]{4})', device_id)
            vendor_id = vendor_match.group(1) if vendor_match else None
            
            # Skip if we already checked this vendor for this device class
            check_key = f"{vendor_id}_{driver.device_class}"
            if check_key in checked_vendors:
                continue
            
            online_info = self.check_driver_online(driver)
            if online_info:
                checked_vendors.add(check_key)
                results.append({
                    'installed_driver': driver,
                    'online_info': online_info,
                    'current_version': driver.driver_version,
                    'device_name': driver.device_name
                })
        
        self.log(f"Found {len(results)} drivers with online update sources")
        return results


class ManufacturerSupport:
    """Handles manufacturer-specific support URLs and driver pages"""
    
    MANUFACTURERS = {
        'dell': {
            'name': 'Dell',
            'detect_url': 'https://www.dell.com/support/home/en-us/product-support/servicetag/{serial}',
            'drivers_url': 'https://www.dell.com/support/home/en-us/drivers/driversdetails',
            'support_url': 'https://www.dell.com/support/home',
            'auto_detect': 'https://www.dell.com/support/home/en-us/product-support/servicetag',
            'keywords': ['dell']
        },
        'hp': {
            'name': 'HP',
            'detect_url': 'https://support.hp.com/us-en/drivers/selfservice/{model}',
            'drivers_url': 'https://support.hp.com/us-en/drivers',
            'support_url': 'https://support.hp.com',
            'auto_detect': 'https://support.hp.com/us-en/help/hp-support-assistant',
            'keywords': ['hp', 'hewlett', 'packard']
        },
        'lenovo': {
            'name': 'Lenovo',
            'detect_url': 'https://pcsupport.lenovo.com/us/en/products/{model}/downloads/driver-list',
            'drivers_url': 'https://pcsupport.lenovo.com/us/en/drivers',
            'support_url': 'https://pcsupport.lenovo.com',
            'auto_detect': 'https://support.lenovo.com/solutions/ht003029-lenovo-system-update-update-drivers-bios-and-applications',
            'keywords': ['lenovo', 'thinkpad', 'thinkcentre', 'ideapad', 'ideacentre']
        },
        'asus': {
            'name': 'ASUS',
            'detect_url': 'https://www.asus.com/support/Download-Center/',
            'drivers_url': 'https://www.asus.com/support/Download-Center/',
            'support_url': 'https://www.asus.com/support',
            'auto_detect': 'https://www.asus.com/supportonly/MyASUS/',
            'keywords': ['asus', 'asustek', 'rog', 'tuf']
        },
        'acer': {
            'name': 'Acer',
            'detect_url': 'https://www.acer.com/ac/en/US/content/drivers',
            'drivers_url': 'https://www.acer.com/ac/en/US/content/drivers',
            'support_url': 'https://www.acer.com/ac/en/US/content/support',
            'auto_detect': 'https://www.acer.com/ac/en/US/content/software-acer-care-center',
            'keywords': ['acer', 'predator', 'nitro']
        },
        'msi': {
            'name': 'MSI',
            'detect_url': 'https://www.msi.com/support/download',
            'drivers_url': 'https://www.msi.com/support/download',
            'support_url': 'https://www.msi.com/support',
            'auto_detect': 'https://www.msi.com/Landing/dragon-center-download',
            'keywords': ['msi', 'micro-star']
        },
        'gigabyte': {
            'name': 'GIGABYTE',
            'detect_url': 'https://www.gigabyte.com/Support',
            'drivers_url': 'https://www.gigabyte.com/Support/Consumer',
            'support_url': 'https://www.gigabyte.com/Support',
            'auto_detect': 'https://www.gigabyte.com/Support/Utility/Graphics-Card',
            'keywords': ['gigabyte', 'aorus']
        },
        'microsoft': {
            'name': 'Microsoft',
            'detect_url': 'https://support.microsoft.com/en-us/surface',
            'drivers_url': 'https://www.catalog.update.microsoft.com/Home.aspx',
            'support_url': 'https://support.microsoft.com',
            'auto_detect': 'https://support.microsoft.com/en-us/windows/update-drivers-in-windows-ec62f46c-ff14-c91d-eead-d7126dc1f7b6',
            'keywords': ['microsoft', 'surface']
        },
        'samsung': {
            'name': 'Samsung',
            'detect_url': 'https://www.samsung.com/us/support/downloads/',
            'drivers_url': 'https://www.samsung.com/us/support/downloads/',
            'support_url': 'https://www.samsung.com/us/support/',
            'auto_detect': 'https://www.samsung.com/us/support/',
            'keywords': ['samsung']
        },
        'toshiba': {
            'name': 'Toshiba/Dynabook',
            'detect_url': 'https://support.dynabook.com/drivers',
            'drivers_url': 'https://support.dynabook.com/drivers',
            'support_url': 'https://support.dynabook.com',
            'auto_detect': 'https://support.dynabook.com',
            'keywords': ['toshiba', 'dynabook']
        }
    }
    
    @classmethod
    def detect_manufacturer(cls, manufacturer: str, model: str = "") -> Optional[str]:
        """Detect manufacturer from system info"""
        search_text = f"{manufacturer} {model}".lower()
        
        for mfr_key, mfr_info in cls.MANUFACTURERS.items():
            for keyword in mfr_info['keywords']:
                if keyword in search_text:
                    return mfr_key
        return None
    
    @classmethod
    def get_support_urls(cls, manufacturer: str, model: str = "", serial: str = "") -> Dict:
        """Get all relevant support URLs for a manufacturer"""
        mfr_key = cls.detect_manufacturer(manufacturer, model)
        
        if not mfr_key:
            return {
                'drivers': 'https://www.catalog.update.microsoft.com/Home.aspx',
                'support': 'https://support.microsoft.com',
                'auto_detect': '',
                'manufacturer_tool': {'name': '', 'url': ''}
            }
        
        mfr_info = cls.MANUFACTURERS[mfr_key]
        
        # Try to build model-specific URL
        drivers_url = mfr_info['drivers_url']
        if '{model}' in mfr_info.get('detect_url', ''):
            model_slug = model.replace(' ', '-').lower()
            drivers_url = mfr_info['detect_url'].format(model=model_slug)
        elif '{serial}' in mfr_info.get('detect_url', '') and serial:
            drivers_url = mfr_info['detect_url'].format(serial=serial)
        
        return {
            'name': mfr_info['name'],
            'drivers': drivers_url,
            'support': mfr_info['support_url'],
            'auto_detect': mfr_info.get('auto_detect', ''),
            'manufacturer_tool': cls.get_manufacturer_tool_info(mfr_key)
        }
    
    @classmethod
    def get_manufacturer_tool_info(cls, mfr_key: str) -> Dict[str, str]:
        """Get info about manufacturer's driver update tool"""
        tools = {
            'dell': {'name': 'Dell SupportAssist', 'url': 'https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/software-and-downloads/supportassist'},
            'hp': {'name': 'HP Support Assistant', 'url': 'https://support.hp.com/us-en/help/hp-support-assistant'},
            'lenovo': {'name': 'Lenovo Vantage / System Update', 'url': 'https://support.lenovo.com/solutions/ht003029'},
            'asus': {'name': 'MyASUS', 'url': 'https://www.asus.com/supportonly/MyASUS/'},
            'acer': {'name': 'Acer Care Center', 'url': 'https://www.acer.com/ac/en/US/content/software-acer-care-center'},
            'msi': {'name': 'MSI Dragon Center / Center', 'url': 'https://www.msi.com/Landing/dragon-center-download'},
            'gigabyte': {'name': 'GIGABYTE Control Center', 'url': 'https://www.gigabyte.com/Support/Utility'},
        }
        return tools.get(mfr_key, {'name': '', 'url': ''})


class DriverScanner:
    """Handles driver scanning operations"""
    
    def __init__(self, callback=None):
        self.callback = callback  # Progress callback function
        self.drivers: List[DriverInfo] = []
        self.available_updates: List[dict] = []
        
    def log(self, message: str):
        """Send log message to callback"""
        if self.callback:
            self.callback(message)
    
    def run_powershell(self, command: str) -> str:
        """Execute a PowerShell command and return output"""
        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            self.log(f"Error running command: {e}")
            return ""
    
    def get_system_info(self) -> dict:
        """Get system manufacturer and model information"""
        self.log("Detecting system information...")
        
        command = """
        $cs = Get-CimInstance Win32_ComputerSystem
        $bios = Get-CimInstance Win32_BIOS
        @{
            Manufacturer = $cs.Manufacturer
            Model = $cs.Model
            SystemType = $cs.SystemType
            SerialNumber = $bios.SerialNumber
        } | ConvertTo-Json
        """
        
        output = self.run_powershell(command)
        try:
            return json.loads(output)
        except:
            return {"Manufacturer": "Unknown", "Model": "Unknown"}
    
    def scan_installed_drivers(self) -> List[DriverInfo]:
        """Scan all installed drivers using WMI"""
        self.log("Scanning installed drivers...")
        
        command = """
        Get-CimInstance Win32_PnPSignedDriver | 
        Where-Object { $_.DeviceName -ne $null } |
        Select-Object DeviceName, DeviceID, Manufacturer, DriverVersion, DriverDate, 
                      InfName, DeviceClass, IsSigned, HardWareID |
        ConvertTo-Json -Depth 3
        """
        
        output = self.run_powershell(command)
        drivers = []
        
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('DeviceName'):
                    driver_date = ""
                    if item.get('DriverDate'):
                        try:
                            # Parse WMI date format
                            date_str = item['DriverDate']
                            if '/Date(' in date_str:
                                timestamp = int(date_str.replace('/Date(', '').replace(')/', '').split('-')[0].split('+')[0])
                                driver_date = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d')
                            else:
                                driver_date = str(date_str)[:10]
                        except:
                            driver_date = str(item.get('DriverDate', ''))[:10]
                    
                    # Get hardware ID (can be string or array)
                    hw_id = item.get('HardWareID', '')
                    if isinstance(hw_id, list):
                        hw_id = hw_id[0] if hw_id else ''
                    
                    drivers.append(DriverInfo(
                        device_name=item.get('DeviceName', 'Unknown'),
                        device_id=item.get('DeviceID', ''),
                        manufacturer=item.get('Manufacturer', 'Unknown'),
                        driver_version=item.get('DriverVersion', 'Unknown'),
                        driver_date=driver_date,
                        status="OK" if item.get('IsSigned') else "Unsigned",
                        inf_name=item.get('InfName', ''),
                        device_class=item.get('DeviceClass', ''),
                        hardware_id=hw_id
                    ))
            
            self.log(f"Found {len(drivers)} installed drivers")
            
        except json.JSONDecodeError as e:
            self.log(f"Error parsing driver data: {e}")
        
        self.drivers = drivers
        return drivers
    
    def scan_problem_devices(self) -> List[dict]:
        """Find devices with problems (missing drivers, errors)"""
        self.log("Checking for problem devices...")
        
        command = """
        Get-CimInstance Win32_PnPEntity | 
        Where-Object { $_.ConfigManagerErrorCode -ne 0 } |
        Select-Object Name, DeviceID, ConfigManagerErrorCode, Status |
        ConvertTo-Json
        """
        
        output = self.run_powershell(command)
        problems = []
        
        try:
            data = json.loads(output) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('Name'):
                    problems.append({
                        'name': item.get('Name', 'Unknown Device'),
                        'device_id': item.get('DeviceID', ''),
                        'error_code': item.get('ConfigManagerErrorCode', 0),
                        'status': item.get('Status', 'Error')
                    })
            
            if problems:
                self.log(f"Found {len(problems)} devices with problems")
            else:
                self.log("No problem devices found")
                
        except:
            pass
        
        return problems
    
    def check_windows_update_drivers(self) -> List[dict]:
        """Check Windows Update for available driver updates"""
        self.log("Checking Windows Update for driver updates...")
        self.log("(This may take a minute...)")
        
        command = """
        try {
            $UpdateSession = New-Object -ComObject Microsoft.Update.Session
            $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
            $SearchResult = $UpdateSearcher.Search("IsInstalled=0 and Type='Driver'")
            
            $updates = @()
            foreach ($Update in $SearchResult.Updates) {
                $updates += @{
                    Title = $Update.Title
                    Description = $Update.Description
                    DriverClass = $Update.DriverClass
                    DriverHardwareID = $Update.DriverHardwareID
                    DriverManufacturer = $Update.DriverManufacturer
                    DriverModel = $Update.DriverModel
                    DriverProvider = $Update.DriverProvider
                    DriverVerDate = $Update.DriverVerDate.ToString("yyyy-MM-dd")
                    RebootRequired = $Update.RebootRequired
                    IsMandatory = $Update.IsMandatory
                }
            }
            $updates | ConvertTo-Json -Depth 3
        } catch {
            Write-Output "[]"
        }
        """
        
        output = self.run_powershell(command)
        updates = []
        
        try:
            data = json.loads(output) if output.strip() and output.strip() != "[]" else []
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('Title'):
                    updates.append({
                        'title': item.get('Title', ''),
                        'description': item.get('Description', ''),
                        'driver_class': item.get('DriverClass', ''),
                        'manufacturer': item.get('DriverManufacturer', ''),
                        'model': item.get('DriverModel', ''),
                        'provider': item.get('DriverProvider', ''),
                        'date': item.get('DriverVerDate', ''),
                        'reboot_required': item.get('RebootRequired', False),
                        'mandatory': item.get('IsMandatory', False),
                        'source': 'Windows Update'
                    })
            
            if updates:
                self.log(f"Found {len(updates)} driver updates available from Windows Update")
            else:
                self.log("No driver updates available from Windows Update")
                
        except Exception as e:
            self.log(f"Could not check Windows Update: {e}")
        
        self.available_updates = updates
        return updates
    
    def get_manufacturer_support_url(self, manufacturer: str, model: str) -> str:
        """Get manufacturer support URL for driver downloads"""
        manufacturer_lower = manufacturer.lower()
        
        urls = {
            'dell': f'https://www.dell.com/support/home/en-us/product-support/servicetag',
            'hp': 'https://support.hp.com/drivers',
            'lenovo': 'https://pcsupport.lenovo.com/us/en/products',
            'asus': 'https://www.asus.com/support/Download-Center/',
            'acer': 'https://www.acer.com/ac/en/US/content/drivers',
            'msi': 'https://www.msi.com/support/download',
            'gigabyte': 'https://www.gigabyte.com/Support',
            'intel': 'https://www.intel.com/content/www/us/en/download-center/home.html',
            'nvidia': 'https://www.nvidia.com/Download/index.aspx',
            'amd': 'https://www.amd.com/en/support',
            'realtek': 'https://www.realtek.com/en/downloads',
        }
        
        for key, url in urls.items():
            if key in manufacturer_lower:
                return url
        
        return 'https://www.catalog.update.microsoft.com/Home.aspx'
    
    def install_windows_updates(self, callback=None) -> bool:
        """Install available driver updates from Windows Update"""
        self.log("Installing driver updates from Windows Update...")
        self.log("This requires administrator privileges...")
        
        command = """
        try {
            $UpdateSession = New-Object -ComObject Microsoft.Update.Session
            $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
            $SearchResult = $UpdateSearcher.Search("IsInstalled=0 and Type='Driver'")
            
            if ($SearchResult.Updates.Count -eq 0) {
                Write-Output "NO_UPDATES"
                exit
            }
            
            $UpdatesToInstall = New-Object -ComObject Microsoft.Update.UpdateColl
            foreach ($Update in $SearchResult.Updates) {
                $UpdatesToInstall.Add($Update) | Out-Null
            }
            
            Write-Output "DOWNLOADING"
            $Downloader = $UpdateSession.CreateUpdateDownloader()
            $Downloader.Updates = $UpdatesToInstall
            $Downloader.Download() | Out-Null
            
            Write-Output "INSTALLING"
            $Installer = $UpdateSession.CreateUpdateInstaller()
            $Installer.Updates = $UpdatesToInstall
            $Result = $Installer.Install()
            
            Write-Output "RESULT:$($Result.ResultCode)"
            Write-Output "REBOOT:$($Result.RebootRequired)"
        } catch {
            Write-Output "ERROR:$($_.Exception.Message)"
        }
        """
        
        output = self.run_powershell(command)
        
        if "NO_UPDATES" in output:
            self.log("No updates to install")
            return True
        elif "ERROR:" in output:
            error = output.split("ERROR:")[1].strip()
            self.log(f"Installation error: {error}")
            return False
        elif "RESULT:2" in output:  # 2 = Succeeded
            self.log("Driver updates installed successfully!")
            if "REBOOT:True" in output:
                self.log("A system restart is required to complete the installation")
            return True
        else:
            self.log("Installation completed with warnings")
            return True
    
    def find_old_drivers(self) -> List[dict]:
        """Find old/outdated drivers in the driver store"""
        self.log("Scanning for old drivers in driver store...")
        
        command = """
        # Get all third-party drivers from driver store
        $drivers = Get-WindowsDriver -Online -All | Where-Object { $_.Driver -like 'oem*.inf' }
        
        # Group by original file name to find duplicates
        $grouped = $drivers | Group-Object OriginalFileName
        
        $oldDrivers = @()
        foreach ($group in $grouped) {
            if ($group.Count -gt 1) {
                # Sort by version/date and mark older ones
                $sorted = $group.Group | Sort-Object { [version]($_.Version -replace '[^0-9.]', '') } -Descending -ErrorAction SilentlyContinue
                if ($sorted.Count -gt 1) {
                    # Skip the newest, mark rest as old
                    for ($i = 1; $i -lt $sorted.Count; $i++) {
                        $oldDrivers += @{
                            Driver = $sorted[$i].Driver
                            OriginalFileName = $sorted[$i].OriginalFileName
                            ClassName = $sorted[$i].ClassName
                            ProviderName = $sorted[$i].ProviderName
                            Version = $sorted[$i].Version
                            Date = if ($sorted[$i].Date) { $sorted[$i].Date.ToString("yyyy-MM-dd") } else { "" }
                            NewestVersion = $sorted[0].Version
                            Reason = "Superseded"
                        }
                    }
                }
            }
        }
        $oldDrivers | ConvertTo-Json -Depth 3
        """
        
        old_drivers = []
        try:
            output = self.run_powershell(command)
            data = json.loads(output) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('Driver'):
                    old_drivers.append({
                        'driver': item.get('Driver', ''),
                        'name': item.get('OriginalFileName', ''),
                        'class': item.get('ClassName', ''),
                        'provider': item.get('ProviderName', ''),
                        'version': item.get('Version', ''),
                        'date': item.get('Date', ''),
                        'newest_version': item.get('NewestVersion', ''),
                        'reason': item.get('Reason', 'Unknown')
                    })
            
            if old_drivers:
                self.log(f"Found {len(old_drivers)} old driver versions")
            else:
                self.log("No old drivers found")
                
        except Exception as e:
            self.log(f"Error scanning for old drivers: {e}")
        
        return old_drivers
    
    # Protected system driver providers - never auto-remove
    PROTECTED_PROVIDERS = [
        'microsoft', 'windows', 'intel corporation', 'amd', 'nvidia',
        'realtek', 'qualcomm', 'broadcom', 'marvell'  # Current active hardware vendors
    ]
    
    # Known cleanup targets - old driver folders
    CLEANUP_FOLDERS = [
        r'C:\NVIDIA',
        r'C:\AMD', 
        r'C:\Program Files\AMD',
        r'C:\Program Files\NVIDIA Corporation\Installer2'
    ]
    
    def find_unused_drivers(self) -> List[dict]:
        """
        Advanced unused driver detection using multiple methods:
        1. Compare driver store vs active hardware devices
        2. Check for phantom/non-present devices
        3. Identify old driver versions when newer exists
        4. Flag unsigned drivers
        5. Detect ghost USB/Network/Audio drivers
        """
        self.log("Performing comprehensive driver analysis...")
        
        command = """
        $results = @()
        
        # ===== METHOD 1: Driver Store vs Active Devices =====
        # Get all OEM drivers from driver store
        $storeDrivers = @{}
        try {
            $pnpOutput = pnputil /enum-drivers 2>$null
            $currentDriver = $null
            foreach ($line in $pnpOutput -split "`n") {
                if ($line -match "Published Name\\s*:\\s*(.+)") {
                    $currentDriver = @{ InfName = $matches[1].Trim() }
                }
                if ($currentDriver -and $line -match "Original Name\\s*:\\s*(.+)") {
                    $currentDriver.OriginalName = $matches[1].Trim()
                }
                if ($currentDriver -and $line -match "Provider Name\\s*:\\s*(.+)") {
                    $currentDriver.Provider = $matches[1].Trim()
                }
                if ($currentDriver -and $line -match "Class Name\\s*:\\s*(.+)") {
                    $currentDriver.ClassName = $matches[1].Trim()
                }
                if ($currentDriver -and $line -match "Class Version\\s*:\\s*(.+)") {
                    $currentDriver.Version = $matches[1].Trim()
                }
                if ($currentDriver -and $line -match "Driver Version\\s*:\\s*(.+)") {
                    $currentDriver.DriverVersion = $matches[1].Trim()
                }
                if ($currentDriver -and $line -match "Signer Name\\s*:\\s*(.+)") {
                    $currentDriver.Signer = $matches[1].Trim()
                    if ($currentDriver.InfName) {
                        $storeDrivers[$currentDriver.InfName] = $currentDriver
                    }
                    $currentDriver = $null
                }
            }
        } catch {}
        
        # Get connected devices and their drivers
        $connectedDevices = @{}
        try {
            $pnpDevices = pnputil /enum-devices /connected 2>$null
            foreach ($line in $pnpDevices -split "`n") {
                if ($line -match "Driver Name\\s*:\\s*(.+)") {
                    $drvName = $matches[1].Trim()
                    $connectedDevices[$drvName] = $true
                }
            }
        } catch {}
        
        # Get active drivers from WMI
        $activeDrivers = @{}
        try {
            Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | 
            Where-Object { $_.InfName } | 
            ForEach-Object { $activeDrivers[$_.InfName] = $_ }
        } catch {}
        
        # ===== METHOD 2: Find Phantom/Non-Present Devices =====
        $phantomDevices = @()
        try {
            # Get all PnP entities including non-present
            $allDevices = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue
            $connectedHwIds = @{}
            
            # Get connected device hardware IDs
            Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | 
            Where-Object { $_.Status -eq 'OK' -and $_.ConfigManagerErrorCode -eq 0 } |
            ForEach-Object { 
                if ($_.HardwareID) { 
                    foreach ($hwid in $_.HardwareID) {
                        $connectedHwIds[$hwid] = $true 
                    }
                }
            }
        } catch {}
        
        # ===== Analyze each driver in store =====
        foreach ($infName in $storeDrivers.Keys) {
            $driver = $storeDrivers[$infName]
            $dominated = $false
            $dominated = $false
            $dominated = $false
            $dominated = $false
            $dominated = $false
            $dominated = $false
            $dominated = $false
            $reason = @()
            $risk = "safe"  # safe, caution, protected
            
            # Skip if not OEM driver
            if ($infName -notlike "oem*.inf") { continue }
            
            # Check if driver is in use by connected device
            $inUse = $connectedDevices.ContainsKey($infName) -or $activeDrivers.ContainsKey($infName)
            
            if (-not $inUse) {
                $reason += "Not used by any connected device"
            }
            
            # Check provider for protection
            $provider = $driver.Provider.ToLower()
            $isProtected = $false
            $protectedProviders = @('microsoft', 'intel', 'amd', 'nvidia', 'realtek', 'qualcomm', 'broadcom')
            foreach ($pp in $protectedProviders) {
                if ($provider -like "*$pp*") {
                    # Only protect if currently in use
                    if ($inUse) {
                        $isProtected = $true
                        $risk = "protected"
                    }
                    break
                }
            }
            
            # Check if unsigned
            if (-not $driver.Signer -or $driver.Signer -eq "" -or $driver.Signer -like "*not signed*") {
                $reason += "Unsigned driver"
                if ($risk -ne "protected") { $risk = "caution" }
            }
            
            # Check for old versions (same provider, older version exists)
            $className = $driver.ClassName
            $driverProvider = $driver.Provider
            foreach ($otherInf in $storeDrivers.Keys) {
                if ($otherInf -eq $infName) { continue }
                $other = $storeDrivers[$otherInf]
                if ($other.ClassName -eq $className -and $other.Provider -eq $driverProvider) {
                    # Same class and provider - check version
                    try {
                        if ($other.DriverVersion -gt $driver.DriverVersion) {
                            $reason += "Newer version exists ($($other.DriverVersion))"
                            break
                        }
                    } catch {}
                }
            }
            
            # Categorize by driver class
            $category = "Other"
            switch -Wildcard ($className) {
                "*Display*" { $category = "GPU" }
                "*Graphics*" { $category = "GPU" }
                "*Audio*" { $category = "Audio" }
                "*Sound*" { $category = "Audio" }
                "*Network*" { $category = "Network" }
                "*Net*" { $category = "Network" }
                "*Ethernet*" { $category = "Network" }
                "*WiFi*" { $category = "Network" }
                "*USB*" { $category = "USB" }
                "*Printer*" { $category = "Printer" }
                "*Print*" { $category = "Printer" }
                "*Bluetooth*" { $category = "Bluetooth" }
                "*Storage*" { $category = "Storage" }
                "*SCSI*" { $category = "Storage" }
                "*HID*" { $category = "Input" }
                "*Keyboard*" { $category = "Input" }
                "*Mouse*" { $category = "Input" }
            }
            
            # Only add if there's a reason (unused, old, unsigned)
            if ($reason.Count -gt 0 -and -not $isProtected) {
                $results += @{
                    InfName = $infName
                    OriginalName = $driver.OriginalName
                    Provider = $driver.Provider
                    ClassName = $className
                    Category = $category
                    Version = $driver.DriverVersion
                    Signer = $driver.Signer
                    Reasons = ($reason -join "; ")
                    Risk = $risk
                    InUse = $inUse
                }
            }
        }
        
        $results | ConvertTo-Json -Depth 3
        """
        
        unused_drivers = []
        try:
            output = self.run_powershell(command)
            data = json.loads(output) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('InfName'):
                    unused_drivers.append({
                        'driver': item.get('InfName', ''),
                        'name': item.get('OriginalName', item.get('InfName', '')),
                        'class': item.get('ClassName', ''),
                        'category': item.get('Category', 'Other'),
                        'provider': item.get('Provider', ''),
                        'version': item.get('Version', ''),
                        'signer': item.get('Signer', ''),
                        'reason': item.get('Reasons', 'Not in use'),
                        'risk': item.get('Risk', 'safe'),
                        'in_use': item.get('InUse', False)
                    })
            
            # Sort by risk level (caution first, then safe)
            risk_order = {'caution': 0, 'safe': 1, 'protected': 2}
            unused_drivers.sort(key=lambda x: risk_order.get(x.get('risk', 'safe'), 1))
            
            if unused_drivers:
                self.log(f"Found {len(unused_drivers)} potentially removable drivers")
            else:
                self.log("No unused drivers found - system is clean!")
                
        except Exception as e:
            self.log(f"Error scanning for unused drivers: {e}")
        
        return unused_drivers
    
    def scan_phantom_devices(self) -> List[dict]:
        """Find phantom/ghost devices (hardware that was connected but is now gone)"""
        self.log("Scanning for phantom devices...")
        
        command = """
        $phantoms = @()
        
        # Use devcon-like approach via registry
        $baseKey = "HKLM:\\SYSTEM\\CurrentControlSet\\Enum"
        
        # Get all PnP entities
        $allEntities = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue
        
        foreach ($entity in $allEntities) {
            # Check if device is not present (ConfigManagerErrorCode indicates issues)
            # Code 45 = Device not connected
            # Code 22 = Disabled
            # Code 28 = Driver not installed
            
            $errorCode = $entity.ConfigManagerErrorCode
            $status = $entity.Status
            
            # Ghost device indicators
            $isGhost = ($errorCode -eq 45) -or 
                       ($status -ne 'OK' -and $entity.PNPClass -notin @('System', 'Computer', 'Volume'))
            
            if ($isGhost -and $entity.Name) {
                $phantoms += @{
                    Name = $entity.Name
                    DeviceID = $entity.DeviceID
                    Class = $entity.PNPClass
                    Manufacturer = $entity.Manufacturer
                    Status = $status
                    ErrorCode = $errorCode
                }
            }
        }
        
        $phantoms | ConvertTo-Json -Depth 3
        """
        
        phantoms = []
        try:
            output = self.run_powershell(command)
            data = json.loads(output) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            
            for item in data:
                if item.get('Name'):
                    phantoms.append({
                        'name': item.get('Name', ''),
                        'device_id': item.get('DeviceID', ''),
                        'class': item.get('Class', ''),
                        'manufacturer': item.get('Manufacturer', ''),
                        'status': item.get('Status', ''),
                        'error_code': item.get('ErrorCode', 0)
                    })
            
            self.log(f"Found {len(phantoms)} phantom devices")
        except Exception as e:
            self.log(f"Error scanning phantom devices: {e}")
        
        return phantoms
    
    def get_driver_cleanup_summary(self) -> dict:
        """Get a summary of potential cleanup savings"""
        self.log("Calculating cleanup summary...")
        
        command = """
        $summary = @{
            TotalOemDrivers = 0
            UnusedCount = 0
            OldVersionCount = 0
            UnsignedCount = 0
            EstimatedSizeMB = 0
            Categories = @{}
        }
        
        # Count OEM drivers
        try {
            $drivers = pnputil /enum-drivers 2>$null
            $oemCount = ($drivers | Select-String "oem.*\\.inf" -AllMatches).Matches.Count
            $summary.TotalOemDrivers = $oemCount
        } catch {}
        
        # Check driver store size
        try {
            $storePath = "$env:SystemRoot\\System32\\DriverStore\\FileRepository"
            $size = (Get-ChildItem $storePath -Recurse -ErrorAction SilentlyContinue | 
                     Measure-Object -Property Length -Sum).Sum
            $summary.EstimatedSizeMB = [math]::Round($size / 1MB, 2)
        } catch {}
        
        $summary | ConvertTo-Json -Depth 3
        """
        
        try:
            output = self.run_powershell(command)
            return json.loads(output) if output.strip() else {}
        except:
            return {}
    
    def remove_driver(self, driver_inf: str) -> bool:
        """Remove a driver from the driver store"""
        self.log(f"Removing driver: {driver_inf}")
        
        command = f'pnputil /delete-driver {driver_inf} /force'
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self.log(f"Successfully removed {driver_inf}")
                return True
            else:
                self.log(f"Failed to remove {driver_inf}: {result.stderr}")
                return False
        except Exception as e:
            self.log(f"Error removing driver: {e}")
            return False


class DriverUpdaterApp:
    """Main application GUI"""
    
    # Modern glass-style color scheme
    COLORS = {
        'bg': '#0a0a0f',
        'bg_glass': '#12121a',
        'bg_card': '#1a1a24',
        'bg_elevated': '#252532',
        'bg_row_alt': '#16161e',  # Alternating row color
        'accent': '#3b82f6',
        'accent_light': '#60a5fa',
        'text': '#f8fafc',
        'text_secondary': '#94a3b8',
        'text_muted': '#64748b',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
        'border': '#2e2e3a'
    }
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Driver Update Scanner")
        self.root.geometry("1100x720")
        self.root.minsize(950, 620)
        
        # Configure dark background
        self.root.configure(bg=self.COLORS['bg'])
        
        # Set up modern styling
        self.setup_styles()
        
        self.scanner = DriverScanner(callback=self.log_message)
        self.online_checker = OnlineDriverChecker(callback=self.log_message)
        self.system_info = {}
        self.installed_drivers = []
        self.available_updates = []
        self.problem_devices = []
        self.online_drivers = []
        self.manufacturer_urls = {}
        self.update_items = {}
        
        self.setup_ui()
    
    def setup_styles(self):
        """Configure modern glass-style ttk styles"""
        self.style = ttk.Style()
        
        try:
            self.style.theme_use('clam')
        except:
            pass
        
        # Colors
        bg = self.COLORS['bg']
        bg_glass = self.COLORS['bg_glass']
        bg_card = self.COLORS['bg_card']
        bg_elevated = self.COLORS['bg_elevated']
        accent = self.COLORS['accent']
        text = self.COLORS['text']
        text_sec = self.COLORS['text_secondary']
        text_muted = self.COLORS['text_muted']
        border = self.COLORS['border']
        
        # Frame styles
        self.style.configure('TFrame', background=bg)
        self.style.configure('Card.TFrame', background=bg_card)
        self.style.configure('Glass.TFrame', background=bg_glass)
        
        # Label styles - Century Gothic for readability
        self.style.configure('TLabel', background=bg, foreground=text, font=('Century Gothic', 10))
        self.style.configure('Title.TLabel', background=bg, foreground=text, font=('Century Gothic', 28, 'bold'))
        self.style.configure('Subtitle.TLabel', background=bg, foreground=text_sec, font=('Century Gothic', 12))
        self.style.configure('Card.TLabel', background=bg_card, foreground=text, font=('Century Gothic', 10))
        self.style.configure('CardTitle.TLabel', background=bg_glass, foreground=text_sec, font=('Century Gothic', 9))
        self.style.configure('Status.TLabel', background=bg, foreground=self.COLORS['success'], font=('Century Gothic', 10))
        self.style.configure('Muted.TLabel', background=bg_card, foreground=text_sec, font=('Century Gothic', 10))
        
        # Button styles - modern flat look
        self.style.configure('TButton',
                            background=bg_elevated,
                            foreground=text,
                            font=('Century Gothic', 10),
                            borderwidth=0,
                            padding=(14, 10))
        self.style.map('TButton',
                      background=[('active', border), ('pressed', bg_card)])
        
        self.style.configure('Accent.TButton',
                            background=accent,
                            foreground='white',
                            font=('Century Gothic', 10, 'bold'),
                            borderwidth=0,
                            padding=(16, 10))
        self.style.map('Accent.TButton',
                      background=[('active', self.COLORS['accent_light'])])
        
        self.style.configure('Small.TButton',
                            background=bg_elevated,
                            foreground=text,
                            font=('Century Gothic', 9),
                            borderwidth=0,
                            padding=(10, 6))
        self.style.map('Small.TButton',
                      background=[('active', border)])
        
        # Notebook (tabs) - inverted selection style
        self.style.configure('TNotebook', 
                            background=bg, 
                            borderwidth=0,
                            tabmargins=[0, 0, 0, 0])
        self.style.configure('TNotebook.Tab',
                            background=bg_glass,
                            foreground=text_muted,
                            padding=(24, 12),
                            font=('Century Gothic', 10),
                            borderwidth=0)
        self.style.map('TNotebook.Tab',
                      background=[('selected', bg_card)],
                      foreground=[('selected', text)],
                      padding=[('selected', (24, 14))],
                      font=[('selected', ('Century Gothic', 11, 'bold'))])
        
        # Treeview - clean modern look with better readability
        self.style.configure('Treeview',
                            background=bg_glass,
                            foreground=text,
                            fieldbackground=bg_glass,
                            borderwidth=0,
                            font=('Century Gothic', 11),
                            rowheight=38)
        self.style.configure('Treeview.Heading',
                            background=bg_card,
                            foreground=text_sec,
                            font=('Century Gothic', 10, 'bold'),
                            borderwidth=0,
                            padding=(12, 12))
        self.style.map('Treeview',
                      background=[('selected', accent)],
                      foreground=[('selected', 'white')])
        self.style.map('Treeview.Heading',
                      background=[('active', bg_elevated)])
        
        # Labelframe
        self.style.configure('TLabelframe', background=bg_card, borderwidth=1, relief='flat')
        self.style.configure('TLabelframe.Label', background=bg, foreground=text_sec, 
                            font=('Century Gothic', 9))
        
        # Progressbar - accent colored
        self.style.configure('TProgressbar',
                            background=accent,
                            troughcolor=bg_glass,
                            borderwidth=0,
                            thickness=3)
        
        # Scrollbar - minimal
        self.style.configure('TScrollbar',
                            background=bg_glass,
                            troughcolor=bg,
                            borderwidth=0,
                            arrowsize=0,
                            width=8)
        self.style.map('TScrollbar',
                      background=[('active', border)])
        
    def setup_ui(self):
        """Create the main UI"""
        bg = self.COLORS['bg']
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, style='TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame, style='TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.columnconfigure(1, weight=1)
        
        # Title
        ttk.Label(header_frame, text="Driver Update Scanner", 
                 style='Title.TLabel').grid(row=0, column=0, sticky="w")
        
        # Status (right side)
        status_frame = ttk.Frame(header_frame, style='TFrame')
        status_frame.grid(row=0, column=2, sticky="e")
        
        self.status_indicator = tk.Canvas(status_frame, width=8, height=8, 
                                          bg=bg, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self.status_indicator.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        
        self.status_label = ttk.Label(status_frame, text="Ready", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        # System info card
        sys_card = ttk.Frame(main_frame, style='Card.TFrame')
        sys_card.grid(row=1, column=0, sticky="ew", pady=(0, 16), ipady=12, ipadx=16)
        
        ttk.Label(sys_card, text="SYSTEM", style='CardTitle.TLabel').pack(anchor=tk.W, padx=16, pady=(12, 4))
        self.sysinfo_label = ttk.Label(sys_card, text="Click Scan to detect your system", style='Card.TLabel')
        self.sysinfo_label.pack(anchor=tk.W, padx=16, pady=(0, 12))
        
        # Notebook container
        notebook_container = ttk.Frame(main_frame, style='TFrame')
        notebook_container.grid(row=2, column=0, sticky="nsew", pady=(0, 16))
        notebook_container.columnconfigure(0, weight=1)
        notebook_container.rowconfigure(0, weight=1)
        
        self.notebook = ttk.Notebook(notebook_container)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Create tabs with card-style frames
        self.drivers_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.drivers_frame, text="   Installed   ")
        self.setup_drivers_tab()
        
        self.updates_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.updates_frame, text="   Updates   ")
        self.setup_updates_tab()
        
        self.online_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.online_frame, text="   Online   ")
        self.setup_online_tab()
        
        self.problems_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.problems_frame, text="   Issues   ")
        self.setup_problems_tab()
        
        self.mfr_tools_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.mfr_tools_frame, text="   Tools   ")
        self.setup_manufacturer_tools_tab()
        
        self.cleanup_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.cleanup_frame, text="   Cleanup   ")
        self.setup_cleanup_tab()
        
        self.disks_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.disks_frame, text="   Disks   ")
        self.setup_disks_tab()
        
        self.health_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.health_frame, text="   Health   ")
        self.setup_health_tab()
        
        self.log_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.log_frame, text="   Log   ")
        self.setup_log_tab()
        
        # Bottom action bar - responsive layout
        action_bar = ttk.Frame(main_frame, style='TFrame')
        action_bar.grid(row=3, column=0, sticky="ew")
        action_bar.columnconfigure(0, weight=1)
        
        # Use a single row that wraps content
        btn_frame = ttk.Frame(action_bar, style='TFrame')
        btn_frame.pack(fill=tk.X)
        
        # Primary actions (left side)
        self.scan_btn = ttk.Button(btn_frame, text="Scan System", 
                                   command=self.start_scan, style='Accent.TButton')
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 6))
        
        self.check_updates_btn = ttk.Button(btn_frame, text="Check Updates",
                                            command=self.check_online_updates)
        self.check_updates_btn.pack(side=tk.LEFT, padx=(0, 4))
        
        self.check_online_btn = ttk.Button(btn_frame, text="Online Sources",
                                           command=self.check_vendor_drivers)
        self.check_online_btn.pack(side=tk.LEFT, padx=(0, 4))
        
        self.install_btn = ttk.Button(btn_frame, text="Install",
                                      command=self.install_updates, state=tk.DISABLED)
        self.install_btn.pack(side=tk.LEFT)
        
        # Quick links (right side) - these will hide if window is too small
        ttk.Button(btn_frame, text="AMD", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.amd.com/en/support")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="NVIDIA", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.nvidia.com/Download/index.aspx")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="Intel", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.intel.com/content/www/us/en/support/detect.html")).pack(side=tk.RIGHT, padx=2)
        
        # Separator
        ttk.Frame(btn_frame, style='TFrame', width=8).pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="OEM", command=self.open_manufacturer_site,
                   style='Small.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="Export", command=self.export_report, 
                   style='Small.TButton').pack(side=tk.RIGHT, padx=2)
        
        # Status bar with progress and task info
        self.status_bar_frame = ttk.Frame(main_frame, style='Glass.TFrame')
        self.status_bar_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.status_bar_frame.columnconfigure(1, weight=1)
        
        # Task label (left)
        self.task_label = ttk.Label(self.status_bar_frame, text="Ready", 
                                    style='Card.TLabel', font=('Century Gothic', 9))
        self.task_label.grid(row=0, column=0, sticky="w", padx=(8, 16), pady=6)
        
        # Progress bar (center, expandable)
        self.progress = ttk.Progressbar(self.status_bar_frame, mode='determinate', 
                                        style='TProgressbar', length=200)
        self.progress.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        
        # Percentage label (right)
        self.percent_label = ttk.Label(self.status_bar_frame, text="", 
                                       style='Card.TLabel', font=('Century Gothic', 9), width=6)
        self.percent_label.grid(row=0, column=2, sticky="e", padx=(8, 12), pady=6)
        
    def setup_drivers_tab(self):
        """Setup the installed drivers tab"""
        self.drivers_frame.columnconfigure(0, weight=1)
        self.drivers_frame.rowconfigure(1, weight=1)
        
        # Header
        header = ttk.Frame(self.drivers_frame, style='Card.TFrame')
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        ttk.Label(header, text="Installed device drivers", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Treeview
        columns = ('Device', 'Manufacturer', 'Version', 'Date', 'Status')
        self.drivers_tree = ttk.Treeview(self.drivers_frame, columns=columns, show='headings')
        
        self.drivers_tree.heading('Device', text='Device')
        self.drivers_tree.heading('Manufacturer', text='Manufacturer')
        self.drivers_tree.heading('Version', text='Version')
        self.drivers_tree.heading('Date', text='Date')
        self.drivers_tree.heading('Status', text='Status')
        
        # Use minwidth and stretch for responsive columns
        self.drivers_tree.column('Device', width=280, minwidth=150, stretch=True)
        self.drivers_tree.column('Manufacturer', width=150, minwidth=100, stretch=True)
        self.drivers_tree.column('Version', width=120, minwidth=80, stretch=False)
        self.drivers_tree.column('Date', width=90, minwidth=70, stretch=False)
        self.drivers_tree.column('Status', width=70, minwidth=50, stretch=False)
        
        vsb = ttk.Scrollbar(self.drivers_frame, orient="vertical", command=self.drivers_tree.yview)
        self.drivers_tree.configure(yscrollcommand=vsb.set)
        
        self.drivers_tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))
        vsb.grid(row=1, column=1, sticky="ns", padx=(2, 16), pady=(0, 16))
        
    def setup_updates_tab(self):
        """Setup the available updates tab"""
        self.updates_frame.columnconfigure(0, weight=1)
        self.updates_frame.rowconfigure(1, weight=1)
        
        # Header
        header = ttk.Frame(self.updates_frame, style='Card.TFrame')
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        ttk.Label(header, text="Available updates from Windows Update", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Treeview
        columns = ('Select', 'Update', 'Publisher', 'Date', 'Restart')
        self.updates_tree = ttk.Treeview(self.updates_frame, columns=columns, show='headings', selectmode='extended')
        
        self.updates_tree.heading('Select', text='')
        self.updates_tree.heading('Update', text='Update')
        self.updates_tree.heading('Publisher', text='Publisher')
        self.updates_tree.heading('Date', text='Date')
        self.updates_tree.heading('Restart', text='')
        
        self.updates_tree.column('Select', width=40, anchor='center')
        self.updates_tree.column('Update', width=420)
        self.updates_tree.column('Publisher', width=180)
        self.updates_tree.column('Date', width=100)
        self.updates_tree.column('Restart', width=50, anchor='center')
        
        vsb = ttk.Scrollbar(self.updates_frame, orient="vertical", command=self.updates_tree.yview)
        self.updates_tree.configure(yscrollcommand=vsb.set)
        
        self.updates_tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 8))
        vsb.grid(row=1, column=1, sticky="ns", padx=(2, 16), pady=(0, 8))
        
        # Action bar
        action_bar = ttk.Frame(self.updates_frame, style='Card.TFrame')
        action_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        
        ttk.Button(action_bar, text="Select All", style='Small.TButton',
                   command=self.select_all_updates).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(action_bar, text="Clear", style='Small.TButton',
                   command=self.deselect_all_updates).pack(side=tk.LEFT, padx=(0, 12))
        
        self.download_install_btn = ttk.Button(action_bar, text="Download & Install", 
                                                command=self.download_and_install_selected,
                                                style='Accent.TButton')
        self.download_install_btn.pack(side=tk.LEFT)
        
        ttk.Button(action_bar, text="MS Catalog", style='Small.TButton',
                   command=self.open_update_catalog).pack(side=tk.RIGHT)
        
    def setup_problems_tab(self):
        """Setup the problem devices tab"""
        self.problems_frame.columnconfigure(0, weight=1)
        self.problems_frame.rowconfigure(1, weight=1)
        
        # Header
        header = ttk.Frame(self.problems_frame, style='Card.TFrame')
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        ttk.Label(header, text="Devices with missing or problematic drivers", style='Muted.TLabel').pack(side=tk.LEFT)
        
        columns = ('Device', 'Status', 'Error', 'ID')
        self.problems_tree = ttk.Treeview(self.problems_frame, columns=columns, show='headings')
        
        self.problems_tree.heading('Device', text='Device')
        self.problems_tree.heading('Status', text='Status')
        self.problems_tree.heading('Error', text='Error')
        self.problems_tree.heading('ID', text='Device ID')
        
        self.problems_tree.column('Device', width=300)
        self.problems_tree.column('Status', width=100)
        self.problems_tree.column('Error', width=80)
        self.problems_tree.column('ID', width=360)
        
        vsb = ttk.Scrollbar(self.problems_frame, orient="vertical", command=self.problems_tree.yview)
        self.problems_tree.configure(yscrollcommand=vsb.set)
        
        self.problems_tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))
        vsb.grid(row=1, column=1, sticky="ns", padx=(2, 16), pady=(0, 16))
        
    def setup_log_tab(self):
        """Setup the log tab"""
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, 
            wrap=tk.WORD, 
            font=('Consolas', 10),
            bg=self.COLORS['bg_glass'],
            fg=self.COLORS['text_secondary'],
            insertbackground=self.COLORS['text'],
            selectbackground=self.COLORS['accent'],
            relief='flat',
            padx=16,
            pady=16,
            borderwidth=0
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
    
    def setup_online_tab(self):
        """Setup the online driver sources tab"""
        self.online_frame.columnconfigure(0, weight=1)
        self.online_frame.rowconfigure(1, weight=1)
        
        # Header
        header = ttk.Frame(self.online_frame, style='Card.TFrame')
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        ttk.Label(header, text="Download drivers from vendor websites (double-click to open)", 
                 style='Muted.TLabel').pack(side=tk.LEFT)
        
        columns = ('Device', 'Version', 'Source', 'Description')
        self.online_tree = ttk.Treeview(self.online_frame, columns=columns, show='headings')
        
        self.online_tree.heading('Device', text='Device')
        self.online_tree.heading('Version', text='Installed')
        self.online_tree.heading('Source', text='Source')
        self.online_tree.heading('Description', text='Description')
        
        self.online_tree.column('Device', width=300)
        self.online_tree.column('Version', width=120)
        self.online_tree.column('Source', width=100)
        self.online_tree.column('Description', width=360)
        
        vsb = ttk.Scrollbar(self.online_frame, orient="vertical", command=self.online_tree.yview)
        self.online_tree.configure(yscrollcommand=vsb.set)
        
        self.online_tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 8))
        vsb.grid(row=1, column=1, sticky="ns", padx=(2, 16), pady=(0, 8))
        
        self.online_tree.bind('<Double-1>', self.on_online_driver_double_click)
        
        # Action bar
        action_bar = ttk.Frame(self.online_frame, style='Card.TFrame')
        action_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        
        ttk.Button(action_bar, text="Open Selected", style='Small.TButton',
                   command=self.open_selected_online_driver).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(action_bar, text="Open All", style='Small.TButton',
                   command=self.open_all_online_sources).pack(side=tk.LEFT)
    
    def setup_manufacturer_tools_tab(self):
        """Setup the manufacturer tools tab"""
        self.mfr_tools_frame.columnconfigure(0, weight=1)
        self.mfr_tools_frame.rowconfigure(2, weight=1)
        
        # System card
        sys_card = ttk.Frame(self.mfr_tools_frame, style='Glass.TFrame')
        sys_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        
        ttk.Label(sys_card, text="YOUR SYSTEM", style='CardTitle.TLabel').pack(anchor=tk.W, pady=(8, 4))
        self.mfr_sys_label = ttk.Label(sys_card, text="Scan to detect", style='Card.TLabel')
        self.mfr_sys_label.pack(anchor=tk.W, pady=(0, 8))
        
        # OEM links
        self.mfr_links_frame = ttk.Frame(self.mfr_tools_frame, style='Glass.TFrame')
        self.mfr_links_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        self.mfr_links_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.mfr_links_frame, text="OEM SUPPORT", style='CardTitle.TLabel').grid(row=0, column=0, sticky="w", pady=(8, 4), columnspan=2)
        ttk.Label(self.mfr_links_frame, text="Run scan to detect manufacturer", style='Card.TLabel').grid(row=1, column=0, sticky="w", pady=(0, 8))
        
        # Quick links
        quick_card = ttk.Frame(self.mfr_tools_frame, style='Glass.TFrame')
        quick_card.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 16))
        
        ttk.Label(quick_card, text="QUICK LINKS", style='CardTitle.TLabel').pack(anchor=tk.W, pady=(8, 12))
        
        # GPU row
        gpu_row = ttk.Frame(quick_card, style='Glass.TFrame')
        gpu_row.pack(fill=tk.X, pady=4)
        ttk.Label(gpu_row, text="Graphics", style='Card.TLabel', width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(gpu_row, text="NVIDIA", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.nvidia.com/Download/index.aspx")).pack(side=tk.LEFT, padx=2)
        ttk.Button(gpu_row, text="AMD", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.amd.com/en/support")).pack(side=tk.LEFT, padx=2)
        ttk.Button(gpu_row, text="Intel", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.intel.com/content/www/us/en/download/785597/intel-arc-iris-xe-graphics-windows.html")).pack(side=tk.LEFT, padx=2)
        
        # Intel row
        intel_row = ttk.Frame(quick_card, style='Glass.TFrame')
        intel_row.pack(fill=tk.X, pady=4)
        ttk.Label(intel_row, text="Intel", style='Card.TLabel', width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(intel_row, text="Driver Assistant", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.intel.com/content/www/us/en/support/detect.html")).pack(side=tk.LEFT, padx=2)
        ttk.Button(intel_row, text="Downloads", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.intel.com/content/www/us/en/download-center/home.html")).pack(side=tk.LEFT, padx=2)
        
        # Other row
        other_row = ttk.Frame(quick_card, style='Glass.TFrame')
        other_row.pack(fill=tk.X, pady=4)
        ttk.Label(other_row, text="Other", style='Card.TLabel', width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(other_row, text="Realtek Audio", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.realtek.com/en/component/zoo/category/pc-audio-codecs-high-definition-audio-codecs-software")).pack(side=tk.LEFT, padx=2)
        ttk.Button(other_row, text="Realtek LAN", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software")).pack(side=tk.LEFT, padx=2)
        ttk.Button(other_row, text="MS Catalog", style='Small.TButton',
                   command=lambda: webbrowser.open("https://www.catalog.update.microsoft.com/Home.aspx")).pack(side=tk.LEFT, padx=2)
    
    def setup_cleanup_tab(self):
        """Setup the driver cleanup tab for finding unused/outdated drivers"""
        self.cleanup_frame.columnconfigure(0, weight=1)
        self.cleanup_frame.rowconfigure(2, weight=1)
        
        # Header card
        header_card = ttk.Frame(self.cleanup_frame, style='Glass.TFrame')
        header_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        
        ttk.Label(header_card, text="DRIVER CLEANUP", style='CardTitle.TLabel').pack(anchor=tk.W, pady=(8, 4))
        ttk.Label(header_card, text="Find unused drivers, phantom devices, and old driver versions using advanced detection", 
                 style='Card.TLabel').pack(anchor=tk.W, pady=(0, 8))
        
        # Action buttons
        btn_row = ttk.Frame(header_card, style='Glass.TFrame')
        btn_row.pack(fill=tk.X, pady=(0, 8))
        
        self.scan_cleanup_btn = ttk.Button(btn_row, text="Scan for Cleanup", style='Accent.TButton',
                                           command=self.scan_cleanup_drivers)
        self.scan_cleanup_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.remove_unused_btn = ttk.Button(btn_row, text="Remove Selected", 
                                            command=self.remove_unused_drivers, state=tk.DISABLED)
        self.remove_unused_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        self.create_restore_btn = ttk.Button(btn_row, text="Create Restore Point", style='Small.TButton',
                                              command=self.create_restore_point)
        self.create_restore_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Label(btn_row, text="⚠ Create a restore point before removing drivers",
                 style='Card.TLabel', foreground='#ffaa00').pack(side=tk.LEFT, padx=8)
        
        # Legend
        legend_row = ttk.Frame(header_card, style='Glass.TFrame')
        legend_row.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(legend_row, text="Risk: ", style='Card.TLabel').pack(side=tk.LEFT)
        ttk.Label(legend_row, text="● Safe", style='Card.TLabel', foreground='#22c55e').pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(legend_row, text="● Caution", style='Card.TLabel', foreground='#eab308').pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(legend_row, text="Categories: GPU | Audio | Network | USB | Printer | Input | Storage | Other", 
                 style='Muted.TLabel').pack(side=tk.LEFT, padx=(20, 0))
        
        # Unused drivers section
        unused_card = ttk.Frame(self.cleanup_frame, style='Glass.TFrame')
        unused_card.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        unused_card.columnconfigure(0, weight=1)
        unused_card.rowconfigure(1, weight=1)
        
        ttk.Label(unused_card, text="REMOVABLE DRIVERS", 
                 style='CardTitle.TLabel').grid(row=0, column=0, sticky="w", pady=(8, 8))
        
        unused_tree_frame = ttk.Frame(unused_card, style='Glass.TFrame')
        unused_tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        unused_tree_frame.columnconfigure(0, weight=1)
        unused_tree_frame.rowconfigure(0, weight=1)
        
        self.unused_tree = ttk.Treeview(unused_tree_frame, 
                                         columns=("risk", "category", "name", "inf", "provider", "reason"),
                                         show="headings", style='Driver.Treeview', height=8, selectmode="extended")
        self.unused_tree.heading("risk", text="Risk")
        self.unused_tree.heading("category", text="Category")
        self.unused_tree.heading("name", text="Driver Name")
        self.unused_tree.heading("inf", text="INF File")
        self.unused_tree.heading("provider", text="Provider")
        self.unused_tree.heading("reason", text="Reason")
        self.unused_tree.column("risk", width=60, stretch=False, anchor='center')
        self.unused_tree.column("category", width=80, stretch=False)
        self.unused_tree.column("name", width=200, stretch=True)
        self.unused_tree.column("inf", width=100, stretch=False)
        self.unused_tree.column("provider", width=120, stretch=False)
        self.unused_tree.column("reason", width=250, stretch=True)
        self.unused_tree.grid(row=0, column=0, sticky="nsew")
        
        # Configure tags for risk colors
        self.unused_tree.tag_configure('safe', foreground='#22c55e')
        self.unused_tree.tag_configure('caution', foreground='#eab308')
        self.unused_tree.tag_configure('protected', foreground='#3b82f6')
        
        unused_scroll = ttk.Scrollbar(unused_tree_frame, orient=tk.VERTICAL, command=self.unused_tree.yview)
        unused_scroll.grid(row=0, column=1, sticky="ns")
        self.unused_tree.configure(yscrollcommand=unused_scroll.set)
        
        # Outdated drivers section
        outdated_card = ttk.Frame(self.cleanup_frame, style='Glass.TFrame')
        outdated_card.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 16))
        outdated_card.columnconfigure(0, weight=1)
        outdated_card.rowconfigure(1, weight=1)
        
        ttk.Label(outdated_card, text="OLD DRIVER VERSIONS (Consider updating)", 
                 style='CardTitle.TLabel').grid(row=0, column=0, sticky="w", pady=(8, 8))
        
        outdated_tree_frame = ttk.Frame(outdated_card, style='Glass.TFrame')
        outdated_tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        outdated_tree_frame.columnconfigure(0, weight=1)
        outdated_tree_frame.rowconfigure(0, weight=1)
        
        self.outdated_tree = ttk.Treeview(outdated_tree_frame, 
                                           columns=("name", "installed", "available", "manufacturer"),
                                           show="headings", style='Driver.Treeview', height=6, selectmode="extended")
        self.outdated_tree.heading("name", text="Device Name")
        self.outdated_tree.heading("installed", text="Installed Version")
        self.outdated_tree.heading("available", text="Latest Version")
        self.outdated_tree.heading("manufacturer", text="Manufacturer")
        self.outdated_tree.column("name", width=300, stretch=True)
        self.outdated_tree.column("installed", width=150, stretch=False)
        self.outdated_tree.column("available", width=150, stretch=False)
        self.outdated_tree.column("manufacturer", width=150, stretch=False)
        self.outdated_tree.grid(row=0, column=0, sticky="nsew")
        
        outdated_scroll = ttk.Scrollbar(outdated_tree_frame, orient=tk.VERTICAL, command=self.outdated_tree.yview)
        outdated_scroll.grid(row=0, column=1, sticky="ns")
        self.outdated_tree.configure(yscrollcommand=outdated_scroll.set)
        
        # Status label with summary
        status_frame = ttk.Frame(self.cleanup_frame, style='Glass.TFrame')
        status_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        
        self.cleanup_status = ttk.Label(status_frame, 
                                        text="Click 'Scan for Cleanup' to analyze drivers using pnputil and WMI",
                                        style='Card.TLabel')
        self.cleanup_status.pack(side=tk.LEFT)
        
        self.driver_store_size = ttk.Label(status_frame, text="", style='Muted.TLabel')
        self.driver_store_size.pack(side=tk.RIGHT)
    
    def create_restore_point(self):
        """Create a system restore point before driver cleanup"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "Creating a restore point requires administrator privileges.")
            return
        
        if messagebox.askyesno("Create Restore Point",
                "This will create a system restore point.\n\n"
                "This is recommended before removing any drivers.\n"
                "Continue?"):
            
            self.set_status("Creating restore point...", "busy")
            self.update_task_status("Creating restore point...", 50)
            
            thread = threading.Thread(target=self.perform_restore_point_creation)
            thread.daemon = True
            thread.start()
    
    def perform_restore_point_creation(self):
        """Create restore point in background"""
        try:
            command = '''
            Checkpoint-Computer -Description "Driver Cleanup - $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -RestorePointType "MODIFY_SETTINGS"
            '''
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    "Restore point created successfully.\n\nYou can now safely remove drivers."))
                self.root.after(0, lambda: self.log_message("Created system restore point"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("Warning",
                    f"Could not create restore point:\n{result.stderr}\n\n"
                    "You may need to enable System Restore."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to create restore point: {e}"))
        finally:
            self.root.after(0, lambda: self.set_status("Ready", "success"))
            self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def scan_cleanup_drivers(self):
        """Scan for unused and outdated drivers"""
        self.scan_cleanup_btn.config(state=tk.DISABLED)
        self.remove_unused_btn.config(state=tk.DISABLED)
        self.set_status("Scanning for cleanup...", "busy")
        self.update_task_status("Cleanup: Scanning driver store...", 0)
        
        # Clear existing items
        for item in self.unused_tree.get_children():
            self.unused_tree.delete(item)
        for item in self.outdated_tree.get_children():
            self.outdated_tree.delete(item)
        
        self.cleanup_status.config(text="Scanning driver store...")
        
        thread = threading.Thread(target=self.perform_cleanup_scan)
        thread.daemon = True
        thread.start()
    
    def perform_cleanup_scan(self):
        """Perform cleanup scan in background"""
        try:
            # Scan for unused drivers
            self.root.after(0, lambda: self.update_task_status("Cleanup: Finding unused drivers...", 25))
            unused_drivers = self.scanner.find_unused_drivers()
            
            # Scan for outdated drivers
            self.root.after(0, lambda: self.update_task_status("Cleanup: Checking driver versions...", 50))
            installed = self.scanner.scan_installed_drivers()
            outdated_drivers = self.scanner.find_old_drivers()
            
            self.root.after(0, lambda: self.update_task_status("Cleanup: Processing results...", 75))
            
            # Update UI
            self.root.after(0, lambda: self.populate_cleanup_results(unused_drivers, outdated_drivers))
            
        except Exception as e:
            self.root.after(0, lambda: self.cleanup_status.config(text=f"Error during scan: {str(e)}"))
            self.root.after(0, lambda e=e: self.log_message(f"Cleanup scan error: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.scan_cleanup_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.set_status("Cleanup scan complete", "success"))
            self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def populate_cleanup_results(self, unused_drivers: List[dict], outdated_drivers: List[dict]):
        """Populate cleanup results in treeviews"""
        # Risk symbols
        risk_symbols = {
            'safe': '●',
            'caution': '⚠',
            'protected': '🔒'
        }
        
        # Add unused drivers with risk-based colors
        for i, driver in enumerate(unused_drivers):
            risk = driver.get('risk', 'safe')
            risk_symbol = risk_symbols.get(risk, '●')
            
            self.unused_tree.insert("", tk.END, values=(
                f"{risk_symbol} {risk.title()}",
                driver.get('category', 'Other'),
                driver.get('name', driver.get('driver', 'Unknown')),
                driver.get('driver', ''),
                driver.get('provider', ''),
                driver.get('reason', '')
            ), tags=(risk,))
        
        # Add outdated drivers with alternating colors
        for i, driver in enumerate(outdated_drivers):
            tag = 'oddrow' if i % 2 else 'evenrow'
            self.outdated_tree.insert("", tk.END, values=(
                driver.get('name', 'Unknown'),
                driver.get('version', ''),
                driver.get('latest_version', 'N/A'),
                driver.get('manufacturer', '')
            ), tags=(tag,))
        
        # Enable remove button if there are unused drivers
        if unused_drivers:
            self.remove_unused_btn.config(state=tk.NORMAL)
        
        # Count by risk
        safe_count = sum(1 for d in unused_drivers if d.get('risk') == 'safe')
        caution_count = sum(1 for d in unused_drivers if d.get('risk') == 'caution')
        
        # Update status
        unused_count = len(unused_drivers)
        outdated_count = len(outdated_drivers)
        self.cleanup_status.config(
            text=f"Found {unused_count} removable drivers ({safe_count} safe, {caution_count} caution) and {outdated_count} old versions")
        
        # Get driver store size
        summary = self.scanner.get_driver_cleanup_summary()
        if summary.get('EstimatedSizeMB'):
            self.driver_store_size.config(text=f"Driver Store: {summary.get('EstimatedSizeMB', 0):.1f} MB")
        
        self.log_message(f"Cleanup scan complete: {unused_count} removable, {outdated_count} outdated drivers")
    
    def remove_unused_drivers(self):
        """Remove selected unused drivers from the driver store"""
        selected = self.unused_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select drivers to remove from the list.")
            return
        
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "Removing drivers requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        # Get INF files for selected items (INF is now column index 3)
        inf_files = []
        caution_count = 0
        for item in selected:
            values = self.unused_tree.item(item, 'values')
            if values and len(values) > 3:
                inf_files.append(values[3])  # INF file is fourth column (index 3)
                if 'caution' in str(values[0]).lower():
                    caution_count += 1
        
        if not inf_files:
            return
        
        # Extra warning for caution drivers
        warning_msg = f"Are you sure you want to remove {len(inf_files)} driver(s)?\n\n"
        if caution_count > 0:
            warning_msg += f"⚠ {caution_count} driver(s) marked as CAUTION - proceed carefully!\n\n"
        warning_msg += "This action cannot be undone.\n"
        warning_msg += "Click 'Create Restore Point' first if you haven't.\n\n"
        warning_msg += "Continue?"
        
        if messagebox.askyesno("Confirm Removal", warning_msg):
            
            self.remove_unused_btn.config(state=tk.DISABLED)
            self.set_status("Removing drivers...", "busy")
            
            thread = threading.Thread(target=self.perform_driver_removal, args=(inf_files,))
            thread.daemon = True
            thread.start()
    
    def check_driver_in_use(self, inf_name: str) -> bool:
        """Check if a driver is currently in use by any device"""
        try:
            # Method 1: Check pnputil for devices using this driver
            result = subprocess.run(
                ['pnputil', '/enum-devices', '/drivers'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if inf_name.lower() in result.stdout.lower():
                # Found in active devices list
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if inf_name.lower() in line.lower():
                        # Check if device is connected/present
                        for j in range(max(0, i-5), min(len(lines), i+5)):
                            if 'Status:' in lines[j] and 'Started' in lines[j]:
                                return True
            
            # Method 2: Try a dry-run style check by checking if driver is referenced
            result2 = subprocess.run(
                ['pnputil', '/enum-drivers'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # If the driver is in the store, we need to verify it's not actively bound
            # Check WMI for active driver bindings
            ps_cmd = f'''
            $inUse = $false
            Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | 
            Where-Object {{ $_.InfName -eq '{inf_name}' }} |
            ForEach-Object {{
                # Check if device with this driver is present
                $deviceId = $_.DeviceID
                if ($deviceId) {{
                    $device = Get-CimInstance Win32_PnPEntity -Filter "DeviceID='$($deviceId -replace '\\\\', '\\\\\\\\')'" -ErrorAction SilentlyContinue
                    if ($device -and $device.Status -eq 'OK') {{
                        $inUse = $true
                    }}
                }}
            }}
            $inUse
            '''
            result3 = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if 'True' in result3.stdout:
                return True
                
            return False
        except:
            return False  # Assume not in use if we can't check
    
    def perform_driver_removal(self, inf_files: List[str]):
        """Remove drivers in background with smart in-use detection"""
        removed = 0
        skipped = 0
        errors = []
        skipped_drivers = []
        
        # First pass: check which drivers are actually removable
        self.root.after(0, lambda: self.update_task_status("Checking driver status...", 0))
        
        removable_drivers = []
        for i, inf in enumerate(inf_files):
            self.root.after(0, lambda i=i, t=len(inf_files): 
                           self.update_task_status(f"Checking driver {i+1}/{t}...", int((i/t)*50)))
            
            # Quick check if driver is in use
            if self.check_driver_in_use(inf):
                skipped += 1
                skipped_drivers.append(inf)
                self.root.after(0, lambda inf=inf: 
                               self.log_message(f"Skipped (in use): {inf}"))
            else:
                removable_drivers.append(inf)
        
        # Second pass: remove only the removable drivers
        for i, inf in enumerate(removable_drivers):
            progress = 50 + int((i / max(1, len(removable_drivers))) * 50)
            self.root.after(0, lambda i=i, t=len(removable_drivers), p=progress: 
                           self.update_task_status(f"Removing driver {i+1}/{t}...", p))
            try:
                # Use pnputil to delete driver
                result = subprocess.run(
                    ['pnputil', '/delete-driver', inf, '/force'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    removed += 1
                    self.root.after(0, lambda inf=inf: 
                                   self.log_message(f"Removed driver: {inf}"))
                else:
                    output = result.stderr.strip() or result.stdout.strip()
                    # Check for "in use" error
                    if "presently installed" in output.lower() or "in use" in output.lower():
                        skipped += 1
                        skipped_drivers.append(inf)
                        self.root.after(0, lambda inf=inf: 
                                       self.log_message(f"Skipped (active device): {inf}"))
                    else:
                        errors.append(f"{inf}: {output}")
                        self.root.after(0, lambda inf=inf, err=output: 
                                       self.log_message(f"Failed to remove {inf}: {err}"))
                    
            except Exception as e:
                errors.append(f"{inf}: {str(e)}")
        
        # Update UI
        self.root.after(0, lambda: self.scan_cleanup_drivers())  # Refresh list
        
        # Build summary message
        summary_parts = [f"✓ Removed: {removed} driver(s)"]
        
        if skipped > 0:
            summary_parts.append(f"\n⚠ Skipped: {skipped} driver(s) - currently in use by Windows")
            summary_parts.append("\n\nSkipped drivers are actively used by your hardware")
            summary_parts.append("and cannot be safely removed. This is expected.")
        
        if errors:
            summary_parts.append(f"\n\n✗ Failed: {len(errors)} driver(s)")
            error_msg = "\n".join(errors[:3])
            if len(errors) > 3:
                error_msg += f"\n... and {len(errors) - 3} more"
            summary_parts.append(f"\n{error_msg}")
        
        final_message = "".join(summary_parts)
        
        if errors:
            self.root.after(0, lambda: messagebox.showwarning("Removal Complete", final_message))
        elif skipped > 0:
            self.root.after(0, lambda: messagebox.showinfo("Removal Complete", final_message))
        else:
            self.root.after(0, lambda: messagebox.showinfo("Success", final_message))
        
        self.root.after(0, lambda: self.set_status(f"Removed {removed}, skipped {skipped} drivers", "success"))
        self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def setup_disks_tab(self):
        """Setup the disk manager tab"""
        self.disks_frame.columnconfigure(0, weight=1)
        self.disks_frame.rowconfigure(1, weight=1)
        
        # Header card
        header_card = ttk.Frame(self.disks_frame, style='Glass.TFrame')
        header_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        
        header_row = ttk.Frame(header_card, style='Glass.TFrame')
        header_row.pack(fill=tk.X, pady=(8, 4))
        
        ttk.Label(header_row, text="DISK MANAGER", style='CardTitle.TLabel').pack(side=tk.LEFT)
        
        self.refresh_disks_btn = ttk.Button(header_row, text="Refresh", style='Small.TButton',
                                            command=self.refresh_disk_info)
        self.refresh_disks_btn.pack(side=tk.RIGHT, padx=(0, 8))
        
        ttk.Label(header_card, text="View disk information, health status, and run disk checks", 
                 style='Card.TLabel').pack(anchor=tk.W, pady=(0, 8))
        
        # Main content - split into disk list and details
        content_frame = ttk.Frame(self.disks_frame, style='Card.TFrame')
        content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # Left side - Disk list
        disk_list_card = ttk.Frame(content_frame, style='Glass.TFrame')
        disk_list_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        disk_list_card.columnconfigure(0, weight=1)
        disk_list_card.rowconfigure(1, weight=1)
        
        ttk.Label(disk_list_card, text="VOLUMES", style='CardTitle.TLabel').grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 8))
        
        # Disk treeview
        disk_tree_frame = ttk.Frame(disk_list_card, style='Glass.TFrame')
        disk_tree_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        disk_tree_frame.columnconfigure(0, weight=1)
        disk_tree_frame.rowconfigure(0, weight=1)
        
        self.disk_tree = ttk.Treeview(disk_tree_frame, 
                                       columns=("drive", "label", "filesystem", "size", "free", "health"),
                                       show="headings", style='Driver.Treeview', height=10, selectmode="browse")
        self.disk_tree.heading("drive", text="Drive")
        self.disk_tree.heading("label", text="Label")
        self.disk_tree.heading("filesystem", text="FS")
        self.disk_tree.heading("size", text="Size")
        self.disk_tree.heading("free", text="Free")
        self.disk_tree.heading("health", text="Status")
        self.disk_tree.column("drive", width=50, stretch=False, anchor='center')
        self.disk_tree.column("label", width=120, stretch=True)
        self.disk_tree.column("filesystem", width=60, stretch=False)
        self.disk_tree.column("size", width=70, stretch=False, anchor='e')
        self.disk_tree.column("free", width=70, stretch=False, anchor='e')
        self.disk_tree.column("health", width=80, stretch=False, anchor='center')
        self.disk_tree.grid(row=0, column=0, sticky="nsew")
        
        disk_scroll = ttk.Scrollbar(disk_tree_frame, orient=tk.VERTICAL, command=self.disk_tree.yview)
        disk_scroll.grid(row=0, column=1, sticky="ns")
        self.disk_tree.configure(yscrollcommand=disk_scroll.set)
        
        # Bind selection event
        self.disk_tree.bind('<<TreeviewSelect>>', self.on_disk_selected)
        
        # Right side - Disk details and actions
        details_card = ttk.Frame(content_frame, style='Glass.TFrame')
        details_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        details_card.columnconfigure(0, weight=1)
        
        ttk.Label(details_card, text="DISK DETAILS", style='CardTitle.TLabel').grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 8))
        
        # Details area
        self.disk_details_frame = ttk.Frame(details_card, style='Glass.TFrame')
        self.disk_details_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.disk_details_frame.columnconfigure(1, weight=1)
        
        # Create detail labels
        detail_labels = [
            ("Drive:", "disk_drive"),
            ("Label:", "disk_label"),
            ("File System:", "disk_fs"),
            ("Total Size:", "disk_size"),
            ("Free Space:", "disk_free"),
            ("Used:", "disk_used"),
            ("Health:", "disk_health"),
            ("Physical Disk:", "disk_physical"),
            ("Media Type:", "disk_media"),
            ("Partition Style:", "disk_partition"),
        ]
        
        self.disk_detail_values = {}
        for i, (label, key) in enumerate(detail_labels):
            ttk.Label(self.disk_details_frame, text=label, style='Card.TLabel').grid(
                row=i, column=0, sticky="w", pady=2)
            value_label = ttk.Label(self.disk_details_frame, text="-", style='Muted.TLabel')
            value_label.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=2)
            self.disk_detail_values[key] = value_label
        
        # Actions section
        actions_frame = ttk.Frame(details_card, style='Glass.TFrame')
        actions_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(16, 8))
        
        ttk.Label(actions_frame, text="ACTIONS", style='CardTitle.TLabel').pack(anchor=tk.W, pady=(0, 8))
        
        # Check Disk button
        chkdsk_row = ttk.Frame(actions_frame, style='Glass.TFrame')
        chkdsk_row.pack(fill=tk.X, pady=4)
        
        self.disk_chkdsk_btn = ttk.Button(chkdsk_row, text="Check Disk (CHKDSK)", style='Accent.TButton',
                                          command=self.run_chkdsk_on_selected, state=tk.DISABLED)
        self.disk_chkdsk_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(chkdsk_row, text="Scan for errors", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Repair Disk button
        repair_row = ttk.Frame(actions_frame, style='Glass.TFrame')
        repair_row.pack(fill=tk.X, pady=4)
        
        self.disk_repair_btn = ttk.Button(repair_row, text="Repair Disk (CHKDSK /F)", style='Small.TButton',
                                          command=self.run_chkdsk_repair_on_selected, state=tk.DISABLED)
        self.disk_repair_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(repair_row, text="Fix errors (may require restart)", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Optimize button
        optimize_row = ttk.Frame(actions_frame, style='Glass.TFrame')
        optimize_row.pack(fill=tk.X, pady=4)
        
        self.disk_optimize_btn = ttk.Button(optimize_row, text="Optimize Drive", style='Small.TButton',
                                            command=self.optimize_selected_disk, state=tk.DISABLED)
        self.disk_optimize_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(optimize_row, text="Defrag HDD / TRIM SSD", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Disk Cleanup button
        cleanup_row = ttk.Frame(actions_frame, style='Glass.TFrame')
        cleanup_row.pack(fill=tk.X, pady=4)
        
        self.disk_cleanup_btn = ttk.Button(cleanup_row, text="Disk Cleanup", style='Small.TButton',
                                           command=self.run_disk_cleanup, state=tk.DISABLED)
        self.disk_cleanup_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(cleanup_row, text="Remove temporary files", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Open in Explorer button
        explorer_row = ttk.Frame(actions_frame, style='Glass.TFrame')
        explorer_row.pack(fill=tk.X, pady=4)
        
        self.open_explorer_btn = ttk.Button(explorer_row, text="Open in Explorer", style='Small.TButton',
                                            command=self.open_disk_in_explorer, state=tk.DISABLED)
        self.open_explorer_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # Output area
        output_card = ttk.Frame(self.disks_frame, style='Glass.TFrame')
        output_card.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        output_card.columnconfigure(0, weight=1)
        
        ttk.Label(output_card, text="DISK OPERATIONS LOG", style='CardTitle.TLabel').grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        
        self.disk_output = scrolledtext.ScrolledText(
            output_card, 
            wrap=tk.WORD, 
            font=('Consolas', 9),
            bg=self.COLORS['bg_glass'],
            fg=self.COLORS['text'],
            insertbackground=self.COLORS['text'],
            selectbackground=self.COLORS['accent'],
            relief='flat',
            padx=12,
            pady=8,
            borderwidth=0,
            height=6
        )
        self.disk_output.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        
        # Configure text tags
        self.disk_output.tag_configure('good', foreground='#22c55e')
        self.disk_output.tag_configure('warning', foreground='#eab308')
        self.disk_output.tag_configure('error', foreground='#ef4444')
        self.disk_output.tag_configure('info', foreground='#3b82f6')
        
        # Store disk data
        self.disk_data = {}
        
        # Initial load
        self.root.after(100, self.refresh_disk_info)
    
    def refresh_disk_info(self):
        """Refresh disk information"""
        self.refresh_disks_btn.config(state=tk.DISABLED)
        self.set_status("Refreshing disk info...", "busy")
        self.update_task_status("Disk: Scanning...", 50)
        
        # Clear existing
        for item in self.disk_tree.get_children():
            self.disk_tree.delete(item)
        
        thread = threading.Thread(target=self.perform_disk_refresh)
        thread.daemon = True
        thread.start()
    
    def perform_disk_refresh(self):
        """Perform disk info refresh in background"""
        command = """
        $disks = @()
        
        # Get volumes
        $volumes = Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' }
        
        foreach ($vol in $volumes) {
            $diskInfo = @{
                DriveLetter = $vol.DriveLetter
                Label = $vol.FileSystemLabel
                FileSystem = $vol.FileSystem
                Size = $vol.Size
                SizeRemaining = $vol.SizeRemaining
                HealthStatus = $vol.HealthStatus
                DriveType = $vol.DriveType
            }
            
            # Try to get physical disk info
            try {
                $partition = Get-Partition -DriveLetter $vol.DriveLetter -ErrorAction SilentlyContinue
                if ($partition) {
                    $physicalDisk = Get-PhysicalDisk | Where-Object { 
                        $_.DeviceId -eq $partition.DiskNumber 
                    } | Select-Object -First 1
                    
                    if ($physicalDisk) {
                        $diskInfo.PhysicalDisk = $physicalDisk.FriendlyName
                        $diskInfo.MediaType = $physicalDisk.MediaType
                        $diskInfo.PhysicalHealth = $physicalDisk.HealthStatus
                        $diskInfo.DiskNumber = $partition.DiskNumber
                    }
                    
                    $disk = Get-Disk -Number $partition.DiskNumber -ErrorAction SilentlyContinue
                    if ($disk) {
                        $diskInfo.PartitionStyle = $disk.PartitionStyle
                    }
                }
            } catch {}
            
            # Check if dirty (needs CHKDSK)
            try {
                $dirty = (fsutil dirty query "$($vol.DriveLetter):" 2>$null) -match "dirty"
                $diskInfo.NeedsCheck = $dirty
            } catch {
                $diskInfo.NeedsCheck = $false
            }
            
            $disks += $diskInfo
        }
        
        $disks | ConvertTo-Json -Depth 3
        """
        
        try:
            output = self.scanner.run_powershell(command)
            disks = json.loads(output) if output.strip() else []
            if isinstance(disks, dict):
                disks = [disks]
            
            self.root.after(0, lambda: self.populate_disk_list(disks))
        except Exception as e:
            self.root.after(0, lambda: self.append_disk_output(f"Error refreshing disks: {e}\n", 'error'))
        finally:
            self.root.after(0, lambda: self.refresh_disks_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.set_status("Ready", "success"))
            self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def populate_disk_list(self, disks):
        """Populate disk list treeview"""
        self.disk_data = {}
        
        for i, disk in enumerate(disks):
            drive = disk.get('DriveLetter', '?')
            label = disk.get('Label', '') or 'Local Disk'
            fs = disk.get('FileSystem', '')
            size_bytes = disk.get('Size', 0)
            free_bytes = disk.get('SizeRemaining', 0)
            health = disk.get('HealthStatus', 'Unknown')
            
            # Format sizes
            size_gb = f"{size_bytes / (1024**3):.1f} GB" if size_bytes else "-"
            free_gb = f"{free_bytes / (1024**3):.1f} GB" if free_bytes else "-"
            
            # Determine status display
            needs_check = disk.get('NeedsCheck', False)
            if needs_check:
                status = "⚠ Check"
            elif health == 'Healthy':
                status = "● OK"
            else:
                status = f"● {health}"
            
            tag = 'oddrow' if i % 2 else 'evenrow'
            item_id = self.disk_tree.insert("", tk.END, values=(
                f"{drive}:",
                label,
                fs,
                size_gb,
                free_gb,
                status
            ), tags=(tag,))
            
            # Store full data
            self.disk_data[item_id] = disk
        
        self.append_disk_output(f"Found {len(disks)} volume(s)\n", 'info')
    
    def on_disk_selected(self, event):
        """Handle disk selection"""
        selected = self.disk_tree.selection()
        if not selected:
            return
        
        item_id = selected[0]
        disk = self.disk_data.get(item_id, {})
        
        if not disk:
            return
        
        # Update detail labels
        drive = disk.get('DriveLetter', '?')
        size_bytes = disk.get('Size', 0)
        free_bytes = disk.get('SizeRemaining', 0)
        used_bytes = size_bytes - free_bytes if size_bytes and free_bytes else 0
        used_pct = (used_bytes / size_bytes * 100) if size_bytes else 0
        
        self.disk_detail_values['disk_drive'].config(text=f"{drive}:")
        self.disk_detail_values['disk_label'].config(text=disk.get('Label', 'Local Disk') or 'Local Disk')
        self.disk_detail_values['disk_fs'].config(text=disk.get('FileSystem', '-'))
        self.disk_detail_values['disk_size'].config(text=f"{size_bytes / (1024**3):.2f} GB" if size_bytes else "-")
        self.disk_detail_values['disk_free'].config(text=f"{free_bytes / (1024**3):.2f} GB" if free_bytes else "-")
        self.disk_detail_values['disk_used'].config(text=f"{used_bytes / (1024**3):.2f} GB ({used_pct:.1f}%)" if used_bytes else "-")
        self.disk_detail_values['disk_health'].config(text=disk.get('HealthStatus', '-'))
        self.disk_detail_values['disk_physical'].config(text=disk.get('PhysicalDisk', '-'))
        self.disk_detail_values['disk_media'].config(text=disk.get('MediaType', '-'))
        self.disk_detail_values['disk_partition'].config(text=disk.get('PartitionStyle', '-'))
        
        # Enable action buttons
        self.disk_chkdsk_btn.config(state=tk.NORMAL)
        self.disk_repair_btn.config(state=tk.NORMAL)
        self.disk_optimize_btn.config(state=tk.NORMAL)
        self.disk_cleanup_btn.config(state=tk.NORMAL)
        self.open_explorer_btn.config(state=tk.NORMAL)
    
    def get_selected_drive(self):
        """Get the currently selected drive letter"""
        selected = self.disk_tree.selection()
        if not selected:
            return None
        
        disk = self.disk_data.get(selected[0], {})
        return disk.get('DriveLetter')
    
    def run_chkdsk_on_selected(self):
        """Run CHKDSK on selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            messagebox.showinfo("No Selection", "Please select a drive first.")
            return
        
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "CHKDSK requires administrator privileges.")
            return
        
        if messagebox.askyesno("Run CHKDSK",
                f"Run disk check on {drive}: drive?\n\n"
                "This will scan the drive for errors without fixing them.\n"
                "The drive will remain accessible during the scan."):
            
            self.disk_chkdsk_btn.config(state=tk.DISABLED)
            self.set_status(f"Running CHKDSK on {drive}:...", "busy")
            self.append_disk_output(f"\n{'='*40}\n", 'info')
            self.append_disk_output(f"Starting CHKDSK on {drive}: ...\n", 'info')
            
            thread = threading.Thread(target=self.perform_chkdsk, args=(drive, False))
            thread.daemon = True
            thread.start()
    
    def run_chkdsk_repair_on_selected(self):
        """Run CHKDSK /F on selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            messagebox.showinfo("No Selection", "Please select a drive first.")
            return
        
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "CHKDSK requires administrator privileges.")
            return
        
        # Check if it's the system drive
        is_system = drive.upper() == os.environ.get('SystemDrive', 'C')[0].upper()
        
        if is_system:
            if messagebox.askyesno("Schedule CHKDSK",
                    f"The {drive}: drive is the system drive.\n\n"
                    "CHKDSK /F cannot run while Windows is running.\n"
                    "Would you like to schedule it for the next restart?"):
                
                self.schedule_chkdsk_on_restart(drive)
        else:
            if messagebox.askyesno("Run CHKDSK /F",
                    f"Run disk repair on {drive}: drive?\n\n"
                    "This will scan and fix errors on the drive.\n"
                    "The drive may be locked during the repair."):
                
                self.disk_repair_btn.config(state=tk.DISABLED)
                self.set_status(f"Running CHKDSK /F on {drive}:...", "busy")
                self.append_disk_output(f"\n{'='*40}\n", 'info')
                self.append_disk_output(f"Starting CHKDSK /F on {drive}: ...\n", 'info')
                
                thread = threading.Thread(target=self.perform_chkdsk, args=(drive, True))
                thread.daemon = True
                thread.start()
    
    def schedule_chkdsk_on_restart(self, drive):
        """Schedule CHKDSK on system drive for next restart"""
        try:
            result = subprocess.run(
                f'chkdsk {drive}: /F /R',
                capture_output=True,
                text=True,
                shell=True,
                input='Y\n'  # Answer yes to schedule
            )
            
            if 'next restart' in result.stdout.lower() or 'scheduled' in result.stdout.lower():
                messagebox.showinfo("Scheduled",
                    f"CHKDSK has been scheduled for {drive}: drive.\n\n"
                    "The scan will run automatically on the next restart.")
                self.append_disk_output(f"✓ CHKDSK scheduled for {drive}: on next restart\n", 'good')
            else:
                self.append_disk_output(f"CHKDSK output: {result.stdout}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule CHKDSK: {e}")
    
    def perform_chkdsk(self, drive, fix=False):
        """Perform CHKDSK in background"""
        try:
            cmd = f'chkdsk {drive}:'
            if fix:
                cmd += ' /F'
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.root.after(0, lambda l=line: self.append_disk_output(l + "\n"))
                        
                        # Update progress if percentage found
                        if '%' in line:
                            try:
                                import re
                                match = re.search(r'(\d+)\s*(?:percent|%)', line)
                                if match:
                                    pct = int(match.group(1))
                                    self.root.after(0, lambda p=pct: self.update_task_status(f"CHKDSK: {p}%", p))
                            except:
                                pass
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.append_disk_output("\n✓ CHKDSK completed successfully\n", 'good'))
            else:
                self.root.after(0, lambda: self.append_disk_output(f"\n⚠ CHKDSK finished with code {process.returncode}\n", 'warning'))
            
        except Exception as e:
            self.root.after(0, lambda: self.append_disk_output(f"\n✗ Error: {e}\n", 'error'))
        finally:
            self.root.after(0, lambda: self.disk_chkdsk_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.disk_repair_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.set_status("Ready", "success"))
            self.root.after(0, lambda: self.update_task_status("Idle", 100))
            self.root.after(0, self.refresh_disk_info)
    
    def optimize_selected_disk(self):
        """Optimize (defrag/TRIM) selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            messagebox.showinfo("No Selection", "Please select a drive first.")
            return
        
        # Get media type
        selected = self.disk_tree.selection()
        disk = self.disk_data.get(selected[0], {}) if selected else {}
        media_type = disk.get('MediaType', 'Unknown')
        
        if media_type == 'SSD':
            action = "TRIM optimization"
        else:
            action = "defragmentation"
        
        if messagebox.askyesno("Optimize Drive",
                f"Run {action} on {drive}: drive?\n\n"
                f"Media Type: {media_type}\n\n"
                "This may take some time."):
            
            self.disk_optimize_btn.config(state=tk.DISABLED)
            self.set_status(f"Optimizing {drive}:...", "busy")
            self.append_disk_output(f"\n{'='*40}\n", 'info')
            self.append_disk_output(f"Starting {action} on {drive}: ...\n", 'info')
            
            thread = threading.Thread(target=self.perform_optimize, args=(drive,))
            thread.daemon = True
            thread.start()
    
    def perform_optimize(self, drive):
        """Perform drive optimization"""
        try:
            # Use defrag command with optimize flag
            process = subprocess.Popen(
                f'defrag {drive}: /O /U /V',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.root.after(0, lambda l=line: self.append_disk_output(l + "\n"))
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.append_disk_output("\n✓ Optimization completed\n", 'good'))
            else:
                self.root.after(0, lambda: self.append_disk_output(f"\n⚠ Optimization finished with code {process.returncode}\n", 'warning'))
                
        except Exception as e:
            self.root.after(0, lambda: self.append_disk_output(f"\n✗ Error: {e}\n", 'error'))
        finally:
            self.root.after(0, lambda: self.disk_optimize_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.set_status("Ready", "success"))
            self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def run_disk_cleanup(self):
        """Open Disk Cleanup for selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            messagebox.showinfo("No Selection", "Please select a drive first.")
            return
        
        try:
            # Open Disk Cleanup utility
            subprocess.Popen(f'cleanmgr /d {drive}', shell=True)
            self.append_disk_output(f"Opened Disk Cleanup for {drive}:\n", 'info')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Disk Cleanup: {e}")
    
    def open_disk_in_explorer(self):
        """Open selected drive in Windows Explorer"""
        drive = self.get_selected_drive()
        if not drive:
            return
        
        try:
            os.startfile(f"{drive}:\\")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open drive: {e}")
    
    def append_disk_output(self, text, tag=None):
        """Append text to disk output with optional tag"""
        self.disk_output.insert(tk.END, text, tag)
        self.disk_output.see(tk.END)
    
    def setup_health_tab(self):
        """Setup the comprehensive Windows health check tab"""
        self.health_frame.columnconfigure(0, weight=1)
        self.health_frame.columnconfigure(1, weight=1)
        self.health_frame.rowconfigure(1, weight=1)
        
        # Header card with quick scan button
        header_card = ttk.Frame(self.health_frame, style='Glass.TFrame')
        header_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        
        header_row = ttk.Frame(header_card, style='Glass.TFrame')
        header_row.pack(fill=tk.X, pady=(8, 4))
        
        ttk.Label(header_row, text="SYSTEM HEALTH CHECK", style='CardTitle.TLabel').pack(side=tk.LEFT)
        
        self.quick_health_btn = ttk.Button(header_row, text="Run Full Health Check", style='Accent.TButton',
                                           command=self.run_full_health_check)
        self.quick_health_btn.pack(side=tk.RIGHT, padx=(0, 8))
        
        ttk.Label(header_card, text="Comprehensive system health analysis - Windows Update, Security, Disk, Memory, and more", 
                 style='Card.TLabel').pack(anchor=tk.W, pady=(0, 8))
        
        # Left column - Health Status Cards
        left_frame = ttk.Frame(self.health_frame, style='Card.TFrame')
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=8)
        left_frame.columnconfigure(0, weight=1)
        
        # Create scrollable frame for health cards
        health_canvas = tk.Canvas(left_frame, bg=self.COLORS['bg_card'], highlightthickness=0)
        health_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=health_canvas.yview)
        self.health_cards_frame = ttk.Frame(health_canvas, style='Card.TFrame')
        
        self.health_cards_frame.bind("<Configure>", 
            lambda e: health_canvas.configure(scrollregion=health_canvas.bbox("all")))
        
        health_canvas.create_window((0, 0), window=self.health_cards_frame, anchor="nw")
        health_canvas.configure(yscrollcommand=health_scrollbar.set)
        
        health_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        health_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mouse wheel
        health_canvas.bind_all("<MouseWheel>", lambda e: health_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Initialize health check items - comprehensive list
        self.health_items = {}
        health_checks = [
            ("windows_update", "Windows Update", "Update services and failed updates"),
            ("security", "Windows Security", "Defender, Firewall, definitions"),
            ("system_files", "System Files", "SFC/DISM integrity"),
            ("disk_health", "Disk Health", "SMART status, wear level"),
            ("disk_integrity", "Disk Integrity", "CHKDSK, file system errors"),
            ("memory", "Memory", "RAM usage, page file, errors"),
            ("storage_space", "Storage Space", "Free disk space"),
            ("temperatures", "Temperatures", "CPU/GPU thermal status"),
            ("critical_errors", "Critical Errors", "BSOD, WHEA, kernel errors"),
            ("services", "Essential Services", "Auto-start services status"),
            ("drivers", "Driver Health", "Unsigned/problematic drivers"),
            ("boot_time", "Boot Performance", "Startup time analysis"),
            ("reliability", "Reliability Score", "System stability index"),
            ("unexpected_reboots", "Unexpected Reboots", "Power loss events"),
        ]
        
        for i, (key, title, description) in enumerate(health_checks):
            card = self.create_health_card(self.health_cards_frame, key, title, description)
            card.pack(fill=tk.X, padx=8, pady=4)
            self.health_items[key] = {
                'status': 'unknown',
                'card': card,
                'title': title,
                'score': 0  # Health score contribution
            }
        
        # Right column - Actions and Output
        right_frame = ttk.Frame(self.health_frame, style='Glass.TFrame')
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=8)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(2, weight=1)
        
        # Repair Actions
        actions_card = ttk.Frame(right_frame, style='Glass.TFrame')
        actions_card.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(actions_card, text="REPAIR ACTIONS", style='CardTitle.TLabel').pack(anchor=tk.W, pady=(8, 8))
        
        # SFC row
        sfc_row = ttk.Frame(actions_card, style='Glass.TFrame')
        sfc_row.pack(fill=tk.X, pady=4)
        self.sfc_btn = ttk.Button(sfc_row, text="Run SFC Scan", style='Small.TButton', command=self.run_sfc_scan)
        self.sfc_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(sfc_row, text="Repair system files", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # DISM row
        dism_row = ttk.Frame(actions_card, style='Glass.TFrame')
        dism_row.pack(fill=tk.X, pady=4)
        self.dism_btn = ttk.Button(dism_row, text="DISM Health", style='Small.TButton', command=self.run_dism_health)
        self.dism_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.dism_restore_btn = ttk.Button(dism_row, text="DISM Restore", style='Small.TButton', command=self.run_dism_restore)
        self.dism_restore_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(dism_row, text="Component store repair", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # CHKDSK row
        chkdsk_row = ttk.Frame(actions_card, style='Glass.TFrame')
        chkdsk_row.pack(fill=tk.X, pady=4)
        self.chkdsk_btn = ttk.Button(chkdsk_row, text="Check Disk", style='Small.TButton', command=self.run_chkdsk)
        self.chkdsk_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(chkdsk_row, text="Schedule disk check on restart", style='Muted.TLabel').pack(side=tk.LEFT)
        
        # Windows Update row
        wu_row = ttk.Frame(actions_card, style='Glass.TFrame')
        wu_row.pack(fill=tk.X, pady=(4, 8))
        ttk.Button(wu_row, text="Open Windows Update", style='Small.TButton',
                  command=lambda: subprocess.run(['start', 'ms-settings:windowsupdate'], shell=True)).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(wu_row, text="Open Security", style='Small.TButton',
                  command=lambda: subprocess.run(['start', 'windowsdefender:'], shell=True)).pack(side=tk.LEFT, padx=(0, 8))
        
        # Output area
        output_card = ttk.Frame(right_frame, style='Glass.TFrame')
        output_card.pack(fill=tk.BOTH, expand=True)
        output_card.columnconfigure(0, weight=1)
        output_card.rowconfigure(1, weight=1)
        
        ttk.Label(output_card, text="SCAN OUTPUT", style='CardTitle.TLabel').grid(row=0, column=0, sticky="w", pady=(8, 8))
        
        self.health_output = scrolledtext.ScrolledText(
            output_card, 
            wrap=tk.WORD, 
            font=('Consolas', 9),
            bg=self.COLORS['bg_glass'],
            fg=self.COLORS['text'],
            insertbackground=self.COLORS['text'],
            selectbackground=self.COLORS['accent'],
            relief='flat',
            padx=12,
            pady=12,
            borderwidth=0,
            height=10
        )
        self.health_output.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        
        # Configure text tags for colored output
        self.health_output.tag_configure('good', foreground='#22c55e')
        self.health_output.tag_configure('warning', foreground='#eab308')
        self.health_output.tag_configure('error', foreground='#ef4444')
        self.health_output.tag_configure('info', foreground='#3b82f6')
        self.health_output.tag_configure('header', foreground='#f8fafc', font=('Century Gothic', 10, 'bold'))
        
        # Initial message
        self.health_output.insert(tk.END, "Click 'Run Full Health Check' for comprehensive analysis.\n\n", 'info')
        self.health_output.insert(tk.END, "Individual repair actions available on the right.\n")
    
    def create_health_card(self, parent, key, title, description):
        """Create a health status card"""
        card = ttk.Frame(parent, style='Glass.TFrame')
        
        # Status indicator and title row
        title_row = ttk.Frame(card, style='Glass.TFrame')
        title_row.pack(fill=tk.X, padx=8, pady=(8, 4))
        
        # Status indicator (will be updated)
        status_label = ttk.Label(title_row, text="○", style='Card.TLabel', font=('Segoe UI', 14))
        status_label.pack(side=tk.LEFT, padx=(0, 8))
        
        # Title
        ttk.Label(title_row, text=title, style='Card.TLabel', font=('Century Gothic', 11, 'bold')).pack(side=tk.LEFT)
        
        # Status text (will be updated)
        status_text = ttk.Label(title_row, text="Not checked", style='Muted.TLabel')
        status_text.pack(side=tk.RIGHT)
        
        # Description
        ttk.Label(card, text=description, style='Muted.TLabel').pack(anchor=tk.W, padx=8, pady=(0, 8))
        
        # Store references for updating
        card.status_indicator = status_label
        card.status_text = status_text
        
        return card
    
    def update_health_card(self, key, status, text, details=""):
        """Update a health card's status"""
        if key not in self.health_items:
            return
        
        card = self.health_items[key]['card']
        
        # Status colors and symbols
        status_config = {
            'good': ('●', '#22c55e', 'Healthy'),
            'warning': ('◐', '#eab308', 'Warning'),
            'error': ('●', '#ef4444', 'Error'),
            'checking': ('◌', '#3b82f6', 'Checking...'),
            'unknown': ('○', '#64748b', 'Not checked')
        }
        
        symbol, color, default_text = status_config.get(status, status_config['unknown'])
        
        card.status_indicator.config(text=symbol, foreground=color)
        card.status_text.config(text=text or default_text)
        self.health_items[key]['status'] = status
    
    def run_full_health_check(self):
        """Run comprehensive health check"""
        self.quick_health_btn.config(state=tk.DISABLED)
        self.set_status("Running health check...", "busy")
        self.update_task_status("Health: Starting...", 0)
        
        # Clear output
        self.health_output.delete(1.0, tk.END)
        self.health_output.insert(tk.END, "═" * 50 + "\n", 'header')
        self.health_output.insert(tk.END, "    SYSTEM HEALTH CHECK REPORT\n", 'header')
        self.health_output.insert(tk.END, f"    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", 'header')
        self.health_output.insert(tk.END, "═" * 50 + "\n\n", 'header')
        
        # Set all cards to checking
        for key in self.health_items:
            self.update_health_card(key, 'checking', 'Checking...')
        
        thread = threading.Thread(target=self.perform_full_health_check)
        thread.daemon = True
        thread.start()
    
    def perform_full_health_check(self):
        """Perform all health checks"""
        checks = [
            (7, "windows_update", self.check_windows_update_health),
            (14, "security", self.check_security_health),
            (21, "system_files", self.check_system_files_quick),
            (28, "disk_health", self.check_disk_health),
            (35, "disk_integrity", self.check_disk_integrity),
            (42, "memory", self.check_memory_health),
            (49, "storage_space", self.check_storage_space),
            (56, "temperatures", self.check_temperatures),
            (63, "critical_errors", self.check_critical_errors),
            (70, "services", self.check_essential_services),
            (77, "drivers", self.check_driver_health),
            (84, "boot_time", self.check_boot_performance),
            (91, "reliability", self.check_reliability_score),
            (98, "unexpected_reboots", self.check_unexpected_reboots),
        ]
        
        for progress, key, check_func in checks:
            self.root.after(0, lambda p=progress, k=key: (
                self.update_task_status(f"Health: Checking {self.health_items[k]['title']}...", p)
            ))
            try:
                check_func()
            except Exception as e:
                self.root.after(0, lambda k=key, e=e: (
                    self.update_health_card(k, 'error', f'Error: {str(e)[:30]}'),
                    self.append_health_output(f"[ERROR] {self.health_items[k]['title']}: {e}\n")
                ))
        
        # Summary with health score
        self.root.after(0, self.show_health_summary)
        self.root.after(0, lambda: self.quick_health_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.set_status("Health check complete", "success"))
        self.root.after(0, lambda: self.update_task_status("Idle", 100))
    
    def check_windows_update_health(self):
        """Check Windows Update health"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        # Check update services
        $services = @('wuauserv', 'bits', 'cryptsvc', 'TrustedInstaller')
        foreach ($svc in $services) {
            $s = Get-Service $svc -ErrorAction SilentlyContinue
            if ($s -and $s.Status -ne 'Running' -and $s.StartType -ne 'Disabled') {
                $result.Status = 'warning'
                $result.Details += "$svc service not running"
            }
        }
        
        # Check for failed updates
        try {
            $session = New-Object -ComObject Microsoft.Update.Session
            $searcher = $session.CreateUpdateSearcher()
            $history = $searcher.QueryHistory(0, 10)
            $failed = @($history | Where-Object { $_.ResultCode -eq 4 -or $_.ResultCode -eq 5 })
            if ($failed.Count -gt 0) {
                $result.Status = 'warning'
                $result.Details += "$($failed.Count) failed update(s) recently"
            }
        } catch {}
        
        # Check last successful update
        try {
            $lastUpdate = (Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn
            $daysSince = ((Get-Date) - $lastUpdate).Days
            if ($daysSince -gt 30) {
                $result.Status = 'warning'
                $result.Details += "No updates in $daysSince days"
            }
            $result.LastUpdate = $lastUpdate.ToString("yyyy-MM-dd")
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'unknown')
            details = data.get('Details', [])
            last_update = data.get('LastUpdate', 'Unknown')
            
            if status == 'good':
                text = f"OK - Last: {last_update}"
            else:
                text = "; ".join(details[:2]) if details else "Issues found"
            
            self.root.after(0, lambda: self.update_health_card('windows_update', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Windows Update: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('windows_update', 'error', 'Check failed'))
    
    def check_security_health(self):
        """Check Windows Security health"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        try {
            $defender = Get-MpComputerStatus -ErrorAction Stop
            
            # Real-time protection
            if (-not $defender.RealTimeProtectionEnabled) {
                $result.Status = 'error'
                $result.Details += "Real-time protection OFF"
            }
            
            # Antivirus enabled
            if (-not $defender.AntivirusEnabled) {
                $result.Status = 'error'
                $result.Details += "Antivirus disabled"
            }
            
            # Definitions age
            $defAge = ((Get-Date) - $defender.AntivirusSignatureLastUpdated).Days
            if ($defAge -gt 7) {
                $result.Status = 'warning'
                $result.Details += "Definitions $defAge days old"
            }
            $result.DefAge = $defAge
            
            # Tamper protection
            if (-not $defender.IsTamperProtected) {
                $result.Details += "Tamper protection off"
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
            }
            
        } catch {
            $result.Status = 'warning'
            $result.Details += "Could not query Defender"
        }
        
        # Check firewall
        try {
            $fw = Get-NetFirewallProfile -ErrorAction SilentlyContinue
            $disabled = @($fw | Where-Object { -not $_.Enabled })
            if ($disabled.Count -gt 0) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "Firewall: $($disabled.Count) profile(s) disabled"
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'unknown')
            details = data.get('Details', [])
            def_age = data.get('DefAge', 'Unknown')
            
            if status == 'good':
                text = f"Protected - Defs: {def_age}d old"
            else:
                text = "; ".join(details[:2]) if details else "Issues found"
            
            self.root.after(0, lambda: self.update_health_card('security', status, text))
            
            tag = 'good' if status == 'good' else ('error' if status == 'error' else 'warning')
            symbol = '✓' if status == 'good' else ('✗' if status == 'error' else '⚠')
            self.root.after(0, lambda: self.append_health_output(
                f"[{symbol}] Windows Security: {text}\n", tag))
        except:
            self.root.after(0, lambda: self.update_health_card('security', 'warning', 'Check limited'))
    
    def check_system_files_quick(self):
        """Quick check of system file integrity (not full SFC)"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        # Check last SFC result from CBS log
        try {
            $cbsLog = "$env:windir\\Logs\\CBS\\CBS.log"
            if (Test-Path $cbsLog) {
                $lastLines = Get-Content $cbsLog -Tail 100 -ErrorAction SilentlyContinue
                if ($lastLines -match "Corruption.*detected|found corrupt") {
                    $result.Status = 'warning'
                    $result.Details += "Corruption detected in CBS log"
                }
                if ($lastLines -match "successfully repaired") {
                    $result.Details += "Last SFC repaired files"
                }
            }
        } catch {}
        
        # Check component store health quickly
        try {
            $pending = Test-Path "$env:windir\\WinSxS\\pending.xml"
            if ($pending) {
                $result.Status = 'warning'
                $result.Details += "Pending operations in component store"
            }
        } catch {}
        
        # Check for recent DISM operations
        try {
            $dismLog = "$env:windir\\Logs\\DISM\\dism.log"
            if (Test-Path $dismLog) {
                $lastMod = (Get-Item $dismLog).LastWriteTime
                $result.LastDism = $lastMod.ToString("yyyy-MM-dd")
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            details = data.get('Details', [])
            
            if status == 'good':
                text = "No issues detected"
            else:
                text = "; ".join(details[:2]) if details else "Run SFC for details"
            
            self.root.after(0, lambda: self.update_health_card('system_files', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] System Files: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('system_files', 'unknown', 'Run SFC to check'))
    
    def check_disk_health(self):
        """Check disk SMART health"""
        command = """
        $result = @{ Status = 'good'; Details = @(); Disks = @() }
        
        try {
            $disks = Get-PhysicalDisk -ErrorAction SilentlyContinue
            foreach ($disk in $disks) {
                $diskInfo = @{
                    Name = $disk.FriendlyName
                    Status = $disk.HealthStatus
                    MediaType = $disk.MediaType
                    Size = [math]::Round($disk.Size / 1GB, 0)
                }
                
                if ($disk.HealthStatus -ne 'Healthy') {
                    $result.Status = 'error'
                    $result.Details += "$($disk.FriendlyName): $($disk.HealthStatus)"
                }
                
                # Check wear level for SSDs
                if ($disk.MediaType -eq 'SSD') {
                    try {
                        $reliability = Get-StorageReliabilityCounter -PhysicalDisk $disk -ErrorAction SilentlyContinue
                        if ($reliability.Wear -gt 80) {
                            $result.Status = 'warning'
                            $result.Details += "SSD wear: $($reliability.Wear)%"
                        }
                        $diskInfo.Wear = $reliability.Wear
                    } catch {}
                }
                
                $result.Disks += $diskInfo
            }
        } catch {
            $result.Status = 'warning'
            $result.Details += "Could not query SMART data"
        }
        
        $result | ConvertTo-Json -Depth 3
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            disks = data.get('Disks', [])
            details = data.get('Details', [])
            
            if disks:
                disk_summary = f"{len(disks)} disk(s) healthy"
                for d in disks:
                    if d.get('Status') != 'Healthy':
                        disk_summary = f"{d.get('Name')}: {d.get('Status')}"
                        break
                text = disk_summary
            else:
                text = "Could not query"
            
            self.root.after(0, lambda: self.update_health_card('disk_health', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Disk Health: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('disk_health', 'unknown', 'Check failed'))
    
    def check_disk_integrity(self):
        """Check disk integrity and CHKDSK status"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        # Check if disk is dirty (needs CHKDSK)
        try {
            $volumes = Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' }
            foreach ($vol in $volumes) {
                $dirty = (fsutil dirty query "$($vol.DriveLetter):" 2>$null) -match "dirty"
                if ($dirty) {
                    $result.Status = 'warning'
                    $result.Details += "$($vol.DriveLetter): needs CHKDSK"
                }
            }
        } catch {}
        
        # Check event logs for disk errors
        try {
            $diskErrors = Get-WinEvent -FilterHashtable @{
                LogName = 'System'
                ProviderName = 'disk', 'ntfs', 'Ntfs'
                Level = 2,3  # Error, Warning
                StartTime = (Get-Date).AddDays(-7)
            } -MaxEvents 10 -ErrorAction SilentlyContinue
            
            if ($diskErrors.Count -gt 0) {
                $result.Status = 'warning'
                $result.Details += "$($diskErrors.Count) disk error(s) in 7 days"
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            details = data.get('Details', [])
            
            text = "No errors" if status == 'good' else "; ".join(details[:2])
            
            self.root.after(0, lambda: self.update_health_card('disk_integrity', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Disk Integrity: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('disk_integrity', 'unknown', 'Check failed'))
    
    def check_memory_health(self):
        """Check memory usage and stability"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        # Get memory info
        $os = Get-CimInstance Win32_OperatingSystem
        $totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
        $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
        $usedPct = [math]::Round((1 - ($os.FreePhysicalMemory / $os.TotalVisibleMemorySize)) * 100, 0)
        
        $result.TotalGB = $totalGB
        $result.FreeGB = $freeGB
        $result.UsedPercent = $usedPct
        
        if ($usedPct -gt 90) {
            $result.Status = 'error'
            $result.Details += "Memory usage critical: $usedPct%"
        } elseif ($usedPct -gt 80) {
            $result.Status = 'warning'
            $result.Details += "Memory usage high: $usedPct%"
        }
        
        # Check for memory errors in event log
        try {
            $memErrors = Get-WinEvent -FilterHashtable @{
                LogName = 'System'
                Id = 1101, 1102  # Memory diagnostic events
                StartTime = (Get-Date).AddDays(-7)
            } -MaxEvents 5 -ErrorAction SilentlyContinue
            
            if ($memErrors.Count -gt 0) {
                $result.Status = 'warning'
                $result.Details += "Memory errors in event log"
            }
        } catch {}
        
        # Check page file usage
        $pageFile = Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue
        if ($pageFile) {
            $pfUsedPct = [math]::Round(($pageFile.CurrentUsage / $pageFile.AllocatedBaseSize) * 100, 0)
            if ($pfUsedPct -gt 80) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "Page file high: $pfUsedPct%"
            }
        }
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            used_pct = data.get('UsedPercent', 0)
            free_gb = data.get('FreeGB', 0)
            
            text = f"{used_pct}% used ({free_gb:.1f} GB free)"
            
            self.root.after(0, lambda: self.update_health_card('memory', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Memory: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('memory', 'unknown', 'Check failed'))
    
    def check_storage_space(self):
        """Check storage space on drives"""
        command = """
        $result = @{ Status = 'good'; Details = @(); Drives = @() }
        
        $volumes = Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' -and $_.Size -gt 0 }
        
        foreach ($vol in $volumes) {
            $freeGB = [math]::Round($vol.SizeRemaining / 1GB, 1)
            $totalGB = [math]::Round($vol.Size / 1GB, 1)
            $freePct = [math]::Round(($vol.SizeRemaining / $vol.Size) * 100, 0)
            
            $result.Drives += @{
                Letter = $vol.DriveLetter
                FreeGB = $freeGB
                TotalGB = $totalGB
                FreePercent = $freePct
            }
            
            # Check OS drive specifically
            if ($vol.DriveLetter -eq $env:SystemDrive[0]) {
                if ($freePct -lt 10) {
                    $result.Status = 'error'
                    $result.Details += "OS drive critical: $freePct% free"
                } elseif ($freePct -lt 15) {
                    $result.Status = 'warning'
                    $result.Details += "OS drive low: $freePct% free"
                }
                $result.OSDrive = @{ Letter = $vol.DriveLetter; FreeGB = $freeGB; FreePct = $freePct }
            }
        }
        
        $result | ConvertTo-Json -Depth 3
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            os_drive = data.get('OSDrive', {})
            
            free_gb = os_drive.get('FreeGB', 0)
            free_pct = os_drive.get('FreePct', 0)
            text = f"C: {free_gb:.1f} GB free ({free_pct}%)"
            
            self.root.after(0, lambda: self.update_health_card('storage_space', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Storage: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('storage_space', 'unknown', 'Check failed'))
    
    def check_temperatures(self):
        """Check CPU/GPU temperatures"""
        command = """
        $result = @{ Status = 'good'; Details = @() }
        
        # Try to get CPU temp via WMI (works on some systems)
        try {
            $temp = Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace "root/wmi" -ErrorAction Stop
            if ($temp) {
                $cpuTempC = [math]::Round(($temp.CurrentTemperature - 2732) / 10, 0)
                $result.CPUTemp = $cpuTempC
                
                if ($cpuTempC -gt 85) {
                    $result.Status = 'error'
                    $result.Details += "CPU temp critical: $cpuTempC°C"
                } elseif ($cpuTempC -gt 70) {
                    $result.Status = 'warning'
                    $result.Details += "CPU temp high: $cpuTempC°C"
                }
            }
        } catch {
            $result.CPUTemp = "N/A"
        }
        
        # Check for thermal throttling events
        try {
            $thermalEvents = Get-WinEvent -FilterHashtable @{
                LogName = 'System'
                ProviderName = 'Microsoft-Windows-Kernel-Power', 'Microsoft-Windows-Kernel-Processor-Power'
                StartTime = (Get-Date).AddDays(-7)
            } -MaxEvents 20 -ErrorAction SilentlyContinue | 
            Where-Object { $_.Message -match 'throttl|thermal|overheat' }
            
            if ($thermalEvents.Count -gt 0) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "Thermal events detected"
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            cpu_temp = data.get('CPUTemp', 'N/A')
            
            if cpu_temp != 'N/A':
                text = f"CPU: {cpu_temp}°C"
            else:
                text = "Sensor data limited"
            
            details = data.get('Details', [])
            if details:
                text += f" - {details[0]}"
            
            self.root.after(0, lambda: self.update_health_card('temperatures', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Temperatures: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('temperatures', 'unknown', 'Sensors not accessible'))
    
    def check_critical_errors(self):
        """Check for critical errors in event logs"""
        command = """
        $result = @{ Status = 'good'; Details = @(); Errors = @() }
        
        try {
            $criticalEvents = Get-WinEvent -FilterHashtable @{
                LogName = 'System'
                Level = 1,2  # Critical, Error
                StartTime = (Get-Date).AddHours(-48)
            } -MaxEvents 50 -ErrorAction SilentlyContinue
            
            # Categorize errors
            $kernelPower = @($criticalEvents | Where-Object { $_.ProviderName -like '*Kernel-Power*' })
            $whea = @($criticalEvents | Where-Object { $_.ProviderName -like '*WHEA*' })
            $bugcheck = @($criticalEvents | Where-Object { $_.Id -eq 1001 })
            $other = @($criticalEvents | Where-Object { 
                $_.ProviderName -notlike '*Kernel-Power*' -and 
                $_.ProviderName -notlike '*WHEA*' -and 
                $_.Id -ne 1001 
            })
            
            $result.KernelPower = $kernelPower.Count
            $result.WHEA = $whea.Count
            $result.Bugcheck = $bugcheck.Count
            $result.Other = $other.Count
            $result.Total = $criticalEvents.Count
            
            if ($bugcheck.Count -gt 0) {
                $result.Status = 'error'
                $result.Details += "$($bugcheck.Count) BSOD event(s)"
            }
            if ($whea.Count -gt 0) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "$($whea.Count) hardware error(s)"
            }
            if ($kernelPower.Count -gt 2) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "$($kernelPower.Count) unexpected shutdown(s)"
            }
            
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            total = data.get('Total', 0)
            details = data.get('Details', [])
            
            if status == 'good':
                text = f"No critical errors (48h)"
            else:
                text = "; ".join(details[:2]) if details else f"{total} error(s)"
            
            self.root.after(0, lambda: self.update_health_card('critical_errors', status, text))
            
            tag = 'good' if status == 'good' else ('error' if status == 'error' else 'warning')
            symbol = '✓' if status == 'good' else ('✗' if status == 'error' else '⚠')
            self.root.after(0, lambda: self.append_health_output(
                f"[{symbol}] Critical Errors: {text}\n", tag))
        except:
            self.root.after(0, lambda: self.update_health_card('critical_errors', 'unknown', 'Check failed'))
    
    def check_essential_services(self):
        """Check essential Windows services"""
        command = """
        $result = @{ Status = 'good'; Details = @(); FailedServices = @() }
        
        # Essential services that should be running
        $essential = @(
            @{ Name = 'wuauserv'; Display = 'Windows Update' },
            @{ Name = 'BITS'; Display = 'Background Transfer' },
            @{ Name = 'WSearch'; Display = 'Windows Search' },
            @{ Name = 'SysMain'; Display = 'Superfetch' },
            @{ Name = 'Themes'; Display = 'Themes' },
            @{ Name = 'EventLog'; Display = 'Event Log' },
            @{ Name = 'Schedule'; Display = 'Task Scheduler' },
            @{ Name = 'Winmgmt'; Display = 'WMI' }
        )
        
        foreach ($svc in $essential) {
            $s = Get-Service $svc.Name -ErrorAction SilentlyContinue
            if ($s) {
                # Check if service should run but isn't
                if ($s.StartType -eq 'Automatic' -and $s.Status -ne 'Running') {
                    $result.FailedServices += $svc.Display
                }
            }
        }
        
        if ($result.FailedServices.Count -gt 0) {
            $result.Status = 'warning'
            $result.Details = $result.FailedServices
        }
        
        # Check for high-impact startup items
        try {
            $startupApps = Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue
            $result.StartupCount = $startupApps.Count
            if ($startupApps.Count -gt 15) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "High startup items: $($startupApps.Count)"
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            failed = data.get('FailedServices', [])
            startup_count = data.get('StartupCount', 0)
            
            if status == 'good':
                text = f"All running ({startup_count} startup items)"
            else:
                text = f"{len(failed)} service(s) not running"
            
            self.root.after(0, lambda: self.update_health_card('services', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Services: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('services', 'unknown', 'Check failed'))
    
    def check_driver_health(self):
        """Check for unsigned or problematic drivers"""
        command = """
        $result = @{ Status = 'good'; Details = @(); UnsignedCount = 0; ProblemCount = 0 }
        
        try {
            # Check for unsigned drivers
            $drivers = Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue
            $unsigned = @($drivers | Where-Object { $_.IsSigned -eq $false -and $_.DeviceName })
            $result.UnsignedCount = $unsigned.Count
            
            if ($unsigned.Count -gt 0) {
                $result.Status = 'warning'
                $result.Details += "$($unsigned.Count) unsigned driver(s)"
            }
            
            # Check for problem devices
            $problems = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | 
                        Where-Object { $_.ConfigManagerErrorCode -ne 0 }
            $result.ProblemCount = @($problems).Count
            
            if (@($problems).Count -gt 0) {
                if ($result.Status -eq 'good') { $result.Status = 'warning' }
                $result.Details += "$(@($problems).Count) device(s) with issues"
            }
            
            # Check for old drivers (>2 years)
            $oldDrivers = @($drivers | Where-Object { 
                $_.DriverDate -and 
                ((Get-Date) - [DateTime]::Parse($_.DriverDate.Split('.')[0])).Days -gt 730 
            } -ErrorAction SilentlyContinue)
            
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            unsigned = data.get('UnsignedCount', 0)
            problems = data.get('ProblemCount', 0)
            
            if status == 'good':
                text = "All drivers signed & OK"
            else:
                parts = []
                if unsigned > 0:
                    parts.append(f"{unsigned} unsigned")
                if problems > 0:
                    parts.append(f"{problems} issues")
                text = ", ".join(parts)
            
            self.root.after(0, lambda: self.update_health_card('drivers', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Drivers: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('drivers', 'unknown', 'Check failed'))
    
    def check_boot_performance(self):
        """Check boot time performance"""
        command = """
        $result = @{ Status = 'good'; Details = @(); BootTimeMs = 0 }
        
        try {
            # Get last boot time from event log
            $bootEvent = Get-WinEvent -FilterHashtable @{
                LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'
                Id = 100  # Boot performance event
            } -MaxEvents 1 -ErrorAction SilentlyContinue
            
            if ($bootEvent) {
                $bootTimeMs = $bootEvent.Properties[0].Value
                $result.BootTimeMs = $bootTimeMs
                $bootTimeSec = [math]::Round($bootTimeMs / 1000, 1)
                $result.BootTimeSec = $bootTimeSec
                
                # Check if SSD or HDD
                $systemDrive = $env:SystemDrive[0]
                $partition = Get-Partition -DriveLetter $systemDrive -ErrorAction SilentlyContinue
                $physicalDisk = $null
                if ($partition) {
                    $physicalDisk = Get-PhysicalDisk | Where-Object { $_.DeviceId -eq $partition.DiskNumber } | Select-Object -First 1
                }
                
                $isSSD = $physicalDisk -and $physicalDisk.MediaType -eq 'SSD'
                $result.IsSSD = $isSSD
                
                # Thresholds: SSD <15s good, <25s ok, HDD <40s good, <60s ok
                if ($isSSD) {
                    if ($bootTimeSec -gt 25) {
                        $result.Status = 'warning'
                        $result.Details += "Slow SSD boot: ${bootTimeSec}s (target <15s)"
                    } elseif ($bootTimeSec -gt 15) {
                        $result.Status = 'warning'
                        $result.Details += "Boot could be faster: ${bootTimeSec}s"
                    }
                } else {
                    if ($bootTimeSec -gt 60) {
                        $result.Status = 'warning'
                        $result.Details += "Slow HDD boot: ${bootTimeSec}s (target <40s)"
                    } elseif ($bootTimeSec -gt 40) {
                        $result.Status = 'warning'
                        $result.Details += "Boot could be faster: ${bootTimeSec}s"
                    }
                }
            }
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            boot_sec = data.get('BootTimeSec', 0)
            is_ssd = data.get('IsSSD', False)
            
            drive_type = "SSD" if is_ssd else "HDD"
            if boot_sec:
                text = f"{boot_sec}s ({drive_type})"
            else:
                text = "Could not measure"
                status = 'unknown'
            
            self.root.after(0, lambda: self.update_health_card('boot_time', status, text))
            self.root.after(0, lambda: self.append_health_output(
                f"[{'✓' if status == 'good' else '⚠'}] Boot Time: {text}\n",
                'good' if status == 'good' else 'warning'))
        except:
            self.root.after(0, lambda: self.update_health_card('boot_time', 'unknown', 'Check failed'))
    
    def check_reliability_score(self):
        """Check Windows Reliability Score"""
        command = """
        $result = @{ Status = 'good'; Score = 0; Details = @() }
        
        try {
            # Get reliability data from WMI
            $reliability = Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics -ErrorAction Stop | 
                           Sort-Object TimeGenerated -Descending | Select-Object -First 1
            
            if ($reliability) {
                $score = [math]::Round($reliability.SystemStabilityIndex, 1)
                $result.Score = $score
                
                if ($score -lt 5) {
                    $result.Status = 'error'
                    $result.Details += "Very low stability: $score/10"
                } elseif ($score -lt 7) {
                    $result.Status = 'warning'
                    $result.Details += "Stability below target: $score/10"
                }
            } else {
                $result.Score = -1
            }
        } catch {
            $result.Score = -1
            $result.Details += "Could not query reliability"
        }
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            score = data.get('Score', -1)
            
            if score >= 0:
                text = f"{score}/10"
                if score >= 7:
                    status = 'good'
                elif score >= 5:
                    status = 'warning'
                else:
                    status = 'error'
            else:
                text = "Not available"
                status = 'unknown'
            
            self.root.after(0, lambda: self.update_health_card('reliability', status, text))
            
            symbol = '✓' if status == 'good' else ('✗' if status == 'error' else '⚠')
            tag = 'good' if status == 'good' else ('error' if status == 'error' else 'warning')
            self.root.after(0, lambda: self.append_health_output(
                f"[{symbol}] Reliability: {text}\n", tag))
        except:
            self.root.after(0, lambda: self.update_health_card('reliability', 'unknown', 'Check failed'))
    
    def check_unexpected_reboots(self):
        """Check for unexpected reboots/shutdowns"""
        command = """
        $result = @{ Status = 'good'; Details = @(); Count = 0 }
        
        try {
            # Event ID 41 = Kernel-Power unexpected shutdown
            # Event ID 1074 = Clean shutdown/restart (normal)
            # Event ID 6008 = Previous shutdown was unexpected
            
            $unexpectedEvents = Get-WinEvent -FilterHashtable @{
                LogName = 'System'
                ProviderName = 'Microsoft-Windows-Kernel-Power', 'EventLog'
                Id = 41, 6008
                StartTime = (Get-Date).AddDays(-7)
            } -MaxEvents 20 -ErrorAction SilentlyContinue
            
            $result.Count = @($unexpectedEvents).Count
            
            if (@($unexpectedEvents).Count -gt 3) {
                $result.Status = 'error'
                $result.Details += "$(@($unexpectedEvents).Count) unexpected reboots in 7 days"
            } elseif (@($unexpectedEvents).Count -gt 0) {
                $result.Status = 'warning'
                $result.Details += "$(@($unexpectedEvents).Count) unexpected reboot(s) in 7 days"
            }
            
            # Get last unexpected reboot time
            if ($unexpectedEvents) {
                $last = $unexpectedEvents | Sort-Object TimeCreated -Descending | Select-Object -First 1
                $result.LastEvent = $last.TimeCreated.ToString("yyyy-MM-dd HH:mm")
            }
            
        } catch {}
        
        $result | ConvertTo-Json
        """
        
        output = self.scanner.run_powershell(command)
        try:
            data = json.loads(output)
            status = data.get('Status', 'good')
            count = data.get('Count', 0)
            last_event = data.get('LastEvent', '')
            
            if status == 'good':
                text = "None in 7 days"
            else:
                text = f"{count} in 7 days"
                if last_event:
                    text += f" (last: {last_event})"
            
            self.root.after(0, lambda: self.update_health_card('unexpected_reboots', status, text))
            
            symbol = '✓' if status == 'good' else ('✗' if status == 'error' else '⚠')
            tag = 'good' if status == 'good' else ('error' if status == 'error' else 'warning')
            self.root.after(0, lambda: self.append_health_output(
                f"[{symbol}] Unexpected Reboots: {text}\n", tag))
        except:
            self.root.after(0, lambda: self.update_health_card('unexpected_reboots', 'unknown', 'Check failed'))
    
    def show_health_summary(self):
        """Show comprehensive health summary with score"""
        good = sum(1 for k, v in self.health_items.items() if v['status'] == 'good')
        warning = sum(1 for k, v in self.health_items.items() if v['status'] == 'warning')
        error = sum(1 for k, v in self.health_items.items() if v['status'] == 'error')
        unknown = sum(1 for k, v in self.health_items.items() if v['status'] == 'unknown')
        
        total_checks = len(self.health_items)
        scored_checks = total_checks - unknown
        
        # Calculate health score (0-100)
        # Good = 100%, Warning = 50%, Error = 0%
        if scored_checks > 0:
            score = int(((good * 100) + (warning * 50)) / scored_checks)
        else:
            score = 0
        
        # Determine overall health rating
        if score >= 90 and error == 0:
            rating = "EXCELLENT"
            rating_color = 'good'
            emoji = "🎉"
        elif score >= 75 and error == 0:
            rating = "GOOD"
            rating_color = 'good'
            emoji = "✓"
        elif score >= 50:
            rating = "FAIR"
            rating_color = 'warning'
            emoji = "⚠"
        else:
            rating = "POOR"
            rating_color = 'error'
            emoji = "✗"
        
        self.append_health_output("\n" + "═" * 50 + "\n", 'header')
        self.append_health_output("        WINDOWS HEALTH SUMMARY\n", 'header')
        self.append_health_output("═" * 50 + "\n\n", 'header')
        
        # Health Score Display
        self.append_health_output(f"    {emoji} HEALTH SCORE: {score}/100 ({rating})\n\n", rating_color)
        
        # Breakdown
        self.append_health_output("    Results:\n")
        if good > 0:
            self.append_health_output(f"      ✓ {good} check(s) passed\n", 'good')
        if warning > 0:
            self.append_health_output(f"      ⚠ {warning} warning(s)\n", 'warning')
        if error > 0:
            self.append_health_output(f"      ✗ {error} critical issue(s)\n", 'error')
        if unknown > 0:
            self.append_health_output(f"      ○ {unknown} could not be checked\n")
        
        # What healthy looks like
        self.append_health_output("\n" + "─" * 50 + "\n")
        self.append_health_output("    What a healthy system looks like:\n", 'info')
        
        healthy_criteria = [
            ("windows_update", "Windows Update functional"),
            ("security", "Defender fully active"),
            ("system_files", "SFC/DISM clean"),
            ("disk_health", "No disk errors"),
            ("critical_errors", "No WHEA/kernel errors"),
            ("drivers", "No unsigned unknown drivers"),
            ("reliability", "Reliability score above 7"),
            ("unexpected_reboots", "No unexpected reboots"),
            ("boot_time", "Fast boot time"),
            ("temperatures", "Normal temperatures"),
        ]
        
        for key, description in healthy_criteria:
            status = self.health_items.get(key, {}).get('status', 'unknown')
            if status == 'good':
                self.append_health_output(f"      ✓ {description}\n", 'good')
            elif status == 'error':
                self.append_health_output(f"      ✗ {description}\n", 'error')
            elif status == 'warning':
                self.append_health_output(f"      ⚠ {description}\n", 'warning')
            else:
                self.append_health_output(f"      ○ {description}\n")
        
        # Recommendations
        if error > 0 or warning > 0:
            self.append_health_output("\n" + "─" * 50 + "\n")
            self.append_health_output("    Recommendations:\n", 'info')
            
            if self.health_items.get('system_files', {}).get('status') in ['warning', 'error']:
                self.append_health_output("      → Run SFC and DISM repairs\n", 'warning')
            if self.health_items.get('disk_health', {}).get('status') in ['warning', 'error']:
                self.append_health_output("      → Check disk health, consider backup\n", 'warning')
            if self.health_items.get('security', {}).get('status') in ['warning', 'error']:
                self.append_health_output("      → Update Windows Defender definitions\n", 'warning')
            if self.health_items.get('drivers', {}).get('status') in ['warning', 'error']:
                self.append_health_output("      → Review driver issues in Issues tab\n", 'warning')
            if self.health_items.get('unexpected_reboots', {}).get('status') in ['warning', 'error']:
                self.append_health_output("      → Check power supply, RAM, temps\n", 'warning')
            if self.health_items.get('boot_time', {}).get('status') == 'warning':
                self.append_health_output("      → Review startup programs\n", 'warning')
        
        self.append_health_output("\n" + "═" * 50 + "\n", 'header')
        
        self.log_message(f"Health check complete: Score {score}/100 ({rating}) - {good} OK, {warning} warnings, {error} errors")
    
    def append_health_output(self, text, tag=None):
        """Append text to health output with optional tag"""
        self.health_output.insert(tk.END, text, tag)
        self.health_output.see(tk.END)
    
    def run_sfc_scan(self):
        """Run System File Checker"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "SFC scan requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        if messagebox.askyesno("Run SFC Scan",
                "This will run the System File Checker.\n\n"
                "The scan may take 10-30 minutes to complete.\n"
                "Do you want to continue?"):
            
            self.sfc_btn.config(state=tk.DISABLED)
            self.set_status("Running SFC scan...", "busy")
            self.root.after(0, lambda: self.update_task_status("SFC: Initializing...", 0))
            
            self.health_output.delete(1.0, tk.END)
            self.health_output.insert(tk.END, "Starting SFC scan...\n")
            self.health_output.insert(tk.END, "This may take 10-30 minutes. Please wait...\n\n")
            
            thread = threading.Thread(target=self.perform_sfc_scan)
            thread.daemon = True
            thread.start()
    
    def perform_sfc_scan(self):
        """Perform SFC scan in background"""
        try:
            process = subprocess.Popen(
                ['sfc', '/scannow'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.root.after(0, lambda l=line: self.append_health_output(l + "\n"))
                        # Parse percentage from SFC output
                        if '%' in line:
                            try:
                                # Extract percentage (e.g., "Verification 45% complete")
                                import re
                                match = re.search(r'(\d+)\s*%', line)
                                if match:
                                    pct = int(match.group(1))
                                    stage = "Verifying" if "verif" in line.lower() else "Repairing"
                                    self.root.after(0, lambda p=pct, s=stage: self.update_task_status(f"SFC: {s}...", p))
                            except:
                                pass
            
            process.wait()
            
            self.root.after(0, lambda: self.update_task_status("SFC: Complete", 100))
            self.root.after(0, lambda: self.append_health_output("\n--- SFC Scan Complete ---\n"))
            self.log_message("SFC scan completed")
            
        except Exception as e:
            self.root.after(0, lambda: self.append_health_output(f"\nError: {e}\n"))
            self.log_message(f"SFC scan error: {e}")
        finally:
            self.root.after(0, self.health_scan_complete)
    
    def run_dism_health(self):
        """Run DISM health check"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "DISM requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        self.dism_btn.config(state=tk.DISABLED)
        self.set_status("Running DISM health check...", "busy")
        self.root.after(0, lambda: self.update_task_status("DISM: Initializing...", 0))
        
        self.health_output.delete(1.0, tk.END)
        self.health_output.insert(tk.END, "Starting DISM CheckHealth...\n\n")
        
        thread = threading.Thread(target=self.perform_dism_health)
        thread.daemon = True
        thread.start()
    
    def perform_dism_health(self):
        """Perform DISM health check in background"""
        try:
            # First run CheckHealth (quick)
            self.root.after(0, lambda: self.update_task_status("DISM: CheckHealth...", 10))
            self.root.after(0, lambda: self.append_health_output("Running DISM /CheckHealth...\n"))
            
            result = subprocess.run(
                ['dism', '/Online', '/Cleanup-Image', '/CheckHealth'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.root.after(0, lambda: self.append_health_output(result.stdout))
            self.root.after(0, lambda: self.update_task_status("DISM: CheckHealth complete", 30))
            
            # Then run ScanHealth (thorough)
            self.root.after(0, lambda: self.update_task_status("DISM: ScanHealth...", 40))
            self.root.after(0, lambda: self.append_health_output("\nRunning DISM /ScanHealth (this may take a few minutes)...\n"))
            
            result = subprocess.run(
                ['dism', '/Online', '/Cleanup-Image', '/ScanHealth'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.root.after(0, lambda: self.append_health_output(result.stdout))
            
            self.root.after(0, lambda: self.update_task_status("DISM: Complete", 100))
            self.root.after(0, lambda: self.append_health_output("\n--- DISM Health Check Complete ---\n"))
            self.log_message("DISM health check completed")
            
        except Exception as e:
            self.root.after(0, lambda: self.append_health_output(f"\nError: {e}\n"))
            self.log_message(f"DISM error: {e}")
        finally:
            self.root.after(0, self.health_scan_complete)
    
    def run_dism_restore(self):
        """Run DISM RestoreHealth"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "DISM requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        if messagebox.askyesno("Run DISM RestoreHealth",
                "This will attempt to repair Windows component store.\n\n"
                "• Requires an internet connection\n"
                "• May take 15-30 minutes to complete\n\n"
                "Do you want to continue?"):
            
            self.dism_restore_btn.config(state=tk.DISABLED)
            self.set_status("Running DISM RestoreHealth...", "busy")
            self.root.after(0, lambda: self.update_task_status("DISM: RestoreHealth starting...", 0))
            
            self.health_output.delete(1.0, tk.END)
            self.health_output.insert(tk.END, "Starting DISM RestoreHealth...\n")
            self.health_output.insert(tk.END, "This may take 15-30 minutes. Please wait...\n\n")
            
            thread = threading.Thread(target=self.perform_dism_restore)
            thread.daemon = True
            thread.start()
    
    def perform_dism_restore(self):
        """Perform DISM RestoreHealth in background"""
        try:
            import re
            process = subprocess.Popen(
                ['dism', '/Online', '/Cleanup-Image', '/RestoreHealth'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.root.after(0, lambda l=line: self.append_health_output(l + "\n"))
                        # Parse percentage from DISM output
                        if '%' in line:
                            try:
                                match = re.search(r'(\d+(\.\d+)?)\s*%', line)
                                if match:
                                    pct = int(float(match.group(1)))
                                    self.root.after(0, lambda p=pct: self.update_task_status(f"DISM: RestoreHealth...", p))
                            except:
                                pass
            
            process.wait()
            
            self.root.after(0, lambda: self.update_task_status("DISM: RestoreHealth complete", 100))
            self.root.after(0, lambda: self.append_health_output("\n--- DISM RestoreHealth Complete ---\n"))
            self.root.after(0, lambda: self.append_health_output("\nIf repairs were made, run SFC scan next.\n"))
            self.log_message("DISM RestoreHealth completed")
            
        except Exception as e:
            self.root.after(0, lambda: self.append_health_output(f"\nError: {e}\n"))
            self.log_message(f"DISM RestoreHealth error: {e}")
        finally:
            self.root.after(0, self.health_scan_complete)
    
    def run_chkdsk(self):
        """Schedule Check Disk"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "Check Disk requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        if messagebox.askyesno("Schedule Check Disk",
                "This will schedule a disk check on your system drive.\n\n"
                "The check will run on the next system restart.\n\n"
                "Do you want to schedule it?"):
            
            try:
                result = subprocess.run(
                    ['chkdsk', 'C:', '/F', '/R'],
                    capture_output=True,
                    text=True,
                    input='Y\n',
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                self.health_output.delete(1.0, tk.END)
                self.health_output.insert(tk.END, "Check Disk Scheduled\n\n")
                self.health_output.insert(tk.END, result.stdout)
                self.health_output.insert(tk.END, "\nDisk check will run on next restart.\n")
                
                self.log_message("Check Disk scheduled for next restart")
                messagebox.showinfo("Check Disk Scheduled",
                    "Disk check has been scheduled.\n\n"
                    "It will run automatically on the next restart.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule Check Disk:\n{e}")
                self.log_message(f"Check Disk error: {e}")
    
    def append_health_output(self, text):
        """Append text to health output"""
        self.health_output.insert(tk.END, text)
        self.health_output.see(tk.END)
        self.root.update_idletasks()
    
    def update_task_status(self, task: str, percent: int = -1):
        """Update the bottom status bar with current task and percentage"""
        self.task_label.config(text=task)
        if percent >= 0:
            self.progress.config(mode='determinate')
            self.progress['value'] = percent
            self.percent_label.config(text=f"{percent}%")
        else:
            # Indeterminate mode
            self.progress.config(mode='indeterminate')
            self.percent_label.config(text="")
        self.root.update_idletasks()
    
    def reset_task_status(self):
        """Reset the status bar to ready state"""
        self.task_label.config(text="Ready")
        self.progress.stop()
        self.progress.config(mode='determinate')
        self.progress['value'] = 0
        self.percent_label.config(text="")
        self.root.update_idletasks()
    
    def health_scan_complete(self):
        """Called when health scan is complete"""
        self.reset_task_status()
        self.set_status("Health scan complete", "normal")
        self.sfc_btn.config(state=tk.NORMAL)
        self.dism_btn.config(state=tk.NORMAL)
        self.dism_restore_btn.config(state=tk.NORMAL)

    def log_message(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def set_status(self, status: str, state: str = "normal"):
        """Update status label and indicator"""
        self.status_label.config(text=status)
        
        # Update indicator color based on state
        colors = {
            "normal": self.COLORS['success'],
            "busy": self.COLORS['warning'],
            "error": self.COLORS['accent']
        }
        color = colors.get(state, self.COLORS['success'])
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(2, 2, 10, 10, fill=color, outline='')
        
        self.root.update_idletasks()
        
    def start_scan(self):
        """Start the driver scan in a background thread"""
        self.scan_btn.config(state=tk.DISABLED)
        self.set_status("Scanning...", "busy")
        self.update_task_status("Scanning system...", 0)
        
        thread = threading.Thread(target=self.perform_scan)
        thread.daemon = True
        thread.start()
        
    def perform_scan(self):
        """Perform the actual driver scan"""
        try:
            # Get system info
            self.root.after(0, lambda: self.update_task_status("Getting system info...", 10))
            self.system_info = self.scanner.get_system_info()
            self.root.after(0, self.update_system_info)
            
            # Scan installed drivers
            self.root.after(0, lambda: self.update_task_status("Scanning drivers...", 40))
            self.installed_drivers = self.scanner.scan_installed_drivers()
            self.root.after(0, self.populate_drivers_tree)
            
            # Check for problem devices
            self.root.after(0, lambda: self.update_task_status("Checking problem devices...", 80))
            self.problem_devices = self.scanner.scan_problem_devices()
            self.root.after(0, self.populate_problems_tree)
            
            self.root.after(0, lambda: self.update_task_status("Scan complete", 100))
            
        except Exception as e:
            self.log_message(f"Error during scan: {e}")
        finally:
            self.root.after(0, self.scan_complete)
            
    def scan_complete(self):
        """Called when scan is complete"""
        self.reset_task_status()
        self.scan_btn.config(state=tk.NORMAL)
        self.set_status(f"{len(self.installed_drivers)} drivers found", "normal")
        self.log_message("Scan complete!")
        
    def check_online_updates(self):
        """Check for online driver updates"""
        self.check_updates_btn.config(state=tk.DISABLED)
        self.set_status("Checking Windows Update...", "busy")
        self.update_task_status("Checking Windows Update...", -1)
        
        thread = threading.Thread(target=self.perform_online_check)
        thread.daemon = True
        thread.start()
        
    def perform_online_check(self):
        """Perform online update check"""
        try:
            self.available_updates = self.scanner.check_windows_update_drivers()
            self.root.after(0, self.populate_updates_tree)
        except Exception as e:
            self.log_message(f"Error checking updates: {e}")
        finally:
            self.root.after(0, self.online_check_complete)
            
    def online_check_complete(self):
        """Called when online check is complete"""
        self.reset_task_status()
        self.check_updates_btn.config(state=tk.NORMAL)
        
        if self.available_updates:
            self.install_btn.config(state=tk.NORMAL)
            self.set_status(f"{len(self.available_updates)} updates available", "normal")
            self.notebook.select(1)  # Switch to updates tab
        else:
            self.set_status("System up to date", "normal")
            
    def install_updates(self):
        """Install available updates"""
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "Installing driver updates requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
            
        if messagebox.askyesno("Install Updates",
                f"Install {len(self.available_updates)} driver update(s)?\n\n"
                "This may take several minutes and could require a restart."):
            
            self.install_btn.config(state=tk.DISABLED)
            self.progress.start()
            self.set_status("Installing updates...")
            
            thread = threading.Thread(target=self.perform_install)
            thread.daemon = True
            thread.start()
            
    def perform_install(self):
        """Perform update installation"""
        try:
            success = self.scanner.install_windows_updates()
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    "Driver updates installed successfully!"))
        except Exception as e:
            self.log_message(f"Installation error: {e}")
        finally:
            self.root.after(0, self.install_complete)
            
    def install_complete(self):
        """Called when installation is complete"""
        self.progress.stop()
        self.install_btn.config(state=tk.NORMAL)
        self.set_status("Installation complete")
        
    def update_system_info(self):
        """Update system info display"""
        mfr = self.system_info.get('Manufacturer', 'Unknown')
        model = self.system_info.get('Model', 'Unknown')
        sys_type = self.system_info.get('SystemType', 'Unknown')
        
        info_text = f"{mfr}  •  {model}  •  {sys_type}"
        self.sysinfo_label.config(text=info_text)
        
        # Also update manufacturer tools tab
        self.update_manufacturer_tools_tab()
        
    def populate_drivers_tree(self):
        """Populate the drivers treeview"""
        # Clear existing items
        for item in self.drivers_tree.get_children():
            self.drivers_tree.delete(item)
        
        # Configure alternating row tags
        self.drivers_tree.tag_configure('oddrow', background=self.COLORS['bg_glass'])
        self.drivers_tree.tag_configure('evenrow', background=self.COLORS['bg_row_alt'])
            
        # Add drivers with alternating colors
        for idx, driver in enumerate(self.installed_drivers):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.drivers_tree.insert('', tk.END, values=(
                driver.device_name,
                driver.manufacturer,
                driver.driver_version,
                driver.driver_date,
                driver.status
            ), tags=(tag,))
            
    def populate_updates_tree(self):
        """Populate the updates treeview"""
        for item in self.updates_tree.get_children():
            self.updates_tree.delete(item)
        
        # Configure alternating row tags
        self.updates_tree.tag_configure('oddrow', background=self.COLORS['bg_glass'])
        self.updates_tree.tag_configure('evenrow', background=self.COLORS['bg_row_alt'])
        
        # Store update objects for later reference
        self.update_items = {}
        
        for idx, update in enumerate(self.available_updates):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            item_id = self.updates_tree.insert('', tk.END, values=(
                '☐',  # Unchecked checkbox
                update.get('title', ''),
                update.get('manufacturer', ''),
                update.get('date', ''),
                '⟳' if update.get('reboot_required') else ''
            ), tags=(tag,))
            self.update_items[item_id] = update
        
        # Bind click to toggle selection
        self.updates_tree.bind('<ButtonRelease-1>', self.on_update_click)
            
    def populate_problems_tree(self):
        """Populate the problems treeview"""
        for item in self.problems_tree.get_children():
            self.problems_tree.delete(item)
        
        # Configure alternating row tags
        self.problems_tree.tag_configure('oddrow', background=self.COLORS['bg_glass'])
        self.problems_tree.tag_configure('evenrow', background=self.COLORS['bg_row_alt'])
            
        for idx, problem in enumerate(self.problem_devices):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.problems_tree.insert('', tk.END, values=(
                problem.get('name', ''),
                problem.get('status', ''),
                problem.get('error_code', ''),
                problem.get('device_id', '')
            ), tags=(tag,))
    
    def populate_online_tree(self):
        """Populate the online drivers treeview"""
        for item in self.online_tree.get_children():
            self.online_tree.delete(item)
        
        # Configure alternating row tags
        self.online_tree.tag_configure('oddrow', background=self.COLORS['bg_glass'])
        self.online_tree.tag_configure('evenrow', background=self.COLORS['bg_row_alt'])
        
        for idx, driver_info in enumerate(self.online_drivers):
            online = driver_info.get('online_info')
            if online:
                tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
                self.online_tree.insert('', tk.END, values=(
                    driver_info.get('device_name', ''),
                    driver_info.get('current_version', ''),
                    online.source,
                    online.description
                ), tags=(tag, online.download_url))
    
    def on_update_click(self, event):
        """Handle click on update item to toggle checkbox"""
        region = self.updates_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.updates_tree.identify_column(event.x)
            item = self.updates_tree.identify_row(event.y)
            if item and column == '#1':  # First column (checkbox)
                self.toggle_update_selection(item)
    
    def toggle_update_selection(self, item):
        """Toggle the selection checkbox for an update"""
        current_values = list(self.updates_tree.item(item, 'values'))
        if current_values[0] == '☐':
            current_values[0] = '☑'
        else:
            current_values[0] = '☐'
        self.updates_tree.item(item, values=current_values)
    
    def select_all_updates(self):
        """Select all updates"""
        for item in self.updates_tree.get_children():
            current_values = list(self.updates_tree.item(item, 'values'))
            current_values[0] = '☑'
            self.updates_tree.item(item, values=current_values)
    
    def deselect_all_updates(self):
        """Deselect all updates"""
        for item in self.updates_tree.get_children():
            current_values = list(self.updates_tree.item(item, 'values'))
            current_values[0] = '☐'
            self.updates_tree.item(item, values=current_values)
    
    def get_selected_updates(self):
        """Get list of selected update items"""
        selected = []
        for item in self.updates_tree.get_children():
            values = self.updates_tree.item(item, 'values')
            if values[0] == '☑':
                if item in self.update_items:
                    selected.append(self.update_items[item])
        return selected
    
    def download_and_install_selected(self):
        """Download and install selected updates"""
        selected = self.get_selected_updates()
        
        if not selected:
            messagebox.showinfo("No Selection", 
                "Please select at least one update to install.\n\n"
                "Click the checkbox (☐) next to each update you want to install.")
            return
        
        if not self.is_admin():
            messagebox.showwarning("Administrator Required",
                "Installing driver updates requires administrator privileges.\n\n"
                "Please restart this application as Administrator.")
            return
        
        # Confirm installation
        update_list = "\n".join([f"• {u.get('title', 'Unknown')}" for u in selected[:5]])
        if len(selected) > 5:
            update_list += f"\n... and {len(selected) - 5} more"
        
        if messagebox.askyesno("Install Updates",
                f"Download and install {len(selected)} driver update(s)?\n\n{update_list}\n\n"
                "This may take several minutes and could require a restart."):
            
            self.download_install_btn.config(state=tk.DISABLED)
            self.progress.start()
            self.set_status(f"Installing {len(selected)} update(s)...")
            
            thread = threading.Thread(target=lambda: self.perform_download_install(selected))
            thread.daemon = True
            thread.start()
    
    def perform_download_install(self, updates):
        """Perform the download and installation of selected updates"""
        try:
            self.log_message(f"Starting installation of {len(updates)} update(s)...")
            
            # Use Windows Update API to install specific updates
            success = self.scanner.install_windows_updates()
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"Driver updates installed successfully!\n\n"
                    "A system restart may be required to complete the installation."))
                self.log_message("Installation completed successfully")
            else:
                self.log_message("Installation completed with some issues")
                
        except Exception as e:
            self.log_message(f"Installation error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", 
                f"Failed to install updates:\n{e}"))
        finally:
            self.root.after(0, self.download_install_complete)
    
    def download_install_complete(self):
        """Called when download/install is complete"""
        self.progress.stop()
        self.download_install_btn.config(state=tk.NORMAL)
        self.set_status("Installation complete")
        
        # Refresh the updates list
        self.check_online_updates()
    
    def open_update_catalog(self):
        """Open Microsoft Update Catalog to search for drivers"""
        # If we have a selected update, search for it
        selection = self.updates_tree.selection()
        if selection:
            item = selection[0]
            values = self.updates_tree.item(item, 'values')
            if len(values) > 1:
                title = values[1]  # Title is second column now
                # Create search URL
                search_term = title.split('(')[0].strip()  # Get driver name without version
                url = f"https://www.catalog.update.microsoft.com/Search.aspx?q={search_term.replace(' ', '+')}"
                webbrowser.open(url)
                self.log_message(f"Opened MS Update Catalog: {search_term}")
                return
        
        # Otherwise just open the catalog
        webbrowser.open("https://www.catalog.update.microsoft.com/Home.aspx")
        self.log_message("Opened Microsoft Update Catalog")
    
    def check_vendor_drivers(self):
        """Check vendor websites for driver updates"""
        if not self.installed_drivers:
            messagebox.showinfo("Scan Required", 
                "Please scan drivers first before checking online sources.")
            return
        
        self.check_online_btn.config(state=tk.DISABLED)
        self.progress.start()
        self.set_status("Checking vendor driver sources...")
        
        thread = threading.Thread(target=self.perform_vendor_check)
        thread.daemon = True
        thread.start()
    
    def perform_vendor_check(self):
        """Perform vendor driver check in background"""
        try:
            self.online_drivers = self.online_checker.scan_all_drivers_online(self.installed_drivers)
            self.root.after(0, self.populate_online_tree)
        except Exception as e:
            self.log_message(f"Error checking vendor drivers: {e}")
        finally:
            self.root.after(0, self.vendor_check_complete)
    
    def vendor_check_complete(self):
        """Called when vendor check is complete"""
        self.progress.stop()
        self.check_online_btn.config(state=tk.NORMAL)
        
        if self.online_drivers:
            self.set_status(f"Found {len(self.online_drivers)} drivers with online sources")
            self.notebook.select(2)  # Switch to online sources tab
        else:
            self.set_status("No vendor driver sources found")
    
    def on_online_driver_double_click(self, event):
        """Handle double-click on online driver item"""
        self.open_selected_online_driver()
    
    def open_selected_online_driver(self):
        """Open the download URL for selected online driver"""
        selection = self.online_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a driver to open.")
            return
        
        item = selection[0]
        # Find the corresponding driver info
        item_values = self.online_tree.item(item, 'values')
        device_name = item_values[0] if item_values else ''
        
        for driver_info in self.online_drivers:
            if driver_info.get('device_name') == device_name:
                online = driver_info.get('online_info')
                if online and online.download_url:
                    webbrowser.open(online.download_url)
                    self.log_message(f"Opened: {online.download_url}")
                    return
        
        messagebox.showwarning("No URL", "No download URL available for this driver.")
    
    def open_all_online_sources(self):
        """Open all unique online driver source URLs"""
        if not self.online_drivers:
            messagebox.showinfo("No Sources", "No online driver sources to open.")
            return
        
        # Get unique URLs
        urls = set()
        for driver_info in self.online_drivers:
            online = driver_info.get('online_info')
            if online and online.download_url:
                urls.add(online.download_url)
        
        if urls:
            if messagebox.askyesno("Open URLs", 
                    f"Open {len(urls)} driver download page(s) in your browser?"):
                for url in urls:
                    webbrowser.open(url)
                    self.log_message(f"Opened: {url}")
        else:
            messagebox.showinfo("No URLs", "No download URLs available.")
    
    def update_manufacturer_tools_tab(self):
        """Update the manufacturer tools tab with detected system info"""
        mfr = self.system_info.get('Manufacturer', 'Unknown')
        model = self.system_info.get('Model', 'Unknown')
        serial = self.system_info.get('SerialNumber', '')
        
        # Update system label
        self.mfr_sys_label.config(text=f"Detected: {mfr} {model}")
        
        # Get manufacturer URLs
        self.manufacturer_urls = ManufacturerSupport.get_support_urls(mfr, model, serial)
        
        # Clear existing links
        for widget in self.mfr_links_frame.winfo_children():
            widget.destroy()
        
        # Add manufacturer-specific links
        row = 0
        mfr_name = self.manufacturer_urls.get('name', mfr)
        
        # Drivers page link
        if self.manufacturer_urls.get('drivers'):
            ttk.Label(self.mfr_links_frame, text=f"{mfr_name} Drivers:", 
                     font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, sticky="w", pady=5)
            link_btn = ttk.Button(self.mfr_links_frame, text="Open Driver Downloads",
                                 command=lambda url=self.manufacturer_urls['drivers']: webbrowser.open(url))
            link_btn.grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1
        
        # Support page link
        if self.manufacturer_urls.get('support'):
            ttk.Label(self.mfr_links_frame, text="Support Page:").grid(row=row, column=0, sticky="w", pady=5)
            link_btn = ttk.Button(self.mfr_links_frame, text="Open Support",
                                 command=lambda url=self.manufacturer_urls['support']: webbrowser.open(url))
            link_btn.grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1
        
        # Auto-detect tool
        if self.manufacturer_urls.get('auto_detect'):
            ttk.Label(self.mfr_links_frame, text="Auto-Detect Tool:").grid(row=row, column=0, sticky="w", pady=5)
            link_btn = ttk.Button(self.mfr_links_frame, text="Download Auto-Detect",
                                 command=lambda url=self.manufacturer_urls['auto_detect']: webbrowser.open(url))
            link_btn.grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1
        
        # Manufacturer tool info
        mfr_tool = self.manufacturer_urls.get('manufacturer_tool', {})
        if mfr_tool and mfr_tool.get('name'):
            ttk.Separator(self.mfr_links_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
            row += 1
            
            ttk.Label(self.mfr_links_frame, text="Recommended Tool:", 
                     font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Label(self.mfr_links_frame, text=mfr_tool.get('name', '')).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            row += 1
            
            if mfr_tool.get('url'):
                link_btn = ttk.Button(self.mfr_links_frame, text=f"Get {mfr_tool.get('name', 'Tool')}",
                                     command=lambda url=mfr_tool['url']: webbrowser.open(url))
                link_btn.grid(row=row, column=1, sticky="w", padx=10, pady=5)
    
    def open_manufacturer_tool(self):
        """Open the manufacturer's driver update tool download page"""
        if not self.manufacturer_urls:
            mfr = self.system_info.get('Manufacturer', '')
            model = self.system_info.get('Model', '')
            serial = self.system_info.get('SerialNumber', '')
            self.manufacturer_urls = ManufacturerSupport.get_support_urls(mfr, model, serial)
        
        mfr_tool = self.manufacturer_urls.get('manufacturer_tool', {})
        if mfr_tool and mfr_tool.get('url'):
            webbrowser.open(mfr_tool['url'])
            self.log_message(f"Opened: {mfr_tool['url']}")
        elif self.manufacturer_urls.get('auto_detect'):
            webbrowser.open(self.manufacturer_urls['auto_detect'])
            self.log_message(f"Opened: {self.manufacturer_urls['auto_detect']}")
        else:
            # Show a dialog with common tools
            self.show_common_tools_dialog()
    
    def show_common_tools_dialog(self):
        """Show a dialog with common manufacturer driver tools"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manufacturer Driver Tools")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text="Common Manufacturer Driver Update Tools",
                 font=('Segoe UI', 12, 'bold')).pack(pady=10)
        
        tools = [
            ("Dell SupportAssist", "https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/software-and-downloads/supportassist"),
            ("HP Support Assistant", "https://support.hp.com/us-en/help/hp-support-assistant"),
            ("Lenovo Vantage", "https://support.lenovo.com/solutions/ht003029"),
            ("ASUS MyASUS", "https://www.asus.com/supportonly/MyASUS/"),
            ("Acer Care Center", "https://www.acer.com/ac/en/US/content/software-acer-care-center"),
            ("MSI Dragon Center", "https://www.msi.com/Landing/dragon-center-download"),
            ("Intel Driver & Support Assistant", "https://www.intel.com/content/www/us/en/support/detect.html"),
            ("NVIDIA GeForce Experience", "https://www.nvidia.com/en-us/geforce/geforce-experience/"),
            ("AMD Adrenalin Software", "https://www.amd.com/en/support"),
        ]
        
        for name, url in tools:
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.X, padx=20, pady=2)
            ttk.Label(frame, text=name, width=30).pack(side=tk.LEFT)
            ttk.Button(frame, text="Download", 
                      command=lambda u=url: webbrowser.open(u)).pack(side=tk.RIGHT)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=20)
            
    def export_report(self):
        """Export driver report to file"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"driver_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("=" * 60 + "\n")
                    f.write("DRIVER UPDATE REPORT\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    
                    f.write("SYSTEM INFORMATION\n")
                    f.write("-" * 40 + "\n")
                    for key, value in self.system_info.items():
                        f.write(f"{key}: {value}\n")
                    f.write("\n")
                    
                    f.write("INSTALLED DRIVERS\n")
                    f.write("-" * 40 + "\n")
                    for driver in self.installed_drivers:
                        f.write(f"\nDevice: {driver.device_name}\n")
                        f.write(f"  Manufacturer: {driver.manufacturer}\n")
                        f.write(f"  Version: {driver.driver_version}\n")
                        f.write(f"  Date: {driver.driver_date}\n")
                        f.write(f"  Status: {driver.status}\n")
                    
                    if self.available_updates:
                        f.write("\n\nAVAILABLE UPDATES\n")
                        f.write("-" * 40 + "\n")
                        for update in self.available_updates:
                            f.write(f"\n{update.get('title', '')}\n")
                            f.write(f"  Source: {update.get('source', '')}\n")
                            f.write(f"  Date: {update.get('date', '')}\n")
                    
                    if self.problem_devices:
                        f.write("\n\nPROBLEM DEVICES\n")
                        f.write("-" * 40 + "\n")
                        for problem in self.problem_devices:
                            f.write(f"\n{problem.get('name', '')}\n")
                            f.write(f"  Error Code: {problem.get('error_code', '')}\n")
                            f.write(f"  Device ID: {problem.get('device_id', '')}\n")
                
                self.log_message(f"Report exported to: {filename}")
                messagebox.showinfo("Export Complete", f"Report saved to:\n{filename}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {e}")
                
    def open_manufacturer_site(self):
        """Open manufacturer support website"""
        mfr = self.system_info.get('Manufacturer', '')
        model = self.system_info.get('Model', '')
        
        url = self.scanner.get_manufacturer_support_url(mfr, model)
        webbrowser.open(url)
        self.log_message(f"Opened: {url}")
        
    def is_admin(self) -> bool:
        """Check if running with admin privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
            
    def run(self):
        """Start the application"""
        # Check if admin
        if self.is_admin():
            self.log_message("Running with administrator privileges")
        else:
            self.log_message("Running without administrator privileges")
            self.log_message("Note: Installing updates requires admin rights")
        
        self.log_message("Ready - Click 'Scan Drivers' to begin")
        self.root.mainloop()


def require_admin():
    """Ensure the application is running with administrator privileges"""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:
        # Re-run the program with admin rights
        try:
            # Get the script path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                script = sys.executable
                params = ' '.join(sys.argv[1:])
            else:
                # Running as script
                script = sys.executable
                params = f'"{sys.argv[0]}"'
                if len(sys.argv) > 1:
                    params += ' ' + ' '.join(sys.argv[1:])
            
            # Request elevation
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas",  # Request admin
                script, 
                params, 
                None, 
                1  # SW_SHOWNORMAL
            )
            
            # If ShellExecute succeeded (ret > 32), exit this instance
            if ret > 32:
                sys.exit(0)
            else:
                # User declined UAC or error occurred
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("Administrator Required",
                    "This application requires administrator privileges to install drivers.\n\n"
                    "Please right-click the application and select 'Run as administrator'.")
                sys.exit(1)
                
        except Exception as e:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Failed to request administrator privileges:\n{e}")
            sys.exit(1)


def main():
    """Main entry point"""
    # Require admin privileges
    require_admin()
    
    app = DriverUpdaterApp()
    app.run()


if __name__ == "__main__":
    main()
