"""Metadata-only broker with Windows current-user DPAPI; never a model tool."""
import ctypes
from ctypes import wintypes
import re
import sys
import threading
from pathlib import Path
from .files import atomic_bytes

RESERVED={'CON','PRN','AUX','NUL'} | {f'{prefix}{number}' for prefix in ('COM','LPT') for number in range(1,10)}

NAME=re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')

def protect_bytes(data):
    if sys.platform!='win32':raise RuntimeError('Encrypted secret storage requires Windows DPAPI; no plaintext fallback.')
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
    source=ctypes.create_string_buffer(data)
    incoming=Blob(len(data),ctypes.cast(source,ctypes.POINTER(ctypes.c_byte)));outgoing=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype=wintypes.BOOL
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not crypt.CryptProtectData(ctypes.byref(incoming),'Purple Dragon AI Agent',None,None,None,1,ctypes.byref(outgoing)):
        raise RuntimeError('Windows could not encrypt the secret.')
    try:return ctypes.string_at(outgoing.data,outgoing.size)
    finally:kernel.LocalFree(outgoing.data)

class SecretsBroker:
    def __init__(self,folder):
        self.folder=Path(folder);self.lock=threading.RLock()
    def _name(self,name):
        if not isinstance(name,str) or not NAME.fullmatch(name):raise ValueError('Use a name of 1–64 letters, digits, dots, underscores or hyphens, starting with a letter.')
        if name.split('.')[0].upper() in RESERVED:
            raise ValueError('Reserved Windows device names cannot identify credentials.')
        return name
    def _check_folder(self):
        if self.folder.is_symlink() or getattr(self.folder, 'is_junction', lambda: False)():
            raise PermissionError('Linked credential folders are unavailable.')

    def list(self):
        with self.lock:
            if self.folder.is_symlink() or getattr(self.folder,'is_junction',lambda:False)():return []
            return [{'name':f.stem,'storage':'Windows current-user DPAPI','value':'never returned'} for f in sorted(self.folder.glob('*.secret')) if NAME.fullmatch(f.stem)]
    def save(self,name,value):
        name=self._name(name)
        if not isinstance(value,str) or not value or len(value)>8192:raise ValueError('Secret must contain 1–8,192 characters.')
        with self.lock:
            self._check_folder()
            ciphertext=protect_bytes(value.encode('utf-8'))
            self.folder.mkdir(parents=True,exist_ok=True)
            atomic_bytes(self.folder/(name+'.secret'),ciphertext)
        return {'name':name,'storage':'Windows current-user DPAPI'}
    def delete(self,name):
        name=self._name(name)
        with self.lock:
            self._check_folder()
            (self.folder/(name+'.secret')).unlink()
        return {'name':name}
