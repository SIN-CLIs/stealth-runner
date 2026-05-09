#!/usr/bin/env python3
"""
Chrome Cookie Decryptor for macOS Keychain.

Extracts decrypted cookies from Chrome's SQLite database using
the macOS Keychain Safe Storage key.

LIMITATION: Chrome 147+ uses AES-GCM (v11) encryption.
This script only supports AES-CBC (v10). v11 cookies FAIL to decrypt.
WORKAROUND: Use ~/.stealth/heypiggy-backup/heypiggy-cookies.json instead
(it has the correct working cookies from previous successful extraction).

Usage:
    python3 decrypt_cookies.py --profile "Profile 901 (Jeremy)"
    # Output: ~/Library/Application Support/Google/Chrome/Profile 901 (Jeremy)/decrypted_cookies.json
    # ⚠️ WARNING: v11 encrypted cookies will be SKIPPED (decryption fails silently)
"""
import sqlite3
import os
import json
import argparse
import subprocess
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

def get_key():
    """Get Chrome Safe Storage key from macOS Keychain."""
    cmd = [
        'security', 'find-generic-password', '-w',
        '-s', 'Chrome Safe Storage',
        '-a', 'Chrome'
    ]
    output = subprocess.check_output(cmd).strip()
    return output

def decrypt_value(encrypted_value, key):
    """Decrypt a single Chrome cookie value."""
    # Chrome macOS encryption: AES-CBC with PBKDF2
    salt = b'saltysalt'
    iv = b' ' * 16
    length = 16
    
    # Derive key from password
    derived_key = PBKDF2(key, salt, dkLen=length, count=1003)
    cipher = AES.new(derived_key, AES.MODE_CBC, IV=iv)
    
    # Strip 'v10' or 'v11' prefix (3 bytes)
    decrypted = cipher.decrypt(encrypted_value[3:])
    
    # Remove PKCS7 padding
    last_byte = decrypted[-1]
    if last_byte <= 16:
        decrypted = decrypted[:-last_byte]
    return decrypted.decode('utf-8', errors='replace')

def extract_cookies(profile_name="Default", user="jeremy", domain_filter=None):
    """Extract all cookies from Chrome profile."""
    chrome_path = os.path.expanduser(
        f'~/Library/Application Support/Google Chrome/{profile_name}/Cookies'
    )
    
    # Fallback: try other user directories
    if not os.path.exists(chrome_path) and user != os.path.basename(os.path.expanduser('~')):
        chrome_path = f'/Users/{user}/Library/Application Support/Google Chrome/{profile_name}/Cookies'
    
    if not os.path.exists(chrome_path):
        raise FileNotFoundError(f"Cookie DB not found: {chrome_path}")
    
    key = get_key()
    conn = sqlite3.connect(chrome_path)
    cursor = conn.cursor()
    
    # Get all cookies
    cursor.execute(
        'SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly '
        'FROM cookies'
    )
    
    cookies = []
    for row in cursor.fetchall():
        host, name, value, enc_value, path, expires, secure, httponly = row
        
        # Decrypt if needed
        if not value and enc_value:
            try:
                value = decrypt_value(enc_value, key)
            except Exception as e:
                # Some cookies may use newer encryption (v11+)
                # Skip ones we can't decrypt
                continue
        
        # Convert Chrome time to Unix timestamp
        # Chrome time is microseconds since 1601-01-01
        # Unix time is seconds since 1970-01-01
        # Difference: 11644473600 seconds
        if expires and expires > 0:
            expires_unix = (expires / 1000000) - 11644473600
        else:
            expires_unix = -1
        
        cookie = {
            'domain': host,
            'name': name,
            'value': value,
            'path': path,
            'expires': expires_unix if expires_unix > 0 else -1,
            'secure': bool(secure),
            'httpOnly': bool(httponly),
            'sameSite': 'None',  # Not stored in older Chrome versions
        }
        
        if domain_filter is None or domain_filter.lower() in host.lower():
            cookies.append(cookie)
    
    conn.close()
    return cookies

def main():
    parser = argparse.ArgumentParser(description='Decrypt Chrome cookies from macOS')
    parser.add_argument('--profile', default='Profile 901 (Jeremy)', help='Chrome profile name')
    parser.add_argument('--user', default='jeremy', help='macOS username')
    parser.add_argument('--domain', default=None, help='Filter by domain substring')
    parser.add_argument('--output', default=None, help='Output JSON file')
    args = parser.parse_args()
    
    # Default output: Chrome profile directory
    if args.output is None:
        profile_dir = os.path.expanduser(f'~/Library/Application Support/Google/Chrome/{args.profile}')
        args.output = os.path.join(profile_dir, 'decrypted_cookies.json')
    
    cookies = extract_cookies(args.profile, args.user, args.domain)
    
    data = {
        'metadata': {
            'profile': args.profile,
            'user': args.user,
            'count': len(cookies),
            'source': 'chrome_keychain_decrypt',
        },
        'cookies': cookies,
    }
    
    with open(args.output, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Extracted {len(cookies)} cookies → {args.output}")

if __name__ == '__main__':
    main()
