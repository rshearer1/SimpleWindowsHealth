"""
Startup Entry Scanner for Windows
==================================
Comprehensive scanner that inventories all locations where startup apps can register.

Sources scanned:
1. Registry (HKLM/HKCU Run, RunOnce, Policies, Wow6432Node)
2. Startup Folders (All Users + Current User)
3. Task Scheduler (logon triggers)
4. Services (Auto-start, non-Microsoft)
5. WMI (Win32_StartupCommand)

Optimizations:
- Timing instrumentation for profiling
- Individual source scanning for parallel execution (future)

Usage:
    from startup_scanner import collect_startup_entries, StartupEntry
    entries = collect_startup_entries()
    for entry in entries:
        print(f"{entry.name}: {entry.command} [{entry.source}]")
"""

import os
import re
import winreg
import subprocess
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Set, Tuple
from pathlib import Path
import ctypes
from ctypes import wintypes

# Performance utilities
try:
    from perf_utils import timed, TimingContext
    PERF_UTILS_AVAILABLE = True
except ImportError:
    PERF_UTILS_AVAILABLE = False
    # Provide no-op fallbacks
    def timed(name=None):
        def decorator(func):
            return func
        return decorator
    class TimingContext:
        def __init__(self, name): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class StartupSource(Enum):
    """Source type for startup entry"""
    REGISTRY_HKLM_RUN = "Registry (HKLM\\Run)"
    REGISTRY_HKLM_RUNONCE = "Registry (HKLM\\RunOnce)"
    REGISTRY_HKLM_POLICIES = "Registry (HKLM\\Policies)"
    REGISTRY_HKCU_RUN = "Registry (HKCU\\Run)"
    REGISTRY_HKCU_RUNONCE = "Registry (HKCU\\RunOnce)"
    REGISTRY_HKCU_POLICIES = "Registry (HKCU\\Policies)"
    REGISTRY_WOW64 = "Registry (Wow6432Node)"
    STARTUP_FOLDER_USER = "Startup Folder (User)"
    STARTUP_FOLDER_COMMON = "Startup Folder (All Users)"
    TASK_SCHEDULER = "Task Scheduler"
    SERVICE = "Windows Service"
    WMI = "WMI"


class StartupStatus(Enum):
    """Status of startup entry"""
    ENABLED = "Enabled"
    DISABLED = "Disabled"
    UNKNOWN = "Unknown"


class ConfidenceLevel(Enum):
    """Confidence level for the entry (vendor trust)"""
    HIGH = "High"       # Known Microsoft or verified vendor
    MEDIUM = "Medium"   # Known vendor but not Microsoft
    LOW = "Low"         # Unknown vendor
    SUSPICIOUS = "Suspicious"  # Potentially unwanted


# Known trusted vendors
KNOWN_VENDORS = {
    "microsoft": ConfidenceLevel.HIGH,
    "nvidia": ConfidenceLevel.MEDIUM,
    "intel": ConfidenceLevel.MEDIUM,
    "amd": ConfidenceLevel.MEDIUM,
    "realtek": ConfidenceLevel.MEDIUM,
    "adobe": ConfidenceLevel.MEDIUM,
    "google": ConfidenceLevel.MEDIUM,
    "apple": ConfidenceLevel.MEDIUM,
    "logitech": ConfidenceLevel.MEDIUM,
    "corsair": ConfidenceLevel.MEDIUM,
    "razer": ConfidenceLevel.MEDIUM,
    "steam": ConfidenceLevel.MEDIUM,
    "valve": ConfidenceLevel.MEDIUM,
    "discord": ConfidenceLevel.MEDIUM,
    "spotify": ConfidenceLevel.MEDIUM,
    "dropbox": ConfidenceLevel.MEDIUM,
    "zoom": ConfidenceLevel.MEDIUM,
    "slack": ConfidenceLevel.MEDIUM,
}


@dataclass
class StartupEntry:
    """Represents a single startup entry from any source"""
    name: str
    command: str
    source: StartupSource
    source_path: str  # Full path (registry key, folder path, task path, etc.)
    status: StartupStatus = StartupStatus.ENABLED
    publisher: str = ""
    executable_path: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    impact: str = "Not measured"  # High, Medium, Low, Not measured
    description: str = ""
    
    # Unique identifier for deduplication
    def get_key(self) -> str:
        """Generate unique key for deduplication"""
        # Normalize command for comparison
        cmd = self.command.lower().strip()
        cmd = re.sub(r'\s+', ' ', cmd)
        return f"{cmd}|{self.source.value}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for UI consumption"""
        return {
            "name": self.name,
            "command": self.command,
            "source": self.source.value,
            "source_path": self.source_path,
            "status": self.status.value,
            "publisher": self.publisher,
            "executable_path": self.executable_path,
            "confidence": self.confidence.value,
            "impact": self.impact,
            "description": self.description,
            "enabled": self.status == StartupStatus.ENABLED,
        }


@dataclass
class ScanResult:
    """Result of a startup scan"""
    entries: List[StartupEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sources_scanned: List[str] = field(default_factory=list)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_executable_path(command: str) -> str:
    """Extract the executable path from a command line"""
    if not command:
        return ""
    
    command = command.strip()
    
    # Handle quoted paths
    if command.startswith('"'):
        end_quote = command.find('"', 1)
        if end_quote > 0:
            return command[1:end_quote]
    
    # Handle unquoted paths with spaces (look for .exe)
    exe_match = re.search(r'^([^"]+?\.exe)', command, re.IGNORECASE)
    if exe_match:
        return exe_match.group(1)
    
    # Just take the first token
    parts = command.split()
    if parts:
        return parts[0]
    
    return command


def get_publisher_from_path(exe_path: str) -> str:
    """Try to get publisher/company name from executable"""
    if not exe_path or not os.path.exists(exe_path):
        return ""
    
    try:
        # Use PowerShell to get file version info
        ps_cmd = f'''
        $file = Get-ItemProperty "{exe_path}" -ErrorAction SilentlyContinue
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("{exe_path}")
        $ver.CompanyName
        '''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    return ""


def determine_confidence(publisher: str, command: str) -> ConfidenceLevel:
    """Determine confidence level based on publisher and command"""
    if not publisher and not command:
        return ConfidenceLevel.LOW
    
    check_str = (publisher + " " + command).lower()
    
    for vendor, level in KNOWN_VENDORS.items():
        if vendor in check_str:
            return level
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'\\temp\\',
        r'\\appdata\\local\\temp',
        r'powershell.*-enc',
        r'cmd.*\/c.*del',
        r'wscript.*\.vbs',
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, check_str, re.IGNORECASE):
            return ConfidenceLevel.SUSPICIOUS
    
    return ConfidenceLevel.LOW


def estimate_impact(exe_path: str) -> str:
    """Estimate startup impact based on file size and type"""
    if not exe_path or not os.path.exists(exe_path):
        return "Not measured"
    
    try:
        size = os.path.getsize(exe_path)
        # Very rough heuristic
        if size > 50 * 1024 * 1024:  # > 50MB
            return "High"
        elif size > 10 * 1024 * 1024:  # > 10MB
            return "Medium"
        else:
            return "Low"
    except Exception:
        return "Not measured"


# =============================================================================
# REGISTRY SCANNER
# =============================================================================

@timed("scan_registry")
def scan_registry() -> Tuple[List[StartupEntry], List[str]]:
    """Scan all registry locations for startup entries"""
    entries = []
    warnings = []
    
    # Define all registry paths to scan
    registry_paths = [
        # HKLM paths
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 
         StartupSource.REGISTRY_HKLM_RUN, winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
         StartupSource.REGISTRY_HKLM_RUNONCE, winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run",
         StartupSource.REGISTRY_HKLM_POLICIES, winreg.KEY_READ),
        
        # HKLM Wow6432Node (32-bit apps on 64-bit Windows)
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
         StartupSource.REGISTRY_WOW64, winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce",
         StartupSource.REGISTRY_WOW64, winreg.KEY_READ),
        
        # HKCU paths
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
         StartupSource.REGISTRY_HKCU_RUN, winreg.KEY_READ),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
         StartupSource.REGISTRY_HKCU_RUNONCE, winreg.KEY_READ),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run",
         StartupSource.REGISTRY_HKCU_POLICIES, winreg.KEY_READ),
    ]
    
    for hive, path, source, access in registry_paths:
        try:
            key = winreg.OpenKey(hive, path, 0, access | winreg.KEY_WOW64_64KEY)
            try:
                i = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, i)
                        if value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                            # Expand environment variables
                            if value_type == winreg.REG_EXPAND_SZ:
                                value = os.path.expandvars(value)
                            
                            exe_path = extract_executable_path(value)
                            publisher = get_publisher_from_path(exe_path)
                            
                            entry = StartupEntry(
                                name=name,
                                command=value,
                                source=source,
                                source_path=f"{_hive_name(hive)}\\{path}",
                                status=StartupStatus.ENABLED,
                                publisher=publisher,
                                executable_path=exe_path,
                                confidence=determine_confidence(publisher, value),
                                impact=estimate_impact(exe_path),
                            )
                            entries.append(entry)
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)
        except FileNotFoundError:
            # Key doesn't exist, that's fine
            pass
        except PermissionError:
            warnings.append(f"Permission denied: {_hive_name(hive)}\\{path}")
        except Exception as e:
            warnings.append(f"Error reading {_hive_name(hive)}\\{path}: {str(e)}")
    
    # Also scan for disabled entries in StartupApproved
    entries.extend(_scan_startup_approved(warnings))
    
    return entries, warnings


def _hive_name(hive: int) -> str:
    """Get human-readable name for registry hive"""
    names = {
        winreg.HKEY_LOCAL_MACHINE: "HKLM",
        winreg.HKEY_CURRENT_USER: "HKCU",
        winreg.HKEY_CLASSES_ROOT: "HKCR",
        winreg.HKEY_USERS: "HKU",
    }
    return names.get(hive, str(hive))


def _scan_startup_approved(warnings: List[str]) -> List[StartupEntry]:
    """Scan StartupApproved registry keys for disabled entries"""
    entries = []
    
    approved_paths = [
        (winreg.HKEY_CURRENT_USER, 
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
         StartupSource.REGISTRY_HKCU_RUN),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
         StartupSource.REGISTRY_HKLM_RUN),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32",
         StartupSource.REGISTRY_WOW64),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32",
         StartupSource.REGISTRY_WOW64),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder",
         StartupSource.STARTUP_FOLDER_USER),
    ]
    
    for hive, path, source in approved_paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            try:
                i = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, i)
                        if value_type == winreg.REG_BINARY and len(value) >= 12:
                            # First byte indicates enabled (02/06) or disabled (03/07)
                            is_disabled = value[0] in (0x03, 0x07)
                            if is_disabled:
                                # This is a disabled entry
                                entry = StartupEntry(
                                    name=name,
                                    command="",  # Command not stored here
                                    source=source,
                                    source_path=f"{_hive_name(hive)}\\{path}",
                                    status=StartupStatus.DISABLED,
                                    description="Disabled via StartupApproved",
                                )
                                entries.append(entry)
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except PermissionError:
            warnings.append(f"Permission denied: {_hive_name(hive)}\\{path}")
        except Exception as e:
            warnings.append(f"Error reading StartupApproved: {str(e)}")
    
    return entries


# =============================================================================
# STARTUP FOLDER SCANNER
# =============================================================================

@timed("scan_startup_folders")
def scan_startup_folders() -> Tuple[List[StartupEntry], List[str]]:
    """Scan startup folders for shortcuts and executables"""
    entries = []
    warnings = []
    
    folders = [
        # Current user startup folder
        (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
         StartupSource.STARTUP_FOLDER_USER),
        # All users startup folder
        (os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup"),
         StartupSource.STARTUP_FOLDER_COMMON),
    ]
    
    for folder_path, source in folders:
        if not os.path.exists(folder_path):
            continue
        
        try:
            for filename in os.listdir(folder_path):
                full_path = os.path.join(folder_path, filename)
                
                if not os.path.isfile(full_path):
                    continue
                
                # Handle .lnk shortcuts
                if filename.lower().endswith('.lnk'):
                    target = _resolve_shortcut(full_path)
                    name = os.path.splitext(filename)[0]
                    command = target if target else full_path
                    exe_path = extract_executable_path(target) if target else ""
                else:
                    name = filename
                    command = full_path
                    exe_path = full_path
                
                publisher = get_publisher_from_path(exe_path)
                
                entry = StartupEntry(
                    name=name,
                    command=command,
                    source=source,
                    source_path=folder_path,
                    status=StartupStatus.ENABLED,
                    publisher=publisher,
                    executable_path=exe_path,
                    confidence=determine_confidence(publisher, command),
                    impact=estimate_impact(exe_path),
                )
                entries.append(entry)
                
        except PermissionError:
            warnings.append(f"Permission denied: {folder_path}")
        except Exception as e:
            warnings.append(f"Error reading {folder_path}: {str(e)}")
    
    return entries, warnings


def _resolve_shortcut(lnk_path: str) -> str:
    """Resolve a .lnk shortcut to its target using PowerShell"""
    try:
        ps_cmd = f'''
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut("{lnk_path}")
        $shortcut.TargetPath
        '''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


# =============================================================================
# TASK SCHEDULER SCANNER
# =============================================================================

@timed("scan_task_scheduler")
def scan_task_scheduler() -> Tuple[List[StartupEntry], List[str]]:
    """Scan Task Scheduler for startup/logon tasks"""
    entries = []
    warnings = []
    
    try:
        # Use PowerShell to get scheduled tasks with logon triggers
        ps_script = '''
        $tasks = @()
        Get-ScheduledTask | ForEach-Object {
            $task = $_
            $triggers = $task.Triggers | Where-Object {
                $_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' -or
                $_.CimClass.CimClassName -eq 'MSFT_TaskBootTrigger' -or
                $_.CimClass.CimClassName -eq 'MSFT_TaskSessionStateChangeTrigger'
            }
            if ($triggers) {
                $action = ($task.Actions | Select-Object -First 1)
                $tasks += [PSCustomObject]@{
                    Name = $task.TaskName
                    Path = $task.TaskPath
                    State = $task.State.ToString()
                    Execute = $action.Execute
                    Arguments = $action.Arguments
                    Author = $task.Author
                    Description = $task.Description
                    TriggerType = ($triggers | Select-Object -First 1).CimClass.CimClassName
                }
            }
        }
        $tasks | ConvertTo-Json -Depth 3
        '''
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                # Handle single object vs array
                if isinstance(data, dict):
                    data = [data]
                
                for task in data:
                    if not task:
                        continue
                    
                    execute = task.get('Execute', '') or ''
                    arguments = task.get('Arguments', '') or ''
                    command = f"{execute} {arguments}".strip() if execute else ""
                    
                    state = task.get('State', 'Unknown')
                    status = StartupStatus.ENABLED if state == 'Ready' else (
                        StartupStatus.DISABLED if state == 'Disabled' else StartupStatus.UNKNOWN
                    )
                    
                    exe_path = extract_executable_path(execute)
                    publisher = task.get('Author', '') or get_publisher_from_path(exe_path)
                    
                    entry = StartupEntry(
                        name=task.get('Name', 'Unknown Task'),
                        command=command,
                        source=StartupSource.TASK_SCHEDULER,
                        source_path=task.get('Path', ''),
                        status=status,
                        publisher=publisher,
                        executable_path=exe_path,
                        confidence=determine_confidence(publisher, command),
                        impact=estimate_impact(exe_path),
                        description=task.get('Description', ''),
                    )
                    entries.append(entry)
                    
            except json.JSONDecodeError as e:
                warnings.append(f"Failed to parse task scheduler data: {str(e)}")
        
        if result.stderr:
            warnings.append(f"Task Scheduler warnings: {result.stderr[:200]}")
            
    except subprocess.TimeoutExpired:
        warnings.append("Task Scheduler scan timed out")
    except Exception as e:
        warnings.append(f"Error scanning Task Scheduler: {str(e)}")
    
    return entries, warnings


# =============================================================================
# SERVICES SCANNER
# =============================================================================

@timed("scan_services")
def scan_services() -> Tuple[List[StartupEntry], List[str]]:
    """Scan for auto-start services (non-Microsoft)"""
    entries = []
    warnings = []
    
    try:
        # Get auto-start services
        ps_script = r'''
        Get-WmiObject Win32_Service | Where-Object {
            $_.StartMode -eq 'Auto' -and
            $_.ServiceType -in @('Own Process', 'Share Process', 'Kernel Driver', 'File System Driver')
        } | ForEach-Object {
            $svc = $_
            $isMicrosoft = $false
            $path = $svc.PathName
            if ($path) {
                $exePath = if ($path -match '^"([^"]+)"') { $matches[1] } 
                           elseif ($path -match '^([^\s]+\.exe)') { $matches[1] }
                           else { $path.Split()[0] }
                if (Test-Path $exePath -ErrorAction SilentlyContinue) {
                    $sig = Get-AuthenticodeSignature $exePath -ErrorAction SilentlyContinue
                    if ($sig.SignerCertificate.Subject -match 'Microsoft') {
                        $isMicrosoft = $true
                    }
                }
            }
            [PSCustomObject]@{
                Name = $svc.Name
                DisplayName = $svc.DisplayName
                PathName = $svc.PathName
                StartMode = $svc.StartMode
                State = $svc.State
                ServiceType = $svc.ServiceType
                IsMicrosoft = $isMicrosoft
                Description = $svc.Description
            }
        } | Where-Object { -not $_.IsMicrosoft } | ConvertTo-Json -Depth 2
        '''
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                
                for svc in data:
                    if not svc:
                        continue
                    
                    path_name = svc.get('PathName', '') or ''
                    exe_path = extract_executable_path(path_name)
                    publisher = get_publisher_from_path(exe_path)
                    
                    state = svc.get('State', '')
                    status = StartupStatus.ENABLED if state == 'Running' else (
                        StartupStatus.DISABLED if state == 'Stopped' else StartupStatus.UNKNOWN
                    )
                    
                    entry = StartupEntry(
                        name=svc.get('DisplayName', svc.get('Name', 'Unknown')),
                        command=path_name,
                        source=StartupSource.SERVICE,
                        source_path=f"Service: {svc.get('Name', '')}",
                        status=status,
                        publisher=publisher,
                        executable_path=exe_path,
                        confidence=determine_confidence(publisher, path_name),
                        impact="Medium",  # Services generally have medium impact
                        description=svc.get('Description', ''),
                    )
                    entries.append(entry)
                    
            except json.JSONDecodeError as e:
                warnings.append(f"Failed to parse services data: {str(e)}")
        
        if result.stderr and "error" in result.stderr.lower():
            warnings.append(f"Services scan warnings: {result.stderr[:200]}")
            
    except subprocess.TimeoutExpired:
        warnings.append("Services scan timed out")
    except Exception as e:
        warnings.append(f"Error scanning services: {str(e)}")
    
    return entries, warnings


# =============================================================================
# WMI SCANNER
# =============================================================================

@timed("scan_wmi")
def scan_wmi() -> Tuple[List[StartupEntry], List[str]]:
    """Scan WMI Win32_StartupCommand"""
    entries = []
    warnings = []
    
    try:
        ps_script = '''
        Get-WmiObject Win32_StartupCommand | ForEach-Object {
            [PSCustomObject]@{
                Name = $_.Name
                Command = $_.Command
                Location = $_.Location
                User = $_.User
                Description = $_.Description
            }
        } | ConvertTo-Json -Depth 2
        '''
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                
                for item in data:
                    if not item:
                        continue
                    
                    command = item.get('Command', '') or ''
                    exe_path = extract_executable_path(command)
                    publisher = get_publisher_from_path(exe_path)
                    
                    entry = StartupEntry(
                        name=item.get('Name', 'Unknown'),
                        command=command,
                        source=StartupSource.WMI,
                        source_path=item.get('Location', ''),
                        status=StartupStatus.ENABLED,
                        publisher=publisher,
                        executable_path=exe_path,
                        confidence=determine_confidence(publisher, command),
                        impact=estimate_impact(exe_path),
                        description=item.get('Description', ''),
                    )
                    entries.append(entry)
                    
            except json.JSONDecodeError as e:
                warnings.append(f"Failed to parse WMI data: {str(e)}")
                
    except subprocess.TimeoutExpired:
        warnings.append("WMI scan timed out")
    except Exception as e:
        warnings.append(f"Error scanning WMI: {str(e)}")
    
    return entries, warnings


# =============================================================================
# MAIN COLLECTOR
# =============================================================================

@timed("collect_startup_entries")
def collect_startup_entries(
    include_registry: bool = True,
    include_folders: bool = True,
    include_tasks: bool = True,
    include_services: bool = True,
    include_wmi: bool = True,
    dedupe: bool = True
) -> ScanResult:
    """
    Collect all startup entries from all sources.
    
    Args:
        include_registry: Scan registry locations
        include_folders: Scan startup folders
        include_tasks: Scan Task Scheduler
        include_services: Scan auto-start services
        include_wmi: Scan WMI
        dedupe: Remove duplicate entries
    
    Returns:
        ScanResult with entries, warnings, and errors
    """
    result = ScanResult()
    all_entries: List[StartupEntry] = []
    
    # Scan each source
    if include_registry:
        entries, warnings = scan_registry()
        all_entries.extend(entries)
        result.warnings.extend(warnings)
        result.sources_scanned.append("Registry")
    
    if include_folders:
        entries, warnings = scan_startup_folders()
        all_entries.extend(entries)
        result.warnings.extend(warnings)
        result.sources_scanned.append("Startup Folders")
    
    if include_tasks:
        entries, warnings = scan_task_scheduler()
        all_entries.extend(entries)
        result.warnings.extend(warnings)
        result.sources_scanned.append("Task Scheduler")
    
    if include_services:
        entries, warnings = scan_services()
        all_entries.extend(entries)
        result.warnings.extend(warnings)
        result.sources_scanned.append("Services")
    
    if include_wmi:
        entries, warnings = scan_wmi()
        all_entries.extend(entries)
        result.warnings.extend(warnings)
        result.sources_scanned.append("WMI")
    
    # Deduplicate
    if dedupe:
        seen: Set[str] = set()
        unique_entries: List[StartupEntry] = []
        for entry in all_entries:
            key = entry.get_key()
            if key not in seen:
                seen.add(key)
                unique_entries.append(entry)
            else:
                # Merge info from duplicate (prefer enabled status, longer descriptions)
                for existing in unique_entries:
                    if existing.get_key() == key:
                        if entry.status == StartupStatus.ENABLED:
                            existing.status = entry.status
                        entry_desc = entry.description or ""
                        existing_desc = existing.description or ""
                        if len(entry_desc) > len(existing_desc):
                            existing.description = entry.description
                        if entry.publisher and not existing.publisher:
                            existing.publisher = entry.publisher
                        break
        result.entries = unique_entries
    else:
        result.entries = all_entries
    
    return result


def get_startup_summary() -> dict:
    """Get a quick summary of startup entries for dashboard display"""
    result = collect_startup_entries()
    
    enabled_count = sum(1 for e in result.entries if e.status == StartupStatus.ENABLED)
    disabled_count = sum(1 for e in result.entries if e.status == StartupStatus.DISABLED)
    
    high_impact = [e for e in result.entries if e.impact == "High" and e.status == StartupStatus.ENABLED]
    
    return {
        "enabled_count": enabled_count,
        "disabled_count": disabled_count,
        "unknown_count": len(result.entries) - enabled_count - disabled_count,
        "high_impact": [e.to_dict() for e in high_impact[:5]],
        "threshold": 15,  # Warning if enabled > threshold
        "total": len(result.entries),
        "warnings": result.warnings,
    }


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Windows Startup Entry Scanner")
    print("=" * 70)
    print()
    
    print("Scanning all sources...")
    result = collect_startup_entries()
    
    print(f"\nSources scanned: {', '.join(result.sources_scanned)}")
    print(f"Total entries found: {len(result.entries)}")
    
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for w in result.warnings[:10]:
            print(f"  - {w}")
        if len(result.warnings) > 10:
            print(f"  ... and {len(result.warnings) - 10} more")
    
    # Group by source
    by_source: Dict[str, List[StartupEntry]] = {}
    for entry in result.entries:
        source = entry.source.value
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(entry)
    
    print("\n" + "=" * 70)
    print("ENTRIES BY SOURCE")
    print("=" * 70)
    
    for source, entries in sorted(by_source.items()):
        print(f"\n[{source}] - {len(entries)} entries")
        print("-" * 50)
        for entry in entries[:10]:
            status_icon = "✓" if entry.status == StartupStatus.ENABLED else "○"
            print(f"  {status_icon} {entry.name}")
            print(f"      Command: {entry.command[:60]}..." if len(entry.command) > 60 else f"      Command: {entry.command}")
            print(f"      Publisher: {entry.publisher or 'Unknown'} | Impact: {entry.impact}")
        if len(entries) > 10:
            print(f"  ... and {len(entries) - 10} more")
    
    # Summary stats
    enabled = sum(1 for e in result.entries if e.status == StartupStatus.ENABLED)
    disabled = sum(1 for e in result.entries if e.status == StartupStatus.DISABLED)
    high_impact = sum(1 for e in result.entries if e.impact == "High" and e.status == StartupStatus.ENABLED)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total:        {len(result.entries)}")
    print(f"  Enabled:      {enabled}")
    print(f"  Disabled:     {disabled}")
    print(f"  High Impact:  {high_impact}")
    print()
    print("Compare with Task Manager's Startup tab for verification.")
