"""Create only this package's isolated environment; never edit MCP host settings."""
import os
import shutil
import importlib.util
from pathlib import Path
import subprocess
import sys
import venv

root = Path(__file__).resolve().parent
venv_dir = root / '.venv'
use_uv = importlib.util.find_spec('ensurepip') is None and shutil.which('uv') is not None
if use_uv:
    subprocess.run(['uv', 'venv', '--allow-existing', str(venv_dir)], check=True)
else:
    venv.EnvBuilder(with_pip=True).create(venv_dir)
python = venv_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
installer = ['uv', 'pip', 'install', '--python', str(python)] if use_uv else [str(python), '-m', 'pip', 'install']
subprocess.run(installer + ['-r', str(root / 'requirements.lock')], check=True)
subprocess.run(installer + ['--no-build-isolation', '--no-deps', str(root)], check=True)
print(f'Ready: {python} -m nara_data_mcp --help')
