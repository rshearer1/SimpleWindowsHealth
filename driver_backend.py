"""
Driver Update Scanner & Installer - Backend Module
Contains all business logic, WMI queries, and system operations
"""

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
from typing import List, Optional, Dict, Tuple, Callable
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
    
    DRIVER_DATABASE = {
        'nvidia': {
            'vendor_id': '10DE',
            'api_url': 'https://www.nvidia.com/Download/processFind.aspx',
            'support_url': 'https://www.nvidia.com/Download/index.aspx'
        },
        'amd': {
            'vendor_id': '1002',
            'api_url': 'https://www.amd.com/en/support',
            'support_url': 'https://www.amd.com/en/support'
        },
        'intel': {
            'vendor_id': '8086',
            'api_url': 'https://www.intel.com/content/www/us/en/download-center/home.html',
            'support_url': 'https://www.intel.com/content/www/us/en/download-center/home.html'
        },
        'realtek': {
            'vendor_id': '10EC',
            'support_url': 'https://www.realtek.com/en/downloads'
        }
    }
    
    def __init__(self, callback: Callable[[str], None] = None):
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
            numbers = re.findall(r'\d+', version_str)
            return tuple(int(n) for n in numbers[:4])
        except:
            return (0,)
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns: -1 if v1<v2, 0 if equal, 1 if v1>v2"""
        t1 = self.parse_version(v1)
        t2 = self.parse_version(v2)
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
            match = re.search(r'DEV_([0-9A-F]{4})', device_id.upper())
            if not match:
                return None
            dev_id = match.group(1)
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
            intel_dsa_url = "https://www.intel.com/content/www/us/en/support/detect.html"
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
        
        if 'VEN_10DE' in device_id:
            return self.check_nvidia_driver(device_id, driver.driver_version)
        elif 'VEN_1002' in device_id:
            return self.check_amd_driver(device_id, driver.driver_version)
        elif 'VEN_8086' in device_id:
            return self.check_intel_driver(device_id, device_class, driver.driver_version)
        elif 'VEN_10EC' in device_id:
            return self.check_realtek_driver(device_id, device_class)
        
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
        checked_vendors = set()
        
        for driver in drivers:
            device_id = driver.device_id.upper()
            vendor_match = re.search(r'VEN_([0-9A-F]{4})', device_id)
            vendor_id = vendor_match.group(1) if vendor_match else None
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
            'auto_detect': 'https://support.microsoft.com/en-us/windows/update-drivers-in-windows',
            'keywords': ['microsoft', 'surface']
        },
        'samsung': {
            'name': 'Samsung',
            'detect_url': 'https://www.samsung.com/us/support/downloads/',
            'drivers_url': 'https://www.samsung.com/us/support/downloads/',
            'support_url': 'https://www.samsung.com/us/support/',
            'auto_detect': 'https://www.samsung.com/us/support/',
            'keywords': ['samsung']
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
    
    PROTECTED_PROVIDERS = [
        'microsoft', 'windows', 'intel corporation', 'amd', 'nvidia',
        'realtek', 'qualcomm', 'broadcom', 'marvell'
    ]
    
    def __init__(self, callback: Callable[[str], None] = None):
        self.callback = callback
        self.drivers: List[DriverInfo] = []
        self.available_updates: List[dict] = []
        
    def log(self, message: str):
        """Send log message to callback"""
        if self.callback:
            self.callback(message)
    
    def run_powershell(self, command: str, timeout: int = 120) -> str:
        """Execute a PowerShell command and return output"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
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
                            date_str = item['DriverDate']
                            if '/Date(' in date_str:
                                timestamp = int(date_str.replace('/Date(', '').replace(')/', '').split('-')[0].split('+')[0])
                                driver_date = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d')
                            else:
                                driver_date = str(date_str)[:10]
                        except:
                            driver_date = str(item.get('DriverDate', ''))[:10]
                    
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
    
    def install_windows_updates(self) -> bool:
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
        elif "RESULT:2" in output:
            self.log("Driver updates installed successfully!")
            if "REBOOT:True" in output:
                self.log("A system restart is required to complete the installation")
            return True
        else:
            self.log("Installation completed with warnings")
            return True
    
    def find_unused_drivers(self) -> List[dict]:
        """Advanced unused driver detection"""
        self.log("Performing comprehensive driver analysis...")
        
        command = """
        $results = @()
        
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
        
        $activeDrivers = @{}
        try {
            Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | 
            Where-Object { $_.InfName } | 
            ForEach-Object { $activeDrivers[$_.InfName] = $_ }
        } catch {}
        
        foreach ($infName in $storeDrivers.Keys) {
            $driver = $storeDrivers[$infName]
            $reason = @()
            $risk = "safe"
            
            if ($infName -notlike "oem*.inf") { continue }
            
            $inUse = $connectedDevices.ContainsKey($infName) -or $activeDrivers.ContainsKey($infName)
            
            if (-not $inUse) {
                $reason += "Not used by any connected device"
            }
            
            $provider = $driver.Provider.ToLower()
            $isProtected = $false
            $protectedProviders = @('microsoft', 'intel', 'amd', 'nvidia', 'realtek', 'qualcomm', 'broadcom')
            foreach ($pp in $protectedProviders) {
                if ($provider -like "*$pp*") {
                    if ($inUse) {
                        $isProtected = $true
                        $risk = "protected"
                    }
                    break
                }
            }
            
            if (-not $driver.Signer -or $driver.Signer -eq "" -or $driver.Signer -like "*not signed*") {
                $reason += "Unsigned driver"
                if ($risk -ne "protected") { $risk = "caution" }
            }
            
            $className = $driver.ClassName
            $category = "Other"
            switch -Wildcard ($className) {
                "*Display*" { $category = "GPU" }
                "*Graphics*" { $category = "GPU" }
                "*Audio*" { $category = "Audio" }
                "*Sound*" { $category = "Audio" }
                "*Network*" { $category = "Network" }
                "*Net*" { $category = "Network" }
                "*USB*" { $category = "USB" }
                "*Printer*" { $category = "Printer" }
                "*Bluetooth*" { $category = "Bluetooth" }
                "*Storage*" { $category = "Storage" }
                "*HID*" { $category = "Input" }
            }
            
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
            
            risk_order = {'caution': 0, 'safe': 1, 'protected': 2}
            unused_drivers.sort(key=lambda x: risk_order.get(x.get('risk', 'safe'), 1))
            
            if unused_drivers:
                self.log(f"Found {len(unused_drivers)} potentially removable drivers")
            else:
                self.log("No unused drivers found - system is clean!")
        except Exception as e:
            self.log(f"Error scanning for unused drivers: {e}")
        
        return unused_drivers
    
    def check_driver_in_use(self, inf_name: str) -> bool:
        """Check if a driver is currently in use by any device"""
        try:
            result = subprocess.run(
                ['pnputil', '/enum-devices', '/drivers'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if inf_name.lower() in result.stdout.lower():
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if inf_name.lower() in line.lower():
                        for j in range(max(0, i-5), min(len(lines), i+5)):
                            if 'Status:' in lines[j] and 'Started' in lines[j]:
                                return True
            return False
        except:
            return False
    
    def remove_driver(self, driver_inf: str) -> Tuple[bool, str]:
        """Remove a driver from the driver store"""
        self.log(f"Removing driver: {driver_inf}")
        
        try:
            result = subprocess.run(
                ['pnputil', '/delete-driver', driver_inf, '/force'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0:
                self.log(f"Successfully removed {driver_inf}")
                return True, "Success"
            else:
                output = result.stderr.strip() or result.stdout.strip()
                if "presently installed" in output.lower() or "in use" in output.lower():
                    return False, "Driver is in use"
                self.log(f"Failed to remove {driver_inf}: {output}")
                return False, output
        except Exception as e:
            self.log(f"Error removing driver: {e}")
            return False, str(e)


class HealthChecker:
    """Windows system health checking"""
    
    def __init__(self, callback: Callable[[str], None] = None):
        self.callback = callback
    
    def log(self, message: str):
        if self.callback:
            self.callback(message)
    
    def run_powershell(self, command: str, timeout: int = 120) -> str:
        """Execute a PowerShell command and return output"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.stdout
        except:
            return ""
    
    def check_defender_status(self) -> dict:
        """Check Windows Defender status"""
        self.log("Checking Windows Defender status...")
        command = """
        try {
            $defender = Get-MpComputerStatus -ErrorAction Stop
            @{
                RealTimeProtection = $defender.RealTimeProtectionEnabled
                AntivirusEnabled = $defender.AntivirusEnabled
                AntispywareEnabled = $defender.AntispywareEnabled
                SignatureAge = $defender.AntivirusSignatureAge
                LastScan = $defender.LastFullScanEndTime.ToString("yyyy-MM-dd HH:mm")
                QuickScanAge = $defender.QuickScanAge
            } | ConvertTo-Json
        } catch {
            @{ Error = $_.Exception.Message } | ConvertTo-Json
        }
        """
        output = self.run_powershell(command)
        try:
            return json.loads(output)
        except:
            return {"Error": "Could not check Defender status"}
    
    def check_windows_update_status(self) -> dict:
        """Check Windows Update status"""
        self.log("Checking Windows Update status...")
        command = """
        try {
            $session = New-Object -ComObject Microsoft.Update.Session
            $searcher = $session.CreateUpdateSearcher()
            $pending = $searcher.Search("IsInstalled=0").Updates.Count
            
            $lastCheck = Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\Results\\Detect" -ErrorAction SilentlyContinue
            $lastInstall = Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\Results\\Install" -ErrorAction SilentlyContinue
            
            @{
                PendingUpdates = $pending
                LastCheck = if ($lastCheck.LastSuccessTime) { $lastCheck.LastSuccessTime } else { "Unknown" }
                LastInstall = if ($lastInstall.LastSuccessTime) { $lastInstall.LastSuccessTime } else { "Unknown" }
            } | ConvertTo-Json
        } catch {
            @{ Error = $_.Exception.Message } | ConvertTo-Json
        }
        """
        output = self.run_powershell(command)
        try:
            return json.loads(output)
        except:
            return {"Error": "Could not check Windows Update status"}
    
    def run_sfc_scan(self) -> str:
        """Run System File Checker"""
        self.log("Running System File Checker (this may take several minutes)...")
        try:
            result = subprocess.run(
                ['sfc', '/scannow'],
                capture_output=True,
                text=True,
                timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.stdout
        except Exception as e:
            return f"Error running SFC: {e}"
    
    def run_dism_scan(self) -> str:
        """Run DISM health check"""
        self.log("Running DISM health check...")
        try:
            result = subprocess.run(
                ['DISM', '/Online', '/Cleanup-Image', '/ScanHealth'],
                capture_output=True,
                text=True,
                timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.stdout
        except Exception as e:
            return f"Error running DISM: {e}"
    
    def check_disk_health(self) -> List[dict]:
        """Check disk health using SMART data"""
        self.log("Checking disk health...")
        command = """
        Get-CimInstance Win32_DiskDrive | ForEach-Object {
            $disk = $_
            $smart = Get-CimInstance -Namespace root\\wmi MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue |
                     Where-Object { $_.InstanceName -like "*$($disk.Index)*" }
            
            @{
                Model = $disk.Model
                Size = [math]::Round($disk.Size / 1GB, 2)
                Status = $disk.Status
                MediaType = $disk.MediaType
                PredictFailure = if ($smart) { $smart.PredictFailure } else { $null }
            }
        } | ConvertTo-Json -Depth 2
        """
        output = self.run_powershell(command)
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return data
        except:
            return []
    
    def get_volume_info(self) -> List[dict]:
        """Get information about all volumes"""
        self.log("Getting volume information...")
        command = """
        Get-Volume | Where-Object { $_.DriveLetter } | ForEach-Object {
            @{
                DriveLetter = $_.DriveLetter
                FileSystemLabel = $_.FileSystemLabel
                FileSystem = $_.FileSystem
                SizeGB = [math]::Round($_.Size / 1GB, 2)
                FreeSpaceGB = [math]::Round($_.SizeRemaining / 1GB, 2)
                HealthStatus = $_.HealthStatus
                DriveType = $_.DriveType
            }
        } | ConvertTo-Json -Depth 2
        """
        output = self.run_powershell(command)
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return data
        except:
            return []


class DiskManager:
    """Disk management operations"""
    
    def __init__(self, callback: Callable[[str], None] = None):
        self.callback = callback
    
    def log(self, message: str):
        if self.callback:
            self.callback(message)
    
    def run_chkdsk(self, drive_letter: str, fix: bool = False) -> str:
        """Run CHKDSK on a drive"""
        self.log(f"Running CHKDSK on {drive_letter}:...")
        cmd = ['chkdsk', f'{drive_letter}:']
        if fix:
            cmd.append('/F')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.stdout
        except Exception as e:
            return f"Error running CHKDSK: {e}"
    
    def optimize_drive(self, drive_letter: str) -> str:
        """Optimize/defragment a drive"""
        self.log(f"Optimizing drive {drive_letter}:...")
        try:
            result = subprocess.run(
                ['defrag', f'{drive_letter}:', '/O'],
                capture_output=True,
                text=True,
                timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.stdout
        except Exception as e:
            return f"Error optimizing drive: {e}"
    
    def run_disk_cleanup(self, drive_letter: str) -> str:
        """Run disk cleanup"""
        self.log(f"Running disk cleanup on {drive_letter}:...")
        try:
            result = subprocess.run(
                ['cleanmgr', '/d', drive_letter],
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return "Disk Cleanup launched"
        except Exception as e:
            return f"Error running cleanup: {e}"


def is_admin() -> bool:
    """Check if running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Relaunch the application with admin privileges"""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()


def open_url(url: str):
    """Open a URL in the default browser"""
    webbrowser.open(url)
