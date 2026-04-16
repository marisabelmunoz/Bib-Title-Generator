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

def get_terminal_command():
    """Detect the terminal emulator being used."""
    system = platform.system()
    
    if system == "Windows":
        return "cmd.exe"
    elif system == "Darwin":  # macOS
        return "Terminal"
    else:  # Linux and others
        terminals = [
            "gnome-terminal",
            "xterm",
            "konsole",
            "terminator",
            "xfce4-terminal",
            "lxterminal",
            "urxvt",
            "st"
        ]
        
        for term in terminals:
            if shutil.which(term):
                return term
        return "xterm"

def get_application_path():
    """Get the full absolute path where the application is stored."""
    return os.path.dirname(os.path.abspath(__file__))

def install_requirements():
    """Check and install requirements from requirements.txt."""
    requirements_file = os.path.join(get_application_path(), "requirements.txt")
    
    if not os.path.exists(requirements_file):
        print("⚠️ requirements.txt not found. Skipping dependency installation.")
        return True
    
    print("📦 Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        print("✅ Requirements installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def create_shortcut_windows(app_path):
    """Create a proper .lnk shortcut for Windows."""
    try:
        import win32com.client
    except ImportError:
        print("❌ pywin32 not installed. Please run: pip install pywin32")
        return None
    
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.lnk")
    
    # Create the shortcut
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    
    # Set to open with cmd.exe and run the Python script
    shortcut.TargetPath = "cmd.exe"
    shortcut.Arguments = f'/k "cd /d "{app_path}" && "{python_exe}" "{app_script}"'
    shortcut.WorkingDirectory = app_path
    shortcut.Description = "Run Flask Application"
    shortcut.IconLocation = python_exe + ",0"  # Use Python icon
    
    shortcut.Save()
    print(f"✅ Shortcut created: {shortcut_path}")
    return shortcut_path

def create_shortcut_macos(app_path):
    """Create a .command file for macOS (acts like shortcut)."""
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.command")
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    
    with open(shortcut_path, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(f'cd "{app_path}"\n')
        f.write(f'"{python_exe}" "{app_script}"\n')
        f.write('read -p "Press Enter to close..."\n')
    
    os.chmod(shortcut_path, 0o755)
    print(f"✅ Shortcut created: {shortcut_path}")
    return shortcut_path

def create_shortcut_linux(app_path):
    """Create a .desktop shortcut for Linux."""
    shortcut_path = os.path.join(app_path, "Bibliographic Record AI Prompt Generator.desktop")
    python_exe = sys.executable
    app_script = os.path.join(app_path, "app.py")
    
    with open(shortcut_path, 'w') as f:
        f.write('[Desktop Entry]\n')
        f.write('Type=Application\n')
        f.write('Name=Bibliographic Record AI Prompt Generator\n')
        f.write(f'Exec=bash -c "cd \\"{app_path}\\" && \\"{python_exe}\\" \\"{app_script}\\"; read -p \'Press Enter to close...\'"\n')
        f.write(f'Path={app_path}\n')
        f.write('Terminal=true\n')
    
    os.chmod(shortcut_path, 0o755)
    print(f"✅ Shortcut created: {shortcut_path}")
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
    print("🔧 Installing Application")
    print("=" * 50)
    
    # 1. Install requirements
    if not install_requirements():
        print("❌ Installation failed due to dependency issues.")
        sys.exit(1)
    
    # 2. Detect terminal
    terminal = get_terminal_command()
    print(f"🖥️  Terminal detected: {terminal}")
    
    # 3. Get application path
    app_path = get_application_path()
    print(f"📁 Application path: {app_path}")
    
    # 4. Create shortcut
    shortcut_path = create_shortcut()
    
    if shortcut_path:
        print("\n" + "=" * 50)
        print("✅ Installation complete!")
        print(f"📝 Double-click '{os.path.basename(shortcut_path)}' to run the application.")
        print("=" * 50)

if __name__ == "__main__":
    main()