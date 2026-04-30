#!/usr/bin/env python3
"""
Installation script for the application.
Run with: python install.py
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def get_application_path():
    """Get the full absolute path where the application is stored."""
    return os.path.dirname(os.path.abspath(__file__))

def check_requirements_installed():
    """Check if requirements are already installed."""
    requirements_file = os.path.join(get_application_path(), "requirements.txt")
    
    if not os.path.exists(requirements_file):
        return False
    
    # Read requirements
    with open(requirements_file, 'r') as f:
        required_packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    missing_packages = []
    for package in required_packages:
        # Extract package name (remove version specifiers)
        package_name = package.split('>=')[0].split('==')[0].split('<')[0].strip()
        try:
            subprocess.check_call([sys.executable, "-c", f"import {package_name.replace('-', '_')}"], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            missing_packages.append(package)
    
    return len(missing_packages) == 0, missing_packages

def install_requirements():
    """Smart check and install requirements from requirements.txt."""
    requirements_file = os.path.join(get_application_path(), "requirements.txt")
    
    if not os.path.exists(requirements_file):
        print("⚠️ requirements.txt not found. Skipping dependency installation.")
        return True
    
    # Check if requirements are already installed
    installed, missing = check_requirements_installed()
    
    if installed:
        print("✅ All requirements are already installed. Skipping installation.")
        return True
    
    if missing:
        print(f"📦 Installing missing requirements: {', '.join(missing)}")
    else:
        print("📦 Installing requirements...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("✅ Requirements installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def get_icon_path():
    """Get the path to the application icon."""
    app_path = get_application_path()
    icon_path = os.path.join(app_path, "static", "bibpromp.ico")
    
    # If .ico doesn't exist, try .png or other common formats
    if not os.path.exists(icon_path):
        for ext in ['.png', '.svg', '.icns']:
            alt_icon = os.path.join(app_path, "static", f"bibpromp{ext}")
            if os.path.exists(alt_icon):
                return alt_icon
    
    return icon_path if os.path.exists(icon_path) else None

def create_shortcut_windows(app_path):
    """Create a proper .lnk shortcut for Windows with icon."""
    try:
        import win32com.client
    except ImportError:
        print("⚠️ pywin32 not installed. Installing it for better shortcut support...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
            import win32com.client
        except:
            print("❌ Could not install pywin32. Shortcut will be created without icon.")
            return create_simple_shortcut_windows(app_path)
    
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.lnk")
    
    # Get icon path
    icon_path = get_icon_path()
    
    # Create the shortcut
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    
    # Set to open with cmd.exe and run the Python script
    shortcut.TargetPath = "cmd.exe"
    shortcut.Arguments = f'/k "cd /d "{app_path}" && "{python_exe}" "{app_script}"'
    shortcut.WorkingDirectory = app_path
    shortcut.Description = "Bibliographic Record AI Prompt Generator"
    
    # Set icon if available
    if icon_path and os.path.exists(icon_path):
        shortcut.IconLocation = icon_path
    else:
        shortcut.IconLocation = python_exe + ",0"  # Fallback to Python icon
    
    shortcut.Save()
    print(f"✅ Shortcut created: {shortcut_path}")
    if icon_path:
        print(f"   Icon applied: {icon_path}")
    return shortcut_path

def create_simple_shortcut_windows(app_path):
    """Fallback method to create a .bat file if pywin32 fails."""
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.bat")
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    
    with open(shortcut_path, 'w') as f:
        f.write('@echo off\n')
        f.write(f'cd /d "{app_path}"\n')
        f.write(f'"{python_exe}" "{app_script}"\n')
        f.write('pause\n')
    
    print(f"✅ Batch file created: {shortcut_path}")
    print("   Note: For a proper shortcut with icon, please run: pip install pywin32")
    return shortcut_path

def create_shortcut_macos(app_path):
    """Create a .command file for macOS with icon support."""
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.command")
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    icon_path = get_icon_path()
    
    with open(shortcut_path, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(f'cd "{app_path}"\n')
        f.write(f'"{python_exe}" "{app_script}"\n')
        f.write('read -p "Press Enter to close..."\n')
    
    os.chmod(shortcut_path, 0o755)
    
    # On macOS, .command files don't support custom icons easily
    # But we can create an .app bundle or use AppleScript
    if icon_path and icon_path.endswith('.icns'):
        print(f"ℹ️ Icon file found at {icon_path}")
        print("   For better icon support on macOS, consider creating a proper .app bundle")
    
    print(f"✅ Shortcut created: {shortcut_path}")
    return shortcut_path

def create_shortcut_linux(app_path):
    """Create a .desktop shortcut for Linux with icon support."""
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.desktop")
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    icon_path = get_icon_path()
    
    with open(shortcut_path, 'w') as f:
        f.write('[Desktop Entry]\n')
        f.write('Type=Application\n')
        f.write('Name=Bibliographic Record AI Prompt Generator\n')
        f.write('Comment=Generate MARC21 prompts for AI processing\n')
        f.write(f'Exec=bash -c "cd \\"{app_path}\\" && \\"{python_exe}\\" \\"{app_script}\\; read -p \'Press Enter to close...\'"\n')
        f.write(f'Path={app_path}\n')
        f.write('Terminal=true\n')
        
        # Add icon if available
        if icon_path and os.path.exists(icon_path):
            f.write(f'Iron={icon_path}\n')
        
        # Categories for desktop environments
        f.write('Categories=Office;Education;Utility;\n')
    
    os.chmod(shortcut_path, 0o755)
    
    # Try to register the shortcut with the desktop environment
    desktop_dir = Path.home() / ".local/share/applications"
    if desktop_dir.exists():
        try:
            shutil.copy2(shortcut_path, desktop_dir / shortcut_path.name)
            print(f"✅ Shortcut also copied to {desktop_dir}")
        except Exception as e:
            print(f"⚠️ Could not copy to applications directory: {e}")
    
    print(f"✅ Shortcut created: {shortcut_path}")
    if icon_path:
        print(f"   Icon applied: {icon_path}")
    return shortcut_path

def create_shortcut():
    """Create a shortcut to run the application based on the OS."""
    app_path = get_application_path()
    system = platform.system()
    
    if system == "Windows":
        return create_shortcut_windows(app_path)
    elif system == "Darwin":
        return create_shortcut_macos(app_path)
    else:
        return create_shortcut_linux(app_path)

def main():
    """Main installation function."""
    print("=" * 50)
    print("🔧 Installing Bibliographic Record AI Prompt Generator")
    print("=" * 50)
    
    # Check for icon
    icon_path = get_icon_path()
    if icon_path:
        print(f"🎨 Icon found: {icon_path}")
    else:
        print("⚠️ No icon file found in static/ directory. Using default icon.")
        print("   Expected path: static/bibpromp.ico")
    
    # 1. Install requirements (smart check)
    if not install_requirements():
        print("❌ Installation failed due to dependency issues.")
        sys.exit(1)
    
    # 2. Get application path
    app_path = get_application_path()
    print(f"📁 Application path: {app_path}")
    
    # 3. Create shortcut
    shortcut_path = create_shortcut()
    
    if shortcut_path:
        print("\n" + "=" * 50)
        print("✅ Installation complete!")
        print(f"📝 Double-click '{os.path.basename(shortcut_path)}' to run the application.")
        if platform.system() == "Windows" and not shortcut_path.endswith('.bat'):
            print("   The shortcut will appear in the application folder with the custom icon.")
        elif platform.system() == "Linux":
            print("   You can also find the shortcut in your applications menu.")
        print("=" * 50)
    else:
        print("\n❌ Failed to create shortcut. You can run the app manually:")
        print(f"   python {os.path.join(app_path, 'app.py')}")

if __name__ == "__main__":
    main()