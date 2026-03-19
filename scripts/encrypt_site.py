"""Encrypt HTML pages with AES-256 for password-protected sharing.

Produces self-contained HTML files that prompt for a password and decrypt
in-browser using the Web Crypto API. Same approach as StatiCrypt but
implemented in Python to avoid Node.js dependency issues.
"""

import os
import sys
import json
import base64
import hashlib
import shutil
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "site-encrypted"

PASSWORD_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HKS Focus Group Analysis</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,-apple-system,sans-serif;background:#fff;color:#111;display:flex;align-items:center;justify-content:center;min-height:100vh}
.login{max-width:380px;width:100%;padding:40px}
h1{font-size:1.25rem;font-weight:600;letter-spacing:-0.02em;margin-bottom:8px}
p{font-size:0.875rem;color:#555;margin-bottom:24px;line-height:1.5}
label{display:block;font-size:0.75rem;font-family:monospace;color:#888;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px}
input{width:100%;padding:10px 12px;border:1px solid #e5e5e5;font-size:0.875rem;font-family:Inter,sans-serif;outline:none;transition:border-color 0.2s}
input:focus{border-color:#111}
button{width:100%;padding:10px;background:#111;color:#fff;border:none;font-size:0.875rem;font-family:Inter,sans-serif;cursor:pointer;margin-top:12px;font-weight:500;transition:background 0.2s}
button:hover{background:#333}
.error{color:#dc2626;font-size:0.8125rem;margin-top:8px;display:none}
.remember{display:flex;align-items:center;gap:6px;margin-top:12px;font-size:0.8125rem;color:#555}
.remember input{width:auto}
</style>
</head>
<body>
<div class="login">
<h1>HKS Focus Group Analysis</h1>
<p>This report is password-protected. Enter the shared password to continue.</p>
<form id="f">
<label>Password</label>
<input type="password" id="pw" autofocus>
<div class="remember"><input type="checkbox" id="rem" checked><label for="rem" style="margin:0;text-transform:none;font-family:Inter,sans-serif;color:#555">Remember for 30 days</label></div>
<button type="submit">Unlock</button>
<div class="error" id="err">Incorrect password. Please try again.</div>
</form>
</div>
<script>
const ENCRYPTED = "__ENCRYPTED_DATA__";
const SALT = "__SALT__";
const IV = "__IV__";

async function deriveKey(password, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits", "deriveKey"]);
  return crypto.subtle.deriveKey({name: "PBKDF2", salt: Uint8Array.from(atob(salt), c => c.charCodeAt(0)), iterations: 100000, hash: "SHA-256"}, keyMaterial, {name: "AES-GCM", length: 256}, true, ["decrypt"]);
}

async function decrypt(password) {
  try {
    const key = await deriveKey(password, SALT);
    const ciphertext = Uint8Array.from(atob(ENCRYPTED), c => c.charCodeAt(0));
    const iv = Uint8Array.from(atob(IV), c => c.charCodeAt(0));
    const decrypted = await crypto.subtle.decrypt({name: "AES-GCM", iv: iv}, key, ciphertext);
    return new TextDecoder().decode(decrypted);
  } catch (e) {
    return null;
  }
}

const STORAGE_KEY = "hks_focus_group_pw";

async function tryUnlock(pw) {
  const html = await decrypt(pw);
  if (html) {
    if (document.getElementById("rem").checked) {
      const expires = Date.now() + 30 * 24 * 60 * 60 * 1000;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({pw: pw, expires: expires}));
    }
    document.open();
    document.write(html);
    document.close();
    return true;
  }
  return false;
}

// Check stored password
(async () => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      const {pw, expires} = JSON.parse(stored);
      if (Date.now() < expires && await tryUnlock(pw)) return;
    } catch(e) {}
    localStorage.removeItem(STORAGE_KEY);
  }
})();

document.getElementById("f").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pw = document.getElementById("pw").value;
  if (!await tryUnlock(pw)) {
    document.getElementById("err").style.display = "block";
    document.getElementById("pw").select();
  }
});
</script>
</body>
</html>"""


def encrypt_html(html_content, password):
    """Encrypt HTML content with AES-256-GCM using PBKDF2 key derivation."""
    salt = get_random_bytes(16)
    iv = get_random_bytes(12)

    # Derive key using PBKDF2 (matching the JS implementation)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(html_content.encode('utf-8'))

    # Combine ciphertext + tag (GCM tag is appended for Web Crypto API compatibility)
    encrypted = ciphertext + tag

    return (
        base64.b64encode(encrypted).decode(),
        base64.b64encode(salt).decode(),
        base64.b64encode(iv).decode(),
    )


def encrypt_file(input_path, output_path, password):
    """Encrypt a single HTML file."""
    html = input_path.read_text(encoding='utf-8')
    encrypted_data, salt, iv = encrypt_html(html, password)

    page = PASSWORD_PAGE_TEMPLATE
    page = page.replace('__ENCRYPTED_DATA__', encrypted_data)
    page = page.replace('__SALT__', salt)
    page = page.replace('__IV__', iv)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding='utf-8')


def main():
    password = sys.argv[1] if len(sys.argv) > 1 else "HKSfocusgroups2025"

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Copy static assets (CSS, JS, images) unencrypted
    static_src = SITE_DIR / "static"
    static_dest = OUTPUT_DIR / "static"
    if static_src.exists():
        shutil.copytree(str(static_src), str(static_dest))

    # Encrypt all HTML files
    html_files = list(SITE_DIR.rglob("*.html"))
    print(f"Encrypting {len(html_files)} HTML files...")

    for html_file in html_files:
        rel = html_file.relative_to(SITE_DIR)
        output_file = OUTPUT_DIR / rel
        encrypt_file(html_file, output_file, password)
        print(f"  Encrypted {rel}")

    print(f"\nEncrypted site at {OUTPUT_DIR}")
    print(f"Password: {password}")


if __name__ == "__main__":
    main()
