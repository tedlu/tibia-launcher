"""
Launcher Core Module (packaged)

Moved into tibialauncher/core for better project organization.
"""
import os
import json
import zipfile
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import requests
from .github_downloader import GitHubDownloader
from .file_manager import FileManager


class LauncherCore:
	def __init__(self, tibia_dir: str | None = None):
		"""LauncherCore initializer.

		Parameters
		----------
		tibia_dir: Optional[str]
			If provided, use this as the base installation directory instead of auto-detection.
		"""
		# Determine base dir (allow caller override)
		self.tibia_dir = tibia_dir or self.get_default_tibia_directory()
		self.github_downloader = GitHubDownloader()
		self.file_manager = FileManager()
        
		# Default protected folders that should not be overwritten
		self.default_protected_folders = ['minimap', 'conf', 'characterdata']
		self.protected_folders = self.default_protected_folders.copy()
        
		# Folder structure
		self.download_folder_name = 'downloadclient'
		self.target_folder_name = 'Tibia'
        
		# Configuration file path (portable mode aware)
		self.config_file = os.path.join(self.tibia_dir, 'launcher_config.json')
		# Remote config cache
		self.remote_config = None
		# Load config (sets last_version if exists)
		self.load_config()
		# Mark first run if no recorded version
		self.first_run = not bool(getattr(self, 'last_version', ''))
		# Apply portable mode override if flag file present
		self.enable_portable_mode_if_requested()
		# Debug flags
		self.debug_players = os.environ.get('LAUNCHER_DEBUG_PLAYERS', '0') == '1'
    
	def get_default_tibia_directory(self):
		"""Get the default Tibia installation directory"""
		appdata = os.path.expandvars(r"%APPDATA%")  # Roaming profile
		if appdata and os.path.isdir(appdata):
			preferred = os.path.join(appdata, "Tibia")
			# Create it if missing so we commit to this location
			try:
				os.makedirs(preferred, exist_ok=True)
				return preferred
			except Exception:
				pass

		# Fallback sequence (legacy compatibility)
		legacy_paths = [
			os.path.expandvars(r"%USERPROFILE%\Documents\Tibia"),
			os.path.expandvars(r"%PROGRAMFILES%\Tibia"),
			os.path.expandvars(r"%PROGRAMFILES(X86)%\Tibia"),
			os.path.join(os.getcwd(), "Tibia")
		]
		for path in legacy_paths:
			if os.path.exists(path):
				return path
		return os.path.join(os.getcwd(), "Tibia")
    
	def set_tibia_directory(self, directory):
		"""Set the Tibia installation directory.

		Creates directory if it does not exist and persists config.
		"""
		if not directory:
			return
		self.tibia_dir = directory
		os.makedirs(self.tibia_dir, exist_ok=True)
		self.config_file = os.path.join(self.tibia_dir, 'launcher_config.json')
		self.save_config()

	# ------------------------------------------------------------------
	# Portable mode helper
	# ------------------------------------------------------------------
	@staticmethod
	def is_frozen() -> bool:
		return getattr(sys, 'frozen', False)

	@staticmethod
	def executable_dir() -> str:
		if getattr(sys, 'frozen', False):  # PyInstaller
			return os.path.dirname(sys.executable)
		return str(Path(__file__).resolve().parent)

	def enable_portable_mode_if_requested(self):
		"""If user drops a file named 'portable.flag' next to the EXE, store config there.

		This allows distributing a fully portable package without writing to %APPDATA%.
		"""
		try:
			exe_dir = self.executable_dir()
			flag = os.path.join(exe_dir, 'portable.flag')
			if os.path.exists(flag):
				# Use exe_dir/Tibia as base
				portable_target = os.path.join(exe_dir, 'Tibia')
				os.makedirs(portable_target, exist_ok=True)
				self.tibia_dir = portable_target
				self.config_file = os.path.join(self.tibia_dir, 'launcher_config.json')
				self.save_config()
		except Exception:
			pass
    
	def load_config(self):
		"""Load configuration from file"""
		if os.path.exists(self.config_file):
			try:
				with open(self.config_file, 'r') as f:
					config = json.load(f)
					self.last_version = config.get('last_version', '')
					self.last_update = config.get('last_update', '')
					custom_protected = config.get('protected_folders', [])
					if custom_protected:
						self.protected_folders = custom_protected
			except Exception:
				self.last_version = ''
				self.last_update = ''
		else:
			self.last_version = ''
			self.last_update = ''

	def save_config(self):
		"""Persist launcher configuration to JSON file.

		Stores last_version, last_update, and protected_folders. Silently
		ignores filesystem errors (so a readonly or portable medium does not
		crash the launcher). Returns True on success, False otherwise.
		"""
		try:
			os.makedirs(self.tibia_dir, exist_ok=True)
			data = {
				'last_version': getattr(self, 'last_version', ''),
				'last_update': getattr(self, 'last_update', ''),
				'protected_folders': self.protected_folders,
			}
			with open(self.config_file, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=2)
			return True
		except Exception:
			return False

	def get_remote_config(self, force_refresh: bool = False):
		"""Return remote configuration (cached).

		Delegates to GitHubDownloader. Cache result to avoid repeated network
		calls within a single launcher session.
		"""
		if self.remote_config is not None and not force_refresh:
			return self.remote_config
		self.remote_config = self.github_downloader.get_remote_config()
		return self.remote_config
    
	def set_protected_folders(self, folders):
		"""Set custom protected folders"""
		self.protected_folders = folders if folders else self.default_protected_folders.copy()
		self.file_manager.protected_folders = self.protected_folders
		self.save_config()
    
	def add_protected_folder(self, folder_name):
		"""Add a folder to the protected list"""
		if folder_name and folder_name not in self.protected_folders:
			self.protected_folders.append(folder_name)
			self.file_manager.protected_folders = self.protected_folders
			self.save_config()
    
	def remove_protected_folder(self, folder_name):
		"""Remove a folder from the protected list"""
		if folder_name in self.protected_folders:
			self.protected_folders.remove(folder_name)
			self.file_manager.protected_folders = self.protected_folders
			self.save_config()
    
	def get_download_folder_path(self):
		"""Get the full path to the download folder"""
		return os.path.join(self.tibia_dir, self.download_folder_name)
    
	def get_target_folder_path(self):
		"""Get the full path to the target Tibia folder"""
		return os.path.join(self.tibia_dir, self.target_folder_name)
    
	def ensure_folders_exist(self):
		"""Create the download and target folders if they don't exist"""
		download_path = self.get_download_folder_path()
		target_path = self.get_target_folder_path()
        
		os.makedirs(download_path, exist_ok=True)
		os.makedirs(target_path, exist_ok=True)
        
		return download_path, target_path
    
	def get_current_version(self):
		"""Get the currently installed version"""
		# Try to read from config first
		if hasattr(self, 'last_version') and self.last_version:
			return self.last_version
        
		# Try to find version file in Tibia folder first
		target_path = self.get_target_folder_path()
		version_file = os.path.join(target_path, 'version.txt')
		if os.path.exists(version_file):
			try:
				with open(version_file, 'r') as f:
					return f.read().strip()
			except Exception:
				pass
        
		# Try to find version file in main directory
		version_file = os.path.join(self.tibia_dir, 'version.txt')
		if os.path.exists(version_file):
			try:
				with open(version_file, 'r') as f:
					return f.read().strip()
			except Exception:
				pass
        
		# Check if any Tibia files exist in Tibia folder
		tibia_exe = os.path.join(target_path, 'Tibia.exe')
		if os.path.exists(tibia_exe):
			return "Unknown version (installed)"
        
		# Check if any Tibia files exist in main directory
		tibia_exe = os.path.join(self.tibia_dir, 'Tibia.exe')
		if os.path.exists(tibia_exe):
			return "Unknown version (installed)"
        
		return None
    
	def get_latest_release_info(self):
		"""Get information about the latest release from GitHub"""
		# Try config-based approach first
		download_info = self.github_downloader.get_download_info_from_config()
		if download_info:
			rel = download_info['release']
			# Normalize to always expose a 'version' key
			version_val = rel.get('version') or rel.get('tag_name') or rel.get('name') or ''
			# Strip common leading 'v'
			if isinstance(version_val, str) and version_val.lower().startswith('v') and version_val[1:2].isdigit():
				version_val = version_val[1:]
			rel['version'] = version_val
			return rel
        
		# Fallback to latest release
		rel = self.github_downloader.get_latest_release()
		if rel:
			version_val = rel.get('version') or rel.get('tag_name') or rel.get('name') or ''
			if isinstance(version_val, str) and version_val.lower().startswith('v') and version_val[1:2].isdigit():
				version_val = version_val[1:]
			rel['version'] = version_val
		return rel
    
	def is_update_available(self):
		"""Check if an update is available with enhanced version comparison"""
		current_version = self.get_current_version()
        
		# Get remote config to determine target version
		remote_config = self.get_remote_config()
		if remote_config:
			target_version = remote_config.get('release_tag') or remote_config.get('current_version') or remote_config.get('version')
			if target_version:
				if not current_version or current_version == "Not installed":
					return True
				return self._compare_versions(current_version, target_version) < 0
        
		# Fallback to release info
		latest_info = self.get_latest_release_info()
		if not latest_info:
			return False
        
		if not current_version or current_version == "Not installed":
			return True
        
		# Compare versions using enhanced comparison
		latest_version = latest_info.get('version') or latest_info.get('tag_name', '')
		return self._compare_versions(current_version, latest_version) < 0
    
	def _compare_versions(self, version1, version2):
		"""
		Compare two version strings using semantic versioning logic.
		Returns: -1 if version1 < version2, 0 if equal, 1 if version1 > version2
		"""
		def normalize_version(v):
			"""Normalize version string by removing 'v' prefix and splitting into parts"""
			if not v:
				return [0]
			# Remove 'v' prefix if present
			v = str(v).strip().lower()
			if v.startswith('v'):
				v = v[1:]
            
			try:
				# Split by dots and convert to integers
				parts = []
				for part in v.split('.'):
					# Handle pre-release suffixes like '1.0.0-beta'
					if '-' in part:
						part = part.split('-')[0]
					parts.append(int(part))
				return parts
			except (ValueError, AttributeError):
				# If parsing fails, treat as [0]
				return [0]
        
		v1_parts = normalize_version(version1)
		v2_parts = normalize_version(version2)
        
		# Pad shorter version with zeros
		max_length = max(len(v1_parts), len(v2_parts))
		v1_parts.extend([0] * (max_length - len(v1_parts)))
		v2_parts.extend([0] * (max_length - len(v2_parts)))
        
		# Compare part by part
		for p1, p2 in zip(v1_parts, v2_parts):
			if p1 < p2:
				return -1
			elif p1 > p2:
				return 1
        
		return 0
    
	def check_tibia_version_status(self):
		"""
		Comprehensive check of Tibia version status with detailed information.
		Returns dict with status, current_version, latest_version, update_available, etc.
		"""
		try:
			current_version = self.get_current_version()
			latest_info = self.get_latest_release_info()
            
			status = {
				'current_version': current_version or 'Not installed',
				'latest_version': None,
				'update_available': False,
				'first_install': False,
				'status_message': 'Unknown status',
				'description': '',
				'success': False
			}
            
			if not latest_info:
				status['status_message'] = '❌ Unable to check for updates'
				status['description'] = 'Failed to fetch latest release information'
				return status
            
			latest_version = latest_info.get('version') or latest_info.get('tag_name') or 'Unknown'
			description = latest_info.get('description') or latest_info.get('body', '').split('\n')[0] or 'New update available'
            
			status['latest_version'] = latest_version
			status['description'] = description
			status['success'] = True
            
			if not current_version or current_version == "Not installed":
				status['first_install'] = True
				status['update_available'] = True
				status['status_message'] = '📦 Ready to install'
			else:
				comparison = self._compare_versions(current_version, latest_version)
				if comparison < 0:
					status['update_available'] = True
					status['status_message'] = '🔄 Update available'
				elif comparison == 0:
					status['status_message'] = '✅ Up to date'
				else:
					# Current version is newer than latest (development version?)
					status['status_message'] = '🚀 Development version'
            
			return status
            
		except Exception as e:
			return {
				'current_version': current_version or 'Unknown',
				'latest_version': 'Unknown', 
				'update_available': False,
				'first_install': False,
				'status_message': f'⚠️ Check failed: {str(e)}',
				'description': 'Error occurred while checking version',
				'success': False
			}

	def download_and_install(self, progress_callback=None):
		"""Download and install the latest version"""
		try:
			# Get download info from config
			download_info = self.github_downloader.get_download_info_from_config()
			if not download_info:
				raise Exception("Could not get download information from remote config")
            
			release_info = download_info['release']
			config = download_info.get('config', {})
            
			# Find the specified zip asset
			if not download_info.get('assets'):
				raise Exception("No zip assets found")
            
			zip_asset = download_info['assets'][0]  # Use the first (and should be only) asset
            
			if not zip_asset:
				raise Exception("Could not find zip file to download")
            
			# Update protected folders from remote config if specified
			remote_protected = config.get('protected_folders')
			if remote_protected:
				if isinstance(remote_protected, str):
					# If it's a string, split by comma
					remote_protected = [f.strip() for f in remote_protected.split(',')]
				if isinstance(remote_protected, list):
					self.set_protected_folders(remote_protected)
            
			# Ensure folders exist
			download_path, target_path = self.ensure_folders_exist()
            
			# Check if this is first install or update
			current_version = self.get_current_version()
			is_first_install = not current_version or current_version == "Not installed"
            
			# Create temporary directory for download
			with tempfile.TemporaryDirectory() as temp_dir:
				zip_path = os.path.join(temp_dir, zip_asset['name'])
                
				if progress_callback:
					progress_callback(10, 100)
                
				# Download the zip file
				download_url = zip_asset.get('download_url') or zip_asset.get('browser_download_url')
				success = self.github_downloader.download_file(
					download_url,
					zip_path,
					progress_callback
				)
                
				if not success:
					raise Exception("Failed to download the update")
                
				if progress_callback:
					progress_callback(40, 100)
                
				# CLEAN: remove all non-protected items from target first
				self.clean_target_directory(target_path)

				if progress_callback:
					progress_callback(55, 100)

				# Backup protected folders AFTER cleaning for safety (only if update scenario)
				if not is_first_install:
					backup_path = os.path.join(temp_dir, 'backup')
					self.backup_protected_folders_from_target(backup_path, target_path)

				if progress_callback:
					progress_callback(60, 100)

				# Extract zip contents
				with zipfile.ZipFile(zip_path, 'r') as zip_ref:
					for member in zip_ref.infolist():
						# Skip protected folders entirely
						parts = member.filename.split('/')
						if parts and parts[0] in self.protected_folders:
							continue
						try:
							zip_ref.extract(member, target_path)
						except PermissionError:
							# Try to rename existing then re-attempt extract
							target_member_path = os.path.join(target_path, member.filename)
							if os.path.exists(target_member_path):
								try:
									renamed = target_member_path + f".old_{datetime.now().strftime('%Y%m%d%H%M%S')}"
									os.replace(target_member_path, renamed)
									zip_ref.extract(member, target_path)
								except Exception:
									print(f"Warning: skipped locked file {member.filename}")
							else:
								print(f"Warning: permission error extracting {member.filename}")
						except Exception as e:
							print(f"Warning extracting {member.filename}: {e}")

				if progress_callback:
					progress_callback(80, 100)

				# Restore protected folders (if update)
				if not is_first_install:
					self.restore_protected_folders_to_target(backup_path, target_path)
                
				if progress_callback:
					progress_callback(90, 100)
                
				# Update version info
				target_version = config.get('version') or config.get('release_tag') or release_info.get('tag_name', '1.0')
				self.last_version = target_version
				self.last_update = datetime.now().isoformat()
				self.save_config()
                
				# Create version file in target folder
				version_file = os.path.join(target_path, 'version.txt')
				with open(version_file, 'w') as f:
					f.write(self.last_version)
                
				if progress_callback:
					progress_callback(100, 100)
                
				return True
                
		except Exception as e:
			print(f"Installation error: {e}")
			raise e
    
	def backup_protected_folders(self, backup_dir):
		"""Backup protected folders before extraction"""
		backup_path = os.path.join(backup_dir, 'backup')
		os.makedirs(backup_path, exist_ok=True)
        
		for folder_name in self.protected_folders:
			source_path = os.path.join(self.tibia_dir, folder_name)
			if os.path.exists(source_path):
				dest_path = os.path.join(backup_path, folder_name)
				if os.path.isdir(source_path):
					shutil.copytree(source_path, dest_path)
				else:
					shutil.copy2(source_path, dest_path)
    
	def restore_protected_folders(self, backup_dir):
		"""Restore protected folders after extraction"""
		backup_path = os.path.join(backup_dir, 'backup')
        
		if not os.path.exists(backup_path):
			return
        
		for folder_name in self.protected_folders:
			source_path = os.path.join(backup_path, folder_name)
			if os.path.exists(source_path):
				dest_path = os.path.join(self.tibia_dir, folder_name)
                
				# Remove the extracted folder first if it exists
				if os.path.exists(dest_path):
					if os.path.isdir(dest_path):
						shutil.rmtree(dest_path)
					else:
						os.remove(dest_path)
                
				# Restore from backup
				if os.path.isdir(source_path):
					shutil.copytree(source_path, dest_path)
				else:
					shutil.copy2(source_path, dest_path)
    
	def backup_protected_folders_from_target(self, backup_dir, target_path):
		"""Backup protected folders from the target directory"""
		os.makedirs(backup_dir, exist_ok=True)
        
		for folder_name in self.protected_folders:
			source_path = os.path.join(target_path, folder_name)
			if os.path.exists(source_path):
				dest_path = os.path.join(backup_dir, folder_name)
				if os.path.isdir(source_path):
					shutil.copytree(source_path, dest_path)
				else:
					shutil.copy2(source_path, dest_path)
    
	def restore_protected_folders_to_target(self, backup_dir, target_path):
		"""Restore protected folders to the target directory"""
		if not os.path.exists(backup_dir):
			return
        
		for folder_name in self.protected_folders:
			source_path = os.path.join(backup_dir, folder_name)
			if os.path.exists(source_path):
				dest_path = os.path.join(target_path, folder_name)
                
				# Remove the existing folder first if it exists
				if os.path.exists(dest_path):
					if os.path.isdir(dest_path):
						shutil.rmtree(dest_path)
					else:
						os.remove(dest_path)
                
				# Restore from backup
				if os.path.isdir(source_path):
					shutil.copytree(source_path, dest_path)
				else:
					shutil.copy2(source_path, dest_path)

	def clean_target_directory(self, target_path, prune_old_backups=True):
		"""Remove all non-protected items from target directory.

		If a file/folder cannot be removed due to permission (locked), attempt a rename to .old_<timestamp>.
		Optionally prune very old .old_ backups (keep the last 5 per original name).
		"""
		if not os.path.isdir(target_path):
			return

		timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
		backups = {}
		for item in os.listdir(target_path):
			if item in self.protected_folders:
				continue
			item_path = os.path.join(target_path, item)
			# Skip version file until after extraction (it will be overwritten later)
			try:
				if os.path.isdir(item_path) and not os.path.islink(item_path):
					shutil.rmtree(item_path, ignore_errors=False)
				else:
					os.remove(item_path)
			except PermissionError:
				try:
					renamed = f"{item_path}.old_{timestamp}"
					os.replace(item_path, renamed)
					base = os.path.basename(item_path)
					backups.setdefault(base, []).append(renamed)
				except Exception:
					print(f"Warning: could not remove or rename locked item: {item_path}")
			except Exception as e:
				print(f"Warning deleting {item_path}: {e}")

		if prune_old_backups:
			# Collect all .old_ siblings and keep only newest 5 for each base name
			for entry in os.listdir(target_path):
				if '.old_' in entry:
					base_root = entry.split('.old_')[0]
					backups.setdefault(base_root, []).append(os.path.join(target_path, entry))
			for base, paths in backups.items():
				# Sort by modified time descending
				paths_sorted = sorted(paths, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
				for obsolete in paths_sorted[5:]:
					try:
						if os.path.isdir(obsolete):
							shutil.rmtree(obsolete, ignore_errors=True)
						else:
							os.remove(obsolete)
					except Exception:
						pass
    
	def extract_to_download_folder(self, zip_path, download_path):
		"""Extract the zip file to the download folder"""
		with zipfile.ZipFile(zip_path, 'r') as zip_ref:
			zip_ref.extractall(download_path)
    
	def move_files_to_target(self, download_path, target_path):
		"""Move files from download folder to target folder, skipping protected folders"""
		for item_name in os.listdir(download_path):
			# Skip protected folders
			if item_name in self.protected_folders:
				continue
            
			source_item = os.path.join(download_path, item_name)
			target_item = os.path.join(target_path, item_name)
            
			# Remove existing item in target if it exists
			if os.path.exists(target_item):
				if os.path.isdir(target_item):
					shutil.rmtree(target_item)
				else:
					os.remove(target_item)
            
			# Move item to target
			shutil.move(source_item, target_item)
    
	def extract_update(self, zip_path):
		"""Extract the update zip file (legacy method for backward compatibility)"""
		target_path = self.get_target_folder_path()
		os.makedirs(target_path, exist_ok=True)
        
		with zipfile.ZipFile(zip_path, 'r') as zip_ref:
			# Extract all files
			zip_ref.extractall(target_path)
    
	def launch_tibia(self):
		"""Launch the Tibia client"""
		# Priority 1: Look for client.exe in Tibia/bin/ folder
		target_path = self.get_target_folder_path()
		client_exe = os.path.join(target_path, 'bin', 'client.exe')
		if os.path.exists(client_exe):
			subprocess.Popen([client_exe], cwd=os.path.join(target_path, 'bin'))
			return
        
		# Priority 2: Look for common exe names in Tibia root
		exe_names = ['client.exe', 'Tibia.exe', 'tibia.exe', 'TibiaClient.exe']
		for exe_name in exe_names:
			exe_path = os.path.join(target_path, exe_name)
			if os.path.exists(exe_path):
				subprocess.Popen([exe_path], cwd=target_path)
				return
        
		# Priority 3: Look in any bin folder in Tibia
		bin_folder = os.path.join(target_path, 'bin')
		if os.path.exists(bin_folder):
			for exe_name in exe_names:
				exe_path = os.path.join(bin_folder, exe_name)
				if os.path.exists(exe_path):
					subprocess.Popen([exe_path], cwd=bin_folder)
					return
        
		# Fallback: Look in main directory
		for exe_name in exe_names:
			exe_path = os.path.join(self.tibia_dir, exe_name)
			if os.path.exists(exe_path):
				subprocess.Popen([exe_path], cwd=self.tibia_dir)
				return
        
		raise Exception("Could not find client executable. Expected: Tibia/bin/client.exe")

	# ------------------------------------------------------------------
	# Miscellaneous info helpers
	# ------------------------------------------------------------------
	def get_players_online(self, force_scrape: bool | None = None):
		"""Return current players online using JSON API if available, else fallback to HTML scraping.

		Order:
		  1. Attempt JSON endpoints (fast, stable)
		  2. Fallback to legacy /?online? HTML page scraping
		Returns an int or None.
		"""
		if force_scrape is None:
			force_scrape = os.environ.get('PLAYERS_FORCE_SCRAPE', '0') == '1'
		if self.debug_players and force_scrape:
			print("[players-debug] Force scrape mode active (skip API)")

		if not force_scrape:
			# 1. JSON API attempt(s)
			override = os.environ.get('PLAYERS_API_ENDPOINTS')
			if override:
				api_endpoints = [p.strip() for p in override.split(',') if p.strip()]
			else:
				api_endpoints = [
					"https://your-tibia-server.com/api/online",
					"https://your-tibia-server.com/api/status",
				]
			for api_url in api_endpoints:
				try:
					resp = requests.get(api_url, timeout=5)
					if not resp.ok:
						if self.debug_players:
							print(f"[players-debug] API {api_url} -> HTTP {resp.status_code}")
						continue
					data = resp.json()
					for key in ("online", "players_online", "players", "playersOnline"):
						if key in data:
							try:
								val = int(data[key])
								if 0 <= val <= 50000:
									if self.debug_players:
										print(f"[players-debug] API {api_url} key '{key}'={val}")
									return val
							except (TypeError, ValueError):
								continue
				except Exception as ex:
					if self.debug_players:
						print(f"[players-debug] Exception calling {api_url}: {ex}")
					continue

		# 2. Fallback HTML scraping (expanded list of likely pages)
		html_pages = [
			"https://your-tibia-server.com/?online",
			"https://your-tibia-server.com/?subtopic=serverinfo",
			"https://your-tibia-server.com/?subtopic=worlds",
			"https://your-tibia-server.com/?subtopic=highscores",
			"https://your-tibia-server.com/?subtopic=latestnews",
			"https://your-tibia-server.com/index.php",
			"https://your-tibia-server.com/",
		]

		import re
		patterns = [
			r"Players? Online\D+(\d+)",
			r"Online Players?\D+(\d+)",
			r"(\d+)\s+players? online",
			r"(\d+)\s+online now",
		]

		for page in html_pages:
			try:
				resp = requests.get(page, timeout=8)
				if not resp.ok:
					continue
				text = resp.text
				if self.debug_players:
					print(f"[players-debug] Scrape {page} status={resp.status_code} length={len(text)}")
				for pat in patterns:
					m = re.search(pat, text, re.IGNORECASE)
					if m:
						try:
							val = int(m.group(1).replace(',', ''))
							if 0 <= val <= 50000:
								if self.debug_players:
									print(f"[players-debug] Pattern '{pat}' matched {val} on {page}")
								return val
						except ValueError:
							continue
				# Broad heuristic fallback: capture standalone small integers near words 'player' or 'online'
				vicinity = re.findall(r"(\d{1,5})", text)
				if vicinity:
					candidates = [int(v) for v in vicinity if v.isdigit() and 0 < int(v) <= 50000]
					if candidates:
						# pick the most frequent plausible number to reduce random noise
						from collections import Counter
						most_common = Counter(candidates).most_common(3)
						if most_common:
							if self.debug_players:
								print(f"[players-debug] Heuristic chose {most_common[0][0]} on {page}")
							return most_common[0][0]
			except Exception as ex:
				if self.debug_players:
					print(f"[players-debug] Exception scraping {page}: {ex}")
				continue
		return None

	def check_launcher_update(self):
		"""Check if there's a newer version of the launcher available"""
		try:
			config = self.get_remote_config()
			if not config:
				return None
                
			# Support both old and new config formats
			if 'enable_auto_update' in config and config.get('enable_auto_update'):
				current_launcher_version = config.get('current_launcher_version', '1.0.0')
				launcher_username = config.get('launcher_github_username', '')
				launcher_repo = config.get('launcher_github_repository', 'tibialauncher')
                
				if launcher_username and launcher_repo:
					# Get latest release from launcher repository
					api_url = f"https://api.github.com/repos/{launcher_username}/{launcher_repo}/releases/latest"
					response = requests.get(api_url, timeout=10)
                    
					if response.ok:
						release_data = response.json()
						latest_version = release_data.get('tag_name', '').lstrip('v')
                        
						# Simple version comparison (assumes semantic versioning)
						if self._is_newer_version(latest_version, self.get_current_launcher_version()):
							return {
								'available': True,
								'latest_version': latest_version,
								'current_version': self.get_current_launcher_version(),
								'download_url': self._get_launcher_download_url(release_data),
								'changelog': release_data.get('body', ''),
								'release_name': release_data.get('name', f'Version {latest_version}')
							}
            
			return {'available': False}
		except Exception as e:
			print(f"Error checking launcher update: {e}")
			return None
    
	def get_current_launcher_version(self):
		"""Get the current launcher version"""
		# This should match the version in your launcher
		return "2.0.0"  # Update this when you release new versions
    
	def _is_newer_version(self, latest, current):
		"""Simple version comparison for semantic versioning (X.Y.Z)"""
		try:
			latest_parts = [int(x) for x in latest.split('.')]
			current_parts = [int(x) for x in current.split('.')]
            
			# Pad with zeros if different lengths
			max_len = max(len(latest_parts), len(current_parts))
			latest_parts += [0] * (max_len - len(latest_parts))
			current_parts += [0] * (max_len - len(current_parts))
            
			return latest_parts > current_parts
		except (ValueError, AttributeError):
			return False
    
	def _get_launcher_download_url(self, release_data):
		"""Extract the launcher download URL from GitHub release"""
		assets = release_data.get('assets', [])
        
		# Look for common launcher file patterns
		for asset in assets:
			name = asset.get('name', '').lower()
			if any(pattern in name for pattern in ['launcher.exe', 'tibialauncher.exe', '.exe']):
				return asset.get('browser_download_url')
        
		# Fallback to the first asset if no .exe found
		if assets:
			return assets[0].get('browser_download_url')
        
		return None
    
	def download_launcher_update(self, download_url, progress_callback=None):
		"""Download the launcher update"""
		try:
			response = requests.get(download_url, stream=True)
			response.raise_for_status()
            
			# Get file size for progress
			total_size = int(response.headers.get('content-length', 0))
            
			# Create temporary file
			with tempfile.NamedTemporaryFile(delete=False, suffix='.exe') as temp_file:
				downloaded = 0
				chunk_size = 8192
                
				for chunk in response.iter_content(chunk_size=chunk_size):
					if chunk:
						temp_file.write(chunk)
						downloaded += len(chunk)
                        
						# Report progress
						if progress_callback and total_size > 0:
							progress = (downloaded / total_size) * 100
							progress_callback(progress)
                
				return temp_file.name
                
		except Exception as e:
			print(f"Error downloading launcher update: {e}")
			return None
    
	def apply_launcher_update(self, update_file_path):
		"""Apply the launcher update by replacing the current executable"""
		try:
			import sys
			current_exe = sys.executable
            
			# If running from Python, try to find the actual launcher executable
			if current_exe.endswith('python.exe') or 'python' in current_exe.lower():
				# Look for launcher executable in current directory
				possible_names = ['tibialauncher.exe', 'launcher.exe', 'TibiaLauncher.exe']
				for name in possible_names:
					test_path = os.path.join(os.getcwd(), name)
					if os.path.exists(test_path):
						current_exe = test_path
						break
            
			if not os.path.exists(current_exe) or 'python' in current_exe.lower():
				raise Exception("Could not find launcher executable to update")
            
			# Create batch file to handle the update
			batch_content = f'''@echo off
echo Updating Tibia Launcher...
timeout /t 2 /nobreak >nul
copy /y "{update_file_path}" "{current_exe}"
if %errorlevel% equ 0 (
	echo Update completed successfully!
	echo Starting updated launcher...
	start "" "{current_exe}"
) else (
	echo Update failed!
	pause
)
del "{update_file_path}"
del "%~f0"
'''
            
			batch_file = os.path.join(tempfile.gettempdir(), 'launcher_update.bat')
			with open(batch_file, 'w') as f:
				f.write(batch_content)
            
			# Execute the batch file and exit current launcher
			subprocess.Popen([batch_file], shell=True)
			return True
            
		except Exception as e:
			print(f"Error applying launcher update: {e}")
			return False

