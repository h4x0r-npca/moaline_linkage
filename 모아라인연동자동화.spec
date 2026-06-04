# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('로고.webp', '.'), ('로고한글.webp', '.'), ('로고.svg', '.'), ('moaline.ico', '.')]
datas += collect_data_files('customtkinter')


block_cipher = None


a = Analysis(['main.py'],
             pathex=['C:\\Users\\inbiz_ks\\OneDrive - 바로고\\Program\\moa-linkage'],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='모아라인연동자동화',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , version='version_info.txt', uac_admin=True, icon='moaline.ico')
