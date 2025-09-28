"""
GitHub Downloader Module (packaged)

Handles downloading files from GitHub releases, specifically for the tibia repository.
"""

import os
import json
import requests
from urllib.parse import urlparse


class GitHubDownloader:
    def __init__(self):
        self.repo_owner = "hecmo94"
        self.repo_name = "testclient"
        self.api_base_url = "https://api.github.com"
        self.raw_base_url = "https://raw.githubusercontent.com"
        self.config_file_name = "sample_launcher_config"
        self.config_branch = "refs/heads/main"  # Use refs/heads/main for the branch
        
        # Set up session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Tibia-Launcher/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def get_remote_config(self):
        """Get the launcher configuration from the remote repository"""
        try:
            # Check for test overrides first (for local testing)
            test_config_url = os.environ.get('LAUNCHER_CONFIG_URL')
            test_config_path = os.environ.get('LAUNCHER_CONFIG_PATH')
            
            if test_config_path and os.path.exists(test_config_path):
                # Load from local file for testing
                with open(test_config_path, 'r', encoding='utf-8') as f:
                    config_text = f.read().strip()
            elif test_config_url:
                # Load from custom URL for testing
                response = self.session.get(test_config_url, timeout=10)
                response.raise_for_status()
                config_text = response.text.strip()
            else:
                # Normal production config - try launcher_config.json first, then fall back
                config_urls = [
                    f"{self.raw_base_url}/{self.repo_owner}/{self.repo_name}/{self.config_branch}/launcher_config.json",
                    f"{self.raw_base_url}/{self.repo_owner}/{self.repo_name}/{self.config_branch}/{self.config_file_name}"
                ]
                
                config_text = None
                for url in config_urls:
                    try:
                        response = self.session.get(url, timeout=10)
                        response.raise_for_status()
                        config_text = response.text.strip()
                        break
                    except requests.exceptions.RequestException:
                        continue
                
                if not config_text:
                    raise requests.exceptions.RequestException("Could not fetch config from any URL")
            
            # Parse the config (assuming it's JSON format)
            try:
                config_data = json.loads(config_text)
                
                # Update repository settings from the new easy config format
                self._update_repo_from_config(config_data)
                
                return config_data
            except json.JSONDecodeError:
                # If it's not JSON, treat as simple key=value format
                config_data = {}
                for line in config_text.split('\n'):
                    line = line.strip()
                    if line and '=' in line:
                        key, value = line.split('=', 1)
                        config_data[key.strip()] = value.strip()
                return config_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching remote config: {e}")
            return None
        except Exception as e:
            print(f"Error parsing remote config: {e}")
            return None
    
    def get_release_by_tag(self, tag):
        """Get a specific release by tag"""
        try:
            url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/releases/tags/{tag}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            return release_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching release info for tag '{tag}': {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing release JSON: {e}")
            return None

    def get_latest_release(self):
        """Get the latest release information from GitHub (fallback method)"""
        try:
            url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            return release_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching latest release info: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing release JSON: {e}")
            return None
    
    def get_all_releases(self):
        """Get all releases from the repository"""
        try:
            url = f"{self.api_base_url}/repos/{self.repo_owner}/{self.repo_name}/releases"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            releases_data = self.session.get(url, timeout=10).json()
            return releases_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching releases: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing releases JSON: {e}")
            return []
    
    def find_zip_assets(self, release_data, zip_name=None):
        """Find zip assets in a release"""
        if not release_data or 'assets' not in release_data:
            return []
        
        zip_assets = []
        for asset in release_data['assets']:
            asset_name = asset.get('name', '')
            
            if zip_name:
                # Look for specific zip file
                if asset_name == zip_name or asset_name.lower() == zip_name.lower():
                    zip_assets.append(asset)
            else:
                # Find any zip files
                if asset_name.lower().endswith('.zip'):
                    zip_assets.append(asset)
        
        return zip_assets
    
    def find_tibia_assets(self, release_data):
        """Find all tibia.zip assets in a release (backwards compatibility)"""
        return self.find_zip_assets(release_data, 'tibia.zip')
    
    def get_asset_info(self, asset):
        """Get detailed information about an asset"""
        return {
            'name': asset.get('name', ''),
            'size': asset.get('size', 0),
            'download_url': asset.get('browser_download_url', ''),
            'created_at': asset.get('created_at', ''),
            'updated_at': asset.get('updated_at', ''),
            'download_count': asset.get('download_count', 0)
        }
    
    def download_file(self, url, local_path, progress_callback=None):
        """Download a file from URL with progress tracking"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Call progress callback if provided
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded_size, total_size)
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return False
        except IOError as e:
            print(f"Error writing file: {e}")
            return False
    
    def get_download_info_from_config(self):
        """Get download information based on remote config"""
        config = self.get_remote_config()
        if not config:
            return None
        
        # Check if there's a direct download link
        download_link = config.get('download_link') or config.get('download_url')
        if download_link:
            # Handle direct download link
            file_name = os.path.basename(download_link.split('?')[0])  # Remove query params
            if not file_name.endswith('.zip'):
                file_name = 'client.zip'  # Default name
            
            info = {
                'config': config,
                'direct_download': True,
                'download_link': download_link,
                'release': {
                    'tag_name': config.get('version', '1.0'),
                    'name': config.get('description', 'Direct Download'),
                    'published_at': '',
                    'body': '',
                    'prerelease': False,
                    'draft': False
                },
                'assets': [{
                    'name': file_name,
                    'size': 0,  # Unknown size for direct links
                    'download_url': download_link,
                    'created_at': '',
                    'updated_at': '',
                    'download_count': 0
                }]
            }
            return info
        
        # Fallback to GitHub release approach
        release_tag = config.get('release_tag') or config.get('version')
        zip_file_name = config.get('zip_file') or config.get('download_file')
        
        if not release_tag:
            print("No release_tag or download_link specified in remote config")
            return None
        
        # Get the specific release
        release_info = self.get_release_by_tag(release_tag)
        if not release_info:
            return None
        
        # Find the specified zip file
        if zip_file_name:
            zip_assets = self.find_zip_assets(release_info, zip_file_name)
        else:
            zip_assets = self.find_zip_assets(release_info)
        
        info = {
            'config': config,
            'direct_download': False,
            'release': {
                'tag_name': release_info.get('tag_name', ''),
                'name': release_info.get('name', ''),
                'published_at': release_info.get('published_at', ''),
                'body': release_info.get('body', ''),
                'prerelease': release_info.get('prerelease', False),
                'draft': release_info.get('draft', False)
            },
            'assets': []
        }
        
        for asset in zip_assets:
            info['assets'].append(self.get_asset_info(asset))
        
        return info
    
    def get_download_info(self):
        """Get comprehensive download information (backwards compatibility)"""
        # Try config-based approach first
        config_info = self.get_download_info_from_config()
        if config_info:
            return config_info
        
        # Fallback to old method
        release_info = self.get_latest_release()
        if not release_info:
            return None
        
        tibia_assets = self.find_tibia_assets(release_info)
        
        info = {
            'release': {
                'tag_name': release_info.get('tag_name', ''),
                'name': release_info.get('name', ''),
                'published_at': release_info.get('published_at', ''),
                'body': release_info.get('body', ''),
                'prerelease': release_info.get('prerelease', False),
                'draft': release_info.get('draft', False)
            },
            'assets': []
        }
        
        for asset in tibia_assets:
            info['assets'].append(self.get_asset_info(asset))
        
        return info
    
    def _update_repo_from_config(self, config_data):
        """Update repository settings from the new easy config format"""
        # Support both flat and nested config formats
        github_username = (config_data.get('github_username') or 
                          config_data.get('📁 GITHUB DOWNLOAD SETTINGS', {}).get('github_username'))
        github_repository = (config_data.get('github_repository') or 
                            config_data.get('📁 GITHUB DOWNLOAD SETTINGS', {}).get('github_repository'))
        
        if github_username:
            self.repo_owner = github_username
        if github_repository:
            self.repo_name = github_repository
            
        # Update config file name if specified
        client_zip_filename = (config_data.get('client_zip_filename') or 
                              config_data.get('📁 GITHUB DOWNLOAD SETTINGS', {}).get('client_zip_filename'))
        if client_zip_filename and not client_zip_filename.endswith('.zip'):
            # If they specify just a name without .zip, add it
            client_zip_filename += '.zip'
    
    def check_connectivity(self):
        """Check if GitHub API is accessible"""
        try:
            response = self.session.get(f"{self.api_base_url}/rate_limit", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
