"""
File Manager Module (packaged)

Handles file operations for the Tibia launcher, including selective extraction,
backup operations, and file system management.
"""

import os
import shutil
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime


class FileManager:
    def __init__(self):
        self.protected_folders = ['minimap', 'conf', 'character data']
        self.protected_files = [
            'launcher_config.json',
            'version.txt'
        ]
    
    def create_backup(self, source_dir, backup_dir, folders_to_backup=None):
        """Create a backup of specified folders"""
        if folders_to_backup is None:
            folders_to_backup = self.protected_folders
        
        backup_info = {
            'timestamp': datetime.now().isoformat(),
            'backed_up_items': [],
            'backup_path': backup_dir
        }
        
        os.makedirs(backup_dir, exist_ok=True)
        
        for item_name in folders_to_backup:
            source_path = os.path.join(source_dir, item_name)
            
            if os.path.exists(source_path):
                dest_path = os.path.join(backup_dir, item_name)
                
                try:
                    if os.path.isdir(source_path):
                        shutil.copytree(source_path, dest_path)
                        backup_info['backed_up_items'].append({
                            'name': item_name,
                            'type': 'directory',
                            'size': self.get_directory_size(source_path)
                        })
                    else:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                        backup_info['backed_up_items'].append({
                            'name': item_name,
                            'type': 'file',
                            'size': os.path.getsize(source_path)
                        })
                        
                except Exception as e:
                    print(f"Warning: Could not backup {item_name}: {e}")
        
        return backup_info
    
    def restore_backup(self, backup_dir, target_dir, items_to_restore=None):
        """Restore backed up items to target directory"""
        if not os.path.exists(backup_dir):
            return False
        
        if items_to_restore is None:
            items_to_restore = self.protected_folders
        
        restored_items = []
        
        for item_name in items_to_restore:
            source_path = os.path.join(backup_dir, item_name)
            
            if os.path.exists(source_path):
                dest_path = os.path.join(target_dir, item_name)
                
                try:
                    # Remove existing item if it exists
                    if os.path.exists(dest_path):
                        if os.path.isdir(dest_path):
                            shutil.rmtree(dest_path)
                        else:
                            os.remove(dest_path)
                    
                    # Restore from backup
                    if os.path.isdir(source_path):
                        shutil.copytree(source_path, dest_path)
                    else:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                    
                    restored_items.append(item_name)
                    
                except Exception as e:
                    print(f"Warning: Could not restore {item_name}: {e}")
        
        return restored_items
    
    def extract_zip_selective(self, zip_path, extract_to, exclude_folders=None):
        """Extract zip file while excluding specified folders"""
        if exclude_folders is None:
            exclude_folders = self.protected_folders
        
        extracted_files = []
        skipped_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Check if file is in excluded folder
                should_skip = False
                for exclude_folder in exclude_folders:
                    if member.startswith(f"{exclude_folder}/") or member.startswith(f"{exclude_folder}\\"):
                        should_skip = True
                        skipped_files.append(member)
                        break
                
                if not should_skip:
                    try:
                        zip_ref.extract(member, extract_to)
                        extracted_files.append(member)
                    except Exception as e:
                        print(f"Warning: Could not extract {member}: {e}")
        
        return {
            'extracted_files': extracted_files,
            'skipped_files': skipped_files
        }
    
    def get_directory_size(self, directory):
        """Calculate total size of a directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        return total_size
    
    def get_directory_info(self, directory):
        """Get comprehensive information about a directory"""
        if not os.path.exists(directory):
            return None
        
        info = {
            'path': directory,
            'exists': True,
            'size': 0,
            'file_count': 0,
            'folder_count': 0,
            'protected_items_present': [],
            'last_modified': None
        }
        
        try:
            # Get basic stats
            stat_info = os.stat(directory)
            info['last_modified'] = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
            
            # Count files and folders, calculate size
            for dirpath, dirnames, filenames in os.walk(directory):
                info['folder_count'] += len(dirnames)
                info['file_count'] += len(filenames)
                
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        info['size'] += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        pass
            
            # Check for protected items
            for item_name in self.protected_folders + self.protected_files:
                item_path = os.path.join(directory, item_name)
                if os.path.exists(item_path):
                    item_info = {
                        'name': item_name,
                        'type': 'directory' if os.path.isdir(item_path) else 'file',
                        'size': self.get_directory_size(item_path) if os.path.isdir(item_path) else os.path.getsize(item_path)
                    }
                    info['protected_items_present'].append(item_info)
                    
        except Exception as e:
            print(f"Error getting directory info: {e}")
        
        return info
    
    def cleanup_temp_files(self, temp_dir):
        """Clean up temporary files and directories"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                return True
        except Exception as e:
            print(f"Warning: Could not clean up temp files: {e}")
        return False
    
    def verify_extraction(self, zip_path, extract_dir):
        """Verify that extraction was successful"""
        verification_info = {
            'success': True,
            'missing_files': [],
            'corrupted_files': [],
            'total_files_in_zip': 0,
            'total_files_extracted': 0
        }
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_files = [f for f in zip_ref.namelist() if not f.endswith('/')]
                verification_info['total_files_in_zip'] = len(zip_files)
                
                for zip_file in zip_files:
                    extracted_path = os.path.join(extract_dir, zip_file)
                    
                    if os.path.exists(extracted_path):
                        verification_info['total_files_extracted'] += 1
                        
                        # Basic size check
                        try:
                            zip_info = zip_ref.getinfo(zip_file)
                            if os.path.getsize(extracted_path) != zip_info.file_size:
                                verification_info['corrupted_files'].append(zip_file)
                        except Exception:
                            pass  # Skip size verification if there's an issue
                    else:
                        verification_info['missing_files'].append(zip_file)
                
                if verification_info['missing_files'] or verification_info['corrupted_files']:
                    verification_info['success'] = False
                    
        except Exception as e:
            print(f"Error during extraction verification: {e}")
            verification_info['success'] = False
        
        return verification_info
    
    def create_directory_structure(self, base_dir, structure):
        """Create a directory structure from a dictionary"""
        created_dirs = []
        
        for dir_name in structure:
            dir_path = os.path.join(base_dir, dir_name)
            try:
                os.makedirs(dir_path, exist_ok=True)
                created_dirs.append(dir_path)
            except Exception as e:
                print(f"Warning: Could not create directory {dir_path}: {e}")
        
        return created_dirs
