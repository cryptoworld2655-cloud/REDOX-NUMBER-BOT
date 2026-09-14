#!/usr/bin/env python3
"""
🤖 StexSMS Bot Unified Runner
----------------------------------
A highly robust Python combination of the panel monitoring/forwarding system
and the interactive Telegram Bot Controller.

This single file handles:
1. Multi-threaded background panel monitoring (CDRs & Active GetNum/Info numbers) for StexSMS.
2. Dynamic solving of mathematical captchas for logins.
3. Fully functional interactive Telegram Bot matching server.ts exactly.
4. Professional copy and exploration commands: /start, /getnum, /search, and /traffic.
5. Absolute error safety by sanitizing Telegram button schemas to prevent Status 400 errors.

Usage:
    python bot.py
"""

import os
import re
import sys
import time
import json
import random
import logging
import threading
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load env variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("REDOX_Bot")

# Config Files
PANELS_FILE = "panels.json"
SERVICES_FILE = "services.json"
ADMIN_DB_FILE = "admin_db.json"
OWNER_ID = "6423903661" # Change this ID to your main Admin ID
TELEGRAM_TOKEN = "8987687367:AAFxTX9URvsKOC9PI3GuFtIHBg4Yr6vttsQ"  # আপনার টেলিগ্রাম বট টোকেনটি এখানে দিন

# Admin DB Logic (Tracks Users and Today's Numbers)
def load_admin_db():
    default_db = {"users": [], "today_date": datetime.now().strftime("%Y-%m-%d"), "today_numbers_count": 0, "today_otp_success": 0, "last_stats_post_ts": 0, "admins": [OWNER_ID], "force_join_status": False, "force_join_channels": [], "otp_group_link": "", "forward_groups": [], "redox_config": {"withdraw_group": "", "otp_reward": 0.0, "min_withdraw": 20.0, "methods": [], "max_concurrent": 3, "cooldown": 0, "refer_bonus": 0.0, "stats_auto_post": False, "stats_interval_min": 60}, "user_stats": {}, "active_numbers": {}, "num_panel_map": {}, "panel_stats": {}, "refer_stats": {}, "task": {"price": 0.0, "required_otp": 0, "duration_hours": 0, "active": False, "start_ts": 0, "end_ts": 0, "task_id": 0}}
    if os.path.exists(ADMIN_DB_FILE):
        try:
            with open(ADMIN_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "admins" not in data: data["admins"] = [OWNER_ID]
                if "force_join_status" not in data: data["force_join_status"] = False
                if "force_join_channels" not in data: data["force_join_channels"] = []
                if "otp_group_link" not in data: data["otp_group_link"] = ""
                if "forward_groups" not in data: data["forward_groups"] = []
                if "redox_config" not in data: data["redox_config"] = {"withdraw_group": "", "otp_reward": 0.0, "min_withdraw": 20.0, "methods": [], "max_concurrent": 3, "cooldown": 0}
                else:
                    data["redox_config"].setdefault("max_concurrent", 3)
                    data["redox_config"].setdefault("cooldown", 0)
                    data["redox_config"].setdefault("stats_auto_post", False)
                    data["redox_config"].setdefault("stats_interval_min", 60)
                if "user_stats" not in data: data["user_stats"] = {}
                if "active_numbers" not in data: data["active_numbers"] = {}
                if "num_panel_map" not in data: data["num_panel_map"] = {}
                if "panel_stats" not in data: data["panel_stats"] = {}
                if "today_otp_success" not in data: data["today_otp_success"] = 0
                if "last_stats_post_ts" not in data: data["last_stats_post_ts"] = 0
                return data
        except: pass
    return default_db

def check_user_limits(chat_id, update_cooldown=True):
    cfg = admin_db.get("redox_config", {})
    max_c = int(cfg.get("max_concurrent", 1))
    if max_c < 1: max_c = 1
    
    if str(chat_id) in admin_db.get("admins", [OWNER_ID]):
        return True, "", max_c
        
    cd = int(cfg.get("cooldown", 0))

    stats = admin_db.setdefault("user_stats", {}).setdefault(str(chat_id), {})
    stats.setdefault("otp_count", 0)
    stats.setdefault("balance", 0.0)
    stats.setdefault("last_req", 0)

    now = int(time.time())
    last_req = stats.get("last_req", 0)
    
    if cd > 0 and (now - last_req) < cd:
        rem = cd - (now - last_req)
        return False, f"⏳ Cooldown Active!\nPlease wait {rem} seconds before getting another number.", max_c

    if update_cooldown:
        stats["last_req"] = now
        save_admin_db()
        
    return True, "", max_c

def save_admin_db():
    try:
        with admin_db_lock:
            with open(ADMIN_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(admin_db, f, indent=2)
    except: pass

admin_db = load_admin_db()

# ----------------------------------------------------
# Firebase Cloud Firestore Setup (Hardcoded)
# ----------------------------------------------------
firebase_cred_dict = {
  "type": "service_account",
  "project_id": "redox-sms-panel",
  "private_key_id": "3aed767606ff2fab88a8550ab502f3849d8e1a40",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCvBXsDD8pKbWT+\nsKKi7gUEcQDGy6cBCfxYEVpouq2ZkLduNP7UytB4fEhRuIK8cIr0yLksRirxHyvC\nCqhbK8SBb/dLIMcVV4q7Zeihd5Wd0jp1HwhMWOezv65iyCHQ+d3kMeWNseQ3d9Kc\nCybsl8OWsNvY4OHzIq1UyajHH9ioPwtFQ877nj0iNvxsRoBFF2MqXDNf28TPC2lQ\nS8bb1PRPmtdPGA/Pge3kB5OJxtLKEQ7gyeQ+hqsO/YaTnt/qWnliFOd9CkkFn1cM\nZOVRwfpLFbZZ4FuaVHmHTfVpl0FabjcjI0RizFCo2699V7A9HPXug3PzpMwZcz7w\nZiCcbQMDAgMBAAECggEABl86tUfT45XMAYHIygnEYP8EOjib4evNJh+rnPh+7YJZ\nS0fepzyjDl/n+iGvkNDAHl1YcIY1dgXef/gHXRpg0x2ScUfGN76yLFRvfcFuzwoi\nWrVAhhcOiHrIDIygvoz6SR6P7vK1DlfscQXu6tozor7ZojG9yC5RBS86V9WO+8EQ\nXM3lQNhFPfu90UsCaGAKtz1FsFfFglgCMz7EzNs3jiTa1zcHP/AkEvIIiHi2TjkT\ncDic+DqElACYAFgMKIelTFzSdN5ZtLWzI6/w/+UuzM1HNwqtYYWxLh7hQf8AAG6r\ny5DYSr2CGlEcZkXPEbQ5uL81J+nyCrx4Docwswp78QKBgQDnQhIefN9l8f/Dm/+F\n1Q4rK9wsa/AhzXFxtqUr4/WRPMpPQj4vTnU+AhXIjZm04JYvBCBhCE/5MQaNRczg\nYiYap2yPD0lTP+3OTmZFXmrN7Oq7R/RfObxaz0oVK0cnr8CCOWrKNa5bwS30jt3L\nWMNJZTI2G9HmKi7KIKzzZPzflQKBgQDBvySX8/XD2TQGRmzHANUsDfOWxCA52OHL\necnK3GdjySr7D3CuMAB0U3LQgpZlDc+sAf6TNyCBh5Nn7eVBxuJqvrjH1OHxy8QB\nMK6CyNVGVZN7W4k7OrZNFtr09tQSAKeshMwFDqrZPga0xlON0p2LYs6R1w/YV7cs\nmpZIOr6SNwKBgDHL6FroSLKLCaf1T3BiEEr7hs2J8ItW0bbKvYZV7+r2TBoFCZ7m\nJhjUGhy1YQOx2KUHHnHGeHIQPHjvLs6iU9IpexbTE9b5TRu/hgYp7pWpDmKFe/mF\nVSm4uRsV1pyVG77u3i/snz7iuiKPIPNIicSkJcvA8dG+A5VCs/s1I76BAoGATnK+\ntmgpkutXjVLmqI1Fw1jC0MEI62NNyb2+X01u75B8vrs5vM3i4TcIvjSiALje5Z7J\nHYKsvsXOgb5pnYCSHPasiv0/n1AKRREZGAuJj7kGxmQB5OGY/w3KCnYG2GM7gTck\nBMgzlVLwFDJZkos9DzsquRKDb+3UVVMiloxyrXECgYEA0pOcYGbipwrlkZosEcVA\nBNnyZIGLWcEeHqaH3b5ULIwesuLdwZEDC0ssgJn1yzl3VLzLcfCwzjKnoz81nbrL\netheEDckY3j5a1HyJ4XjaZW5zSDlPIY1ZD4Uy/qPPn2fKBv0FbkAsJQQAt431ahY\n71wYy2FpVaPJGoh3bQ9YM50=\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@redox-sms-panel.iam.gserviceaccount.com",
  "client_id": "105389159391896027097",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40redox-sms-panel.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
db_firestore = None

def initialize_firebase():
    global db_firestore
    try:
        cred = credentials.Certificate(firebase_cred_dict)
        if firebase_admin._apps:
            firebase_admin.delete_app(firebase_admin.get_app())
        firebase_admin.initialize_app(cred)
        db_firestore = firestore.client()
        logger.info("Firebase Firestore initialized successfully using hardcoded dict!")
        return True, "Firebase connected successfully!"
    except Exception as e:
        db_firestore = None
        logger.error(f"Firebase initialization failed: {e}")
        return False, str(e)

initialize_firebase()

def restore_from_firestore():
    global admin_db
    if not db_firestore: return
    try:
        # ১. অ্যাডমিন কনফিগ রি-স্টোর
        cfg_doc = db_firestore.collection("REDOX_System").document("Bot_Config").get()
        if cfg_doc.exists:
            data = cfg_doc.to_dict()
            if "redox_config" in data: admin_db["redox_config"] = data["redox_config"]
            if "search_cfg" in data: admin_db["search_cfg"] = data["search_cfg"]
            if "admins" in data: admin_db["admins"] = data["admins"]
            if "otp_group_link" in data: admin_db["otp_group_link"] = data["otp_group_link"]
            if "forward_groups" in data: admin_db["forward_groups"] = data["forward_groups"]
            if "force_join_status" in data: admin_db["force_join_status"] = data["force_join_status"]
            if "force_join_channels" in data: admin_db["force_join_channels"] = data["force_join_channels"]
            if "banned_users" in data: admin_db["banned_users"] = data["banned_users"]
            if "refer_stats" in data: admin_db["refer_stats"] = data["refer_stats"]
            if "task" in data: admin_db["task"] = data["task"]
        
        # ২. ইউজার ব্যালেন্স ও OTP 리-স্টোর
        users_doc = db_firestore.collection("REDOX_System").document("Users_Data").get()
        if users_doc.exists:
            data = users_doc.to_dict()
            if "active_users" in data:
                for uid, udata in data["active_users"].items():
                    stats = admin_db.setdefault("user_stats", {}).setdefault(uid, {})
                    stats["balance"] = udata.get("balance", 0.0)
                    stats["otp_count"] = udata.get("otp_count", 0)
                    if uid not in admin_db.setdefault("users", []): admin_db["users"].append(uid)
        save_admin_db()
        
        # ৩. সার্ভিস (Service Management) রি-স্টোর
        services_doc = db_firestore.collection("REDOX_System").document("Services_Data").get()
        if services_doc.exists:
            srv_data = services_doc.to_dict()
            if "services" in srv_data:
                with open(SERVICES_FILE, "w", encoding="utf-8") as f:
                    json.dump(srv_data["services"], f, indent=2, ensure_ascii=False)
                    
        # ৪. প্যানেল (Panel Management) রি-স্টোর
        panels_doc = db_firestore.collection("REDOX_System").document("Panels_Data").get()
        if panels_doc.exists:
            pnl_data = panels_doc.to_dict()
            if "panels" in pnl_data:
                with open(PANELS_FILE, "w", encoding="utf-8") as f:
                    json.dump(pnl_data["panels"], f, indent=2, ensure_ascii=False)
                    
        logger.info("Successfully restored essential data from Firestore on boot!")
    except Exception as e:
        logger.error(f"Failed to restore from Firestore: {e}")

# বট স্টার্ট হলেই ডেটা রিস্টোর হবে
restore_from_firestore()

def sync_essential_data_to_firestore():
    """Syncs only essential data: User Balances, Panels, Services, and Config to Firestore"""
    if not db_firestore: 
        return False, "Firebase is not initialized."
    try:
        # 1. User Balances & Stats
        stats = admin_db.get("user_stats", {})
        clean_stats = {}
        for uid, data in stats.items():
            if data.get("balance", 0.0) > 0 or data.get("otp_count", 0) > 0:
                clean_stats[uid] = {
                    "balance": data.get("balance", 0.0),
                    "otp_count": data.get("otp_count", 0)
                }
        
        db_firestore.collection("REDOX_System").document("Users_Data").set({
            "total_users": len(admin_db.get("users", [])),
            "active_users": clean_stats,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 2. Panels Config (Cleaned without junk session cookies)
        clean_panels = []
        for p in panels:
            clean_panels.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "status": p.get("status"),
                "url": p.get("url"),
                "getNumberUrl": p.get("getNumberUrl", ""),
                "getMessageUrl": p.get("getMessageUrl", "")
            })
            
        db_firestore.collection("REDOX_System").document("Panels_Data").set({
            "panels": clean_panels,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 3. Services & Countries
        services_dict = load_services()
        db_firestore.collection("REDOX_System").document("Services_Data").set({
            "services": services_dict,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 4. Admin Config
        db_firestore.collection("REDOX_System").document("Bot_Config").set({
            "redox_config": admin_db.get("redox_config", {}),
            "search_cfg": admin_db.get("search_cfg", {}),
            "admins": admin_db.get("admins", []),
            "otp_group_link": admin_db.get("otp_group_link", ""),
            "forward_groups": admin_db.get("forward_groups", []),
            "force_join_status": admin_db.get("force_join_status", False),
            "force_join_channels": admin_db.get("force_join_channels", []),
            "banned_users": admin_db.get("banned_users", []),
            "refer_stats": admin_db.get("refer_stats", {}),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return True, "Successfully synced Balances, Panels, Services & Config to Firestore!"
    except Exception as e:
        return False, f"Firestore Sync Error: {e}"

# Telegram Secrets moved to the top

# Global variables/caches
user_conversations = {}
pending_referrals = {}  # 🛡️ Force Join চালু থাকলে /start এর ref_ প্যারামিটার এখানে জমা রাখা হয়,
                        # যাতে join করার পরও (Check Again চাপার পর) রেফার বোনাস ঠিকমতো count হয়
user_prompts = {}
sessions = {}
panel_backoff_until = {}  # Dynamic rate limit tracking
panel_creation_temp = {}  # Temp storage for multi-step panel creation
admin_ctr_search_query = {}  # 🔍 Temp storage: chat_id -> current country-search text (for Add Country picker)
admin_db_lock = threading.Lock()  # Thread safety for shared admin_db writes
local_traffic_stats = {}  # 🚀 Fast Traffic Local Database
local_raw_logs_cache = {} # 🚀 Cumulative logs to prevent data loss

# Mapped country metadata
shortCountryCodes = {
    'CI': {'name': "Côte d'Ivoire (Ivory Coast)", 'flag': '🇨🇮'},
    'CM': {'name': 'Cameroon', 'flag': '🇨🇲'},
    'TG': {'name': 'Togo', 'flag': '🇹🇬'},
    'MG': {'name': 'Madagascar', 'flag': '🇲🇬'},
    'BJ': {'name': 'Benin', 'flag': '🇧🇯'},
    'GN': {'name': 'Guinea', 'flag': '🇬🇳'},
    'GA': {'name': 'Gabon', 'flag': '🇬🇦'},
    'CF': {'name': 'Central African Republic', 'flag': '🇨🇫'},
    'CG': {'name': 'Congo', 'flag': '🇨🇬'},
    'CD': {'name': 'DR Congo', 'flag': '🇨🇩'},
    'SN': {'name': 'Senegal', 'flag': '🇸🇳'},
    'ML': {'name': 'Mali', 'flag': '🇲🇱'},
    'TJ': {'name': 'Tajikistan', 'flag': '🇹🇯'},
    'BF': {'name': 'Burkina Faso', 'flag': '🇧🇫'},
    'NE': {'name': 'Niger', 'flag': '🇳🇪'},
    'TD': {'name': 'Chad', 'flag': '🇹🇩'},
}

prefixCountryMap = {
    '237': 'Cameroon 🇨🇲',
    '225': 'Ivory Coast 🇨🇮',
    '228': 'Togo 🇹🇬',
    '261': 'Madagascar 🇲🇬',
    '229': 'Benin 🇧🇯',
    '224': 'Guinea 🇬🇳',
    '241': 'Gabon 🇬🇦',
    '236': 'Central African Republic 🇨🇫',
    '242': 'Congo 🇨🇬',
    '243': 'DR Congo 🇨🇩',
    '221': 'Senegal 🇸🇳',
    '223': 'Mali 🇲🇱',
    '992': 'Tajikistan 🇹🇯',
    '7992': 'Tajikistan 🇹🇯',
    '226': 'Burkina Faso 🇧🇫',
    '227': 'Niger 🇳🇪',
    '235': 'Chad 🇹🇩',
}

# ----------------------------------------------------
# Utilities
# ----------------------------------------------------

# ----------------------------------------------------
# Premium Emoji Database
# ----------------------------------------------------
PREMIUM_EMOJIS = {
    "redox": "<tg-emoji emoji-id='5267456597436699660'>😈</tg-emoji>",
    "admin": "<tg-emoji emoji-id='5267294466716244344'>👨‍💼</tg-emoji>",
    "time": "<tg-emoji emoji-id='5336983442125001376'>🕓</tg-emoji>",
    "otp": "<tg-emoji emoji-id='5337255927735163754'>🔐</tg-emoji>",
    "fire": "<tg-emoji emoji-id='5337267511261960341'>🔥</tg-emoji>",
    "king": "<tg-emoji emoji-id='5353032893096567467'>👑</tg-emoji>",
    "dashboard": "<tg-emoji emoji-id='5352877703043258544'>📊</tg-emoji>",
    "user": "<tg-emoji emoji-id='5352861489541714456'>👤</tg-emoji>",
    "rocket": "<tg-emoji emoji-id='5352597830089347330'>🚀</tg-emoji>",
    "gem": "<tg-emoji emoji-id='5352838545826420397'>💎</tg-emoji>",
    "done": "<tg-emoji emoji-id='5352694861990501856'>✅</tg-emoji>",
    "error": "<tg-emoji emoji-id='5420130255174145507'>❌</tg-emoji>",
    "search": "<tg-emoji emoji-id='5463352748751753567'>🔍</tg-emoji>",
    "number": "<tg-emoji emoji-id='5352862640592949843'>🔢</tg-emoji>",
    "phone": "<tg-emoji emoji-id='5355208818017999139'>📱</tg-emoji>",
    "warn": "<tg-emoji emoji-id='5336944168944047463'>⚠️</tg-emoji>",
    "wait": "<tg-emoji emoji-id='5337172996211648018'>⏳</tg-emoji>",
    "note": "<tg-emoji emoji-id='5395444784611480792'>📝</tg-emoji>",
    "world": "<tg-emoji emoji-id='5336972142066047577'>🌐</tg-emoji>",
    "gear": "<tg-emoji emoji-id='5420155432272438703'>⚙️</tg-emoji>",
    "back": "<tg-emoji emoji-id='5267490665117275176'>⬅️</tg-emoji>",
    "link": "<tg-emoji emoji-id='6267115986541877538'>⛓</tg-emoji>",
    "refer": "<tg-emoji emoji-id='5420396762189831222'>🎁</tg-emoji>",
    "task": "<tg-emoji emoji-id='6217720070181752854'>🎯</tg-emoji>",
    "support": "<tg-emoji emoji-id='5201732344993576400'>🫂</tg-emoji>",
    "vip": "<tg-emoji emoji-id='5352552689983067014'>✨</tg-emoji>",
    "file": "<tg-emoji emoji-id='5352721946054268944'>📁</tg-emoji>",
    "bcast_end": "<tg-emoji emoji-id='6266764202950530136'>🔚</tg-emoji>",
    "rank1": "<tg-emoji emoji-id='6265004494719816749'>🥇</tg-emoji>",
}

RAW_APP_EMOJIS = {
    "facebook": "5334807341109908955", "whatsapp": "5334759662677957452",
    "telegram": "5337010556253543833", "imo": "5337155807752524558",
    "instagram": "5334868205091459431", "apple": "5334637951894722661",
    "google": "5335010201005231986", "microsoft": "5334880948259427772",
    "tiktok": "5339213256001102461", "amazon": "4995019580536524226",
    "twitter": "5215726959056662534", "snapchat": "5359441366554255082",
    "netflix": "6255738712664050133", "linkedin": "6224222994265279792",
    "discord": "5116246243646898866", "viber": "5463060437572528782",
    "wechat": "5782757599560602950", "line": "5399818044866327279",
    "paypal": "5776103539872896061", "uber": "5298715455316303708",
    "bkash": "5348469219761626211", "nagad": "5352985330628730418",
    "rocket": "5352597830089347330",
    "binance": "5348212415077064131", "bybit": "5348372939479751825",
    "gmail": "5348494358205207761", "messenger": "5348486915026884464",
    "chrome": "5346311574221000149", "chatgpt": "5296516998996445955",
    "github": "5417836094098007862", "canva": "5111661409008092227"
}

def get_pemoji(key, fallback=""):
    return PREMIUM_EMOJIS.get(key.lower(), fallback)

def load_premium_apps():
    if os.path.exists("premium_apps.json"):
        try:
            with open("premium_apps.json", "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

RAW_FLAG_EMOJIS = {
    "AD": {"phone_code": "376", "flag": "🇦🇩", "name": "Andorra", "id": "5911314702398396902"},
    "AE": {"phone_code": "971", "flag": "🇦🇪", "name": "United Arab Emirates", "id": "5913726554168365343"},
    "AF": {"phone_code": "93", "flag": "🇦🇫", "name": "Afghanistan", "id": "5913492040364068694"},
    "AG": {"phone_code": "1", "flag": "🇦🇬", "name": "Antigua and Barbuda", "id": "5913389025573475085"},
    "AL": {"phone_code": "355", "flag": "🇦🇱", "name": "Albania", "id": "5911357458797826163"},
    "AM": {"phone_code": "374", "flag": "🇦🇲", "name": "Armenia", "id": "5913272455866093666"},
    "AO": {"phone_code": "244", "flag": "🇦🇴", "name": "Angola", "id": "5913753316109586411"},
    "AR": {"phone_code": "54", "flag": "🇦🇷", "name": "Argentina", "id": "5913573356979884082"},
    "AT": {"phone_code": "43", "flag": "🇦🇹", "name": "Austria", "id": "5911338831524664592"},
    "AU": {"phone_code": "61", "flag": "🇦🇺", "name": "Australia", "id": "5913632326880858455"},
    "AZ": {"phone_code": "994", "flag": "🇦🇿", "name": "Azerbaijan", "id": "5911197578640233518"},
    "BA": {"phone_code": "387", "flag": "🇧🇦", "name": "Bosnia and Herzegovina", "id": "5913700002680541032"},
    "BB": {"phone_code": "1", "flag": "🇧🇧", "name": "Barbados", "id": "5911016996740272263"},
    "BD": {"phone_code": "880", "flag": "🇧🇩", "name": "Bangladesh", "id": "5911365056594973179"},
    "BE": {"phone_code": "32", "flag": "🇧🇪", "name": "Belgium", "id": "5913529642802745141"},
    "BF": {"phone_code": "226", "flag": "🇧🇫", "name": "Burkina Faso", "id": "5913407764515786948"},
    "BG": {"phone_code": "359", "flag": "🇧🇬", "name": "Bulgaria", "id": "5911263776971168517"},
    "BH": {"phone_code": "973", "flag": "🇧🇭", "name": "Bahrain", "id": "5913581663446634403"},
    "BI": {"phone_code": "257", "flag": "🇧🇮", "name": "Burundi", "id": "5913766441529642752"},
    "BJ": {"phone_code": "229", "flag": "🇧🇯", "name": "Benin", "id": "5913735869952430547"},
    "BM": {"phone_code": "1", "flag": "🇧🇲", "name": "Bermuda", "id": "5913680005312811090"},
    "BN": {"phone_code": "673", "flag": "🇧🇳", "name": "Brunei Darussalam", "id": "5911336409163109113"},
    "BO": {"phone_code": "591", "flag": "🇧🇴", "name": "Bolivia, Plurinational State of", "id": "5913638795101606133"},
    "BR": {"phone_code": "55", "flag": "🇧🇷", "name": "Brazil", "id": "5911148568768418614"},
    "BS": {"phone_code": "1", "flag": "🇧🇸", "name": "Bahamas", "id": "5911451643135660214"},
    "BT": {"phone_code": "975", "flag": "🇧🇹", "name": "Bhutan", "id": "5913236734623093021"},
    "BW": {"phone_code": "267", "flag": "🇧🇼", "name": "Botswana", "id": "5911513782722499475"},
    "BY": {"phone_code": "375", "flag": "🇧🇾", "name": "Belarus", "id": "5911011185649521599"},
    "BZ": {"phone_code": "501", "flag": "🇧🇿", "name": "Belize", "id": "5913355005137522807"},
    "CA": {"phone_code": "1", "flag": "🇨🇦", "name": "Canada", "id": "5913623736946265914"},
    "CD": {"phone_code": "243", "flag": "🇨🇩", "name": "Congo, The Democratic Republic of the", "id": "5913770362834783827"},
    "CF": {"phone_code": "236", "flag": "🇨🇫", "name": "Central African Republic", "id": "5913443245240619222"},
    "CG": {"phone_code": "242", "flag": "🇨🇬", "name": "Congo", "id": "5911338788574990168"},
    "CH": {"phone_code": "41", "flag": "🇨🇭", "name": "Switzerland", "id": "5913271227505448072"},
    "CI": {"phone_code": "225", "flag": "🇨🇮", "name": "Côte d'Ivoire (Ivory Coast)", "id": "5222233374948602940"},
    "CL": {"phone_code": "56", "flag": "🇨🇱", "name": "Chile", "id": "5911470957603592832"},
    "CM": {"phone_code": "237", "flag": "🇨🇲", "name": "Cameroon", "id": "5911172109484167745"},
    "CN": {"phone_code": "86", "flag": "🇨🇳", "name": "China", "id": "5913779335021466780"},
    "CO": {"phone_code": "57", "flag": "🇨🇴", "name": "Colombia", "id": "5913773060074246009"},
    "CR": {"phone_code": "506", "flag": "🇨🇷", "name": "Costa Rica", "id": "5911261745451635030"},
    "CV": {"phone_code": "238", "flag": "🇨🇻", "name": "Cabo Verde", "id": "5913571501554012193"},
    "CY": {"phone_code": "357", "flag": "🇨🇾", "name": "Cyprus", "id": "5911023550860366409"},
    "CZ": {"phone_code": "420", "flag": "🇨🇿", "name": "Czechia", "id": "5911198691036764307"},
    "DE": {"phone_code": "49", "flag": "🇩🇪", "name": "Germany", "id": "5911096835887337583"},
    "DJ": {"phone_code": "253", "flag": "🇩🇯", "name": "Djibouti", "id": "5911407709915190157"},
    "DK": {"phone_code": "45", "flag": "🇩🇰", "name": "Denmark", "id": "5911206009661034712"},
    "DM": {"phone_code": "1", "flag": "🇩🇲", "name": "Dominica", "id": "5911377121158107430"},
    "DO": {"phone_code": "1", "flag": "🇩🇴", "name": "Dominican Republic", "id": "5911152099231536123"},
    "DZ": {"phone_code": "213", "flag": "🇩🇿", "name": "Algeria", "id": "5913782968563800236"},
    "EC": {"phone_code": "593", "flag": "🇪🇨", "name": "Ecuador", "id": "5911273865849347408"},
    "EE": {"phone_code": "372", "flag": "🇪🇪", "name": "Estonia", "id": "5910986042910969906"},
    "EG": {"phone_code": "20", "flag": "🇪🇬", "name": "Egypt", "id": "5913694831539916769"},
    "ES": {"phone_code": "34", "flag": "🇪🇸", "name": "Spain", "id": "5911193287967904547"},
    "ET": {"phone_code": "251", "flag": "🇪🇹", "name": "Ethiopia", "id": "5911078333168227043"},
    "FI": {"phone_code": "358", "flag": "🇫🇮", "name": "Finland", "id": "5911041344909873378"},
    "FJ": {"phone_code": "679", "flag": "🇫🇯", "name": "Fiji", "id": "5911393832875856716"},
    "FM": {"phone_code": "691", "flag": "🇫🇲", "name": "Micronesia, Federated States of", "id": "5911271104185373336"},
    "FR": {"phone_code": "33", "flag": "🇫🇷", "name": "France", "id": "5913605586414473124"},
    "GA": {"phone_code": "241", "flag": "🇬🇦", "name": "Gabon", "id": "5911037896051137264"},
    "GB": {"phone_code": "44", "flag": "🇬🇧", "name": "United Kingdom", "id": "5913443365499703513"},
    "GD": {"phone_code": "1", "flag": "🇬🇩", "name": "Grenada", "id": "5913228063084121946"},
    "GE": {"phone_code": "995", "flag": "🇬🇪", "name": "Georgia", "id": "5913434771270144023"},
    "GH": {"phone_code": "233", "flag": "🇬🇭", "name": "Ghana", "id": "5913391155877252952"},
    "GM": {"phone_code": "220", "flag": "🇬🇲", "name": "Gambia", "id": "5913657267755945883"},
    "GN": {"phone_code": "224", "flag": "🇬🇳", "name": "Guinea", "id": "5913471858312744319"},
    "GQ": {"phone_code": "240", "flag": "🇬🇶", "name": "Equatorial Guinea", "id": "5911306279967529251"},
    "GR": {"phone_code": "30", "flag": "🇬🇷", "name": "Greece", "id": "5911210399117611448"},
    "GT": {"phone_code": "502", "flag": "🇬🇹", "name": "Guatemala", "id": "5913324858762072330"},
    "GW": {"phone_code": "245", "flag": "🇬🇼", "name": "Guinea-Bissau", "id": "5911398694778836149"},
    "GY": {"phone_code": "592", "flag": "🇬🇾", "name": "Guyana", "id": "5913579412883771480"},
    "HN": {"phone_code": "504", "flag": "🇭🇳", "name": "Honduras", "id": "5913585086535569727"},
    "HR": {"phone_code": "385", "flag": "🇭🇷", "name": "Croatia", "id": "5913692684056269311"},
    "HT": {"phone_code": "509", "flag": "🇭🇹", "name": "Haiti", "id": "5913459789454643194"},
    "HU": {"phone_code": "36", "flag": "🇭🇺", "name": "Hungary", "id": "5913767635530551104"},
    "ID": {"phone_code": "62", "flag": "🇮🇩", "name": "Indonesia", "id": "5913479361620611038"},
    "IE": {"phone_code": "353", "flag": "🇮🇪", "name": "Ireland", "id": "5913440715504881532"},
    "IL": {"phone_code": "972", "flag": "🇮🇱", "name": "Israel", "id": "5911471936856134692"},
    "IN": {"phone_code": "91", "flag": "🇮🇳", "name": "India", "id": "5913754823643107921"},
    "IQ": {"phone_code": "964", "flag": "🇮🇶", "name": "Iraq", "id": "5911382442622587735"},
    "IR": {"phone_code": "98", "flag": "🇮🇷", "name": "Iran, Islamic Republic of", "id": "5920160977818489355"},
    "IS": {"phone_code": "354", "flag": "🇮🇸", "name": "Iceland", "id": "5911047899029967246"},
    "IT": {"phone_code": "39", "flag": "🇮🇹", "name": "Italy", "id": "5913688444923547525"},
    "JM": {"phone_code": "1", "flag": "🇯🇲", "name": "Jamaica", "id": "5913232280742006526"},
    "JO": {"phone_code": "962", "flag": "🇯🇴", "name": "Jordan", "id": "5913234136167878475"},
    "JP": {"phone_code": "81", "flag": "🇯🇵", "name": "Japan", "id": "5913293711659241040"},
    "KE": {"phone_code": "254", "flag": "🇰🇪", "name": "Kenya", "id": "5911154710571651231"},
    "KG": {"phone_code": "996", "flag": "🇰🇬", "name": "Kyrgyzstan", "id": "5911202161370337549"},
    "KH": {"phone_code": "855", "flag": "🇰🇭", "name": "Cambodia", "id": "5913699998385573485"},
    "KI": {"phone_code": "686", "flag": "🇰🇮", "name": "Kiribati", "id": "5911294443037660118"},
    "KM": {"phone_code": "269", "flag": "🇰🇲", "name": "Comoros", "id": "5911338582416560604"},
    "KN": {"phone_code": "1", "flag": "🇰🇳", "name": "Saint Kitts and Nevis", "id": "5913691898077253637"},
    "KR": {"phone_code": "82", "flag": "🇰🇷", "name": "Korea, Republic of", "id": "5913371673905598425"},
    "KW": {"phone_code": "965", "flag": "🇰🇼", "name": "Kuwait", "id": "5913290705182134003"},
    "KZ": {"phone_code": "7", "flag": "🇰🇿", "name": "Kazakhstan", "id": "5913724621433082323"},
    "LA": {"phone_code": "856", "flag": "🇱🇦", "name": "Lao People's Democratic Republic", "id": "5913718526874489279"},
    "LB": {"phone_code": "961", "flag": "🇱🇧", "name": "Lebanon", "id": "5911504273664905447"},
    "LC": {"phone_code": "1", "flag": "🇱🇨", "name": "Saint Lucia", "id": "5911243659344351824"},
    "LI": {"phone_code": "423", "flag": "🇱🇮", "name": "Liechtenstein", "id": "5911166650580734660"},
    "LK": {"phone_code": "94", "flag": "🇱🇰", "name": "Sri Lanka", "id": "5911293163137406640"},
    "LR": {"phone_code": "231", "flag": "🇱🇷", "name": "Liberia", "id": "5913324167272337727"},
    "LS": {"phone_code": "266", "flag": "🇱🇸", "name": "Lesotho", "id": "5911059881988723711"},
    "LT": {"phone_code": "370", "flag": "🇱🇹", "name": "Lithuania", "id": "5911172315642597775"},
    "LU": {"phone_code": "352", "flag": "🇱🇺", "name": "Luxembourg", "id": "5913390842344640293"},
    "LV": {"phone_code": "371", "flag": "🇱🇻", "name": "Latvia", "id": "5913738489882480243"},
    "LY": {"phone_code": "218", "flag": "🇱🇾", "name": "Libya", "id": "5911236989260140996"},
    "MA": {"phone_code": "212", "flag": "🇲🇦", "name": "Morocco", "id": "5911482111633658301"},
    "MC": {"phone_code": "377", "flag": "🇲🇨", "name": "Monaco", "id": "5911245347266500057"},
    "MD": {"phone_code": "373", "flag": "🇲🇩", "name": "Moldova, Republic of", "id": "5913456847402045950"},
    "ME": {"phone_code": "382", "flag": "🇲🇪", "name": "Montenegro", "id": "5913239436157522151"},
    "MG": {"phone_code": "261", "flag": "🇲🇬", "name": "Madagascar", "id": "5913766918271012920"},
    "MH": {"phone_code": "692", "flag": "🇲🇭", "name": "Marshall Islands", "id": "5913235935759175692"},
    "MK": {"phone_code": "389", "flag": "🇲🇰", "name": "North Macedonia", "id": "5913394029210374721"},
    "ML": {"phone_code": "223", "flag": "🇲🇱", "name": "Mali", "id": "5911305266355245916"},
    "MM": {"phone_code": "95", "flag": "🇲🇲", "name": "Myanmar", "id": "5433666360003540231"},
    "MN": {"phone_code": "976", "flag": "🇲🇳", "name": "Mongolia", "id": "5911041383564580038"},
    "MQ": {"phone_code": "596", "flag": "🇲🇶", "name": "Martinique", "id": "5911378005921370347"},
    "MR": {"phone_code": "222", "flag": "🇲🇷", "name": "Mauritania", "id": "5433859405898594234"},
    "MT": {"phone_code": "356", "flag": "🇲🇹", "name": "Malta", "id": "5911023714069123567"},
    "MU": {"phone_code": "230", "flag": "🇲🇺", "name": "Mauritius", "id": "5913291113204027321"},
    "MV": {"phone_code": "960", "flag": "🇲🇻", "name": "Maldives", "id": "5913501399097806832"},
    "MX": {"phone_code": "52", "flag": "🇲🇽", "name": "Mexico", "id": "5913687302462246518"},
    "MY": {"phone_code": "60", "flag": "🇲🇾", "name": "Malaysia", "id": "5913654360063087453"},
    "MZ": {"phone_code": "258", "flag": "🇲🇿", "name": "Mozambique", "id": "5911333419865871464"},
    "NA": {"phone_code": "264", "flag": "🇳🇦", "name": "Namibia", "id": "5911108535378252443"},
    "NE": {"phone_code": "227", "flag": "🇳🇪", "name": "Niger", "id": "5911270086278124251"},
    "NG": {"phone_code": "234", "flag": "🇳🇬", "name": "Nigeria", "id": "5911143844304393105"},
    "NL": {"phone_code": "31", "flag": "🇳🇱", "name": "Netherlands", "id": "5913367645226275100"},
    "NO": {"phone_code": "47", "flag": "🇳🇴", "name": "Norway", "id": "5913617397574537046"},
    "NP": {"phone_code": "977", "flag": "🇳🇵", "name": "Nepal", "id": "5913496520014958723"},
    "NZ": {"phone_code": "64", "flag": "🇳🇿", "name": "New Zealand", "id": "5913640044937089340"},
    "OM": {"phone_code": "968", "flag": "🇴🇲", "name": "Oman", "id": "5913570801474343473"},
    "PA": {"phone_code": "507", "flag": "🇵🇦", "name": "Panama", "id": "5913428968769327174"},
    "PE": {"phone_code": "51", "flag": "🇵🇪", "name": "Peru", "id": "5911207993935925780"},
    "PG": {"phone_code": "675", "flag": "🇵🇬", "name": "Papua New Guinea", "id": "5911107251183030903"},
    "PH": {"phone_code": "63", "flag": "🇵🇭", "name": "Philippines", "id": "5911268638874145162"},
    "PK": {"phone_code": "92", "flag": "🇵🇰", "name": "Pakistan", "id": "5913705895375672082"},
    "PL": {"phone_code": "48", "flag": "🇵🇱", "name": "Poland", "id": "5913550391789752571"},
    "PR": {"phone_code": "1", "flag": "🇵🇷", "name": "Puerto Rico", "id": "5911504350974317480"},
    "PS": {"phone_code": "970", "flag": "🇵🇸", "name": "Palestine, State of", "id": "5913684768431541668"},
    "PT": {"phone_code": "351", "flag": "🇵🇹", "name": "Portugal", "id": "5911023653939581472"},
    "PW": {"phone_code": "680", "flag": "🇵🇼", "name": "Palau", "id": "5911283903187915549"},
    "PY": {"phone_code": "595", "flag": "🇵🇾", "name": "Paraguay", "id": "5911014265141072316"},
    "QA": {"phone_code": "974", "flag": "🇶🇦", "name": "Qatar", "id": "5911260864983339619"},
    "RO": {"phone_code": "40", "flag": "🇷🇴", "name": "Romania", "id": "5913460373570195273"},
    "RS": {"phone_code": "381", "flag": "🇷🇸", "name": "Serbia", "id": "5913592598433369871"},
    "RU": {"phone_code": "79", "flag": "🇷🇺", "name": "Russian Federation", "id": "5913274246867456342"},
    "RW": {"phone_code": "250", "flag": "🇷🇼", "name": "Rwanda", "id": "5911455229433352234"},
    "SA": {"phone_code": "966", "flag": "🇸🇦", "name": "Saudi Arabia", "id": "5911300687920108242"},
    "SB": {"phone_code": "677", "flag": "🇸🇧", "name": "Solomon Islands", "id": "5911482712929080608"},
    "SC": {"phone_code": "248", "flag": "🇸🇨", "name": "Seychelles", "id": "5911185183364616913"},
    "SD": {"phone_code": "249", "flag": "🇸🇩", "name": "Sudan", "id": "5911387497799094470"},
    "SE": {"phone_code": "46", "flag": "🇸🇪", "name": "Sweden", "id": "5911156510162949403"},
    "SG": {"phone_code": "65", "flag": "🇸🇬", "name": "Singapore", "id": "5911531460808051849"},
    "SI": {"phone_code": "386", "flag": "🇸🇮", "name": "Slovenia", "id": "5913431983836368644"},
    "SK": {"phone_code": "421", "flag": "🇸🇰", "name": "Slovakia", "id": "5913751666842145020"},
    "SL": {"phone_code": "232", "flag": "🇸🇱", "name": "Sierra Leone", "id": "5911210450657218661"},
    "SM": {"phone_code": "378", "flag": "🇸🇲", "name": "San Marino", "id": "5913587968458625465"},
    "SN": {"phone_code": "221", "flag": "🇸🇳", "name": "Senegal", "id": "5910995302860461643"},
    "SO": {"phone_code": "252", "flag": "🇸🇴", "name": "Somalia", "id": "5911397852965244436"},
    "SR": {"phone_code": "597", "flag": "🇸🇷", "name": "Suriname", "id": "5913275539652611719"},
    "SS": {"phone_code": "211", "flag": "🇸🇸", "name": "South Sudan", "id": "5911406262511211744"},
    "ST": {"phone_code": "239", "flag": "🇸🇹", "name": "Sao Tome and Principe", "id": "5913574331937462345"},
    "SV": {"phone_code": "503", "flag": "🇸🇻", "name": "El Salvador", "id": "5913238624408703010"},
    "SZ": {"phone_code": "268", "flag": "🇸🇿", "name": "Eswatini", "id": "5913374525763883286"},
    "TD": {"phone_code": "235", "flag": "🇹🇩", "name": "Chad", "id": "5913299849167507310"},
    "TG": {"phone_code": "228", "flag": "🇹🇬", "name": "Togo", "id": "5913423260757790970"},
    "TH": {"phone_code": "66", "flag": "🇹🇭", "name": "Thailand", "id": "5913617968805187987"},
    "TJ": {"phone_code": "992", "flag": "🇹🇯", "name": "Tajikistan", "id": "5911287639809463107"},
    "TL": {"phone_code": "670", "flag": "🇹🇱", "name": "Timor-Leste", "id": "5911141915864076479"},
    "TM": {"phone_code": "993", "flag": "🇹🇲", "name": "Turkmenistan", "id": "5913315521503170180"},
    "TN": {"phone_code": "216", "flag": "🇹🇳", "name": "Tunisia", "id": "5911332947419468671"},
    "TR": {"phone_code": "90", "flag": "🇹🇷", "name": "Türkiye", "id": "5910995113881901195"},
    "TT": {"phone_code": "1", "flag": "🇹🇹", "name": "Trinidad and Tobago", "id": "5911228635548750294"},
    "TZ": {"phone_code": "255", "flag": "🇹🇿", "name": "Tanzania", "id": "5911418949844603556"},
    "UA": {"phone_code": "380", "flag": "🇺🇦", "name": "Ukraine", "id": "5222250679371839695"},
    "UG": {"phone_code": "256", "flag": "🇺🇬", "name": "Uganda", "id": "5913488939397681980"},
    "US": {"phone_code": "1", "flag": "🇺🇸", "name": "United States", "id": "5913317269554859959"},
    "UY": {"phone_code": "598", "flag": "🇺🇾", "name": "Uruguay", "id": "5913623088406204470"},
    "UZ": {"phone_code": "998", "flag": "🇺🇿", "name": "Uzbekistan", "id": "5911051846104912282"},
    "VA": {"phone_code": "39", "flag": "🇻🇦", "name": "Holy See (Vatican City State)", "id": "5911211932420938860"},
    "VC": {"phone_code": "1", "flag": "🇻🇨", "name": "Saint Vincent and the Grenadines", "id": "5911318941531116255"},
    "VI": {"phone_code": "1", "flag": "🇻🇮", "name": "Virgin Islands, U.S.", "id": "5911297153162023306"},
    "VN": {"phone_code": "84", "flag": "🇻🇳", "name": "Viet Nam", "id": "5913428887164949581"},
    "VU": {"phone_code": "678", "flag": "🇻🇺", "name": "Vanuatu", "id": "5913511535220625585"},
    "WS": {"phone_code": "685", "flag": "🇼🇸", "name": "Samoa", "id": "5913325971158602854"},
    "XK": {"phone_code": "383", "flag": "🇽🇰", "name": "Kosovo", "id": "5911433681582429010"},
    "YE": {"phone_code": "967", "flag": "🇾🇪", "name": "Yemen", "id": "5913346492512341993"},
    "ZA": {"phone_code": "27", "flag": "🇿🇦", "name": "South Africa", "id": "5911203119148044594"},
    "ZM": {"phone_code": "260", "flag": "🇿🇲", "name": "Zambia", "id": "5913564754160389778"},
    "ZW": {"phone_code": "263", "flag": "🇿🇼", "name": "Zimbabwe", "id": "5911092502265336396"}
}

def load_premium_flags():
    return RAW_FLAG_EMOJIS

def process_premium_txt(text_content):
    return 0, 0

def get_country_info(short_code):
    dyn_flags = load_premium_flags()
    
    # 🚀 Handle if the admin inputted a dialing code (e.g. 225, 880) instead of short code
    if str(short_code).isdigit() or str(short_code).startswith("+"):
        clean_phone = str(short_code).replace("+", "").strip()
        for code, info in dyn_flags.items():
            if info.get("phone_code") == clean_phone:
                return info
        
        resolved_code = get_country_code(clean_phone)
        if resolved_code != 'Unknown':
            short_code = resolved_code

    if short_code in dyn_flags:
        return dyn_flags[short_code]
    return shortCountryCodes.get(short_code, {"name": short_code, "flag": "🏳️", "id": "5336972142066047577"})

def get_app_raw_id(app_name):
    dyn_apps = load_premium_apps()
    name_lower = app_name.lower()
    
    for key, val in dyn_apps.items():
        if key in name_lower: return val
            
    for key, val in RAW_APP_EMOJIS.items():
        if key in name_lower: return val
    return "5336879280578138635" # Default 🖥 Other Service

def get_app_pemoji(app_name):
    raw_id = get_app_raw_id(app_name)
    return f"<tg-emoji emoji-id='{raw_id}'>🖥</tg-emoji>"

def escape_html(text):
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# Regex: any emoji character immediately followed by {emoji_id}
_INLINE_PEMOJI_PATTERN = re.compile(
    r'([\U0001F000-\U0001FFFF\u2600-\u27BF\u2190-\u21FF\u2300-\u23FF\u2B00-\u2BFF\uFE0F]+)\{(\d{10,20})\}'
)

def apply_inline_premium_emoji(text):
    """
    Admin কে দেওয়া একটা সুবিধা: টেক্সটের মধ্যে (আগে/পরে/মাঝে) কোনো emoji-এর ঠিক
    পরে {emoji_id} লিখলে বট সেটাকে আসল প্রিমিয়াম emoji-তে রূপান্তর করে দেয়।
    উদাহরণ: "Hello 🔥{5201732344993576400} World"
          -> "Hello <tg-emoji emoji-id='5201732344993576400'>🔥</tg-emoji> World"
    ব্যবহারের আগে টেক্সট escape_html() দিয়ে escape করা থাকতে হবে (নিরাপত্তার জন্য),
    তারপর এই ফাংশন কল করুন।
    """
    if not text:
        return text
    def _repl(m):
        emoji_char, emoji_id = m.group(1), m.group(2)
        return f"<tg-emoji emoji-id='{emoji_id}'>{emoji_char}</tg-emoji>"
    return _INLINE_PEMOJI_PATTERN.sub(_repl, text)

def mask_number(num):
    if not num:
        return ""
    num_str = str(num).replace("+", "").strip()
    if len(num_str) <= 6:
        return num_str
    first_3 = num_str[:3]
    last_3 = num_str[-3:]
    # এখানে ❖ যোগ করা হলো
    return f"{first_3}❖REDOX❖{last_3}"

def extract_otp(text):
    if not text:
        return "No OTP Found"
    
    # ১. হাইফেন বা স্পেস ছাড়া সরাসরি ৪-৮ ডিজিট (যেমন: 123456)
    match = re.search(r'\b\d{4,8}\b', text)
    if match: return match.group(0)
    
    # ২. হাইফেন যুক্ত ওটিপি (যেমন: 123-456)
    match = re.search(r'\b\d{3}-\d{3}\b', text)
    if match: return match.group(0).replace("-", "")

    # ৩. স্পেস যুক্ত ওটিপি যা Instagram এ থাকে (যেমন: 123 456)
    match = re.search(r'\b\d{3}\s\d{3}\b', text)
    if match: return match.group(0).replace(" ", "")

    # ৪. টেক্সটের ভেতরে থাকা ওটিপি খোঁজা
    matches = re.findall(r'(\b\d{3,4}-\d{3,4}\b)|(\b\d{4,8}\b)', text)
    if matches:
        first_match = next((item for item in matches[0] if item), "")
        return first_match.replace("-", "").replace(" ", "")

    return "No OTP Found"

def normalize_base_url(input_url):
    url = input_url.strip()
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = 'https://' + url
        
    if '/#/' in url:
        url = url.split('/#/')[0]
    elif '/#' in url:
        url = url.split('/#')[0]
        
    while url.endswith('/'):
        url = url[:-1]
        
    changed = True
    while changed:
        changed = False
        lower = url.lower()
        if lower.endswith('/mauth/login'):
            url = url[:-12]
            changed = True
        elif lower.endswith('/mauth'):
            url = url[:-6]
            changed = True
        elif lower.endswith('/auth/login'):
            url = url[:-11]
            changed = True
        elif lower.endswith('/auth'):
            url = url[:-5]
            changed = True
        elif lower.endswith('/login.php'):
            url = url[:-10]
            changed = True
        elif lower.endswith('/login'):
            url = url[:-6]
            changed = True
        elif lower.endswith('/signin'):
            url = url[:-7]
            changed = True
        elif lower.endswith('/client/smscdrstats'):
            url = url[:-19]
            changed = True
        elif lower.endswith('/cdrs'):
            url = url[:-5]
            changed = True
        elif lower.endswith('/app'):
            url = url[:-4]
            changed = True
        elif lower.endswith('/dashboard'):
            url = url[:-10]
            changed = True
            
        while url.endswith('/'):
            url = url[:-1]
            changed = True
            
    return url

# Time Helpers Matching JS CEST timezone logic
def parse_time_to_seconds(time_str):
    if not time_str:
        return 0
    parts = time_str.strip().split(':')
    h = int(parts[0]) if parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    s = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return h * 3600 + m * 60 + s

def get_seconds_difference(time1, time2):
    t1 = parse_time_to_seconds(time1)
    t2 = parse_time_to_seconds(time2)
    diff = abs(t1 - t2)
    if diff > 43200:
        diff = 86400 - diff
    return diff

import datetime as dt
def get_current_cest_time():
    # Fetch UTC timezone then add CEST (+2)
    now_utc = dt.datetime.now(dt.timezone.utc)
    # Simple hours addition for CEST
    hour = (now_utc.hour + 2) % 24
    return f"{hour:02d}:{now_utc.minute:02d}:{now_utc.second:02d}"

# ----------------------------------------------------
# DB Load and Save
# ----------------------------------------------------

def load_services():
    default_services = {}
    if os.path.exists(SERVICES_FILE):
        try:
            with open(SERVICES_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return content
                elif isinstance(content, list): # Purgatory Migration
                    return {"stexsms": content}
        except Exception as e:
            logger.error(f"Error reading services.json: {e}")
            
    try:
        with open(SERVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_services, f, indent=2, ensure_ascii=False)
        return default_services
    except Exception as e:
        logger.error(f"Error saving default services: {e}")
    return default_services

def save_services(services_dict):
    try:
        with open(SERVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(services_dict, f, indent=2, ensure_ascii=False)
        # 🚀 সার্ভিস সেভ হওয়ার সাথে সাথেই ফায়ারবেসে সিঙ্ক করার ব্যাকগ্রাউন্ড থ্রেড
        threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
    except Exception as e:
        logger.error(f"Error saving services.json: {e}")

def load_panels():
    default_panels = [
        {
            "id": "stex_api", "name": "Stex SMS API", "url": "https://api.2oo9.cloud/MKJGS2MSZYB/tness/@public/api", 
            "username": "API", "password": "MKJGS2MSZYB", 
            "getNumberUrl": "https://api.2oo9.cloud/MKJGS2MSZYB/tness/@public/api/getnum", 
            "getMessageUrl": "https://api.2oo9.cloud/MKJGS2MSZYB/tness/@public/api/success-otp", 
            "trafficUrl": "https://api.2oo9.cloud/MKJGS2MSZYB/tness/@public/api/console", 
            "sessionCookie": "MKJGS2MSZYB", "lastSeenCDRId": None, "status": "Initializing...", "lastSeenGetnumIds": []
        }
    ]
    if not os.path.exists(PANELS_FILE):
        save_panels_to_file(default_panels)
        return default_panels
    try:
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            list_panels = json.load(f)
            if not list_panels:
                list_panels = default_panels
            else:
                existing_ids = [p.get("id", "") for p in list_panels]
                for dp in default_panels:
                    if dp["id"] not in existing_ids:
                        list_panels.append(dp)
            for p in list_panels:
                p.setdefault("id", p.get("name", "panel").lower().replace(" ", "-"))
                p.setdefault("sessionCookie", "")
                p.setdefault("lastSeenCDRId", None)
                p.setdefault("lastSeenGetnumIds", [])
                p.setdefault("status", "Initializing...")
            return list_panels
    except Exception as e:
        logger.error(f"Failed to read panels.json: {e}")
        return default_panels

def save_panels_to_file(panels_list):
    try:
        with open(PANELS_FILE, "w", encoding="utf-8") as f:
            json.dump(panels_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save panels.json: {e}")

# Global Active Config List
panels = load_panels()

def get_session(panel_id):
    if panel_id not in sessions:
        try:
            import cloudscraper
            s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        except ImportError:
            s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        sessions[panel_id] = s
    return sessions[panel_id]

# ----------------------------------------------------
# Telegram API - Sanitized for zero Bad Request 400
# ----------------------------------------------------

def clean_keyboard(reply_markup):
    return reply_markup

def call_telegram(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if "reply_markup" in payload:
            payload["reply_markup"] = clean_keyboard(payload["reply_markup"])
        # টাইমআউট 15 থেকে বাড়িয়ে 40 করে দেওয়া হলো
        res = requests.post(url, json=payload, timeout=40)
        return res.json()
    except Exception as e:
        logger.error(f"Telegram {method} raw execution exception: {e}")
        return None

def send_bot_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": apply_inline_premium_emoji(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram("sendMessage", payload)

def edit_bot_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": apply_inline_premium_emoji(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram("editMessageText", payload)

def answer_callback(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
    call_telegram("answerCallbackQuery", payload)

def get_otp_group_btn():
    link = admin_db.get("otp_group_link", "").strip()
    if link and link.startswith("http"):
        return {"text": " Otp Group", "url": link, "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}
    return {"text": " Otp Group", "callback_data": "usr_otp_grp", "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}

def get_service_short_code(name, sms_body=""):
    text = (str(name) + " " + str(sms_body)).lower()
    if 'whatsapp' in text or 'wa' in text: return 'WS'
    if 'facebook' in text or 'fb' in text: return 'FB'
    if 'telegram' in text or 'tg' in text: return 'TG'
    if 'instagram' in text or 'ig' in text: return 'IG'
    if 'tiktok' in text or 'tt' in text: return 'TT'
    if 'google' in text: return 'GG'
    if 'microsoft' in text: return 'MS'
    if 'imo' in text: return 'IMO'
    if 'viber' in text: return 'VI'
    if 'snapchat' in text: return 'SC'
    if 'wechat' in text: return 'WC'
    if 'line' in text: return 'LN'
    if 'twitter' in text or ' x ' in text: return 'TW'
    if 'paypal' in text: return 'PP'
    if 'discord' in text: return 'DC'
    if 'amazon' in text: return 'AMZ'
    return 'OTP'

def send_to_telegram(message, otp=None, quick_range=None, full_sms_body=None, svc_em_id=None, buyer_chat_id=None, unmasked_number=None, svc_short=None, flag=None):
    fwd_groups = admin_db.get("forward_groups", [])
        
    base_keyboard = []
    
    # ওটিপি বাটন লজিক: ওটিপি না থাকলে "Copy SMS" আসবে
    if full_sms_body:
        has_otp = otp and otp != "No OTP Found"
        btn_label = f" {otp}" if has_otp else " Copy SMS"
        copy_val = otp if has_otp else full_sms_body
        
        otp_btn = {
            "text": btn_label,
            "copy_text": {"text": copy_val},
            "style": "success",
            "icon_custom_emoji_id": svc_em_id if svc_em_id else "5337255927735163754"
        }
        base_keyboard.append([otp_btn])

    # Full Message button has been removed from inline keyboard

    # --- Send to Inbox (Buyer) ---
    if buyer_chat_id and unmasked_number and svc_short and flag:
        
        # ডেটাবেস থেকে বর্তমান রিওয়ার্ড অ্যামাউন্ট (TK) নেওয়া হচ্ছে
        reward_amount = admin_db.get("redox_config", {}).get("otp_reward", 0.0)

        inbox_msg = (
            f"━━━━━━━━━━━━━━━\n"
            f"<blockquote><b>{get_pemoji('phone', '📱')} Number :</b> <code>{unmasked_number}</code></blockquote>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<blockquote><b>{get_pemoji('note', '📝')} FULL MESSAGE :</b>\n"
            f"<code><i># {escape_html(full_sms_body)}</i></code></blockquote>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<blockquote><b>{get_pemoji('gem', '💎')} ADDED :</b> <b>{reward_amount} TK</b></blockquote>\n"
            f"━━━━━━━━━━━━━━━"
        )
        
        inbox_payload = {
            "chat_id": buyer_chat_id,
            "text": inbox_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if base_keyboard:
            inbox_payload["reply_markup"] = {"inline_keyboard": base_keyboard}
        call_telegram("sendMessage", inbox_payload)

    # --- Send to Groups ---
    for grp in fwd_groups:
        chat_id = grp.get("id")
        custom_btns = grp.get("buttons", [])
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        group_keyboard = [row for row in base_keyboard]
        
        if custom_btns:
            btn_row = []
            for btn in custom_btns:
                btn_text = btn.get("text", "")
                btn_url = btn.get("url", "")
                
                btn_obj = {"text": btn_text, "url": btn_url}
                
                # 🚀 Priority 1: Use extracted premium emoji ID from DB
                if btn.get("emoji_id"):
                    btn_obj["icon_custom_emoji_id"] = btn.get("emoji_id")
                    btn_obj["style"] = "primary"
                else:
                    # 🚀 Fallback logic for old buttons or normal text
                    match = re.search(r'^([^\w\s]+)\s*(.*)', btn_text)
                    if match:
                        app_em_id = get_app_raw_id(match.group(2).strip())
                        if app_em_id and app_em_id != "5336879280578138635":
                            btn_obj["icon_custom_emoji_id"] = app_em_id
                            btn_obj["style"] = "primary"
                            btn_obj["text"] = f" {match.group(2).strip()}"
                
                btn_row.append(btn_obj)
                if len(btn_row) == 2:
                    group_keyboard.append(btn_row)
                    btn_row = []
            if btn_row:
                group_keyboard.append(btn_row)
                
        if group_keyboard:
            payload["reply_markup"] = {"inline_keyboard": group_keyboard}

        call_telegram("sendMessage", payload)

# ══════════════════════════════════════════════
# 📊 REAL-TIME STATS AUTO-POST (আসল ডেটা — OTP গ্রুপে অটো পোস্ট হয়)
# ══════════════════════════════════════════════
def broadcast_daily_stats():
    """আজকের রিয়েল OTP সাকসেস কাউন্ট + মোট ইউজার + এক্টিভ নাম্বার — OTP গ্রুপে (Forward Groups) সত্যিকারের ডেটা দিয়ে পোস্ট করে।"""
    fwd_groups = admin_db.get("forward_groups", [])
    if not fwd_groups:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    if admin_db.get("today_date") != today:
        admin_db["today_date"] = today
        admin_db["today_numbers_count"] = 0
        admin_db["today_otp_success"] = 0
        save_admin_db()

    today_otp = admin_db.get("today_otp_success", 0)
    users_count = len(admin_db.get("users", []))
    active_now = len(admin_db.get("active_numbers", {}))

    text = (
        f"{get_pemoji('dashboard', '📊')} <b>LIVE STATS UPDATE</b> {get_pemoji('dashboard', '📊')}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_pemoji('otp', '🔐')} <b>আজকের মোট OTP প্রাপ্তি</b> » <b>{today_otp}</b>\n"
        f"{get_pemoji('user', '👤')} <b>মোট ইউজার</b>              » <b>{users_count}</b>\n"
        f"{get_pemoji('phone', '📱')} <b>এখন এক্টিভ</b>            » <b>{active_now}</b>\n\n"
        f"{get_pemoji('done', '✅')} <i>রিয়েল-টাইম আপডেট — Redox বট থেকে সরাসরি</i>"
    )

    for grp in fwd_groups:
        chat_id = grp.get("id")
        if not chat_id:
            continue
        try:
            call_telegram("sendMessage", {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            })
        except Exception as e:
            logger.error(f"broadcast_daily_stats send error to {chat_id}: {e}")

def stats_broadcast_loop():
    """redox_config['stats_auto_post'] ON থাকলে, নির্ধারিত ইন্টারভালে OTP গ্রুপে রিয়েল স্ট্যাটস অটো-পোস্ট করে।"""
    while True:
        try:
            cfg = admin_db.get("redox_config", {})
            if cfg.get("stats_auto_post", False):
                interval_min = int(cfg.get("stats_interval_min", 60) or 60)
                if interval_min < 5:
                    interval_min = 5
                last_ts = admin_db.get("last_stats_post_ts", 0)
                if time.time() - last_ts >= interval_min * 60:
                    broadcast_daily_stats()
                    admin_db["last_stats_post_ts"] = time.time()
                    save_admin_db()
        except Exception as e:
            logger.error(f"stats_broadcast_loop error: {e}")
        time.sleep(60)

def process_and_send_sms(panel_name, raw_number, app_name, msg_body):
    otp = extract_otp(msg_body)
    masked_number = mask_number(raw_number)
    clean_num = str(raw_number).replace("+", "").strip()
    c_code = get_country_code(clean_num)
    c_info = get_country_info(c_code)
    flag = c_info.get('flag', '🏳️')
    
    svc_short = get_service_short_code(app_name, msg_body)
    
    # Smart Service Emoji Finder
    actual_app_name = str(app_name).strip() if app_name else ""
    if not actual_app_name:
        mb_lower = msg_body.lower()
        if "facebook" in mb_lower or "fb" in mb_lower: actual_app_name = "facebook"
        elif "whatsapp" in mb_lower or "wa" in mb_lower: actual_app_name = "whatsapp"
        elif "telegram" in mb_lower: actual_app_name = "telegram"
        elif "instagram" in mb_lower: actual_app_name = "instagram"
        elif "tiktok" in mb_lower: actual_app_name = "tiktok"
        elif "google" in mb_lower: actual_app_name = "google"
        elif "microsoft" in mb_lower: actual_app_name = "microsoft"
        else: actual_app_name = svc_short
        
    svc_em_id = get_app_raw_id(actual_app_name)
    
    # গ্রুপ মেসেজের জন্য প্রিমিয়াম ফ্ল্যাগ তৈরি
    f_id_grp = c_info.get('id', '5336972142066047577')
    premium_flag_grp = f"<tg-emoji emoji-id='{f_id_grp}'>{flag}</tg-emoji>"

    # নতুন মাস্কিং স্টাইল অনুযায়ী স্প্লিট করা হচ্ছে
    parts = masked_number.split("❖REDOX❖")
    if len(parts) == 2:
        # ❖SHA❖ দিয়ে নম্বর মাস্কিং করা হলো
        linked_number = f"{parts[0]}❖SHA❖{parts[1]}"
    else:
        linked_number = f"{masked_number}"
    
    # নতুন ডিজাইনের গ্রুপ মেসেজ (সব লাইন quote format)
    group_message = (
        f"━━━━━━━━━━━━━━━\n"
        f"<blockquote><b>{get_pemoji('phone', '📱')} Number :</b> {premium_flag_grp} <code>{linked_number}</code></blockquote>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<blockquote><b>{get_pemoji('otp', '🔑')} OTP :</b> <code>{otp if otp and otp != 'No OTP Found' else 'No OTP Found'}</code></blockquote>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<blockquote><b>{get_pemoji('note', '📩')} FULL MESSAGE :</b> <code><i>\n# {escape_html(msg_body)}</i></code></blockquote>\n"
        f"━━━━━━━━━━━━━━━"
    )
    
    buyer_chat_id = admin_db.get("active_numbers", {}).get(clean_num)
    if otp and otp != "No OTP Found" and buyer_chat_id:
        stats = admin_db.setdefault("user_stats", {}).setdefault(str(buyer_chat_id), {})
        stats.setdefault("otp_count", 0)
        stats.setdefault("balance", 0.0)
        cfg = admin_db.get("redox_config", {})
        stats["otp_count"] += 1
        stats["balance"] += float(cfg.get("otp_reward", 0.0))
        if stats.get("active_reqs"): stats["active_reqs"].pop(0)
        process_task_progress(str(buyer_chat_id), stats)
        # 📊 Panel Analytics: এই OTP কোন প্যানেল থেকে এসেছে তা ট্র্যাক করা (Success Rate হিসাবের জন্য)
        src_panel_id = admin_db.get("num_panel_map", {}).pop(clean_num, None)
        if src_panel_id:
            record_otp_success(src_panel_id)
        save_admin_db()
        
    quick_range = get_range_from_number(clean_num)
    send_to_telegram(group_message, otp, quick_range, msg_body, svc_em_id, buyer_chat_id, clean_num, svc_short, flag)

# ----------------------------------------------------
# Math Captcha & Authentication Solvers
# ----------------------------------------------------

def is_stex_api(panel):
    if not panel or not panel.get("url"): return False
    url_lower = panel["url"].lower()
    id_lower = panel.get("id", "").lower()
    return "@public/api" in url_lower or "stex" in id_lower

def get_clean_base_url(panel, base_url):
    if panel.get("resolvedBaseUrl"): return panel["resolvedBaseUrl"].rstrip('/')
    return base_url.split('#')[0].rstrip('/')

def login_to_panel(panel, force=False):
    panel_id = panel["id"]
    now = time.time()
    if not force and panel_id in panel_backoff_until and now < panel_backoff_until[panel_id]:
        logger.info(f"[{panel['name']}] Login requested skipped due to backoff.")
        return False

    panel["status"] = "Running (API)"
    panel["sessionCookie"] = panel.get("password", "MKJGS2MSZYB")
    save_panels_to_file(panels)
    return True

# ----------------------------------------------------
# Panel Analytics: Request/Success/OTP Stat Tracking
# ----------------------------------------------------

def record_panel_stat(panel_id, success, err_msg=None):
    """প্রতিটা নাম্বার রিকোয়েস্টের ফলাফল (allocated/failed) প্যানেল-ভিত্তিক ট্র্যাক করে।"""
    if not panel_id:
        return
    stats = admin_db.setdefault("panel_stats", {}).setdefault(panel_id, {
        "requested": 0, "allocated": 0, "failed": 0, "otp_success": 0,
        "last_status": "unknown", "last_error": "", "last_ts": 0
    })
    stats["requested"] = stats.get("requested", 0) + 1
    stats["last_ts"] = time.time()
    if success:
        stats["allocated"] = stats.get("allocated", 0) + 1
        stats["last_status"] = "ok"
        stats["last_error"] = ""
    else:
        stats["failed"] = stats.get("failed", 0) + 1
        stats["last_status"] = "fail"
        stats["last_error"] = str(err_msg or "")[:150]
    save_admin_db()

def record_otp_success(panel_id):
    """একটা নাম্বারে সফলভাবে OTP আসলে সেটা প্যানেলের নামে জমা রাখে (Success Rate হিসাবের জন্য)।"""
    if not panel_id:
        return
    stats = admin_db.setdefault("panel_stats", {}).setdefault(panel_id, {
        "requested": 0, "allocated": 0, "failed": 0, "otp_success": 0,
        "last_status": "unknown", "last_error": "", "last_ts": 0
    })
    stats["otp_success"] = stats.get("otp_success", 0) + 1

    # 📊 আজকের রিয়েল OTP সাকসেস কাউন্ট (Auto Stats Post ফিচারের জন্য — একদম আসল সংখ্যা)
    today = datetime.now().strftime("%Y-%m-%d")
    if admin_db.get("today_date") != today:
        admin_db["today_date"] = today
        admin_db["today_numbers_count"] = 0
        admin_db["today_otp_success"] = 0
    admin_db["today_otp_success"] = admin_db.get("today_otp_success", 0) + 1

    save_admin_db()

# ----------------------------------------------------
# Live SMS Real Purchasing
# ----------------------------------------------------

def buy_number(range_val, target_panel_id=None):
    panel = None
    if target_panel_id:
        panel = next((p for p in panels if p.get("id") == target_panel_id), None)
    else:
        services_data = load_services()
        supported_panels = []
        for p_id, s_list in services_data.items():
            for s in s_list:
                for c in s.get("countries", []):
                    clean_target = range_val.replace("X", "").replace("*", "")
                    if any(clean_target in r for r in c.get("ranges", [])):
                        supported_panels.append(p_id)
        if supported_panels:
            chosen_p_id = random.choice(supported_panels)
            panel = next((p for p in panels if p.get("id") == chosen_p_id), None)
            logger.info(f"Randomly selected panel {chosen_p_id} for range {range_val}")
        else:
            panel = panels[0] if panels else None
            
    if not panel:
        return {"success": False, "message": "No suitable panel configuration found."}

    p_id = panel.get("id")

    # Panel type routing
    ptype = panel.get("panel_type", "stex")
    if ptype in ("yesms", "hadi", "shark", "activation"):
        result = buy_number_activation(panel, range_val)
        record_panel_stat(p_id, result.get("success"), result.get("message"))
        return result

    # --- Default Stex API flow ---
    if not panel.get("sessionCookie"):
        login_to_panel(panel, force=True)
        if not panel.get("sessionCookie"):
            result = {"success": False, "message": "Stex SMS authentication failed. Credentials check required.", "panel_id": p_id}
            record_panel_stat(p_id, False, result["message"])
            return result

    try:
        clean_base = get_clean_base_url(panel, panel["url"])
        num_url = panel.get("getNumberUrl") or f"{clean_base}/getnum"
        headers = {
            "Content-Type": "application/json",
            "mauthapi": panel.get("sessionCookie", "MKJGS2MSZYB")
        }
        rid = range_val.replace("X", "").replace("*", "").strip()
        
        res = requests.post(num_url, json={"rid": rid}, headers=headers, timeout=20)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 200 and data.get("data"):
                num_data = data["data"]
                today = datetime.now().strftime("%Y-%m-%d")
                if admin_db.get("today_date") != today:
                    admin_db["today_date"] = today
                    admin_db["today_numbers_count"] = 0
                admin_db["today_numbers_count"] = admin_db.get("today_numbers_count", 0) + 1
                save_admin_db()

                result = {
                    "success": True,
                    "message": data.get("message", "Number allocated successfully"),
                    "number": num_data.get("full_number") or num_data.get("no_plus_number") or "",
                    "operator": num_data.get("operator", "Unknown"),
                    "country": num_data.get("country", "Unknown"),
                    "panel_id": p_id
                }
                record_panel_stat(p_id, True)
                return result
            result = {"success": False, "message": data.get("message", "Failed to get number from API."), "panel_id": p_id}
            record_panel_stat(p_id, False, result["message"])
            return result
        result = {"success": False, "message": f"API Error: {res.status_code}", "panel_id": p_id}
        record_panel_stat(p_id, False, result["message"])
        return result
    except Exception as e:
        logger.error(f"Error buying number for range: {e}")
        result = {"success": False, "message": str(e), "panel_id": p_id}
        record_panel_stat(p_id, False, result["message"])
        return result


# -----------------------------------------------------------
# Activation-type Panel (yesms / hadi / shark) API handlers
# -----------------------------------------------------------

def buy_number_activation(panel, range_val):
    """Buy number from yesms.online / hadi panel / shark panel style APIs."""
    token = panel.get("password", "")
    base_url = panel.get("url", "").rstrip("/")
    if not token or not base_url:
        return {"success": False, "message": "Panel API token or URL not configured."}

    # Derive service & country from range prefix (e.g. "880XXX" → country code prefix 880)
    rid = range_val.replace("X", "").replace("*", "").strip()
    # Try to find service name from services config
    service_code = "any"
    country_code = "0"
    services_data = load_services()
    for p_id, s_list in services_data.items():
        if p_id == panel.get("id"):
            for s in s_list:
                for c in s.get("countries", []):
                    if any(rid in r for r in c.get("ranges", [])):
                        service_code = s.get("id", "any")
                        country_code = c.get("code", "0")
                        break

    try:
        # Use panel-configured Get Number URL if set (e.g. ZENEX: /v1/getnum),
        # otherwise fall back to the legacy standard path.
        gn_url = panel.get("getNumberUrl") or f"{base_url}/api/getNumber"
        resp = requests.get(
            gn_url,
            params={"token": token, "api_key": token, "service": service_code, "country": country_code},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20
        )
        try:
            data = resp.json()
        except Exception:
            return {"success": False, "message": f"Invalid API response: {resp.text[:200]}"}

        status = str(data.get("status", data.get("success", "")))
        if status in ("1", "True", "true"):
            number = str(data.get("number", data.get("full_number", ""))).replace("+", "").strip()
            activation_id = str(data.get("activationId", data.get("id", data.get("request_id", ""))))
            today = datetime.now().strftime("%Y-%m-%d")
            if admin_db.get("today_date") != today:
                admin_db["today_date"] = today
                admin_db["today_numbers_count"] = 0
            admin_db["today_numbers_count"] = admin_db.get("today_numbers_count", 0) + 1
            save_admin_db()
            return {
                "success": True,
                "message": "Number allocated successfully",
                "number": number,
                "activation_id": activation_id,
                "panel_id": panel.get("id"),
                "operator": "Unknown",
                "country": country_code
            }
        err = data.get("message") or data.get("error") or f"Status: {status}"
        return {"success": False, "message": str(err)}
    except Exception as e:
        logger.error(f"[{panel['name']}] buy_number_activation error: {e}")
        return {"success": False, "message": str(e)}


def poll_activation_otp(panel, activation_id, number, buyer_chat_id, max_attempts=36):
    """Background thread: poll yesms/hadi/shark panel for OTP up to ~6 min."""
    token = panel.get("password", "")
    base_url = panel.get("url", "").rstrip("/")
    logger.info(f"[{panel['name']}] OTP polling started for {number}, activation_id={activation_id}")

    # Use panel-configured Get Message URL if set (e.g. ZENEX: /v1/numsuccess/info),
    # otherwise fall back to the legacy standard path.
    gm_url = panel.get("getMessageUrl") or f"{base_url}/api/getStatus"

    for attempt in range(max_attempts):
        time.sleep(10)
        try:
            resp = requests.get(
                gm_url,
                params={"token": token, "api_key": token, "id": activation_id, "request_id": activation_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15
            )
            try:
                data = resp.json()
            except Exception:
                continue

            status = str(data.get("status", ""))
            sms_text = data.get("sms") or data.get("message") or data.get("otp") or data.get("code") or ""

            if status == "2" or (sms_text and status not in ("3", "6", "0", "")):  # OTP received
                logger.info(f"[{panel['name']}] OTP received for {number}: {sms_text}")
                process_and_send_sms(panel["name"], number, "", sms_text)
                return
            elif status in ("3", "6"):  # Cancelled / expired
                logger.info(f"[{panel['name']}] Activation {activation_id} cancelled/expired.")
                return
        except Exception as e:
            logger.error(f"[{panel['name']}] OTP poll error (attempt {attempt+1}): {e}")

    logger.info(f"[{panel['name']}] OTP polling timed out for {number}")

# ----------------------------------------------------
# Active Traffic Aggregation Compiler
# ----------------------------------------------------

def compile_traffic_stats():
    # 🚀 Returns instant cached data from local database
    global local_traffic_stats
    return local_traffic_stats, get_current_cest_time(), False

def get_country_code(num):
    clean = str(num).replace('+', '').strip()
    
    # স্পেশাল কেস (তাজিকিস্তান)
    if clean.startswith('7992'): return 'TJ'
    
    # আপনার সেট করা নতুন দেশের লিস্ট থেকে স্বয়ংক্রিয়ভাবে চেক করা হবে
    flags = load_premium_flags()
    # ফোন কোডের সাইজ অনুযায়ী সর্ট করা (যাতে বড় কোডগুলো আগে চেক হয়)
    sorted_flags = sorted(flags.items(), key=lambda x: len(x[1].get("phone_code", "")), reverse=True)
    
    for short_code, info in sorted_flags:
        if clean.startswith(info["phone_code"]):
            return short_code
            
    # পুরনো কিছু ফলব্যাক (যদি কোনোটি লিস্টে না থাকে)
    if clean.startswith('241'): return 'GA'
    if clean.startswith('242'): return 'CG'
    if clean.startswith('243'): return 'CD'
    if clean.startswith('221'): return 'SN'
    if clean.startswith('223'): return 'ML'
    if clean.startswith('226'): return 'BF'
    if clean.startswith('227'): return 'NE'
    if clean.startswith('235'): return 'TD'
    
    return 'Unknown'

def get_range_from_number(num):
    clean = str(num).replace('+', '').strip()
    first_x = re.search(r'[Xx*\-]', clean)
    if first_x:
        clean = clean[:first_x.start()]
    if clean.startswith('225') and len(clean) > 7:
        return clean[:7]
    if len(clean) > 8:
        return clean[:8]
    return clean

def get_service_short_code(name, sms_body=""):
    text = (str(name) + " " + str(sms_body)).lower()
    if 'whatsapp' in text or 'wa' in text: return 'WS'
    if 'facebook' in text or 'fb' in text: return 'FB'
    if 'telegram' in text or 'tg' in text: return 'TG'
    if 'instagram' in text or 'ig' in text: return 'IG'
    if 'tiktok' in text or 'tt' in text: return 'TT'
    if 'google' in text: return 'GG'
    if 'microsoft' in text: return 'MS'
    if 'imo' in text: return 'IMO'
    if 'viber' in text: return 'VI'
    if 'snapchat' in text: return 'SC'
    if 'wechat' in text: return 'WC'
    if 'line' in text: return 'LN'
    if 'twitter' in text or ' x ' in text: return 'TW'
    if 'paypal' in text: return 'PP'
    if 'discord' in text: return 'DC'
    if 'amazon' in text: return 'AMZ'
    return 'OTP'

def get_service_display_name(name):
    lower = str(name).strip().lower()
    if 'facebook' in lower or lower == 'fb': return 'Facebook'
    if 'whatsapp' in lower or lower == 'wa': return 'WhatsApp'
    if 'telegram' in lower or lower == 'tg': return 'Telegram'
    if 'instagram' in lower or lower == 'ig': return 'Instagram'
    if 'microsoft' in lower or lower == 'ms': return 'Microsoft'
    if 'google' in lower or lower == 'gg': return 'Google'
    if 'imo' in lower: return 'IMO'
    if 'tiktok' in lower or lower == 'tt': return 'TikTok'
    if 'snapchat' in lower: return 'Snapchat'
    if 'viber' in lower: return 'Viber'
    if 'line' in lower: return 'LINE'
    if 'wechat' in lower: return 'WeChat'
    if 'twitter' in lower or lower == 'x': return 'Twitter'
    if 'postpaid' in lower: return 'PostPaid'
    if 'failed' in lower: return 'Failed Calls'
    return str(name).strip().capitalize()

def find_service_by_slug(stats, slug):
    # একদম হুবহু বা প্রথম ৫০ ক্যারেক্টার ম্যাচ করানো হচ্ছে যাতে কনফ্লিক্ট না হয়
    for service in stats.keys():
        if service[:50] == slug:
            return service
    for service in stats.keys():
        if slug.lower() in service.lower():
            return service
    return None

# ----------------------------------------------------
# Traffic Visualizers Layout
# ----------------------------------------------------

def render_traffic_home(chat_id, message_id=None):
    try:
        stats, ref_time, is_fallback = compile_traffic_stats()
        
        message_text = "╔═══════════════╗\n" \
                       f"║ <tg-emoji emoji-id='5352877703043258544'>📈</tg-emoji> <b>NETWORK TRAFFIC</b>\n" \
                       "╚═══════════════╝\n"

        services_with_counts = []
        for svc, ctrs in stats.items():
            total = sum(ctr_data["success"] for ctr_data in ctrs.values())
            services_with_counts.append((svc, total))

        services_with_counts.sort(key=lambda x: x[1], reverse=True)

        if not services_with_counts:
            message_text += "<i>No active traffic recorded in the last 10 minutes on REDOX.</i>"
        else:
            is_first = True
            # ডাইনামিক ইনলাইন বাটনের ইমোজি আইডি
            raw_ids = {
                "Facebook": "5334807341109908955", "WhatsApp": "5334759662677957452",
                "Telegram": "5337010556253543833", "Instagram": "5334868205091459431",
                "Microsoft": "5334880948259427772", "Google": "5463352748751753567",
                "TikTok": "5339213256001102461"
            }
            
            for svc, total in services_with_counts:
                if not is_first:
                    message_text += "\n"
                is_first = False
                p_emoji = get_app_pemoji(svc)
                message_text += f"» {p_emoji} {svc}\n" \
                               f"➥ {total} OTP\n"

        inline_buttons = []
        for svc, total in services_with_counts:
            safe_slug = svc[:50]
            btn_emoji_id = get_app_raw_id(svc)
            inline_buttons.append([{
                "text": f" Explore {svc} Range",
                "callback_data": f"tr_svc:{safe_slug}",
                "style": "primary",
                "icon_custom_emoji_id": btn_emoji_id
            }])

        inline_buttons.append([
            {"text": " Refresh", "callback_data": "tr_refresh", "style": "success", "icon_custom_emoji_id": "5465368548702446780"},
            {"text": " Close", "callback_data": "tr_close", "style": "danger", "icon_custom_emoji_id": "5420130255174145507"}
        ])

        keyboard = {"inline_keyboard": inline_buttons}
        if message_id:
            edit_bot_message(chat_id, message_id, message_text, keyboard)
        else:
            send_bot_message(chat_id, message_text, keyboard)

    except Exception as e:
        error_msg = f"❌ Error fetching traffic stats: <code>{escape_html(str(e))}</code>"
        if message_id:
            edit_bot_message(chat_id, message_id, error_msg, {
                "inline_keyboard": [[{"text": "🔙 Back to Traffic Menu", "callback_data": "tr_refresh", "style": "danger"}]]
            })
        else:
            send_bot_message(chat_id, error_msg, {
                "inline_keyboard": [[{"text": "🔙 Back to Traffic Menu", "callback_data": "tr_refresh", "style": "danger"}]]
            })

def render_explore_service(chat_id, message_id, service_slug):
    try:
        stats, _, _ = compile_traffic_stats()
        service_name = find_service_by_slug(stats, service_slug)

        if not service_name or service_name not in stats:
            edit_bot_message(chat_id, message_id, f"❌ Service <code>{escape_html(service_slug)}</code> has no active traffic or has expired.", {
                "inline_keyboard": [[{"text": "🔙 Back to Traffic Menu", "callback_data": "tr_refresh", "style": "danger"}]]
            })
            return

        text = f"{get_pemoji('king', '👑')} <b>Explore Service:</b> {service_name}\n\nSelect a country to view available ranges:"
        country_buttons = []
        sorted_codes = sorted(stats[service_name].keys(), key=lambda code: stats[service_name][code]["success"], reverse=True)
        
        for idx, code in enumerate(sorted_codes, start=1):
            c_info = get_country_info(code)
            name = c_info.get("name", "Unknown")
            em_id = c_info.get("id", "5336972142066047577") # Default World ID
            success_count = stats[service_name][code]["success"]
            
            country_buttons.append([{
                "text": f"{idx}. {name} ({code}) - {success_count} OTP",
                "callback_data": f"tr_ctr:{service_slug}:{code}",
                "style": "primary",
                "icon_custom_emoji_id": em_id
            }])

        country_buttons.append([{"text": " Back", "callback_data": "tr_refresh", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
        edit_bot_message(chat_id, message_id, text, {"inline_keyboard": country_buttons})

    except Exception as e:
        edit_bot_message(chat_id, message_id, f"❌ Error: <code>{escape_html(str(e))}</code>", {
            "inline_keyboard": [[{"text": "🔙 Back to Traffic Menu", "callback_data": "tr_refresh", "style": "danger"}]]
        })

def render_explore_ranges(chat_id, message_id, service_slug, country_code):
    try:
        stats, _, _ = compile_traffic_stats()
        service_name = find_service_by_slug(stats, service_slug)

        if not service_name or service_name not in stats or country_code not in stats[service_name]:
            edit_bot_message(chat_id, message_id, "❌ No active ranges found for this service and country.", {
                "inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"tr_svc:{service_slug}", "style": "danger"}]]
            })
            return

        c_info = get_country_info(country_code)
        flag_pemoji = f"<tg-emoji emoji-id='{c_info.get('id', '5336972142066047577')}'>{c_info.get('flag', '🏳️')}</tg-emoji>"
        
        text = f"{get_pemoji('king', '👑')} <b>Ranges for</b> {service_name} - {flag_pemoji} {country_code}\n\n" \
               "Click on any range below to get an instant tap-to-copy message!"

        range_buttons = []
        ranges_data = stats[service_name][country_code]["ranges"]
        sorted_ranges = sorted(ranges_data.items(), key=lambda x: x[1], reverse=True)

        for range_val, count in sorted_ranges:
            range_buttons.append([{
                "text": f" {range_val} ({count})",
                "copy_text": {"text": range_val},
                "style": "success",
                "icon_custom_emoji_id": "5192739271886282680" # Notepad/Clipboard emoji
            }])

        range_buttons.append([{"text": " Back", "callback_data": f"tr_svc:{service_slug}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
        edit_bot_message(chat_id, message_id, text, {"inline_keyboard": range_buttons})
        
    except Exception as e:
        edit_bot_message(chat_id, message_id, f"❌ Error: <code>{escape_html(str(e))}</code>", {
            "inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"tr_svc:{service_slug}", "style": "danger"}]]
        })

# ----------------------------------------------------
# Search Engine and allocation routers
# ----------------------------------------------------

def search_number_otp(chat_id, query):
    passed, err_msg, _ = check_user_limits(chat_id, update_cooldown=False)
    if not passed:
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "usr_search_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
        send_bot_message(chat_id, err_msg, kb)
        return

    clean_num = str(query).replace("+", "").strip()
    valid_panels = panels
    if not valid_panels:
        send_bot_message(chat_id, f"{get_pemoji('error', '❌')} No active panels available.")
        return
        
    panel = random.choice(valid_panels)
    if not panel.get("sessionCookie"): login_to_panel(panel, force=True)

    send_bot_message(chat_id, f"{get_pemoji('search', '🔍')} <i>Searching messages on <b>{panel['name']}</b> for <b>{escape_html(clean_num)}</b>...</i>")

    try:
        baseUrl = normalize_base_url(panel["url"])
        domain_match = re.match(r'^(https?://[^/]+)', baseUrl)
        domain = domain_match.group(1) if domain_match else baseUrl
        today_date_str = datetime.now().strftime("%Y-%m-%d")
        session = get_session(panel["id"])

        get_url = panel.get("getMessageUrl") or f"{get_clean_base_url(panel, panel['url'])}/success-otp"
        headers = {"mauthapi": panel.get("sessionCookie", "MKJGS2MSZYB")}
        res = session.get(get_url, headers=headers, timeout=20)
        
        if res.status_code == 200:
            data = res.json()
            otps = data.get("data", {}).get("otps", [])
            numbers = [{"number": i.get("number"), "message": i.get("message"), "app_name": "OTP"} for i in otps]
        else:
            send_bot_message(chat_id, f"❌ Stex API search error: {res.status_code}")
            return

        if isinstance(numbers, list):
            matched = [num for num in numbers if clean_num in str(num.get("number", ""))]
            if matched:
                send_bot_message(chat_id, f"🔍 Found <b>{len(matched)}</b> match(es) for <code>{clean_num}</code>:")
                for num in matched:
                    raw_msg = num.get("message") or num.get("otp") or num.get("sms") or num.get("smsBody") or num.get("sms_text") or num.get("sms_body") or ""
                    msg = str(raw_msg).strip()
                    number_val = num.get("number", "")
                    
                    c_code = get_country_code(number_val)
                    c_info = get_country_info(c_code)
                    flag_em_id = c_info.get("id", "5336972142066047577")
                    
                    svc_name = num.get("app_name", "OTP")
                    svc_short = get_service_short_code(svc_name, msg)
                    svc_em_id = get_app_raw_id(svc_name)
                    
                    box_design = (
                        f"╔═════════════╗\n"
                        f"║ <tg-emoji emoji-id='{svc_em_id}'>💬</tg-emoji> #{svc_short} <tg-emoji emoji-id='{flag_em_id}'>🚩</tg-emoji> <code>{number_val}</code>\n"
                        f"╚═════════════╝"
                    )

                    inline_keyboard = []
                    if msg:
                        otp_val = extract_otp(msg)
                        has_otp = otp_val != "No OTP Found"
                        inline_keyboard.append([{
                            "text": f" {otp_val}" if has_otp else " Copy SMS",
                            "copy_text": {"text": otp_val if has_otp else msg},
                            "style": "success",
                            "icon_custom_emoji_id": svc_em_id
                        }])
                        inline_keyboard.append([{
                            "text": " Full Message",
                            "copy_text": {"text": msg},
                            "style": "primary",
                            "icon_custom_emoji_id": "5337302974806922068"
                        }])
                    else:
                        inline_keyboard.append([{
                            "text": " Pending (No SMS yet)",
                            "callback_data": "none",
                            "style": "danger",
                            "icon_custom_emoji_id": "5337172996211648018"
                        }])

                    search_range_val = get_range_from_number(number_val)
                    inline_keyboard.extend([
                        [
                            {"text": " Change Number", "callback_data": f"buy_{search_range_val}", "style": "danger", "icon_custom_emoji_id": "5420155432272438703"},
                            get_otp_group_btn()
                        ],
                        [{"text": " Back", "callback_data": "usr_search_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
                    ])
                    send_bot_message(chat_id, box_design, {"inline_keyboard": inline_keyboard})
            else:
                send_bot_message(chat_id, f"❌ No active numbers found matching <code>{clean_num}</code> on {panel['name']} today.")
        else:
            send_bot_message(chat_id, "❌ Failed to retrieve valid numbers format from API.")
    except Exception as e:
        send_bot_message(chat_id, f"❌ Error searching database: <code>{escape_html(str(e))}</code>")

def trigger_buy_number(chat_id, range_val, target_panel_id=None, message_id=None, callback_id=None):
    try:
        passed, err_msg, batch_size = check_user_limits(chat_id)
        if not passed:
            if callback_id:
                answer_callback(callback_id, err_msg, show_alert=True)
            else:
                kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
                if message_id: edit_bot_message(chat_id, message_id, f"⚠️ {err_msg}", kb)
                else: send_bot_message(chat_id, f"⚠️ {err_msg}", kb)
            return

        if callback_id:
            answer_callback(callback_id, f"Requesting {range_val}...")

        initial_text = f"{get_pemoji('wait', '⏳')} <i>Allocating {batch_size} number(s) for range <b>{escape_html(range_val)}</b>... Please wait.</i>"
        
        if message_id:
            edit_bot_message(chat_id, message_id, initial_text)
        else:
            res = send_bot_message(chat_id, initial_text)
            message_id = res.get("result", {}).get("message_id") if res else None

        numbers_fetched = []
        last_err = "Unknown error"
        if "active_numbers" not in admin_db: admin_db["active_numbers"] = {}
        
        for _ in range(batch_size):
            result = buy_number(range_val, target_panel_id)
            if result.get("success"):
                numbers_fetched.append(result)
                number_val = result.get("number") or ""
                clean_num = str(number_val).replace("+", "").strip()
                admin_db["active_numbers"][clean_num] = str(chat_id)
                if result.get("panel_id"):
                    admin_db.setdefault("num_panel_map", {})[clean_num] = result.get("panel_id")
                # Start OTP polling for activation-type panels (yesms/hadi/shark)
                act_id = result.get("activation_id")
                act_panel_id = result.get("panel_id")
                if act_id and act_panel_id:
                    act_panel = next((p for p in panels if p.get("id") == act_panel_id), None)
                    if act_panel:
                        threading.Thread(
                            target=poll_activation_otp,
                            args=(act_panel, act_id, clean_num, chat_id),
                            daemon=True
                        ).start()
            else:
                last_err = result.get("message", "Failed.")
                break
                
        if numbers_fetched:
            save_admin_db()
            c_code = get_country_code(numbers_fetched[0].get("number", ""))
            c_info = get_country_info(c_code)
            flag_em_id = c_info.get("id", "5336972142066047577")
            
            blank_text = "ㅤ"
            keyboard = {"inline_keyboard": []}
            
            for res in numbers_fetched:
                num = res.get("number", "")
                keyboard["inline_keyboard"].append([{
                    "text": f" +{num.replace('+', '')}",
                    "copy_text": {"text": f"{num}"},
                    "style": "primary",
                    "icon_custom_emoji_id": flag_em_id
                }])
                
            keyboard["inline_keyboard"].extend([
                [
                    {"text": " Change Number", "callback_data": f"buy_{range_val}", "style": "danger", "icon_custom_emoji_id": "5420155432272438703"},
                    get_otp_group_btn()
                ],
                [{"text": " Back", "callback_data": "usr_search_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
            ])
            if message_id:
                edit_bot_message(chat_id, message_id, blank_text, keyboard)
            else:
                send_bot_message(chat_id, blank_text, keyboard)
        else:
            failure_text = f"❌ <b>Get Number Failed!</b>\n\n" \
                           f"<b>Range:</b> <code>{escape_html(range_val)}</code>\n" \
                           f"<b>Error:</b> <code>{escape_html(last_err)}</code>\n\n" \
                           f"<i>Please try again, or confirm you have enough balance.</i>"

            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔁 Retry getting range", "callback_data": f"buy_{range_val}", "style": "danger"}]
                ]
            }
            if message_id:
                edit_bot_message(chat_id, message_id, failure_text, keyboard)
            else:
                send_bot_message(chat_id, failure_text, keyboard)
    except Exception as e:
        logger.error(f"Error buying range: {e}")
        send_bot_message(chat_id, f"❌ <code>Error requesting number: {escape_html(str(e))}</code>")

def render_admin_panel(chat_id, message_id=None):
    if str(chat_id) not in admin_db.get("admins", [OWNER_ID]):
        send_bot_message(chat_id, "❌ You are not authorized to view the Admin Panel.")
        return

    # Check and reset daily count if needed
    today = datetime.now().strftime("%Y-%m-%d")
    if admin_db.get("today_date") != today:
        admin_db["today_date"] = today
        admin_db["today_numbers_count"] = 0
        save_admin_db()

    users_count = len(admin_db.get("users", []))
    numbers_count = admin_db.get("today_numbers_count", 0)

    panels_count = len(load_panels())
    active_now = len(admin_db.get("active_numbers", {}))
    panel_stats = admin_db.get("panel_stats", {})
    total_requested = sum(s.get("requested", 0) for s in panel_stats.values())
    total_allocated = sum(s.get("allocated", 0) for s in panel_stats.values())
    total_otp_success = sum(s.get("otp_success", 0) for s in panel_stats.values())
    success_rate = round((total_otp_success / total_allocated) * 100, 1) if total_allocated else 0.0

    # Progress bar for Success Rate — ক্লাসিক বার + পার্সেন্ট ভিতরে
    filled = round(success_rate / 20)  # out of 20 blocks
    filled = max(0, min(20, filled))
    bar = f"{'▓' * filled}{'░' * (20 - filled)} {success_rate}%"
    if success_rate >= 80:
        status_line = f"{get_pemoji('done', '🔥')} <b>Status:</b> Excellent"
    elif success_rate >= 50:
        status_line = f"{get_pemoji('warn', '⚡')} <b>Status:</b> Good"
    else:
        status_line = f"{get_pemoji('cross', '⚠️')} <b>Status:</b> Needs Improvement"

    text = (
        f"{get_pemoji('dashboard', '📊')} <b>ADMIN CONTROL PANEL</b> {get_pemoji('dashboard', '📊')}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_pemoji('dashboard', '📊')} <b>DATABASE OVERVIEW</b>\n"
        "— — — — — — — — — —\n"
        f"{get_pemoji('user', '👤')} <b>Users</b>          » {users_count}\n"
        f"{get_pemoji('gear', '⚙️')} <b>Panels</b>         » {panels_count}\n"
        f"{get_pemoji('number', '🔢')} <b>Numbers Today</b>  » {numbers_count}\n"
        f"{get_pemoji('phone', '📱')} <b>Active Now</b>     » {active_now}\n"
        f"{get_pemoji('rocket', '🚀')} <b>Total Requests</b> » {total_requested}\n"
        f"{get_pemoji('otp', '🔐')} <b>OTP Success</b>    » {total_otp_success}\n"
        "— — — — — — — — — —\n"
        f"{get_pemoji('done', '✅')} <b>Success Rate</b> » <b>{success_rate}%</b>\n"
        f"{bar}\n"
        f"{status_line}\n"
    )

    inline_keyboard = [
        [
            {"text": " Broadcast", "callback_data": "adm_broadcast", "style": "primary", "icon_custom_emoji_id": "5789428375261023681"},
            {"text": " Force Join", "callback_data": "adm_fj_menu", "style": "primary", "icon_custom_emoji_id": "5190447043545438788"}
        ],
        [{"text": " User Management", "callback_data": "adm_user_mgmt_menu", "style": "success", "icon_custom_emoji_id": "5352861489541714456"}],
        [{"text": " Leaderboard", "callback_data": "adm_leaderboard", "style": "success", "icon_custom_emoji_id": "5352838545826420397"}],
        [{"text": " Task", "callback_data": "adm_task_menu", "style": "success", "icon_custom_emoji_id": "6217720070181752854"}],
        [{"text": " Admin Management", "callback_data": "adm_admin_menu", "style": "danger", "icon_custom_emoji_id": "5353032893096567467"}],
        [
            {"text": " System", "callback_data": "adm_system_menu", "style": "primary", "icon_custom_emoji_id": "5420155432272438703"},
            {"text": " Manage Redox", "callback_data": "adm_redox_menu", "style": "success", "icon_custom_emoji_id": "5352838545826420397"}
        ],
        [{"text": " Developer Info", "callback_data": "adm_developer", "style": "primary", "icon_custom_emoji_id": "5353032893096567467"}],
        [{"text": " Back to Home", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    
    keyboard = {"inline_keyboard": inline_keyboard}
    if message_id:
        edit_bot_message(chat_id, message_id, text, keyboard)
    else:
        send_bot_message(chat_id, text, keyboard)

def render_admin_leaderboard(chat_id, message_id):
    if str(chat_id) not in admin_db.get("admins", [OWNER_ID]):
        send_bot_message(chat_id, "❌ You are not authorized to view the Leaderboard.")
        return

    user_stats = admin_db.get("user_stats", {})
    # Sort users by otp_count descending, keep only those with at least 1 OTP
    ranked = sorted(
        ((uid, stats.get("otp_count", 0)) for uid, stats in user_stats.items() if stats.get("otp_count", 0) > 0),
        key=lambda x: x[1],
        reverse=True
    )[:20]  # Top 20

    medal = {
        1: "<tg-emoji emoji-id='5201731915496845849'>🥇</tg-emoji>",
        2: "<tg-emoji emoji-id='6206222099132978580'>🥈</tg-emoji>",
        3: "<tg-emoji emoji-id='6339226365727874326'>🥉</tg-emoji>",
    }
    lines = []
    for rank, (uid, otp_count) in enumerate(ranked, start=1):
        icon = medal.get(rank, f"{rank}.")
        lines.append(f"{icon} <code>{uid}</code> » <b>{otp_count}</b> OTP")

    body = "\n".join(lines) if lines else "<i>এখনো কোনো ইউজার OTP সংগ্রহ করেনি।</i>"

    text = (
        f"{get_pemoji('gem', '🏆')} <b>OTP LEADERBOARD (TOP 20)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{body}"
    )

    inline_keyboard = [
        [{"text": " Refresh", "callback_data": "adm_leaderboard", "style": "success", "icon_custom_emoji_id": "5465368548702446780"}],
        [{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_developer(chat_id, message_id):
    text = (
        "╔═══════════╗\n"
        f"      {get_pemoji('redox', '😒')} <b>DEVELOPER</b> {get_pemoji('redox', '😒')}\n"
        "╚═══════════╝\n"
        f"{get_pemoji('user', '👤')} ➤ 𝐍𝐚𝐦𝐞 : <a href='https://t.me/SHAFIN_AHMED_1'>REDOX </a> {get_pemoji('done', '✅')}\n\n"
        f"{get_pemoji('user', '👤')} ➤ 𝐍𝐢𝐜𝐤𝐍𝐚𝐦𝐞 : REDOX\n\n"
        "📍 ➤ 𝐂𝐨𝐮𝐧𝐭𝐫𝐲 : Bangladesh\n\n"
        f"{get_pemoji('world', '🌐')} ➤ 𝐑𝐞𝐥𝐢𝐠𝐢𝐨𝐧 : Islam\n\n"
        "🔹 ➤ 𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞 : বাংলা | English | Hindi\n\n"
        f"{get_pemoji('gem', '💎')} ➤ 𝐒𝐤𝐢𝐥𝐥 : Technology • Coding\n\n"
        f"{get_pemoji('fire', '🔥')} ➤ 𝐇𝐨𝐛𝐛𝐢𝐞𝐬 : Music • Anime"
    )
    
    inline_keyboard = [
        [{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def check_force_join(chat_id, message_id=None):
    if str(chat_id) in admin_db.get("admins", [OWNER_ID]) or not admin_db.get("force_join_status", False):
        return True
        
    channels = admin_db.get("force_join_channels", [])
    if not channels:
        return True
        
    not_joined = []
    for ch in channels:
        raw = ch.get("id") if isinstance(ch, dict) else ch
        check_id = raw
        if isinstance(raw, str) and "t.me/joinchat/" in raw or (isinstance(raw, str) and "t.me/+" in raw):
            # Private invite links can't be resolved to a chat_id by username lookup.
            # If the admin also stored a resolved numeric chat_id (via forwarding), use it.
            resolved = ch.get("chat_id") if isinstance(ch, dict) else None
            if resolved:
                check_id = resolved
            else:
                # Can't verify membership for a bare invite link — skip blocking on this one
                # instead of falsely rejecting real members due to a resolution failure.
                continue
        elif isinstance(raw, str) and "t.me/" in raw:
            check_id = "@" + raw.split("t.me/")[1].split("/")[0]
        elif isinstance(raw, str) and raw.lstrip("-").isdigit():
            check_id = raw  # numeric chat_id, use as-is (no "@" prefix)

        res = call_telegram("getChatMember", {"chat_id": check_id, "user_id": chat_id})
        if res and res.get("ok"):
            status = res.get("result", {}).get("status")
            if status in ["left", "kicked"]:
                not_joined.append(ch)
            # "restricted" removed from block-list: a restricted member is still a member
            # (Telegram marks users "restricted" for limited permissions, not for pending join requests)
        else:
            # API call failed (bad id/username, bot not admin, etc.) — log it but don't
            # falsely block a real member because of a configuration/resolution issue.
            logger.warning(f"check_force_join: could not verify membership for channel={raw} user={chat_id}: {res}")
            
    if not_joined:
        inline_keyboard = []
        for idx, ch in enumerate(not_joined, start=1):
            ch_disp = ch.get("id") if isinstance(ch, dict) else ch
            url = ch_disp if ch_disp.startswith("http") else f"https://t.me/{ch_disp.replace('@', '')}"
            # Join channel buttons with premium 📢 icon — channel name/link hidden from label
            label = " Join Channel" if len(not_joined) == 1 else f" Join Channel {idx}"
            inline_keyboard.append([{"text": label, "url": url, "style": "primary", "icon_custom_emoji_id": "5789428375261023681"}])
        
        # Check again button with premium 🔄 icon
        inline_keyboard.append([{"text": " Check Again", "callback_data": "check_fj", "style": "success", "icon_custom_emoji_id": "5465368548702446780"}])
        
        text = (
            "╔═══════════════╗\n"
            "   <tg-emoji emoji-id='5190447043545438788'>🛡</tg-emoji> <b>ACCESS RESTRICTED</b>\n"
            "╚═══════════════╝\n\n"
            "Hello! To use our bot services, you must join our official channels listed below.\n\n"
            "<i>After joining, click the 'Check Again' button to verify.</i>"
        )
        
        if message_id:
            edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
        else:
            send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard})
        return False
    return True

def handle_join_request(join_request):
    """
    Fires when a user sends a 'Request to Join' to a group/channel that requires
    admin approval. If that chat is one of our force-join channels, auto-approve
    it immediately so the user doesn't get stuck being blocked by check_force_join.
    """
    try:
        chat = join_request.get("chat", {})
        user = join_request.get("from", {})
        chat_id = chat.get("id")
        chat_username = chat.get("username")
        user_id = user.get("id")
        if not chat_id or not user_id:
            return

        channels = admin_db.get("force_join_channels", [])
        matched = False
        for ch in channels:
            raw = ch.get("id") if isinstance(ch, dict) else ch
            if not isinstance(raw, str):
                continue
            raw_clean = raw.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").strip("/")
            if chat_username and raw_clean.lower() == str(chat_username).lower():
                matched = True
                break
            if raw.lstrip("-").isdigit() and str(raw) == str(chat_id):
                matched = True
                break

        if matched:
            res = call_telegram("approveChatJoinRequest", {"chat_id": chat_id, "user_id": user_id})
            if res and res.get("ok"):
                logger.info(f"Auto-approved join request: user={user_id} chat={chat_id}")
            else:
                logger.warning(f"Failed to auto-approve join request: user={user_id} chat={chat_id} res={res}")
    except Exception as e:
        logger.error(f"handle_join_request error: {e}")

def render_force_join_menu(chat_id, message_id):
    status = admin_db.get("force_join_status", False)
    # Status label and style
    status_label = " ACTIVE: ON" if status else " ACTIVE: OFF"
    status_style = "success" if status else "danger"
    # ✅ if ON, ❌ if OFF
    status_emoji_id = "5352694861990501856" if status else "5420130255174145507"
    
    inline_keyboard = [
        [{"text": status_label, "callback_data": "adm_fj_toggle", "style": status_style, "icon_custom_emoji_id": status_emoji_id}]
    ]
    
    channels = admin_db.get("force_join_channels", [])
    if channels:
        for idx, ch in enumerate(channels):
            if isinstance(ch, dict):
                ch_disp = ch.get("title") or ch.get("id")
                verified_mark = " ✔" if ch.get("chat_id") else " (unverified)"
            else:
                ch_disp = ch
                is_priv = ("t.me/+" in ch) or ("t.me/joinchat/" in ch)
                verified_mark = " (unverified)" if is_priv else ""
            # Channel list with 🗑 icon and Danger style
            inline_keyboard.append([{"text": f" Remove: {ch_disp}{verified_mark}", "callback_data": f"adm_fj_del:{idx}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
    
    # Add Channel button with ➕ icon
    inline_keyboard.append([{"text": " Add New Channel", "callback_data": "adm_fj_add", "style": "primary", "icon_custom_emoji_id": "5420323438508155202"}])
    # Back button with ⬅️ icon
    inline_keyboard.append([{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    
    text = (
        f"<tg-emoji emoji-id='5420517437885943844'>🔗</tg-emoji> <b>FORCE JOIN MANAGEMENT</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Configure the channels users must join before using the bot.\n"
        "<i>Click the toggle to enable/disable the system.</i>"
    )
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_user_mgmt_menu(chat_id, message_id):
    text = (
        f"<tg-emoji emoji-id='5352861489541714456'>👤</tg-emoji> <b>USER MANAGEMENT</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Search for users to view profiles, manage their balances, or restrict their access."
    )
    inline_keyboard = [
        [{"text": " User Profile", "callback_data": "adm_um_prof", "style": "primary", "icon_custom_emoji_id": "5463352748751753567"}],
        [
            {"text": " Manage Balance", "callback_data": "adm_um_bal", "style": "success", "icon_custom_emoji_id": "5352838545826420397"},
            {"text": " Ban / Unban", "callback_data": "adm_um_ban", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}
        ],
        [{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_um_profile(chat_id, message_id, target_uid):
    stats = admin_db.get("user_stats", {}).get(str(target_uid), {"otp_count": 0, "balance": 0.0})
    is_banned = str(target_uid) in admin_db.get("banned_users", [])
    status_text = "Banned 🚫" if is_banned else "Active ✅"
    
    text = (
        f"╔═══════════════╗\n"
        f"║ <tg-emoji emoji-id='5352861489541714456'>👤</tg-emoji> <b>USER PROFILE</b>\n"
        f"╚═══════════════╝\n\n"
        f"<b>User ID:</b> <code>{target_uid}</code>\n"
        f"<b>Status:</b> <b>{status_text}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id='5352838545826420397'>💎</tg-emoji> <b>Balance:</b> <code>{stats.get('balance', 0.0)} ৳</code>\n"
        f"<tg-emoji emoji-id='5352694861990501856'>✅</tg-emoji> <b>Total OTPs:</b> <code>{stats.get('otp_count', 0)}</code>\n"
    )
    inline_keyboard = [
        [{"text": " Manage Balance", "callback_data": f"adm_um_view_bal:{target_uid}", "style": "success", "icon_custom_emoji_id": "5352838545826420397"}],
        [{"text": " Ban / Unban", "callback_data": f"adm_um_view_ban:{target_uid}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}],
        [{"text": " Back to Menu", "callback_data": "adm_user_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    if message_id: edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
    else: send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard})

def render_um_balance(chat_id, message_id, target_uid):
    stats = admin_db.get("user_stats", {}).get(str(target_uid), {"otp_count": 0, "balance": 0.0})
    text = (
        f"<tg-emoji emoji-id='5352838545826420397'>💎</tg-emoji> <b>MANAGE BALANCE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>User ID:</b> <code>{target_uid}</code>\n"
        f"<b>Current Balance:</b> <code>{stats.get('balance', 0.0)} ৳</code>\n\n"
        f"<i>Choose an action below to add or deduct balance.</i>"
    )
    inline_keyboard = [
        [
            {"text": " Add Balance", "callback_data": f"adm_bal_add:{target_uid}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"},
            {"text": " Deduct Balance", "callback_data": f"adm_bal_sub:{target_uid}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}
        ],
        [{"text": " Back to Profile", "callback_data": f"adm_um_view_prof:{target_uid}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    if message_id: edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
    else: send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard})

def render_um_ban(chat_id, message_id, target_uid):
    is_banned = str(target_uid) in admin_db.get("banned_users", [])
    status_text = f"BANNED {get_pemoji('error', '🚫')}" if is_banned else f"ACTIVE {get_pemoji('done', '✅')}"
    
    text = (
        f"<tg-emoji emoji-id='5422557736330106570'>🚫</tg-emoji> <b>BAN / UNBAN USER</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>User ID:</b> <code>{target_uid}</code>\n"
        f"<b>Current Status:</b> <b>{status_text}</b>\n\n"
        f"<i>Banned users cannot use any bot commands or features.</i>"
    )
    
    btn_text = " Unban User" if is_banned else " Ban User"
    btn_icon = "5352694861990501856" if is_banned else "5420130255174145507"
    btn_style = "success" if is_banned else "danger"
    
    inline_keyboard = [
        [{"text": btn_text, "callback_data": f"adm_ban_tog:{target_uid}", "style": btn_style, "icon_custom_emoji_id": btn_icon}],
        [{"text": " Back to Profile", "callback_data": f"adm_um_view_prof:{target_uid}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    if message_id: edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
    else: send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_management_menu(chat_id, message_id):
    admins = admin_db.get("admins", [OWNER_ID])
    inline_keyboard = []
    
    for adm in admins:
        if adm == OWNER_ID:
            inline_keyboard.append([{"text": f" Owner: {adm}", "callback_data": "none", "style": "primary", "icon_custom_emoji_id": "5353032893096567467"}])
        else:
            inline_keyboard.append([{"text": f" Delete: {adm}", "callback_data": f"adm_admin_del:{adm}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
    
    inline_keyboard.append([{"text": " Add Admin", "callback_data": "adm_admin_add", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    
    text = f"{get_pemoji('user', '👤')} <b>ADMIN MANAGEMENT</b>\n━━━━━━━━━━━━━━━━━━\nManage your bot admins below:"
    if message_id:
        edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
    else:
        send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_system_menu(chat_id, message_id):
    text = (
        f"<tg-emoji emoji-id='5420155432272438703'>⚙️</tg-emoji> <b>SYSTEM CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option to manage the core systems:"
    )
    inline_keyboard = [
        [
            {"text": " Panel Management", "callback_data": "adm_panel_mgmt_menu", "style": "primary", "icon_custom_emoji_id": "5420155432272438703"}
        ],
        [{"text": " Manage Otp Group", "callback_data": "adm_otp_grp_menu", "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}],
        [{"text": " Number Stats & Health", "callback_data": "adm_analytics_menu", "style": "success", "icon_custom_emoji_id": "5352877703043258544"}],
        [{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_otp_grp_menu(chat_id, message_id):
    link = admin_db.get("otp_group_link", "")
    fwd_groups = admin_db.get("forward_groups", [])
    cfg = admin_db.get("redox_config", {})
    stats_on = cfg.get("stats_auto_post", False)
    interval_min = int(cfg.get("stats_interval_min", 60) or 60)
    today_otp = admin_db.get("today_otp_success", 0)
    
    text = f"{get_pemoji('gear', '⚙️')} <b>OTP GROUP MANAGEMENT</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    text += f"<b>User Button Link:</b>\n<code>{escape_html(link) if link else 'Not Set'}</code>\n\n"
    text += f"<b>Forward Groups ({len(fwd_groups)}):</b>\n"
    text += "— — — — — — — — — —\n"
    text += f"{get_pemoji('dashboard', '📊')} <b>Auto Stats Post</b> » আজকের রিয়েল OTP কাউন্ট ({today_otp}) নির্ধারিত সময় পর পর OTP গ্রুপে অটো-পোস্ট হয়।\n"
    text += f"<b>Interval:</b> প্রতি {interval_min} মিনিটে\n"
    
    inline_keyboard = [
        [{"text": " Edit User Button Link", "callback_data": "adm_otp_edit_link", "style": "primary", "icon_custom_emoji_id": "5395444784611480792"}]
    ]
    
    for idx, grp in enumerate(fwd_groups):
        g_id = grp.get("id")
        btns = len(grp.get("buttons", []))
        inline_keyboard.append([{"text": f" FWD: {g_id} ({btns} Btns)", "callback_data": f"adm_fwd_view:{idx}", "style": "success", "icon_custom_emoji_id": "5789428375261023681"}])
        
    inline_keyboard.append([{"text": " Add Forward Group", "callback_data": "adm_fwd_add", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])

    stats_label = f" Auto Stats Post: ON ({interval_min}m)" if stats_on else " Auto Stats Post: OFF"
    stats_style = "success" if stats_on else "danger"
    stats_emoji_id = "5352694861990501856" if stats_on else "5420130255174145507"
    inline_keyboard.append([{"text": stats_label, "callback_data": "adm_stats_toggle", "style": stats_style, "icon_custom_emoji_id": stats_emoji_id}])
    inline_keyboard.append([{"text": " Change Interval", "callback_data": "adm_stats_interval", "style": "primary", "icon_custom_emoji_id": "5420155432272438703"}])

    inline_keyboard.append([{"text": " Back to System", "callback_data": "adm_system_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_fwd_view(chat_id, message_id, idx):
    fwd_groups = admin_db.get("forward_groups", [])
    if idx >= len(fwd_groups): return
    grp = fwd_groups[idx]
    g_id = grp.get("id")
    btns = grp.get("buttons", [])
    
    text = f"{get_pemoji('gear', '⚙️')} <b>FORWARD GROUP: {g_id}</b>\n━━━━━━━━━━━━━━━━━━\nManage inline buttons for this forward group:\n"
    
    inline_keyboard = []
    for b_idx, btn in enumerate(btns):
        inline_keyboard.append([{"text": f"❌ {btn['text']} - {btn['url'][:15]}...", "callback_data": f"adm_fwd_btn_del:{idx}:{b_idx}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
        
    inline_keyboard.append([{"text": " Add Inline Button", "callback_data": f"adm_fwd_btn_add:{idx}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Remove Forward Group", "callback_data": f"adm_fwd_del:{idx}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_otp_grp_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_firebase_menu(chat_id, message_id):
    status = "✅ Connected" if db_firestore else "❌ Not Connected"
    
    text = (
        f"<tg-emoji emoji-id='5337267511261960341'>🔥</tg-emoji> <b>FIREBASE CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Auto-Sync:</b> Every 5 Minutes 🔄\n\n"
        "<i>Syncs: User Balances, Panels, Services & Config.</i>"
    )
    inline_keyboard = [
        [
            {"text": " Force Sync Database", "callback_data": "adm_fb_sync_users", "style": "success", "icon_custom_emoji_id": "5465368548702446780"}
        ],
        [{"text": " Back to System", "callback_data": "adm_system_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_panel_mgmt_menu(chat_id, message_id):
    text = (
        f"{get_pemoji('gear', '⚙️')} <b>PANEL MANAGEMENT</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Configure your API panels and traffic filters:"
    )
    inline_keyboard = [
        [
            {"text": " Manage Panel", "callback_data": "adm_pnl_home", "style": "primary", "icon_custom_emoji_id": "5366231924597604153"},
            {"text": " Manage Traffic", "callback_data": "adm_trf_home", "style": "success", "icon_custom_emoji_id": "5352877703043258544"}
        ],
        [
            {"text": " Manage Service", "callback_data": "adm_svc_home", "style": "success", "icon_custom_emoji_id": "5366231924597604153"}
        ],
        [{"text": " Back to System", "callback_data": "adm_system_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_analytics_menu(chat_id, message_id):
    """📊 Number Stats + Success Rate — প্রতিটা প্যানেলের রিকোয়েস্ট/সফলতার হিসাব দেখায়।"""
    p_stats = admin_db.get("panel_stats", {})
    text = f"{get_pemoji('dashboard', '📊')} <b>NUMBER STATS & SUCCESS RATE</b>\n━━━━━━━━━━━━━━━━━━\n\n"

    if not panels:
        text += f"{get_pemoji('warn', '⚠️')} কোনো প্যানেল কনফিগার করা নেই।"
    else:
        for p in panels:
            pid = p.get("id")
            s = p_stats.get(pid, {})
            requested = s.get("requested", 0)
            allocated = s.get("allocated", 0)
            failed = s.get("failed", 0)
            otp_ok = s.get("otp_success", 0)
            alloc_rate = (allocated / requested * 100) if requested else 0.0
            otp_rate = (otp_ok / allocated * 100) if allocated else 0.0
            last_status = s.get("last_status")
            status_emoji = get_pemoji('done', '✅') if last_status == "ok" else (get_pemoji('error', '❌') if last_status == "fail" else get_pemoji('wait', '⏳'))

            text += (
                f"{status_emoji} <b>{escape_html(p.get('name', pid))}</b>\n"
                f"{get_pemoji('number', '🔢')} অনুরোধ: <code>{requested}</code>  |  {get_pemoji('phone', '📱')} পেয়েছে: <code>{allocated}</code>  |  {get_pemoji('error', '❌')} ব্যর্থ: <code>{failed}</code>\n"
                f"{get_pemoji('rocket', '🚀')} এলোকেশন সাকসেস: <code>{alloc_rate:.1f}%</code>\n"
                f"{get_pemoji('otp', '🔐')} OTP সাকসেস রেট: <code>{otp_rate:.1f}%</code> ({otp_ok}/{allocated})\n\n"
            )

    inline_keyboard = [
        [{"text": " Run Panel Health Check", "callback_data": "adm_health_check", "style": "success", "icon_custom_emoji_id": "5352694861990501856"}],
        [{"text": " Reset Stats", "callback_data": "adm_stats_reset", "style": "danger", "icon_custom_emoji_id": "5420130255174145507"}],
        [{"text": " Back to System", "callback_data": "adm_system_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def run_panel_health_check():
    """প্রতিটা প্যানেলের বেস URL-এ লাইভ রিকোয়েস্ট পাঠিয়ে দেখে সেটা রেসপন্স করছে কিনা (রিয়েল নাম্বার না কিনেই)।"""
    results = []
    for p in panels:
        p_name = p.get("name", p.get("id"))
        base_url = (p.get("url") or "").split('#')[0].rstrip('/')
        if not base_url:
            results.append({"name": p_name, "ok": False, "detail": "No URL configured", "ms": 0})
            continue
        start = time.time()
        try:
            res = requests.get(base_url, timeout=8)
            elapsed_ms = int((time.time() - start) * 1000)
            ok = res.status_code < 500
            results.append({"name": p_name, "ok": ok, "detail": f"HTTP {res.status_code}", "ms": elapsed_ms})
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            results.append({"name": p_name, "ok": False, "detail": str(e)[:80], "ms": elapsed_ms})
    return results

def render_admin_health_check(chat_id, message_id):
    edit_bot_message(chat_id, message_id, f"{get_pemoji('wait', '⏳')} <i>Checking all panels, please wait...</i>")
    results = run_panel_health_check()
    text = f"{get_pemoji('gear', '⚙️')} <b>PANEL HEALTH CHECK</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if not results:
        text += f"{get_pemoji('warn', '⚠️')} কোনো প্যানেল কনফিগার করা নেই।"
    for r in results:
        emoji = get_pemoji('done', '✅') if r["ok"] else get_pemoji('error', '❌')
        text += f"{emoji} <b>{escape_html(r['name'])}</b> — {escape_html(r['detail'])} ({r['ms']}ms)\n"
    text += f"\n{get_pemoji('time', '🕓')} <i>চেক করা হয়েছে: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    inline_keyboard = [
        [{"text": " Run Again", "callback_data": "adm_health_check", "style": "success", "icon_custom_emoji_id": "5352694861990501856"}],
        [{"text": " Back", "callback_data": "adm_analytics_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_trf_home(chat_id, message_id):
    text = f"{get_pemoji('dashboard', '📊')} <b>TRAFFIC MANAGEMENT</b>\n━━━━━━━━━━━━━━━━━━\nSelect a panel to manage its traffic logging:"
    inline_keyboard = []
    
    for p in panels:
        inline_keyboard.append([{"text": f" {p['name']}", "callback_data": f"adm_trf_pnl:{p['id']}", "style": "primary", "icon_custom_emoji_id": "5352877703043258544"}])
        
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_panel_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_trf_pnl_view(chat_id, message_id, panel_id):
    panel = next((p for p in panels if p["id"] == panel_id), None)
    if not panel: return
    p_name = panel["name"]
    is_active = panel.get("is_traffic_active", True)
    
    status_text = " Traffic Logging: ON" if is_active else " Traffic Logging: OFF"
    status_style = "success" if is_active else "danger"
    status_icon = "5352694861990501856" if is_active else "5420130255174145507"
    
    text = f"{get_pemoji('dashboard', '📊')} <b>TRAFFIC: {p_name}</b>\n━━━━━━━━━━━━━━━━━━\nEnable or disable traffic monitoring for this panel.\n\n<i>If OFF, this panel's logs will not appear in the /traffic menu.</i>"
    inline_keyboard = [
        [{"text": status_text, "callback_data": f"adm_trf_tog_pnl:{panel_id}", "style": status_style, "icon_custom_emoji_id": status_icon}],
        [{"text": " Back to Panels", "callback_data": "adm_trf_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_srch_home(chat_id, message_id):
    text = f"{get_pemoji('search', '🔍')} <b>SEARCH MANAGEMENT</b>\n━━━━━━━━━━━━━━━━━━\nSelect a panel to manage its search routing and allowed country codes:"
    inline_keyboard = []
    for p in panels:
        inline_keyboard.append([{"text": f" {p['name']}", "callback_data": f"adm_srch_pnl:{p['id']}", "style": "primary", "icon_custom_emoji_id": "5463352748751753567"}])
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_panel_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_srch_pnl_view(chat_id, message_id, panel_id):
    panel = next((p for p in panels if p["id"] == panel_id), None)
    if not panel: return
    p_name = panel["name"]
    
    search_cfg = admin_db.setdefault("search_cfg", {})
    p_cfg = search_cfg.setdefault(panel_id, {"is_active": True, "prefixes": []})
    is_active = p_cfg.get("is_active", True)
    prefixes = p_cfg.get("prefixes", [])
    
    status_text = " Search Status: ON" if is_active else " Search Status: OFF"
    status_style = "success" if is_active else "danger"
    status_icon = "5352694861990501856" if is_active else "5420130255174145507"
    
    text = f"{get_pemoji('search', '🔍')} <b>SEARCH ROUTES: {p_name}</b>\n━━━━━━━━━━━━━━━━━━\nManage allowed country codes for this panel. If a user searches for a number outside these codes, it will be blocked.\n"
    inline_keyboard = [
        [{"text": status_text, "callback_data": f"adm_srch_tog:{panel_id}", "style": status_style, "icon_custom_emoji_id": status_icon}]
    ]
    
    for pfx in prefixes:
        inline_keyboard.append([{"text": f"❌ Prefix: +{pfx}", "callback_data": f"adm_srch_del:{panel_id}:{pfx}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
        
    inline_keyboard.append([{"text": " Add Country Code", "callback_data": f"adm_srch_add:{panel_id}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Back to Panels", "callback_data": "adm_srch_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_svc_home(chat_id, message_id):
    text = f"{get_pemoji('gear', '⚙️')} <b>SELECT PANEL</b>\n━━━━━━━━━━━━━━━━━━\nSelect a panel to manage its services:"
    inline_keyboard = []
    
    for p in panels:
        inline_keyboard.append([{"text": f" {p['name']}", "callback_data": f"adm_svc_pnl:{p['id']}", "style": "primary", "icon_custom_emoji_id": "5366231924597604153"}])
        
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_panel_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_svc_pnl_view(chat_id, message_id, panel_id):
    services_dict = load_services()
    p_services = services_dict.get(panel_id, [])
    
    panel = next((p for p in panels if p["id"] == panel_id), None)
    if not panel: return
    p_name = panel["name"]
    is_active = panel.get("is_active", True)
    
    status_text = " Panel Status: ON" if is_active else " Panel Status: OFF"
    status_style = "success" if is_active else "danger"
    status_icon = "5352694861990501856" if is_active else "5420130255174145507"
    
    text = f"{get_pemoji('gear', '⚙️')} <b>SERVICES: {p_name}</b>\n━━━━━━━━━━━━━━━━━━\nManage services for this panel:"
    inline_keyboard = [
        [{"text": status_text, "callback_data": f"adm_svc_tog_pnl:{panel_id}", "style": status_style, "icon_custom_emoji_id": status_icon}]
    ]
    
    for s in p_services:
        em_id = get_app_raw_id(s['name'])
        inline_keyboard.append([{"text": f" {s['name']} ({len(s.get('countries', []))} Countries)", "callback_data": f"adm_svc_view:{panel_id}:{s['id']}", "style": "primary", "icon_custom_emoji_id": em_id}])
        
    inline_keyboard.append([{"text": " Add New Service", "callback_data": f"adm_svc_add:{panel_id}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Back to Panels", "callback_data": "adm_svc_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_admin_svc_view(chat_id, message_id, panel_id, service_id):
    services_dict = load_services()
    p_services = services_dict.get(panel_id, [])
    service = next((s for s in p_services if s["id"] == service_id), None)
    if not service: return
    
    text = f"{get_pemoji('gear', '⚙️')} <b>SERVICE: {service['name'].upper()}</b>\n━━━━━━━━━━━━━━━━━━\nSelect a country to manage ranges:"
    inline_keyboard = []
    
    for c in service.get("countries", []):
        c_info = get_country_info(c['code'])
        name = c.get("name") or c_info["name"]
        em_id = c_info.get("id", "5336972142066047577")
        inline_keyboard.append([{"text": f" {name} ({c['code']}) - {len(c.get('ranges', []))} Ranges", "callback_data": f"adm_svc_ctr:{panel_id}:{service_id}:{c['code']}", "style": "primary", "icon_custom_emoji_id": em_id}])
        
    inline_keyboard.append([{"text": " Add Country", "callback_data": f"adm_svc_add_ctr:{panel_id}:{service_id}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Delete Service", "callback_data": f"adm_svc_del:{panel_id}:{service_id}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
    inline_keyboard.append([{"text": " Back", "callback_data": f"adm_svc_pnl:{panel_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def add_country_to_service(panel_id, service_id, c_code):
    """সার্ভিসে দেশ যোগ করার আসল কাজ। ফেরত দেয় (success: bool, message_text: str)।"""
    services_dict = load_services()
    p_services = services_dict.get(panel_id, [])
    c_info = get_country_info(c_code)
    c_name = c_info.get("name", c_code)

    for s in p_services:
        if s['id'] == service_id:
            if not any(c['code'] == c_code for c in s.get('countries', [])):
                s.setdefault('countries', []).append({"code": c_code, "ranges": []})
                save_services(services_dict)
                return True, f"{get_pemoji('done', '✅')} Country <b>{c_name} ({c_code})</b> added to {s['name']}!"
            else:
                return False, f"{get_pemoji('error', '❌')} Country already added!"
    return False, f"{get_pemoji('error', '❌')} Error processing country."

def render_country_picker(chat_id, message_id, panel_id, service_id, page=0, query=None):
    """🔍 Search + Pagination দিয়ে দেশ বাছাই করার UI — কোনো Short Code মুখস্থ রাখা লাগবে না।"""
    all_countries = sorted(RAW_FLAG_EMOJIS.items(), key=lambda kv: kv[1]["name"])

    if query:
        q = query.strip().lower()
        matches = [(code, info) for code, info in all_countries if q in info["name"].lower() or q == code.lower()]
    else:
        matches = all_countries

    PER_PAGE = 10
    total_pages = max(1, (len(matches) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    page_items = matches[page * PER_PAGE: (page + 1) * PER_PAGE]

    header = f"{get_pemoji('world', '🌐')} <b>ADD COUNTRY</b>\n━━━━━━━━━━━━━━━━━━\n"
    if query:
        header += f"🔍{{5463352748751753567}} Search: <b>{escape_html(query)}</b> ({len(matches)} found)\n\n"
    else:
        header += f"নিচে থেকে দেশ বেছে নিন, অথবা 🔍{{5463352748751753567}} Search চেপে নাম লিখে খুঁজুন:\n\n"
    header += f"Page {page + 1}/{total_pages}"

    if not page_items:
        header += f"\n\n<i>কোনো দেশ পাওয়া যায়নি। অন্য নাম দিয়ে চেষ্টা করুন।</i>"

    inline_keyboard = []
    row = []
    for code, info in page_items:
        btn_text = f" {info['name']}"
        row.append({"text": btn_text, "callback_data": f"adm_ctr_pick:{panel_id}:{service_id}:{code}", "style": "primary", "icon_custom_emoji_id": info.get("id", "5336972142066047577")})
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)

    search_row = [{"text": " Search", "callback_data": f"adm_ctr_search:{panel_id}:{service_id}", "style": "success", "icon_custom_emoji_id": "5463352748751753567"}]
    if query:
        search_row.append({"text": " Clear Search", "callback_data": f"adm_ctr_clear:{panel_id}:{service_id}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"})
    inline_keyboard.append(search_row)

    nav_row = []
    if page > 0:
        nav_row.append({"text": " Prev", "callback_data": f"adm_ctr_pg:{panel_id}:{service_id}:{page - 1}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"})
    if page < total_pages - 1:
        nav_row.append({"text": "Next ", "callback_data": f"adm_ctr_pg:{panel_id}:{service_id}:{page + 1}", "style": "primary", "icon_custom_emoji_id": "5201738280638381060"})
    if nav_row:
        inline_keyboard.append(nav_row)

    inline_keyboard.append([{"text": " Back", "callback_data": f"adm_svc_view:{panel_id}:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, header, {"inline_keyboard": inline_keyboard})

def render_admin_svc_ctr_view(chat_id, message_id, panel_id, service_id, country_code):
    services_dict = load_services()
    p_services = services_dict.get(panel_id, [])
    service = next((s for s in p_services if s["id"] == service_id), None)
    if not service: return
    country = next((c for c in service.get("countries", []) if c["code"] == country_code), None)
    if not country: return
    
    c_info = get_country_info(country_code)
    text = f"{get_pemoji('gear', '⚙️')} <b>RANGES: {c_info.get('name', country_code)} ({service['name']})</b>\n━━━━━━━━━━━━━━━━━━\n"
    
    ranges = country.get("ranges", [])
    if not ranges: text += "<i>No ranges added yet.</i>\n"
    for idx, r in enumerate(ranges):
        text += f"{idx+1}. <code>{r}</code>\n"
        
    inline_keyboard = [
        [{"text": " Add Range", "callback_data": f"adm_svc_add_rg:{panel_id}:{service_id}:{country_code}", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}],
        [{"text": " Clear All Ranges", "callback_data": f"adm_svc_clr_rg:{panel_id}:{service_id}:{country_code}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}],
        [{"text": " Remove Country", "callback_data": f"adm_svc_del_ctr:{panel_id}:{service_id}:{country_code}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}],
        [{"text": " Back", "callback_data": f"adm_svc_view:{panel_id}:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_panel_list(chat_id, message_id):
    text = (
        f"{get_pemoji('gear', '⚙️')} <b>PANEL SELECTION</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Select a panel to configure its API/Login settings:"
    )
    
    # আলাদা আলাদা প্যানেলের জন্য আলাদা আলাদা প্রিমিয়াম ইমোজি আইডি
    panel_emojis = {
        "stexsms": "5336972142066047577", # Chrome
        "xmint": "5336879280578138635",   # Gem
        "mk": "5352552689983067014",      # Proton VPN
        "nexa": "5352838545826420397"     # Express VPN
    }
    
    inline_keyboard = []
    row = []
    for idx, p in enumerate(panels):
        btn_text = f" {p['name']}"
        emoji_id = panel_emojis.get(p.get('id', 'stexsms'), "5366231924597604153") # Default
        
        row.append({"text": btn_text, "callback_data": f"adm_pnl_view:{idx}", "style": "primary", "icon_custom_emoji_id": emoji_id})
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
        
    inline_keyboard.append([{"text": " Add New Panel", "callback_data": "adm_pnl_add", "style": "success", "icon_custom_emoji_id": "5420323438508155202"}])
    inline_keyboard.append([{"text": " Back", "callback_data": "adm_panel_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def prompt_for_get_message(chat_id, prompt_id, tmp):
    base_url = tmp.get("url", "")
    default_gm = f"{base_url}/success-otp"
    user_conversations[chat_id] = f"add_pnl_gm:{tmp.get('type', 'stex')}"
    user_prompts[chat_id] = prompt_id
    edit_bot_message(chat_id, prompt_id,
        f"{get_pemoji('note', '📝')} <b>Panel: {escape_html(tmp.get('name', ''))}</b>\n\n"
        f"এখন <b>Get Message API URL</b> দিন:\n"
        f"(ডিফল্ট: <code>{escape_html(default_gm)}</code>)",
        {"inline_keyboard": [
            [{"text": " Use Default", "callback_data": "adm_pnl_default:gm", "style": "success", "icon_custom_emoji_id": "5366231924597604153"}],
            [{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
        ]})

def prompt_for_traffic(chat_id, prompt_id, tmp):
    base_url = tmp.get("url", "")
    default_tr = f"{base_url}/console"
    user_conversations[chat_id] = f"add_pnl_tr:{tmp.get('type', 'stex')}"
    user_prompts[chat_id] = prompt_id
    edit_bot_message(chat_id, prompt_id,
        f"{get_pemoji('note', '📝')} <b>Panel: {escape_html(tmp.get('name', ''))}</b>\n\n"
        f"এখন <b>Traffic API URL</b> দিন:\n"
        f"(ডিফল্ট: <code>{escape_html(default_tr)}</code>)",
        {"inline_keyboard": [
            [{"text": " Use Default", "callback_data": "adm_pnl_default:tr", "style": "success", "icon_custom_emoji_id": "5366231924597604153"}],
            [{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
        ]})

def finalize_panel_creation(chat_id, prompt_id):
    tmp = panel_creation_temp.pop(chat_id, {})
    user_conversations.pop(chat_id, None)
    user_prompts.pop(chat_id, None)
    ptype = tmp.get("type", "stex")
    pname = tmp.get("name", "New Panel")
    base_url = tmp.get("url", "")
    api_token = tmp.get("token", "")
    pnl_id = pname.lower().replace(" ", "_").replace("-", "_")
    existing_ids = [p.get("id", "") for p in panels]
    counter = 1
    orig_id = pnl_id
    while pnl_id in existing_ids:
        pnl_id = f"{orig_id}_{counter}"
        counter += 1

    new_panel = {
        "id": pnl_id,
        "name": pname,
        "panel_type": ptype,
        "url": base_url,
        "username": "API",
        "password": api_token,
        "sessionCookie": api_token if ptype == "stex" else "",
        "status": "Running (API)" if ptype in ("activation", "yesms", "hadi", "shark") else "Initializing...",
        "lastSeenCDRId": None,
        "lastSeenGetnumIds": []
    }
    new_panel["getNumberUrl"] = tmp.get("getNumberUrl") or f"{base_url}/getnum"
    new_panel["getMessageUrl"] = tmp.get("getMessageUrl") or f"{base_url}/success-otp"
    new_panel["trafficUrl"] = tmp.get("trafficUrl") or f"{base_url}/console"
    extra_lines = (
        f"<b>Get Number API:</b> <code>{escape_html(new_panel['getNumberUrl'])}</code>\n"
        f"<b>Get Message API:</b> <code>{escape_html(new_panel['getMessageUrl'])}</code>\n"
        f"<b>Traffic API:</b> <code>{escape_html(new_panel['trafficUrl'])}</code>\n"
    )

    panels.append(new_panel)
    save_panels_to_file(panels)
    new_idx = len(panels) - 1
    kb = {"inline_keyboard": [[{"text": " View Panel", "callback_data": f"adm_pnl_view:{new_idx}", "style": "success", "icon_custom_emoji_id": "5366231924597604153"}]]}
    edit_bot_message(chat_id, prompt_id,
        f"{get_pemoji('done', '✅')} <b>Panel Added!</b>\n\n"
        f"<b>Name:</b> {escape_html(pname)}\n"
        f"<b>Type:</b> {ptype}\n"
        f"<b>URL:</b> <code>{escape_html(base_url)}</code>\n"
        f"<b>Token:</b> <code>{escape_html(api_token)}</code>\n"
        f"{extra_lines}", kb)

def render_add_panel_type_menu(chat_id, message_id):
    text = (
        f"{get_pemoji('gear', '⚙️')} <b>ADD NEW PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "প্যানেলের ধরন সিলেক্ট করুন:\n\n"
        "• <b>YesSMS / Hadi / Shark</b> — Activation API\n"
        "  (yesms.online, hadi panel, shark panel)\n\n"
        "• <b>Stex SMS</b> — Stex-style API\n"
        "  (2oo9.cloud, stex-compatible panels)"
    )
    inline_keyboard = [
        [{"text": " YesSMS / Hadi / Shark", "callback_data": "adm_pnl_type:activation", "style": "primary", "icon_custom_emoji_id": "5336972142066047577"}],
        [{"text": " Stex SMS API", "callback_data": "adm_pnl_type:stex", "style": "primary", "icon_custom_emoji_id": "5366231924597604153"}],
        [{"text": " Back", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_panel_details(chat_id, message_id, p_idx):
    if p_idx >= len(panels):
        edit_bot_message(chat_id, message_id, f"{get_pemoji('error', '❌')} Panel not found.", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return
    panel = panels[p_idx]
    ptype = panel.get("panel_type", "stex")
    
    status = panel.get('status', 'Unknown')
    status_icon = get_pemoji("done", "✅") if "LoggedIn" in status or "API" in status or "Running" in status else get_pemoji("error", "❌")
    
    type_label = {"stex": "Stex SMS API", "activation": "Activation (YesSMS/Hadi/Shark)", "yesms": "YesSMS", "hadi": "Hadi Panel", "shark": "Shark Panel"}.get(ptype, ptype.upper())

    api_key = panel.get('password', '')

    # সব ধরনের প্যানেলের জন্যই একই ৫-ফিল্ড কনফিগারেশন দেখানো হবে
    baseUrl = normalize_base_url(panel.get("url", ""))
    clean_base = baseUrl.split('#')[0].rstrip('/')
    gn_url = panel.get('getNumberUrl') or f"{clean_base}/getnum"
    gm_url = panel.get('getMessageUrl') or f"{clean_base}/success-otp"
    tr_url = panel.get('trafficUrl') or f"{clean_base}/console"
    text = (
        f"<tg-emoji emoji-id='5420155432272438703'>⚙️</tg-emoji> <b>PANEL CONFIGURATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id='5353032893096567467'>👑</tg-emoji> <b>Name:</b> {panel['name']}\n"
        f"<tg-emoji emoji-id='5352838545826420397'>🔖</tg-emoji> <b>Type:</b> <code>{type_label}</code>\n"
        f"<tg-emoji emoji-id='5337267511261960341'>🔥</tg-emoji> <b>Status:</b> <code>{status}</code> {status_icon}\n\n"
        f"<tg-emoji emoji-id='5336972142066047577'>🌐</tg-emoji> <b>1. Base API URL:</b>\n<code>{panel.get('url', '')}</code>\n\n"
        f"<tg-emoji emoji-id='5337255927735163754'>🔐</tg-emoji> <b>2. API Token:</b>\n<code>{api_key}</code>\n\n"
        f"<tg-emoji emoji-id='5352862640592949843'>🔢</tg-emoji> <b>3. Get Number API:</b>\n<code>{gn_url}</code>\n\n"
        f"<tg-emoji emoji-id='5337302974806922068'>💬</tg-emoji> <b>4. Get Message API:</b>\n<code>{gm_url}</code>\n\n"
        f"<tg-emoji emoji-id='5352877703043258544'>📊</tg-emoji> <b>5. Traffic API:</b>\n<code>{tr_url}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id='5192739271886282680'>📝</tg-emoji> <i>Edit configuration:</i>"
    )
    inline_keyboard = [
        [
            {"text": " Edit Base URL", "callback_data": f"adm_pnl_edit:{p_idx}:url", "style": "primary", "icon_custom_emoji_id": "5336972142066047577"},
            {"text": " Edit API Token", "callback_data": f"adm_pnl_edit:{p_idx}:pass", "style": "success", "icon_custom_emoji_id": "5337255927735163754"}
        ],
        [
            {"text": " Edit GetNum URL", "callback_data": f"adm_pnl_edit:{p_idx}:getnum", "style": "primary", "icon_custom_emoji_id": "5337132498965010628"},
            {"text": " Edit GetMsg URL", "callback_data": f"adm_pnl_edit:{p_idx}:getmsg", "style": "primary", "icon_custom_emoji_id": "5395444784611480792"}
        ],
        [{"text": " Edit Traffic URL", "callback_data": f"adm_pnl_edit:{p_idx}:traffic", "style": "primary", "icon_custom_emoji_id": "5352877703043258544"}],
        [{"text": " Delete Panel", "callback_data": f"adm_pnl_del:{panel['id']}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}],
        [{"text": " Back", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def process_task_progress(uid_str, stats):
    """Task চলাকালীন প্রতিটা সফল OTP গণনা করে, শর্ত পূরণ হলে পুরস্কার দেয়।"""
    task = admin_db.get("task", {})
    if not task.get("active"):
        return
    now_ts = time.time()
    if now_ts > task.get("end_ts", 0):
        return  # সময় শেষ, আর প্রগ্রেস গণনা হবে না

    tprog = stats.setdefault("task_progress", {})
    if tprog.get("task_id") != task.get("task_id"):
        tprog.clear()
        tprog["task_id"] = task.get("task_id")
        tprog["count"] = 0
        tprog["claimed"] = False

    if tprog.get("claimed"):
        return

    tprog["count"] = tprog.get("count", 0) + 1
    if tprog["count"] >= task.get("required_otp", 0) and task.get("required_otp", 0) > 0:
        tprog["claimed"] = True
        stats["balance"] = stats.get("balance", 0.0) + float(task.get("price", 0.0))
        try:
            send_bot_message(
                int(uid_str),
                f"{get_pemoji('done', '🎉')} <b>টাস্ক সম্পন্ন হয়েছে!</b>\n\n"
                f"আপনি <b>{tprog['count']}</b>টি OTP সংগ্রহ করে টাস্ক পূরণ করেছেন।\n"
                f"{get_pemoji('gem', '💎')} <b>পুরস্কার:</b> {task.get('price', 0.0)} ৳ যোগ হয়েছে আপনার ব্যালেন্সে!"
            )
        except Exception:
            pass

def render_admin_task_menu(chat_id, message_id):
    task = admin_db.get("task", {})
    now_ts = time.time()
    if task.get("active") and now_ts > task.get("end_ts", 0):
        task["active"] = False
        save_admin_db()

    status = f"{get_pemoji('done', '✅')} <b>সচল (Active)</b>" if task.get("active") else f"{get_pemoji('error', '❌')} <b>বন্ধ (Inactive)</b>"
    remaining_txt = ""
    if task.get("active"):
        remaining_sec = max(0, int(task.get("end_ts", 0) - now_ts))
        hrs, rem = divmod(remaining_sec, 3600)
        mins = rem // 60
        remaining_txt = f"{get_pemoji('wait', '⏳')} <b>বাকি সময়:</b> <code>{hrs}h {mins}m</code>\n"

    text = (
        f"{get_pemoji('task', '🎯')} <b>TASK MANAGEMENT</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>Status:</b> {status}\n"
        f"{get_pemoji('fire', '💰')} <b>Reward Price:</b> <code>{task.get('price', 0.0)} ৳</code>\n"
        f"{get_pemoji('otp', '🔐')} <b>Required OTP:</b> <code>{task.get('required_otp', 0)}</code>\n"
        f"{get_pemoji('time', '🕓')} <b>Duration:</b> <code>{task.get('duration_hours', 0)} hour(s)</code>\n"
        f"{remaining_txt}"
    )

    inline_keyboard = [
        [
            {"text": " Set Price", "callback_data": "adm_task_price", "style": "primary", "icon_custom_emoji_id": "5352838545826420397"},
            {"text": " Set OTP Target", "callback_data": "adm_task_otp", "style": "primary", "icon_custom_emoji_id": "5352862640592949843"}
        ],
        [{"text": " Set Duration (Hours)", "callback_data": "adm_task_dur", "style": "primary", "icon_custom_emoji_id": "5336983442125001376"}],
    ]
    if task.get("active"):
        inline_keyboard.append([{"text": " Stop Task", "callback_data": "adm_task_stop", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}])
    else:
        inline_keyboard.append([{"text": " Start Task", "callback_data": "adm_task_start", "style": "success", "icon_custom_emoji_id": "6217720070181752854"}])
    inline_keyboard.append([{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])

    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_user_task(chat_id, message_id=None):
    task = admin_db.get("task", {})
    now_ts = time.time()
    stats = admin_db.get("user_stats", {}).get(str(chat_id), {})
    tprog = stats.get("task_progress", {})

    if not task.get("active") or now_ts > task.get("end_ts", 0):
        text = f"{get_pemoji('error', '❌')} <b>এই মুহূর্তে কোনো সক্রিয় টাস্ক নেই।</b>\n\nনতুন টাস্ক আসলে এখানে দেখতে পাবেন।"
        kb = {"inline_keyboard": [[{"text": " Back to Home", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
        if message_id: edit_bot_message(chat_id, message_id, text, kb)
        else: send_bot_message(chat_id, text, kb)
        return

    my_count = tprog.get("count", 0) if tprog.get("task_id") == task.get("task_id") else 0
    claimed = tprog.get("claimed", False) if tprog.get("task_id") == task.get("task_id") else False
    required = task.get("required_otp", 0)
    remaining_sec = max(0, int(task.get("end_ts", 0) - now_ts))
    hrs, rem = divmod(remaining_sec, 3600)
    mins = rem // 60

    text = (
        f"{get_pemoji('task', '🎯')} <b>বর্তমান টাস্ক</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{get_pemoji('fire', '💰')} <b>পুরস্কার:</b> <code>{task.get('price', 0.0)} ৳</code>\n"
        f"{get_pemoji('otp', '🔐')} <b>প্রয়োজনীয় OTP:</b> <code>{required}</code>\n"
        f"{get_pemoji('done', '👋')} <b>আপনার সংগ্রহ:</b> <code>{my_count}/{required}</code>\n"
        f"{get_pemoji('wait', '⏳')} <b>বাকি সময়:</b> <code>{hrs}h {mins}m</code>\n"
    )
    if claimed:
        text += f"\n{get_pemoji('done', '✅')} <b>আপনি ইতিমধ্যে পুরস্কার সংগ্রহ করেছেন! অভিনন্দন!</b>"

    kb = {"inline_keyboard": [[{"text": " Back to Home", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
    if message_id: edit_bot_message(chat_id, message_id, text, kb)
    else: send_bot_message(chat_id, text, kb)

def render_admin_redox_menu(chat_id, message_id):
    cfg = admin_db.get("redox_config", {})
    w_grp = cfg.get("withdraw_group", "")
    rew = cfg.get("otp_reward", 0.0)
    m_wd = cfg.get("min_withdraw", 20.0)
    mth = cfg.get("methods", [])
    max_c = cfg.get("max_concurrent", 3)
    cd = cfg.get("cooldown", 0)
    
    sup_lnk = cfg.get("support_link", "")
    text = f"{get_pemoji('gem', '💎')} <b>MANAGE REDOX (Withdrawal System)</b>\n━━━━━━━━━━━━━━━━━━\n"
    text += f"{get_pemoji('dashboard', '📊')} <b>Withdraw Group:</b> <code>{escape_html(w_grp) if w_grp else 'Not Set'}</code>\n"
    text += f"{get_pemoji('fire', '🔥')} <b>OTP Reward:</b> <code>{rew} ৳</code>\n"
    text += f"{get_pemoji('otp', '🔐')} <b>Min Withdraw:</b> <code>{m_wd} ৳</code>\n"
    text += f"{get_pemoji('user', '👤')} <b>Max Numbers/User:</b> <code>{max_c}</code>\n"
    text += f"{get_pemoji('time', '🕓')} <b>Cooldown:</b> <code>{cd} sec</code>\n"
    text += f"{get_pemoji('note', '📝')} <b>Methods ({len(mth)}):</b> {', '.join(mth) if mth else 'None'}\n"
    text += f"{get_pemoji('support', '🫂')} <b>Support Link:</b> <code>{escape_html(sup_lnk) if sup_lnk else 'Not Set'}</code>\n"
    
    inline_keyboard = [
        [{"text": " Set Withdraw Group", "callback_data": "adm_redox_grp", "style": "primary", "icon_custom_emoji_id": "5395444784611480792"}],
        [
            {"text": " OTP Reward", "callback_data": "adm_redox_rew", "style": "primary", "icon_custom_emoji_id": "5352838545826420397"},
            {"text": " Min Withdraw", "callback_data": "adm_redox_min", "style": "primary", "icon_custom_emoji_id": "5352862640592949843"}
        ],
        [
            {"text": " Max Numbers", "callback_data": "adm_redox_maxc", "style": "primary", "icon_custom_emoji_id": "5352861489541714456"},
            {"text": " Cooldown", "callback_data": "adm_redox_cd", "style": "primary", "icon_custom_emoji_id": "5336983442125001376"}
        ],
        [
            {"text": " Add Method", "callback_data": "adm_redox_mth_add", "style": "success", "icon_custom_emoji_id": "5420323438508155202"},
            {"text": " Clear Methods", "callback_data": "adm_redox_mth_clr", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}
        ],
        [{"text": " Refer Bonus", "callback_data": "adm_redox_refb", "style": "success", "icon_custom_emoji_id": "5352585194295564660"}],
        [{"text": " Set Support Link", "callback_data": "adm_redox_supp", "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}],
        [{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
    ]
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def render_user_balance(chat_id, message_id=None):
    stats = admin_db.get("user_stats", {}).get(str(chat_id), {"otp_count": 0, "balance": 0.0})
    cfg = admin_db.get("redox_config", {})
    min_wd = cfg.get("min_withdraw", 20.0)
    methods = cfg.get("methods", [])
    
    text = f"━━━━━━━━━━━━\n"
    text += f"《 {get_pemoji('redox', '😒')} <b>Profile</b> 》\n"
    text += f"━━━━━━━━━━━━\n"
    text += f"{get_pemoji('done', '👋')} <b>Total Otp:</b> {stats.get('otp_count', 0)}\n"
    text += f"━━━━━━━━━━━━\n"
    text += f"{get_pemoji('user', '👤')} <b>User Id:</b> <code>{chat_id}</code>\n"
    text += f"━━━━━━━━━━━━\n"
    text += f"{get_pemoji('gem', '📅')} <b>BALANCE:</b> {stats.get('balance', 0.0)} ৳\n"
    text += f"━━━━━━━━━━━━\n"
    text += f"{get_pemoji('otp', '🔐')} <b>MINIMUM:</b> {min_wd} ৳\n"
    text += f"━━━━━━━━━━━━\n"
    text += f"<b>SELECT METHOD:</b>"
    
    inline_keyboard = []
    row = []
    METHOD_EMOJI = {
        "bkash": "5348469219761626211", "nagad": "5352985330628730418",
        "binance": "5348212415077064131", "bybit": "5348372939479751825"
    }
    for m in methods:
        m_lower = m.lower()
        m_emoji = next((v for k, v in METHOD_EMOJI.items() if k in m_lower), "5352585194295564660")
        row.append({"text": f" {m}", "callback_data": f"usr_wd_{m}", "style": "success", "icon_custom_emoji_id": m_emoji})
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
        
    if message_id:
        edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard} if inline_keyboard else None)
    else:
        send_bot_message(chat_id, text, {"inline_keyboard": inline_keyboard} if inline_keyboard else None)

def get_bot_menu_keyboard(chat_id):
    keyboard = [
        [
            {"text": "GET NUMBER", "style": "primary", "icon_custom_emoji_id": "5352862640592949843"},
            {"text": "Search Number", "style": "primary", "icon_custom_emoji_id": "5463352748751753567"}
        ],
        [
            {"text": "TRAFFIC", "style": "success", "icon_custom_emoji_id": "5352877703043258544"},
            {"text": "2FA ONLINE", "style": "primary", "icon_custom_emoji_id": "5337255927735163754"}
        ],
        [
            {"text": "Refer", "style": "success", "icon_custom_emoji_id": "5420396762189831222"},
            {"text": "WITHDRAWAL", "style": "danger", "icon_custom_emoji_id": "6217469007868465305"}
        ],
        [
            {"text": "TASK", "style": "success", "icon_custom_emoji_id": "6217720070181752854"},
            {"text": "SUPPORT", "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}
        ]
    ]

    if str(chat_id) in admin_db.get("admins", [OWNER_ID]):
        keyboard.append([{"text": "Admin Panel", "style": "danger", "icon_custom_emoji_id": "5267294466716244344"}])

    return {"keyboard": keyboard, "resize_keyboard": True}

# ----------------------------------------------------
# Refer & Earn System
# ----------------------------------------------------

def get_bot_username():
    """বটের username ক্যাশ করে রাখে"""
    if not hasattr(get_bot_username, "_cached"):
        try:
            res = call_telegram("getMe", {})
            if res and res.get("ok"):
                get_bot_username._cached = res["result"].get("username", "")
            else:
                get_bot_username._cached = ""
        except Exception:
            get_bot_username._cached = ""
    return get_bot_username._cached

def render_refer_page(chat_id, message_id=None):
    bot_username = get_bot_username()
    refer_link = f"https://t.me/{bot_username}?start=ref_{chat_id}" if bot_username else f"t.me/YOUR_BOT?start=ref_{chat_id}"

    refer_stats = admin_db.get("refer_stats", {})
    my_stats = refer_stats.get(str(chat_id), {})
    total_referred = my_stats.get("count", 0)
    refer_bonus = admin_db.get("redox_config", {}).get("refer_bonus", 0.0)

    text = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"« {get_pemoji('refer', '🎁')} <b>REFER &amp; EARN</b> »\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{get_pemoji('link', '🔗')} <b>YOUR LINK:</b>\n"
        f"<code>{refer_link}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{get_pemoji('support', '🫂')} <b>TOTAL REFERS:</b> <b>{total_referred}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{get_pemoji('refer', '🎁')} <b>PER REFER:</b> <b>{refer_bonus} TK</b>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    inline_keyboard = [
        [{"text": " COPY LINK", "copy_text": {"text": refer_link}, "style": "success", "icon_custom_emoji_id": "5420517437885943844"}],
        [{"text": " CLOSE", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5420130255174145507"}]
    ]

    keyboard = {"inline_keyboard": inline_keyboard}
    if message_id:
        edit_bot_message(chat_id, message_id, text, keyboard)
    else:
        send_bot_message(chat_id, text, keyboard)

def process_referral(new_user_id, referrer_id, is_new_user=True):
    """নতুন ইউজার রেফার লিংক দিয়ে জয়েন করলে প্রসেস করে"""
    if str(new_user_id) == str(referrer_id):
        return  # নিজেকে রেফার করা যাবে না

    # শুধুমাত্র একদম নতুন ইউজার — যে এর আগে কখনো বট ব্যবহার করেনি
    # (is_new_user ক্যাপচার করা হয় users list-এ যোগ করার আগেই, main handler থেকে)
    if not is_new_user:
        return

    refer_stats = admin_db.setdefault("refer_stats", {})
    new_user_stats = refer_stats.get(str(new_user_id), {})

    # আগে রেফার হয়ে থাকলে আর প্রসেস করবে না
    if new_user_stats.get("referred_by"):
        return

    # নতুন ইউজারের refer_by সেট করা
    refer_stats.setdefault(str(new_user_id), {})["referred_by"] = str(referrer_id)

    # রেফারারের কাউন্ট ও ব্যালেন্স বাড়ানো
    ref_stat = refer_stats.setdefault(str(referrer_id), {"count": 0})
    ref_stat["count"] = ref_stat.get("count", 0) + 1

    refer_bonus = float(admin_db.get("redox_config", {}).get("refer_bonus", 0.0))
    if refer_bonus > 0:
        user_stat = admin_db.setdefault("user_stats", {}).setdefault(str(referrer_id), {"otp_count": 0, "balance": 0.0})
        user_stat["balance"] = user_stat.get("balance", 0.0) + refer_bonus

    save_admin_db()

    # রেফারারকে নোটিফিকেশন পাঠানো
    bot_username = get_bot_username()
    notif_text = (
        f"╔═══════════════╗\n"
        f"║ {get_pemoji('done', '✅')} <b>নতুন রেফার!</b>\n"
        f"╚═══════════════╝\n\n"
        f"{get_pemoji('user', '👤')} আপনার রেফার লিংক দিয়ে একজন নতুন ইউজার যোগ দিয়েছে!\n"
        f"━━━━━━━━━━━━\n"
        f"{get_pemoji('gem', '💎')} <b>বোনাস যোগ হয়েছে:</b> <b>{refer_bonus} ৳</b>\n"
        f"{get_pemoji('fire', '🔥')} <b>মোট রেফার:</b> <b>{ref_stat.get('count', 0)} জন</b>"
    )
    send_bot_message(referrer_id, notif_text)

# ----------------------------------------------------
# Service selections UI layouts
# ----------------------------------------------------

def render_services_list(chat_id, message_id=None):
    services_dict = load_services()
    merged_services = {}
    
    active_panel_ids = [p["id"] for p in panels if p.get("is_active", True)]
    
    for p_id, s_list in services_dict.items():
        if p_id not in active_panel_ids: continue
        for s in s_list:
            if s["id"] not in merged_services:
                merged_services[s["id"]] = {"id": s["id"], "name": s["name"]}
                
    text = f"{get_pemoji('phone', '📱')} <b>Select a service:</b>"
    
    inline_keyboard = []
    if not merged_services:
        inline_keyboard.append([{"text": " No Services Available", "callback_data": "none", "style": "danger", "icon_custom_emoji_id": "5336944168944047463"}])
    else:
        for s_id, s_data in merged_services.items():
            em_id = get_app_raw_id(s_data['name'])
            inline_keyboard.append([{"text": f" {s_data['name']}", "callback_data": f"usr_srv_sel:{s_id}", "style": "primary", "icon_custom_emoji_id": em_id}])

    keyboard = {"inline_keyboard": inline_keyboard}
    if message_id:
        edit_bot_message(chat_id, message_id, text, keyboard)
    else:
        send_bot_message(chat_id, text, keyboard)

def render_countries_list(chat_id, message_id, service_id):
    services_dict = load_services()
    merged_countries = {}
    service_name = "Unknown"
    
    active_panel_ids = [p["id"] for p in panels if p.get("is_active", True)]
    
    for p_id, s_list in services_dict.items():
        if p_id not in active_panel_ids: continue
        for s in s_list:
            if s["id"] == service_id:
                service_name = s["name"]
                for c in s.get("countries", []):
                    if len(c.get("ranges", [])) > 0:
                        merged_countries[c["code"]] = c

    if not merged_countries:
        edit_bot_message(chat_id, message_id, f"{get_pemoji('error', '❌')} No countries are currently configured for <b>{escape_html(service_name)}</b>.", {
            "inline_keyboard": [[{"text": " Back", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]
        })
        return

    text = f"{get_pemoji('phone', '📱')} <b>Select a country for {service_name.upper()}:</b>"
    inline_keyboard = []
    
    for code, c in merged_countries.items():
        c_info = get_country_info(code)
        name = c.get("name") or c_info["name"]
        em_id = c_info.get("id", "5336972142066047577")
        inline_keyboard.append([
            {"text": f" {name} ({code})", "callback_data": f"usr_ctr_sel:{service_id}:{code}", "style": "primary", "icon_custom_emoji_id": em_id}
        ])
        
    inline_keyboard.append([{"text": " Back", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}])
    edit_bot_message(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def allocate_and_show_number_py(chat_id, message_id, service_id, country_code, callback_id=None):
    passed, err_msg, batch_size = check_user_limits(chat_id)
    if not passed:
        if callback_id:
            answer_callback(callback_id, err_msg, show_alert=True)
        else:
            kb = {"inline_keyboard": [[{"text": " Back", "callback_data": f"usr_srv_sel:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
            edit_bot_message(chat_id, message_id, f"⚠️ {err_msg}", kb)
        return

    if callback_id:
        answer_callback(callback_id, "Allocating number...")

    services_dict = load_services()
    available_panels = []
    service_name = "Unknown"
    
    active_panel_ids = [p["id"] for p in panels if p.get("is_active", True)]
    
    for p_id, s_list in services_dict.items():
        if p_id not in active_panel_ids: continue
        for s in s_list:
            if s["id"] == service_id:
                service_name = s["name"]
                for c in s.get("countries", []):
                    if c["code"] == country_code and len(c.get("ranges", [])) > 0:
                        available_panels.append({"panel_id": p_id, "ranges": c["ranges"]})
                        
    if not available_panels:
        edit_bot_message(chat_id, message_id, f"{get_pemoji('error', '❌')} No ranges configured for this selection.", {
            "inline_keyboard": [[{"text": " Back", "callback_data": f"usr_srv_sel:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]
        })
        return

    chosen_setup = random.choice(available_panels)
    panel_id = chosen_setup["panel_id"]
    range_val = random.choice(chosen_setup["ranges"]).strip().upper()
    
    if not any(c in range_val for c in ("X", "x", "*")) and range_val.isdigit():
        range_val += "XXX"
        
    wait_emoji = get_pemoji("wait", "⏳")
    edit_bot_message(chat_id, message_id, f"{wait_emoji} <i>Allocating {batch_size} number(s) for <b>{escape_html(service_name)}</b>... Please wait.</i>")
    
    numbers_fetched = []
    last_err = "Unknown error"
    if "active_numbers" not in admin_db: admin_db["active_numbers"] = {}
    
    for _ in range(batch_size):
        result = buy_number(range_val, panel_id)
        if result.get("success"):
            numbers_fetched.append(result)
            number_val = result.get("number") or ""
            clean_num = str(number_val).replace("+", "").strip()
            admin_db["active_numbers"][clean_num] = str(chat_id)
            if result.get("panel_id"):
                admin_db.setdefault("num_panel_map", {})[clean_num] = result.get("panel_id")
        else:
            last_err = result.get("message", "Failed to retrieve.")
            break
            
    if numbers_fetched:
        save_admin_db()
        blank_text = "ㅤ"
        svc_em_id = get_app_raw_id(service_name)
        
        inline_keyboard = [
            [{"text": f" {service_name}", "callback_data": "none", "style": "success", "icon_custom_emoji_id": svc_em_id}]
        ]
        
        for res in numbers_fetched:
            num = res.get("number", "")
            actual_c_code = get_country_code(num)
            c_info_actual = get_country_info(actual_c_code)
            actual_flag_em_id = c_info_actual.get("id", "5336972142066047577")
            
            inline_keyboard.append([{
                "text": f" +{num.replace('+', '')}",
                "copy_text": {"text": f"{num}"},
                "style": "primary",
                "icon_custom_emoji_id": actual_flag_em_id
            }])
            
        inline_keyboard.extend([
            [
                {"text": " Change Number", "callback_data": f"usr_change_num:{service_id}:{country_code}", "style": "danger", "icon_custom_emoji_id": "5420155432272438703"},
                get_otp_group_btn()
            ],
            [{"text": " Back", "callback_data": f"usr_srv_sel:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
        ])
        edit_bot_message(chat_id, message_id, blank_text, {"inline_keyboard": inline_keyboard})
    else:
        failure_text = f"{get_pemoji('error', '❌')} <b>Get Number Failed!</b>\n\n" \
                       f"<b>Service:</b> {escape_html(service_name)}\n" \
                       f"<b>Country:</b> {escape_html(country_code)}\n" \
                       f"<b>Range tried:</b> <code>{escape_html(range_val)}</code>\n" \
                       f"<b>Error:</b> <code>{escape_html(last_err)}</code>\n\n" \
                       f"<i>Please try again.</i>"
        
        inline_keyboard = [
            [
                {"text": " Retry Allocating", "callback_data": f"usr_change_num:{service_id}:{country_code}", "style": "success", "icon_custom_emoji_id": "5465368548702446780"},
                {"text": " Back to Countries", "callback_data": f"usr_srv_sel:{service_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}
            ]
        ]
        edit_bot_message(chat_id, message_id, failure_text, {"inline_keyboard": inline_keyboard})

# ----------------------------------------------------
# Telegram Bot Inbound Controllers
# ----------------------------------------------------

def handle_callback_query(callback_query):
    callback_id = callback_query.get("id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    data = callback_query.get("data", "")
    
    if not chat_id or not message_id:
        answer_callback(callback_id)
        return

    # 🚫 Check Ban Status
    if str(chat_id) in admin_db.get("banned_users", []):
        answer_callback(callback_id, "🚫 You are banned from using this bot.", show_alert=True)
        return

    # 🛡️ Force Join Check Middleware — user যদি button ক্লিক করার আগে/পরে চ্যানেল থেকে বের হয়ে যায়,
    # তাহলে এখানেও ধরা পড়বে (আগে শুধু টেক্সট মেসেজে চেক হতো, বাটন ক্লিকে হতো না)।
    # "check_fj" বাটন বাদ, কারণ সেটা নিজেই check_force_join কল করে আলাদাভাবে হ্যান্ডল করে।
    if data != "check_fj" and not check_force_join(chat_id, message_id):
        answer_callback(callback_id)
        return

    # 🔄 গ্লোবাল স্টেট রিসেট: যেকোনো ব্যাক বা হোম বাটনে ক্লিক করলে আগের পেন্ডিং ইনপুট মুছে যাবে
    if data in ["usr_menu_home", "adm_main_menu", "adm_admin_menu", "adm_fj_menu", "adm_system_menu", "adm_firebase_menu", "adm_svc_home", "adm_panel_mgmt_menu", "adm_trf_home", "adm_srch_home", "adm_task_menu", "adm_analytics_menu"]:
        user_conversations.pop(chat_id, None)
        
    if data.startswith("adm_svc_view:") or data.startswith("adm_svc_ctr:"):
        user_conversations.pop(chat_id, None)

    logger.info(f"Bot Callback Triggered: data='{data}'")

    if data == "usr_menu_home":
        answer_callback(callback_id)
        render_services_list(chat_id, message_id)
        
    elif data == "usr_search_home":
        user_conversations.pop(chat_id, None) # আগের স্টেট ক্লিয়ার
        answer_callback(callback_id, "Opening Search Menu...")
        user_conversations[chat_id] = "waiting_for_search"
        text_help = (
            "╔═══════════╗\n"
            f"     {get_pemoji('search', '🔍')} <b>SEARCH RANGE</b>\n"
            "╚═══════════╝\n"
            f"{get_pemoji('done', '📌')} Enter 3 to 11 digits  \n"
            "to search for a number.\n"
            "━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id='5395444784611480792'>📝</tg-emoji> Example:\n"
            "➥ 880\n"
            "➥ 9227373\n"
            "━━━━━━━━━━━━━\n"
            f"{get_pemoji('search', '🔍')} Fast Number Lookup System"
        )
        edit_bot_message(chat_id, message_id, text_help, {"inline_keyboard": [[{"text": " Back", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        
    elif data.startswith("usr_srv_sel:"):
        service_id = data.split(":")[1]
        answer_callback(callback_id, "Loading countries...")
        render_countries_list(chat_id, message_id, service_id)
        
    elif data.startswith("usr_ctr_sel:"):
        parts = data.split(":")
        service_id = parts[1]
        country_code = parts[2]
        allocate_and_show_number_py(chat_id, message_id, service_id, country_code, callback_id)
        
    elif data.startswith("usr_change_num:"):
        parts = data.split(":")
        service_id = parts[1]
        country_code = parts[2]
        allocate_and_show_number_py(chat_id, message_id, service_id, country_code, callback_id)
        
    elif data.startswith("buy_"):
        range_val = data.split("_")[1]
        trigger_buy_number(chat_id, range_val, message_id=message_id, callback_id=callback_id)

    elif data == "usr_otp_grp":
        # চ্যাটে মেসেজ পাঠানোর অংশটি ডিলিট করা হয়েছে। এখন লিংক না থাকলে শুধু ছোট্ট পপ-আপ দেখাবে।
        answer_callback(callback_id, "OTP Group link is not set by admin yet!", show_alert=True)

    elif data == "tr_refresh":
         answer_callback(callback_id, "Refreshing traffic dashboard...")
         render_traffic_home(chat_id, message_id)

    elif data == "tr_close":
         answer_callback(callback_id, "Closed")
         call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    elif data == "cancel_2fa":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Canceled")
         call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
         
    elif data.startswith("refresh_2fa:"):
         secret = data.split(":")[1]
         code = get_totp_token(secret)
         if code:
             answer_callback(callback_id, f"Refreshed: {code}")
             msg_text = (
                 f"╔═══════════╗\n"
                 f"     {get_pemoji('otp', '🔐')} <b>2FA CODE GENERATED</b>\n"
                 f"╚═══════════╝\n"
                 f"<b>Secret:</b> <code>{secret}</code>\n"
                 f"━━━━━━━━━━━━━\n"
                 f"{get_pemoji('done', '✅')} <b>Code:</b> <code>{code}</code>\n"
                 f"<i>(This code is valid for 30 seconds)</i>"
             )
             kb = {"inline_keyboard": [
                 [{"text": " Refresh Code", "callback_data": f"refresh_2fa:{secret}", "style": "success", "icon_custom_emoji_id": "5465368548702446780"}],
                 [{"text": " Close", "callback_data": "cancel_2fa", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
             ]}
             edit_bot_message(chat_id, message_id, msg_text, kb)
         else:
             answer_callback(callback_id, "Error generating code", show_alert=True)

    elif data == "adm_coming_soon":
         answer_callback(callback_id, "🚧 This feature is coming soon!")

    elif data == "adm_user_mgmt_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Opening User Management...")
         render_admin_user_mgmt_menu(chat_id, message_id)

    elif data in ["adm_um_prof", "adm_um_bal", "adm_um_ban"]:
         action_map = {"adm_um_prof": "Profile", "adm_um_bal": "Balance", "adm_um_ban": "Ban/Unban"}
         action_type = data.split("_")[2]
         answer_callback(callback_id, "Send User ID...")
         user_conversations[chat_id] = f"um_wait_id_{action_type}"
         user_prompts[chat_id] = message_id
         text = f"<tg-emoji emoji-id='5463352748751753567'>🔍</tg-emoji> <b>Search User for {action_map[data]}</b>\n\nPlease send the Telegram User ID (e.g., <code>123456789</code>)."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_user_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_um_view_prof:"):
         target_uid = data.split(":")[1]
         answer_callback(callback_id)
         render_um_profile(chat_id, message_id, target_uid)

    elif data.startswith("adm_um_view_bal:"):
         target_uid = data.split(":")[1]
         answer_callback(callback_id)
         render_um_balance(chat_id, message_id, target_uid)

    elif data.startswith("adm_um_view_ban:"):
         target_uid = data.split(":")[1]
         answer_callback(callback_id)
         render_um_ban(chat_id, message_id, target_uid)

    elif data.startswith("adm_bal_add:"):
         target_uid = data.split(":")[1]
         answer_callback(callback_id, "Send Amount...")
         user_conversations[chat_id] = f"um_wait_amt_add_{target_uid}"
         user_prompts[chat_id] = message_id
         text = f"<tg-emoji emoji-id='5420323438508155202'>➕</tg-emoji> <b>Add Balance</b>\n\nUser ID: <code>{target_uid}</code>\nSend the amount to add (e.g., <code>50</code>):"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_um_view_bal:{target_uid}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_bal_sub:"):
         target_uid = data.split(":")[1]
         answer_callback(callback_id, "Send Amount...")
         user_conversations[chat_id] = f"um_wait_amt_sub_{target_uid}"
         user_prompts[chat_id] = message_id
         text = f"<tg-emoji emoji-id='5422557736330106570'>➖</tg-emoji> <b>Deduct Balance</b>\n\nUser ID: <code>{target_uid}</code>\nSend the amount to deduct (e.g., <code>50</code>):"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_um_view_bal:{target_uid}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_ban_tog:"):
         target_uid = data.split(":")[1]
         banned_list = admin_db.setdefault("banned_users", [])
         if target_uid in banned_list:
             banned_list.remove(target_uid)
             answer_callback(callback_id, "User Unbanned!")
         else:
             banned_list.append(target_uid)
             answer_callback(callback_id, "User Banned!")
         save_admin_db()
         render_um_ban(chat_id, message_id, target_uid)

    elif data == "check_fj":
         answer_callback(callback_id, "Checking Force Join...")
         if check_force_join(chat_id, message_id):
             # ✅ "Check Again" চেপে জয়েন কনফার্ম হলে জমা রাখা রেফারেল (যদি থাকে) এখন প্রসেস করো
             ref_id = pending_referrals.pop(chat_id, None)
             if ref_id:
                 threading.Thread(target=process_referral, args=(chat_id, ref_id, True), daemon=True).start()
             call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
             send_bot_message(chat_id, "✅ <b>Verification Successful!</b>\nWelcome to REDOX Bot.", get_bot_menu_keyboard(chat_id))

    elif data == "adm_fj_menu":
         user_conversations.pop(chat_id, None) # 🛠️ চ্যানেল লিংক দেওয়ার স্টেট ক্লিয়ার করা হলো
         answer_callback(callback_id, "Opening Force Join Menu...")
         render_force_join_menu(chat_id, message_id)

    elif data == "adm_fj_toggle":
         answer_callback(callback_id, "Toggling status...")
         admin_db["force_join_status"] = not admin_db.get("force_join_status", False)
         save_admin_db()
         render_force_join_menu(chat_id, message_id)

    elif data.startswith("adm_fj_del:"):
         idx = int(data.split(":")[1])
         answer_callback(callback_id, "Deleting channel...")
         channels = admin_db.get("force_join_channels", [])
         if 0 <= idx < len(channels):
             channels.pop(idx)
             save_admin_db()
             threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
         render_force_join_menu(chat_id, message_id)

    elif data == "adm_fj_add":
         answer_callback(callback_id, "Send Channel Link...")
         user_conversations[chat_id] = "waiting_fj_channel"
         text = "🔗 <b>Add Force Join Channel</b>\n\nPlease send the channel username (e.g., <code>@redox_admin</code>) or an invite link."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_fj_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_admin_menu":
         user_conversations.pop(chat_id, None) # 🛠️ আইডি দেওয়ার স্টেট ক্লিয়ার করা হলো
         answer_callback(callback_id, "Opening Admin Management...")
         render_admin_management_menu(chat_id, message_id)

    elif data.startswith("adm_admin_del:"):
         adm_id = data.split(":")[1]
         answer_callback(callback_id, "Deleting admin...")
         admins = admin_db.get("admins", [OWNER_ID])
         if adm_id in admins and adm_id != OWNER_ID:
             admins.remove(adm_id)
             save_admin_db()
             threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
         render_admin_management_menu(chat_id, message_id)

    elif data == "adm_admin_add":
         answer_callback(callback_id, "Send Admin ID...")
         user_conversations[chat_id] = "waiting_admin_id"
         text = "👤 <b>Add New Admin</b>\n\nPlease send the Telegram User ID of the new admin (e.g., <code>123456789</code>)."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_admin_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_broadcast":
         answer_callback(callback_id, "Ready for broadcast")
         user_conversations[chat_id] = "waiting_for_broadcast"
         text = f"<tg-emoji emoji-id='5789428375261023681'>📢</tg-emoji> <b>BROADCAST SYSTEM</b>\n\nPlease send the message (Text, Photo, Video, Audio, Document, etc.) you want to broadcast to all users."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_main_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_main_menu":
         answer_callback(callback_id, "Returning to Admin Panel...")
         render_admin_panel(chat_id, message_id)

    elif data == "adm_developer":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Loading Developer Info...")
         render_admin_developer(chat_id, message_id)

    elif data == "adm_leaderboard":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Loading Leaderboard...")
         render_admin_leaderboard(chat_id, message_id)

    elif data == "adm_system_menu":
         answer_callback(callback_id, "Opening System Menu...")
         render_admin_system_menu(chat_id, message_id)

    elif data == "adm_panel_mgmt_menu":
         answer_callback(callback_id, "Opening Panel Management...")
         render_admin_panel_mgmt_menu(chat_id, message_id)

    elif data == "adm_analytics_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Loading Stats...")
         render_admin_analytics_menu(chat_id, message_id)

    elif data == "adm_health_check":
         answer_callback(callback_id, "Running Health Check...")
         render_admin_health_check(chat_id, message_id)

    elif data == "adm_stats_reset":
         admin_db["panel_stats"] = {}
         save_admin_db()
         answer_callback(callback_id, "Stats Reset!", show_alert=True)
         render_admin_analytics_menu(chat_id, message_id)

    elif data == "adm_trf_home":
         answer_callback(callback_id, "Opening Traffic Management...")
         render_admin_trf_home(chat_id, message_id)

    elif data.startswith("adm_trf_pnl:"):
         pnl_id = data.split(":")[1]
         answer_callback(callback_id)
         render_admin_trf_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_trf_tog_pnl:"):
         pnl_id = data.split(":")[1]
         for p in panels:
             if p["id"] == pnl_id:
                 p["is_traffic_active"] = not p.get("is_traffic_active", True)
                 save_panels_to_file(panels)
                 break
         answer_callback(callback_id, "Toggled Traffic Status!")
         render_admin_trf_pnl_view(chat_id, message_id, pnl_id)

    elif data == "adm_srch_home":
         answer_callback(callback_id)
         render_admin_srch_home(chat_id, message_id)

    elif data.startswith("adm_srch_pnl:"):
         pnl_id = data.split(":")[1]
         answer_callback(callback_id)
         render_admin_srch_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_srch_tog:"):
         pnl_id = data.split(":")[1]
         search_cfg = admin_db.setdefault("search_cfg", {})
         p_cfg = search_cfg.setdefault(pnl_id, {"is_active": True, "prefixes": []})
         p_cfg["is_active"] = not p_cfg.get("is_active", True)
         save_admin_db()
         answer_callback(callback_id, "Toggled Search Status!")
         render_admin_srch_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_srch_add:"):
         pnl_id = data.split(":")[1]
         answer_callback(callback_id, "Send Country Code...")
         user_conversations[chat_id] = f"add_srch_pfx:{pnl_id}"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('world', '🌐')} <b>Add Country Code</b>\n\nSend the calling code (e.g., <code>880</code>, <code>92</code>) to allow searching for this panel."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_srch_pnl:{pnl_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_srch_del:"):
         parts = data.split(":")
         pnl_id = parts[1]
         pfx = parts[2]
         search_cfg = admin_db.setdefault("search_cfg", {})
         if pnl_id in search_cfg and pfx in search_cfg[pnl_id].get("prefixes", []):
             search_cfg[pnl_id]["prefixes"].remove(pfx)
             save_admin_db()
         answer_callback(callback_id, "Deleted Prefix!")
         render_admin_srch_pnl_view(chat_id, message_id, pnl_id)

    elif data in ["adm_wd_app", "adm_wd_rej"]:
         user_id = callback_query.get("from", {}).get("id")
         
         # 🔒 সিকিউরিটি: শুধুমাত্র অ্যাডমিন ক্লিক করতে পারবে
         if str(user_id) not in admin_db.get("admins", [OWNER_ID]):
             answer_callback(callback_id, "❌ Only Admins can process withdrawals!", show_alert=True)
             return
             
         msg_text = callback_query.get("message", {}).get("text", "")
         
         u_match = re.search(r"User:\s*(\d+)", msg_text)
         m_match = re.search(r"Method:\s*(.+)", msg_text)
         a_match = re.search(r"Account:\s*([\d\+\w]+)", msg_text)
         amt_match = re.search(r"Amount:\s*([\d\.]+)", msg_text)
         
         if not (u_match and a_match and amt_match):
             answer_callback(callback_id, "❌ Error parsing request data!", show_alert=True)
             return
             
         u_id = u_match.group(1)
         meth = m_match.group(1).strip() if m_match else "Unknown"
         acc_num = a_match.group(1)
         amt = amt_match.group(1)
         
         masked_acc = mask_number(acc_num)
         
         if data == "adm_wd_app":
             status_text = f"APPROVED {get_pemoji('done', '✅')}"
             new_msg = (
                 f"╔═══════════════╗\n"
                 f"║ {get_pemoji('gem', '💎')} <b>WITHDRAWAL {status_text}</b>\n"
                 f"╚═══════════════╝\n\n"
                 f"{get_pemoji('user', '👤')} <b>User:</b> <code>{u_id}</code>\n"
                 f"{get_pemoji('dashboard', '💳')} <b>Method:</b> {meth}\n"
                 f"{get_pemoji('phone', '📱')} <b>Account:</b> <code>{masked_acc}</code>\n"
                 f"{get_pemoji('fire', '💰')} <b>Amount:</b> <b>{amt} ৳</b>\n"
                 f"━━━━━━━━━━━━"
             )
             edit_bot_message(chat_id, message_id, new_msg)
             send_bot_message(u_id, f"{get_pemoji('done', '✅')} <b>Withdrawal Approved!</b>\nYour request for {amt} ৳ via {meth} has been processed.")
             answer_callback(callback_id, "Approved!")
         else:
             status_text = f"REJECTED {get_pemoji('error', '❌')}"
             new_msg = (
                 f"╔═══════════════╗\n"
                 f"║ {get_pemoji('gem', '💎')} <b>WITHDRAWAL {status_text}</b>\n"
                 f"╚═══════════════╝\n\n"
                 f"{get_pemoji('user', '👤')} <b>User:</b> <code>{u_id}</code>\n"
                 f"{get_pemoji('dashboard', '💳')} <b>Method:</b> {meth}\n"
                 f"{get_pemoji('phone', '📱')} <b>Account:</b> <code>{masked_acc}</code>\n"
                 f"{get_pemoji('fire', '💰')} <b>Amount:</b> <b>{amt} ৳</b>\n"
                 f"━━━━━━━━━━━━"
             )
             edit_bot_message(chat_id, message_id, new_msg)
             
             stats = admin_db.setdefault("user_stats", {}).setdefault(u_id, {})
             stats["balance"] = stats.get("balance", 0.0) + float(amt)
             save_admin_db()
             
             send_bot_message(u_id, f"❌ <b>Withdrawal Rejected!</b>\nYour request for {amt} ৳ was declined. The amount has been refunded to your balance.")
             answer_callback(callback_id, "Rejected & Refunded!")

    elif data == "adm_pnl_home":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Loading Panels...")
         render_panel_list(chat_id, message_id)

    elif data.startswith("adm_pnl_view:"):
         user_conversations.pop(chat_id, None)
         p_idx = int(data.split(":")[1])
         answer_callback(callback_id, "Loading Details...")
         render_panel_details(chat_id, message_id, p_idx)

    elif data == "adm_pnl_add":
         answer_callback(callback_id, "Add New Panel...")
         render_add_panel_type_menu(chat_id, message_id)

    elif data.startswith("adm_pnl_default:"):
         field = data.split(":")[1]
         tmp = panel_creation_temp.get(chat_id, {})
         base_url = tmp.get("url", "")
         if field == "gn":
             answer_callback(callback_id, "Using default Get Number API...")
             prompt_for_get_message(chat_id, message_id, tmp)
         elif field == "gm":
             answer_callback(callback_id, "Using default Get Message API...")
             prompt_for_traffic(chat_id, message_id, tmp)
         elif field == "tr":
             answer_callback(callback_id, "Using default Traffic API...")
             finalize_panel_creation(chat_id, message_id)

    elif data.startswith("adm_pnl_type:"):
         ptype = data.split(":")[1]
         answer_callback(callback_id, "Enter panel details...")
         panel_creation_temp[chat_id] = {"type": ptype}
         user_conversations[chat_id] = f"add_pnl_name:{ptype}"
         user_prompts[chat_id] = message_id
         type_label = "YesSMS / Hadi / Shark" if ptype == "activation" else "Stex SMS API"
         edit_bot_message(chat_id, message_id,
             f"{get_pemoji('note', '📝')} <b>Add {type_label} Panel</b>\n\n"
             f"প্যানেলের <b>নাম</b> লিখুন (যেমন: <code>YesSMS BD</code>, <code>Hadi Panel</code>):",
             {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_pnl_del:"):
         pnl_id = data.split(":")[1]
         panel = next((p for p in panels if p.get("id") == pnl_id), None)
         if panel:
             pname = panel["name"]
             answer_callback(callback_id, "Confirm delete...")
             edit_bot_message(chat_id, message_id,
                 f"{get_pemoji('error', '❌')} <b>PANEL DELETE করবেন?</b>\n\n"
                 f"প্যানেল: <b>{escape_html(pname)}</b>\n\n"
                 f"⚠️ এই প্যানেলের সব সেটিং মুছে যাবে!",
                 {"inline_keyboard": [
                     [{"text": " হ্যাঁ, Delete করুন", "callback_data": f"adm_pnl_del_confirm:{pnl_id}", "style": "danger", "icon_custom_emoji_id": "5422557736330106570"}],
                     [{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]
                 ]})
         else:
             answer_callback(callback_id, "Panel not found.")
             render_panel_list(chat_id, message_id)

    elif data.startswith("adm_pnl_del_confirm:"):
         pnl_id = data.split(":")[1]
         panel = next((p for p in panels if p.get("id") == pnl_id), None)
         if panel:
             deleted_name = panel["name"]
             panels.remove(panel)
             save_panels_to_file(panels)
             answer_callback(callback_id, f"Deleted {deleted_name}!")
             edit_bot_message(chat_id, message_id,
                 f"{get_pemoji('done', '✅')} <b>{escape_html(deleted_name)}</b> deleted successfully!",
                 {"inline_keyboard": [[{"text": " Back to Panels", "callback_data": "adm_pnl_home", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
         else:
             answer_callback(callback_id, "Panel not found.")
             render_panel_list(chat_id, message_id)

    elif data == "adm_panel_mgmt_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id)
         render_admin_panel_mgmt_menu(chat_id, message_id)

    elif data == "adm_svc_home":
         answer_callback(callback_id)
         render_admin_svc_home(chat_id, message_id)

    elif data.startswith("adm_svc_pnl:"):
         pnl_id = data.split(":")[1]
         answer_callback(callback_id)
         render_admin_svc_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_svc_tog_pnl:"):
         pnl_id = data.split(":")[1]
         for p in panels:
             if p["id"] == pnl_id:
                 p["is_active"] = not p.get("is_active", True)
                 save_panels_to_file(panels)
                 break
         answer_callback(callback_id, "Toggled Panel Status!")
         render_admin_svc_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_svc_view:"):
         parts = data.split(":")
         answer_callback(callback_id)
         render_admin_svc_view(chat_id, message_id, parts[1], parts[2])

    elif data.startswith("adm_svc_ctr:"):
         parts = data.split(":")
         answer_callback(callback_id)
         render_admin_svc_ctr_view(chat_id, message_id, parts[1], parts[2], parts[3])

    elif data.startswith("adm_svc_add:"):
         pnl_id = data.split(":")[1]
         answer_callback(callback_id, "Send service name...")
         user_conversations[chat_id] = f"add_svc_name:{pnl_id}"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('note', '📝')} <b>Add New Service</b>\n\nSend the exact Name of the service (e.g., <code>Facebook</code>, <code>Netflix</code>)."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_svc_pnl:{pnl_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_svc_add_ctr:"):
         parts = data.split(":")
         pnl_id = parts[1]
         s_id = parts[2]
         answer_callback(callback_id)
         admin_ctr_search_query.pop(chat_id, None)
         render_country_picker(chat_id, message_id, pnl_id, s_id, page=0)

    elif data.startswith("adm_ctr_pg:"):
         parts = data.split(":")
         pnl_id, s_id, pg = parts[1], parts[2], int(parts[3])
         answer_callback(callback_id)
         q = admin_ctr_search_query.get(chat_id)
         render_country_picker(chat_id, message_id, pnl_id, s_id, page=pg, query=q)

    elif data.startswith("adm_ctr_search:"):
         parts = data.split(":")
         pnl_id, s_id = parts[1], parts[2]
         answer_callback(callback_id, "Send country name...")
         user_conversations[chat_id] = f"add_svc_ctr_search:{pnl_id}:{s_id}"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('search', '🔍')} <b>Search Country</b>\n\nদেশের নাম লিখুন (যেমন: <code>Bangladesh</code>, <code>India</code>, <code>USA</code>)।\nশুধু ২-৩ অক্ষর লিখলেই চলবে।"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_svc_add_ctr:{pnl_id}:{s_id}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_ctr_clear:"):
         parts = data.split(":")
         pnl_id, s_id = parts[1], parts[2]
         answer_callback(callback_id)
         admin_ctr_search_query.pop(chat_id, None)
         render_country_picker(chat_id, message_id, pnl_id, s_id, page=0)

    elif data.startswith("adm_ctr_pick:"):
         parts = data.split(":")
         pnl_id, s_id, c_code = parts[1], parts[2], parts[3]
         admin_ctr_search_query.pop(chat_id, None)
         success, res_text = add_country_to_service(pnl_id, s_id, c_code)
         answer_callback(callback_id, "Added!" if success else "Already exists!")
         kb = {"inline_keyboard": [[{"text": " Back to Service", "callback_data": f"adm_svc_view:{pnl_id}:{s_id}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
         edit_bot_message(chat_id, message_id, res_text, kb)

    elif data.startswith("adm_svc_add_rg:"):
         parts = data.split(":")
         pnl_id = parts[1]
         s_id = parts[2]
         c_code = parts[3]
         answer_callback(callback_id, "Send range...")
         user_conversations[chat_id] = f"add_svc_rg:{pnl_id}:{s_id}:{c_code}"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('number', '🔢')} <b>Add Range</b>\n\nSend the number range (e.g., <code>225070</code> or <code>225070XXX</code>).\n<i>(If you forget 'XXX', the bot will add it automatically!)</i>"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_svc_ctr:{pnl_id}:{s_id}:{c_code}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_svc_del_rg:"): # Added for completion if needed
         pass

    elif data.startswith("adm_svc_del:"):
         parts = data.split(":")
         pnl_id = parts[1]
         s_id = parts[2]
         answer_callback(callback_id, "Deleted Service")
         services_dict = load_services()
         services_dict[pnl_id] = [s for s in services_dict.get(pnl_id, []) if s['id'] != s_id]
         save_services(services_dict)
         render_admin_svc_pnl_view(chat_id, message_id, pnl_id)

    elif data.startswith("adm_svc_del_ctr:"):
         parts = data.split(":")
         pnl_id = parts[1]
         s_id = parts[2]
         c_code = parts[3]
         answer_callback(callback_id, "Deleted Country")
         services_dict = load_services()
         p_services = services_dict.get(pnl_id, [])
         for s in p_services:
             if s['id'] == s_id:
                 s['countries'] = [c for c in s.get('countries', []) if c['code'] != c_code]
                 break
         save_services(services_dict)
         render_admin_svc_view(chat_id, message_id, pnl_id, s_id)

    elif data.startswith("adm_svc_clr_rg:"):
         parts = data.split(":")
         pnl_id = parts[1]
         s_id = parts[2]
         c_code = parts[3]
         answer_callback(callback_id, "Cleared Ranges")
         services_dict = load_services()
         p_services = services_dict.get(pnl_id, [])
         for s in p_services:
             if s['id'] == s_id:
                 for c in s.get('countries', []):
                     if c['code'] == c_code:
                         c['ranges'] = []
                         break
                 break
         save_services(services_dict)
         render_admin_svc_ctr_view(chat_id, message_id, pnl_id, s_id, c_code)

    elif data.startswith("adm_pnl_edit:"):
        parts = data.split(":")
        p_idx = int(parts[1])
        field = parts[2]
        answer_callback(callback_id, f"Editing {field}...")
        user_conversations[chat_id] = f"edit_pnl_{p_idx}_{field}"
        user_prompts[chat_id] = message_id
        
        panel = panels[p_idx] if p_idx < len(panels) else {}
        
        if is_stex_api(panel) and field == "pass":
            field_name = "API Key (Token)"
        elif is_stex_api(panel) and field == "url":
            field_name = "Base API URL"
        else:
            names = {"url":"Login Link","user":"Gmail","pass":"Password","getnum":"GetNum URL","getmsg":"GetMsg URL","traffic":"Traffic URL"}
            field_name = names.get(field, field)
        
        panel_name = panel.get("name", "Panel")
        text = f"{get_pemoji('note', '📝')} <b>Editing {field_name} for {panel_name}</b>\n\n" \
               f"Please send the new value/URL to update the system."
        
        edit_bot_message(chat_id, message_id, text, {
            "inline_keyboard": [[{"text": " Back", "callback_data": f"adm_pnl_view:{p_idx}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]
        })

    elif data == "adm_firebase_menu":
         answer_callback(callback_id, "Opening Firebase Control...")
         render_admin_firebase_menu(chat_id, message_id)

    elif data in ["adm_fb_upload", "adm_fb_view", "adm_fb_delete"]:
         answer_callback(callback_id, "Feature disabled. Creds are now fixed in code.")

    elif data == "adm_fb_sync_users":
         answer_callback(callback_id, "Syncing entire database to Firestore...")
         success, msg_text = sync_essential_data_to_firestore()
         status_emoji = "✅" if success else "❌"
         text = f"{status_emoji} <b>FIREBASE SYNC STATUS</b>\n\n{msg_text}"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_firebase_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})

    # adm_prem_flag removed as data is hardcoded

    elif data == "adm_otp_grp_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id)
         render_admin_otp_grp_menu(chat_id, message_id)

    elif data == "adm_stats_toggle":
         cfg = admin_db.setdefault("redox_config", {})
         cfg["stats_auto_post"] = not cfg.get("stats_auto_post", False)
         if cfg["stats_auto_post"]:
             admin_db["last_stats_post_ts"] = time.time()  # টগল অন করার সাথে সাথে যেন হুট করে পোস্ট না হয়ে যায়
         save_admin_db()
         answer_callback(callback_id, "Auto Stats Post: " + ("ON ✅" if cfg["stats_auto_post"] else "OFF ❌"))
         render_admin_otp_grp_menu(chat_id, message_id)

    elif data == "adm_stats_interval":
         cfg = admin_db.setdefault("redox_config", {})
         current = int(cfg.get("stats_interval_min", 60) or 60)
         options = [15, 30, 60, 120, 180]
         try:
             next_idx = (options.index(current) + 1) % len(options)
         except ValueError:
             next_idx = 0
         cfg["stats_interval_min"] = options[next_idx]
         save_admin_db()
         answer_callback(callback_id, f"Interval set to {options[next_idx]} min")
         render_admin_otp_grp_menu(chat_id, message_id)

    elif data == "adm_otp_edit_link":
         answer_callback(callback_id)
         user_conversations[chat_id] = "edit_otp_link"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('note', '📝')} <b>Edit OTP Group Link</b>\n\nSend the new URL (e.g., https://t.me/...) for the user 'Otp Group' button."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_otp_grp_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_fwd_add":
         answer_callback(callback_id)
         user_conversations[chat_id] = "add_fwd_grp"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('note', '📝')} <b>Add Forward Group</b>\n\nSend the Chat ID (e.g., <code>-100123456789</code>) where OTPs should be forwarded."
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_otp_grp_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_fwd_view:"):
         idx = int(data.split(":")[1])
         answer_callback(callback_id)
         render_admin_fwd_view(chat_id, message_id, idx)

    elif data.startswith("adm_fwd_del:"):
         idx = int(data.split(":")[1])
         answer_callback(callback_id, "Deleted Group")
         fwd_groups = admin_db.get("forward_groups", [])
         if 0 <= idx < len(fwd_groups):
             fwd_groups.pop(idx)
             save_admin_db()
         render_admin_otp_grp_menu(chat_id, message_id)

    elif data.startswith("adm_fwd_btn_add:"):
         idx = int(data.split(":")[1])
         answer_callback(callback_id)
         user_conversations[chat_id] = f"add_fwd_btn:{idx}"
         user_prompts[chat_id] = message_id
         text = f"{get_pemoji('note', '📝')} <b>Add Custom Button</b>\n\nSend the button Text and URL separated by a pipe (`|`).\nExample:\n<code>Support|https://t.me/admin</code>"
         edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_fwd_view:{idx}", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("adm_fwd_btn_del:"):
         parts = data.split(":")
         idx = int(parts[1])
         b_idx = int(parts[2])
         answer_callback(callback_id, "Deleted Button")
         fwd_groups = admin_db.get("forward_groups", [])
         if 0 <= idx < len(fwd_groups):
             btns = fwd_groups[idx].get("buttons", [])
             if 0 <= b_idx < len(btns):
                 btns.pop(b_idx)
                 save_admin_db()
         render_admin_fwd_view(chat_id, message_id, idx)

    elif data == "adm_redox_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id)
         render_admin_redox_menu(chat_id, message_id)

    elif data == "adm_task_menu":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id)
         render_admin_task_menu(chat_id, message_id)

    elif data == "adm_task_price":
         answer_callback(callback_id, "Send Task Reward Price")
         user_conversations[chat_id] = "set_task_price"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('fire', '💰')} Send the Reward Price (৳) for completing this task (e.g., <code>50</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_task_otp":
         answer_callback(callback_id, "Send Required OTP Count")
         user_conversations[chat_id] = "set_task_otp"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('otp', '🔐')} Send how many OTPs a user must collect to complete this task (e.g., <code>10</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_task_dur":
         answer_callback(callback_id, "Send Duration in Hours")
         user_conversations[chat_id] = "set_task_dur"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('time', '🕓')} Send the Task Duration in hours (e.g., <code>24</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_task_start":
         task = admin_db.setdefault("task", {})
         if task.get("required_otp", 0) <= 0 or task.get("duration_hours", 0) <= 0:
             answer_callback(callback_id, "❌ Please set OTP Target and Duration first!", show_alert=True)
             return
         now_ts = time.time()
         task["active"] = True
         task["start_ts"] = now_ts
         task["end_ts"] = now_ts + float(task.get("duration_hours", 0)) * 3600
         task["task_id"] = now_ts
         save_admin_db()
         answer_callback(callback_id, "✅ Task Started!")
         render_admin_task_menu(chat_id, message_id)

    elif data == "adm_task_stop":
         admin_db.setdefault("task", {})["active"] = False
         save_admin_db()
         answer_callback(callback_id, "🛑 Task Stopped!")
         render_admin_task_menu(chat_id, message_id)

    elif data == "usr_task":
         answer_callback(callback_id)
         render_user_task(chat_id, message_id)

    elif data == "adm_redox_grp":
         answer_callback(callback_id, "Send group ID")
         user_conversations[chat_id] = "set_redox_grp"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('note', '📝')} Send the Group ID for Withdrawal Posts (e.g., <code>-100...</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_rew":
         answer_callback(callback_id, "Send OTP reward")
         user_conversations[chat_id] = "set_redox_rew"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('fire', '💰')} Send the amount user earns per successful OTP (e.g., <code>0.5</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_min":
         answer_callback(callback_id, "Send Min Withdraw")
         user_conversations[chat_id] = "set_redox_min"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('otp', '🔐')} Send Minimum Withdraw Amount (e.g., <code>20</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_mth_add":
         answer_callback(callback_id, "Send Method Name")
         user_conversations[chat_id] = "add_redox_mth"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('dashboard', '🏦')} Send New Withdrawal Method Name (e.g., <code>bKash</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_mth_clr":
         answer_callback(callback_id, "Cleared Methods!")
         if "redox_config" in admin_db:
             admin_db["redox_config"]["methods"] = []
             save_admin_db()
         render_admin_redox_menu(chat_id, message_id)

    elif data == "adm_redox_maxc":
         answer_callback(callback_id, "Send max numbers per user...")
         user_conversations[chat_id] = "set_redox_maxc"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('number', '🔢')} Send Max Numbers a user can request at a time (e.g., <code>3</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_cd":
         answer_callback(callback_id, "Send cooldown in seconds...")
         user_conversations[chat_id] = "set_redox_cd"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('wait', '⏳')} Send Cooldown Time in seconds (e.g., <code>30</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_refb":
         if str(chat_id) not in admin_db.get("admins", [OWNER_ID]):
             answer_callback(callback_id, "❌ Admin only!", show_alert=True)
             return
         answer_callback(callback_id, "Send Refer Bonus amount...")
         user_conversations[chat_id] = "set_redox_refb"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id, f"{get_pemoji('gem', '💎')} Send Refer Bonus Amount per referral (e.g., <code>5</code>):", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data == "adm_redox_supp":
         answer_callback(callback_id, "Send support username or link")
         user_conversations[chat_id] = "set_support_link"
         user_prompts[chat_id] = message_id
         edit_bot_message(chat_id, message_id,
             f"{get_pemoji('support', '🫂')} Send the <b>Support Username or Link</b>:\n"
             f"<i>Example: @YourSupportUser or https://t.me/YourGroup</i>",
             {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})

    elif data.startswith("usr_wd_"):
         method = data.replace("usr_wd_", "")
         stats = admin_db.get("user_stats", {}).get(str(chat_id), {"otp_count": 0, "balance": 0.0})
         cfg = admin_db.get("redox_config", {})
         if stats.get("balance", 0.0) < float(cfg.get("min_withdraw", 20.0)):
             answer_callback(callback_id, f"❌ Minimum withdraw is {cfg.get('min_withdraw', 20.0)} ৳", show_alert=True)
         else:
             answer_callback(callback_id)
             user_conversations[chat_id] = f"wd_wait_amt_{method}"
             user_prompts[chat_id] = message_id
             text = (
                 f"{get_pemoji('gem', '💎')} <b>Withdraw via {method}</b>\n"
                 f"━━━━━━━━━━━━\n\n"
                 f"{get_pemoji('note', '📝')} Please send the <b>Amount</b> you want to withdraw:\n"
                 f"<i>(Available Balance: {stats.get('balance', 0.0)} ৳)</i>"
             )
             edit_bot_message(chat_id, message_id, text, {"inline_keyboard": [[{"text": " Cancel", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
         
    elif data == "adm_main_menu":
         answer_callback(callback_id, "Returning to Admin Panel...")
         render_admin_panel(chat_id, message_id)

    elif data == "adm_developer":
         user_conversations.pop(chat_id, None)
         answer_callback(callback_id, "Loading Developer Info...")
         render_admin_developer(chat_id, message_id)

    elif data.startswith("tr_svc:"):
         service_slug = data.split(":")[1]
         answer_callback(callback_id, f"Loading {service_slug} stats...")
         render_explore_service(chat_id, message_id, service_slug)

    elif data.startswith("tr_ctr:"):
         parts = data.split(":")
         service_slug = parts[1]
         c_code = parts[2]
         answer_callback(callback_id, f"Loading {c_code} ranges...")
         render_explore_ranges(chat_id, message_id, service_slug, c_code)

    elif data == "usr_refer":
        answer_callback(callback_id, "Loading Refer Page...")
        render_refer_page(chat_id, message_id)

    else:
        answer_callback(callback_id)

import hmac, base64, struct

def get_totp_token(secret):
    try:
        secret = secret.replace(" ", "").upper()
        secret += "=" * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(secret)
        tm = int(time.time() / 30)
        msg = struct.pack(">Q", tm)
        h = hmac.new(key, msg, "sha1").digest()
        o = h[19] & 15
        token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
        return f"{token:06d}"
    except Exception:
        return None

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    chat_type = msg["chat"].get("type", "private")

    # 🔐 প্রাইভেট গ্রুপ যেখানে ফরওয়ার্ড/Restrict Saving Content বন্ধ করা থাকে, সেখানে
    # অ্যাডমিন গ্রুপের ভিতরে গিয়ে /confirmgroup কমান্ড পাঠালে সরাসরি এই গ্রুপের chat_id
    # ধরে Force Join-এ verified হিসেবে যোগ করে দেওয়া হয় — ফরওয়ার্ড করার দরকার হয় না।
    if chat_type in ["group", "supergroup"]:
        group_text = (msg.get("text") or "").strip().lower()
        from_user_id = msg.get("from", {}).get("id")
        if group_text == "/confirmgroup" and from_user_id:
            pending_state = user_conversations.get(from_user_id, "")
            if isinstance(pending_state, str) and pending_state.startswith("waiting_fj_fwd:"):
                invite_link = pending_state.split(":", 1)[1]
                group_chat = msg["chat"]
                resolved_id = group_chat.get("id")
                title = group_chat.get("title") or invite_link
                entry = {"id": invite_link, "chat_id": resolved_id, "title": title}
                if "force_join_channels" not in admin_db:
                    admin_db["force_join_channels"] = []
                existing_ids = [c.get("id") if isinstance(c, dict) else c for c in admin_db["force_join_channels"]]
                if invite_link not in existing_ids:
                    admin_db["force_join_channels"].append(entry)
                    save_admin_db()
                    threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
                user_conversations.pop(from_user_id, None)
                send_bot_message(chat_id, f"{get_pemoji('done', '✅')} <b>এই গ্রুপ Force Join-এ verified হয়ে গেছে!</b>")
                send_bot_message(from_user_id, f"{get_pemoji('done', '✅')} <b>Channel added & verified successfully!</b>\n\n<b>{escape_html(title)}</b> এখন থেকে Force Join-এ ঠিকভাবে চেক হবে।", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_fj_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    # 🚫 গ্রুপে অন্য কোনো মেসেজ বা কমান্ডের উত্তর দেবে না (শুধু বাটন কাজ করবে)
    if chat_type in ["group", "supergroup"]:
        return

    # 🚫 Check Ban Status
    if str(chat_id) in admin_db.get("banned_users", []):
        return

    # Allow text or captions for media support
    text = msg.get("text", "").strip() or msg.get("caption", "").strip()

    # --- BROADCAST HANDLER (Supports All Media Types: Photo, Video, Audio, etc.) ---
    if user_conversations.get(chat_id) == "waiting_for_broadcast":
        user_conversations.pop(chat_id, None)
        users = admin_db.get("users", [])
        if not users:
            send_bot_message(chat_id, "❌ No users found in database to broadcast.", {"inline_keyboard": [[{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
            return

        send_bot_message(chat_id, f"{get_pemoji('wait', '⏳')} Broadcasting to {len(users)} users. Please wait...")
        success_count = 0

        # text message হলে শুধু ইউজারের লেখা টেক্সটই যাবে (কোনো extra wrapper emoji ছাড়া); media হলে copyMessage
        orig_text = msg.get("text") or msg.get("caption", "")
        is_text_only = "text" in msg and not any(k in msg for k in ("photo", "video", "audio", "document", "voice", "sticker", "animation"))
        processed_text = apply_inline_premium_emoji(escape_html(orig_text))
        wrapped_text = processed_text if is_text_only else None

        for u in users:
            try:
                if is_text_only and wrapped_text:
                    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        json={"chat_id": u, "text": wrapped_text, "parse_mode": "HTML"}).json()
                else:
                    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/copyMessage",
                        json={"chat_id": u, "from_chat_id": chat_id, "message_id": msg["message_id"]}).json()
                if res.get("ok"):
                    success_count += 1
            except Exception:
                pass

        send_bot_message(chat_id, f"{get_pemoji('done', '✅')} <b>Broadcast Completed!</b>\n\nSuccessfully sent to {success_count}/{len(users)} users.", {"inline_keyboard": [[{"text": " Back to Admin", "callback_data": "adm_main_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    if user_conversations.get(chat_id) == "waiting_fj_channel":
        channel = text.strip()
        if channel:
            is_private_invite = ("t.me/+" in channel) or ("t.me/joinchat/" in channel)
            if is_private_invite:
                # Private invite links can't be resolved to a numeric chat_id just from the
                # link text — we need the admin to forward a message FROM that channel/group
                # so we can capture its real chat_id and verify membership properly later.
                user_conversations[chat_id] = f"waiting_fj_fwd:{channel}"
                send_bot_message(
                    chat_id,
                    f"{get_pemoji('wait', '⏳')} <b>এটা একটা প্রাইভেট চ্যানেল/গ্রুপ লিংক।</b>\n\n"
                    f"Force Join ঠিকভাবে কাজ করতে হলে বট-কে ওই চ্যানেল/গ্রুপের <b>Admin</b> বানান, তারপর নিচের যেকোনো একটা উপায়ে ভেরিফাই করুন:\n\n"
                    f"<b>উপায় ১ (চ্যানেল বা Forward চালু থাকা গ্রুপ):</b> ওই চ্যানেল/গ্রুপ থেকে যেকোনো একটা মেসেজ <b>Forward</b> করে এখানে পাঠান।\n\n"
                    f"<b>উপায় ২ (গ্রুপে Forward/Save বন্ধ থাকলে):</b> ওই গ্রুপে গিয়ে (বট Admin থাকা অবস্থায়) সরাসরি <code>/confirmgroup</code> কমান্ডটি টাইপ করে পাঠান — বট নিজেই গ্রুপ শনাক্ত করে verified করে দেবে।",
                    {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_fj_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
                )
                return
            if "force_join_channels" not in admin_db:
                admin_db["force_join_channels"] = []
            if channel not in admin_db["force_join_channels"]:
                admin_db["force_join_channels"].append(channel)
                save_admin_db()
                threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
            user_conversations.pop(chat_id, None)
            send_bot_message(chat_id, f"{get_pemoji('done', '✅')} <b>Channel added successfully!</b>", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_fj_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    if isinstance(user_conversations.get(chat_id), str) and user_conversations.get(chat_id, "").startswith("waiting_fj_fwd:"):
        invite_link = user_conversations[chat_id].split(":", 1)[1]
        fwd_chat = msg.get("forward_from_chat")
        if not fwd_chat:
            origin = msg.get("forward_origin", {})
            if origin.get("type") == "channel":
                fwd_chat = origin.get("chat")
        if not fwd_chat:
            send_bot_message(chat_id, f"{get_pemoji('error', '❌')} এটা কোনো চ্যানেল/গ্রুপ থেকে ফরওয়ার্ড করা মেসেজ না। ওই চ্যানেল/গ্রুপ থেকে সরাসরি একটা মেসেজ ফরওয়ার্ড করে পাঠান।")
            return
        resolved_id = fwd_chat.get("id")
        title = fwd_chat.get("title") or fwd_chat.get("username") or invite_link
        entry = {"id": invite_link, "chat_id": resolved_id, "title": title}
        if "force_join_channels" not in admin_db:
            admin_db["force_join_channels"] = []
        existing_ids = [c.get("id") if isinstance(c, dict) else c for c in admin_db["force_join_channels"]]
        if invite_link not in existing_ids:
            admin_db["force_join_channels"].append(entry)
            save_admin_db()
            threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
        user_conversations.pop(chat_id, None)
        send_bot_message(chat_id, f"{get_pemoji('done', '✅')} <b>Channel added & verified successfully!</b>\n\n<b>{escape_html(title)}</b> এখন থেকে Force Join-এ ঠিকভাবে চেক হবে।", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_fj_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    if user_conversations.get(chat_id) == "waiting_admin_id":
        adm_id = text.strip()
        if adm_id.isdigit():
            if "admins" not in admin_db:
                admin_db["admins"] = [OWNER_ID]
            if adm_id not in admin_db["admins"]:
                admin_db["admins"].append(adm_id)
                save_admin_db()
                threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
            user_conversations.pop(chat_id, None)
            send_bot_message(chat_id, f"{get_pemoji('done', '✅')} <b>Admin added successfully!</b>", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_admin_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        else:
            send_bot_message(chat_id, f"{get_pemoji('error', '❌')} Please enter a valid numeric User ID.", {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_admin_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    # adm_prem_flag removed as data is hardcoded

    # --- MANAGE OTP & FORWARD GROUPS ---
    state = user_conversations.get(chat_id, "")

    if state == "set_redox_grp":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        admin_db.setdefault("redox_config", {})["withdraw_group"] = text.strip()
        save_admin_db()
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        res_text = f"{get_pemoji('done', '✅')} Withdraw Group Updated!"
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_redox_rew":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("redox_config", {})["otp_reward"] = float(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} OTP Reward Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Amount!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_redox_min":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("redox_config", {})["min_withdraw"] = float(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Min Withdraw Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Amount!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_redox_maxc":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("redox_config", {})["max_concurrent"] = int(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Max Concurrent Numbers Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Number!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_redox_cd":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("redox_config", {})["cooldown"] = int(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Cooldown Time Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Number!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_task_price":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("task", {})["price"] = float(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Task Reward Price Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Amount!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_task_otp":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("task", {})["required_otp"] = int(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Required OTP Count Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Number!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_task_dur":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        try:
            admin_db.setdefault("task", {})["duration_hours"] = float(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Task Duration Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Number!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_task_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "set_support_link":
        if str(chat_id) not in admin_db.get("admins", [OWNER_ID]):
            user_conversations.pop(chat_id, None)
            return
        prompt_id = user_prompts.pop(chat_id, None)
        val = text.strip()
        kb_back = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
        # @username → full URL রূপান্তর
        if val.startswith("@"):
            val = "https://t.me/" + val[1:]
        # Validation: https:// বা http:// দিয়ে শুরু হতে হবে
        if not (val.startswith("https://") or val.startswith("http://")):
            user_conversations[chat_id] = "set_support_link"  # state রাখো পুনরায় চেষ্টার জন্য
            err_text = (
                f"{get_pemoji('error', '❌')} Invalid link! Please send a valid URL or username.\n"
                f"<i>Example: @YourSupportUser or https://t.me/YourGroup</i>"
            )
            if prompt_id: edit_bot_message(chat_id, prompt_id, err_text, kb_back)
            else: send_bot_message(chat_id, err_text, kb_back)
            return
        user_conversations.pop(chat_id, None)
        admin_db.setdefault("redox_config", {})["support_link"] = val
        save_admin_db()
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        res_text = f"{get_pemoji('done', '✅')} Support Link Updated:\n<code>{escape_html(val)}</code>"
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        else: send_bot_message(chat_id, res_text, {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    if state == "set_redox_refb":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        if str(chat_id) not in admin_db.get("admins", [OWNER_ID]):
            send_bot_message(chat_id, "❌ Unauthorized.")
            return
        try:
            admin_db.setdefault("redox_config", {})["refer_bonus"] = float(text.strip())
            save_admin_db()
            res_text = f"{get_pemoji('done', '✅')} Refer Bonus Updated!"
        except: res_text = f"{get_pemoji('error', '❌')} Invalid Amount!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "add_redox_mth":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        admin_db.setdefault("redox_config", {}).setdefault("methods", []).append(text.strip())
        save_admin_db()
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_redox_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        res_text = f"{get_pemoji('done', '✅')} Method {text.strip()} Added!"
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("wd_wait_amt_"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        method = state.replace("wd_wait_amt_", "")
        
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        kb = {"inline_keyboard": [[{"text": " Cancel", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
        
        try:
            amount = float(text.strip())
            stats = admin_db.get("user_stats", {}).get(str(chat_id), {"otp_count": 0, "balance": 0.0})
            cfg = admin_db.get("redox_config", {})
            
            if amount < float(cfg.get("min_withdraw", 20.0)):
                res_text = f"{get_pemoji('error', '❌')} <b>Failed:</b> Minimum withdraw is {cfg.get('min_withdraw', 20.0)} ৳"
                if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
                else: send_bot_message(chat_id, res_text, kb)
            elif amount > stats.get("balance", 0.0):
                res_text = f"{get_pemoji('error', '❌')} <b>Failed:</b> Insufficient balance!"
                if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
                else: send_bot_message(chat_id, res_text, kb)
            else:
                user_conversations[chat_id] = f"wd_wait_num_{method}_{amount}"
                user_prompts[chat_id] = prompt_id 
                res_text = (
                    f"{get_pemoji('gem', '💎')} <b>Withdraw via {method}</b>\n"
                    f"━━━━━━━━━━━━\n"
                    f"{get_pemoji('done', '✅')} <b>Amount:</b> {amount} ৳\n\n"
                    f"{get_pemoji('phone', '📱')} Now, please send your <b>Account Number</b>:"
                )
                if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
                else: 
                    new_msg = send_bot_message(chat_id, res_text, kb)
                    if new_msg: user_prompts[chat_id] = new_msg.get("result", {}).get("message_id")
        except ValueError:
            res_text = f"{get_pemoji('error', '❌')} Invalid amount format. Please send numbers only."
            if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
            else: send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("wd_wait_num_"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        
        # Method এবং Amount এক্সট্র্যাক্ট করা
        remainder = state.replace("wd_wait_num_", "")
        last_underscore = remainder.rfind("_")
        method = remainder[:last_underscore]
        amount = float(remainder[last_underscore+1:])
        number = text.strip()
        
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        kb = {"inline_keyboard": [[{"text": " Back to Home", "callback_data": "usr_menu_home", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        
        stats = admin_db.get("user_stats", {}).get(str(chat_id), {"otp_count": 0, "balance": 0.0})
        if stats["balance"] >= amount:
            admin_db["user_stats"][str(chat_id)]["balance"] -= amount
            save_admin_db()
            
            res_text = (
                f"{get_pemoji('done', '✅')} <b>Withdrawal requested successfully!</b>\n"
                f"━━━━━━━━━━━━\n"
                f"{get_pemoji('gem', '💎')} <b>Amount:</b> {amount} ৳\n"
                f"{get_pemoji('phone', '📱')} <b>Number:</b> <code>{number}</code>\n"
                f"<i>It will be processed soon by the REDOX admins.</i>"
            )
            
            cfg = admin_db.get("redox_config", {})
            w_grp = cfg.get("withdraw_group")
            if w_grp:
                w_msg = (
                    f"╔═══════════════╗\n"
                    f"║ {get_pemoji('gem', '💎')} <b>NEW WITHDRAWAL REQUEST</b>\n"
                    f"╚═══════════════╝\n\n"
                    f"{get_pemoji('user', '👤')} <b>User:</b> <code>{chat_id}</code>\n"
                    f"{get_pemoji('dashboard', '💳')} <b>Method:</b> {method}\n"
                    f"{get_pemoji('phone', '📱')} <b>Account:</b> <code>{number}</code>\n"
                    f"{get_pemoji('fire', '💰')} <b>Amount:</b> <b>{amount} ৳</b>\n"
                    f"━━━━━━━━━━━━"
                )
                wd_kb = {
                    "inline_keyboard": [
                        [
                            {"text": " Approve", "callback_data": "adm_wd_app", "style": "success", "icon_custom_emoji_id": "5352694861990501856"},
                            {"text": " Reject", "callback_data": "adm_wd_rej", "style": "danger", "icon_custom_emoji_id": "5420130255174145507"}
                        ]
                    ]
                }
                call_telegram("sendMessage", {"chat_id": w_grp, "text": w_msg, "parse_mode": "HTML", "reply_markup": wd_kb})
        else:
            res_text = f"{get_pemoji('error', '❌')} Something went wrong with your balance verification!"

        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return
    
    if state.startswith("um_wait_id_"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        action_type = state.split("_")[3]
        target_uid = text.strip()
        
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        
        if not target_uid.isdigit():
            err_txt = "❌ Invalid User ID. Must be numeric."
            kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_user_mgmt_menu", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
            if prompt_id: edit_bot_message(chat_id, prompt_id, err_txt, kb)
            else: send_bot_message(chat_id, err_txt, kb)
            return

        if action_type == "prof":
            render_um_profile(chat_id, prompt_id, target_uid)
        elif action_type == "bal":
            render_um_balance(chat_id, prompt_id, target_uid)
        elif action_type == "ban":
            render_um_ban(chat_id, prompt_id, target_uid)
        return

    if state.startswith("um_wait_amt_"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        parts = state.split("_")
        action = parts[3] # "add" or "sub"
        target_uid = parts[4]
        
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        kb = {"inline_keyboard": [[{"text": " Back to Balance", "callback_data": f"adm_um_view_bal:{target_uid}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        
        try:
            amount = float(text.strip())
            stats = admin_db.setdefault("user_stats", {}).setdefault(target_uid, {"otp_count": 0, "balance": 0.0})
            
            if action == "add":
                stats["balance"] += amount
                res_txt = f"<tg-emoji emoji-id='5352694861990501856'>✅</tg-emoji> Added {amount} ৳ to <code>{target_uid}</code>'s balance."
            else:
                stats["balance"] = max(0.0, stats["balance"] - amount)
                res_txt = f"<tg-emoji emoji-id='5352694861990501856'>✅</tg-emoji> Deducted {amount} ৳ from <code>{target_uid}</code>'s balance."
                
            save_admin_db()
        except ValueError:
            res_txt = "<tg-emoji emoji-id='5420130255174145507'>❌</tg-emoji> Invalid amount! Please send a valid number."
            
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_txt, kb)
        else: send_bot_message(chat_id, res_txt, kb)
        return

    if state == "edit_otp_link":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        link = text.strip()
        admin_db["otp_group_link"] = link
        save_admin_db()
        threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
        res_text = f"{get_pemoji('done', '✅')} User OTP Group Link updated successfully!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_otp_grp_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state == "add_fwd_grp":
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        g_id = text.strip()
        fwd_groups = admin_db.setdefault("forward_groups", [])
        if not any(g["id"] == g_id for g in fwd_groups):
            fwd_groups.append({"id": g_id, "buttons": []})
            save_admin_db()
            threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
            res_text = f"{get_pemoji('done', '✅')} Forward Group added!"
        else:
            res_text = f"{get_pemoji('error', '❌')} Group already exists!"
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_otp_grp_menu", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("add_fwd_btn:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        idx = int(state.split(":")[1])
        
        res_text = f"{get_pemoji('error', '❌')} Invalid format. Use Text|URL"
        if "|" in text:
            b_text, b_url = text.split("|", 1)
            
            # 🚀 Extract Premium Emoji ID directly from the message entities
            em_id = None
            if "entities" in msg:
                for ent in msg["entities"]:
                    if ent.get("type") == "custom_emoji":
                        em_id = ent.get("custom_emoji_id")
                        break
            
            # Remove the fallback emoji character from the text to avoid double emojis
            clean_text = b_text.strip()
            match = re.search(r'^([^\w\s]+)\s*(.*)', clean_text, re.UNICODE)
            if match:
                clean_text = match.group(2).strip()
            
            btn_data = {"text": f" {clean_text}", "url": b_url.strip()}
            if em_id:
                btn_data["emoji_id"] = em_id
            
            fwd_groups = admin_db.get("forward_groups", [])
            if 0 <= idx < len(fwd_groups):
                fwd_groups[idx].setdefault("buttons", []).append(btn_data)
                save_admin_db()
                threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
                res_text = f"{get_pemoji('done', '✅')} Button added successfully!"
                
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_fwd_view:{idx}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("add_srch_pfx:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        pnl_id = state.split(":")[1]
        pfx = text.strip().replace("+", "")
        
        res_text = f"{get_pemoji('error', '❌')} Invalid format. Only numbers are allowed."
        kb = {"inline_keyboard": [[{"text": " Back", "callback_data": f"adm_srch_pnl:{pnl_id}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        
        if pfx.isdigit():
            search_cfg = admin_db.setdefault("search_cfg", {})
            p_cfg = search_cfg.setdefault(pnl_id, {"is_active": True, "prefixes": []})
            if pfx not in p_cfg["prefixes"]:
                p_cfg["prefixes"].append(pfx)
                save_admin_db()
                res_text = f"{get_pemoji('done', '✅')} Country code <b>+{pfx}</b> added for search!"
            else:
                res_text = f"{get_pemoji('error', '❌')} Country code already exists!"
                
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        if prompt_id: edit_bot_message(chat_id, prompt_id, res_text, kb)
        else: send_bot_message(chat_id, res_text, kb)
        return
    
    if state.startswith("add_svc_name:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        pnl_id = state.split(":")[1]
        svc_name = text.strip()
        svc_id = svc_name.lower().replace(" ", "_")
        services_dict = load_services()
        if pnl_id not in services_dict:
            services_dict[pnl_id] = []
            
        p_services = services_dict[pnl_id]
        kb = {"inline_keyboard": [[{"text": " Back to Services", "callback_data": f"adm_svc_pnl:{pnl_id}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        if not any(s['id'] == svc_id for s in p_services):
            p_services.append({"id": svc_id, "name": svc_name, "countries": []})
            save_services(services_dict)
            res_text = f"{get_pemoji('done', '✅')} Service <b>{svc_name}</b> added to panel!"
        else:
            res_text = f"{get_pemoji('error', '❌')} Service already exists!"
        
        if prompt_id:
            edit_bot_message(chat_id, prompt_id, res_text, kb)
        else:
            send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("add_svc_ctr_search:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        parts = state.split(":")
        pnl_id, s_id = parts[1], parts[2]
        query = text.strip()
        admin_ctr_search_query[chat_id] = query
        if prompt_id:
            render_country_picker(chat_id, prompt_id, pnl_id, s_id, page=0, query=query)
        return

    if state.startswith("add_svc_ctr:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        parts = state.split(":")
        pnl_id = parts[1]
        s_id = parts[2]
        c_code = text.strip().upper()
        services_dict = load_services()
        p_services = services_dict.get(pnl_id, [])
        
        kb = {"inline_keyboard": [[{"text": " Back to Service", "callback_data": f"adm_svc_view:{pnl_id}:{s_id}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        res_text = f"{get_pemoji('error', '❌')} Error processing country."
        
        for s in p_services:
            if s['id'] == s_id:
                if not any(c['code'] == c_code for c in s.get('countries', [])):
                    s.setdefault('countries', []).append({"code": c_code, "ranges": []})
                    save_services(services_dict)
                    res_text = f"{get_pemoji('done', '✅')} Country <b>{c_code}</b> added to {s['name']}!"
                else:
                    res_text = f"{get_pemoji('error', '❌')} Country already added!"
                break
                
        if prompt_id:
            edit_bot_message(chat_id, prompt_id, res_text, kb)
        else:
            send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("add_svc_rg:"):
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        parts = state.split(":")
        pnl_id = parts[1]
        s_id = parts[2]
        c_code = parts[3]
        
        new_range = text.strip().upper()
        if not any(x in new_range for x in ("X", "*")) and new_range.isdigit():
            new_range += "XXX"
            
        services_dict = load_services()
        p_services = services_dict.get(pnl_id, [])
        kb = {"inline_keyboard": [[{"text": " Back to Ranges", "callback_data": f"adm_svc_ctr:{pnl_id}:{s_id}:{c_code}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
        res_text = f"{get_pemoji('error', '❌')} Error processing range."
        
        for s in p_services:
            if s['id'] == s_id:
                for c in s.get('countries', []):
                    if c['code'] == c_code:
                        if new_range not in c.get('ranges', []):
                            c.setdefault('ranges', []).append(new_range)
                            save_services(services_dict)
                            res_text = f"{get_pemoji('done', '✅')} Range <code>{new_range}</code> added!"
                        else:
                            res_text = f"{get_pemoji('error', '❌')} Range already exists!"
                        break
                break
                
        if prompt_id:
            edit_bot_message(chat_id, prompt_id, res_text, kb)
        else:
            send_bot_message(chat_id, res_text, kb)
        return

    if state.startswith("edit_pnl_"):
        parts = state.split("_")
        if len(parts) >= 4:
            p_idx = int(parts[2])
            field_key = parts[3]
            
            if p_idx < len(panels):
                p = panels[p_idx]
                
                mapping = {
                    "url": "url", 
                    "user": "username", 
                    "pass": "password", 
                    "getnum": "getNumberUrl", 
                    "getmsg": "getMessageUrl", 
                    "traffic": "trafficUrl"
                }
                actual_key = mapping.get(field_key, field_key)
                p[actual_key] = text
                
                if field_key in ["url", "user", "pass"]:
                    p["sessionCookie"] = "" # Reset session for auth changes
                    
                save_panels_to_file(panels)
                user_conversations.pop(chat_id, None)
                
                # ইউজারের ইনপুট মেসেজ ডিলিট করে দেওয়া হচ্ছে
                call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
                prompt_id = user_prompts.pop(chat_id, None)
                
                if field_key in ["url", "user", "pass"]:
                    wait_text = f"{get_pemoji('wait', '⏳')} <b>Configuration Saved!</b>\nChecking authentication status for {p['name']}..."
                    if prompt_id:
                        edit_bot_message(chat_id, prompt_id, wait_text)
                    else:
                        wait_msg = send_bot_message(chat_id, wait_text)
                        prompt_id = wait_msg.get("result", {}).get("message_id")
                        
                    login_result = login_to_panel(p, force=True)
                    
                    if login_result:
                        final_text = f"{get_pemoji('done', '✅')} <b>Success!</b> Login verified with new settings."
                        style = "success"
                    else:
                        final_text = f"{get_pemoji('error', '❌')} <b>Login Failed!</b> Please check your URL/Credentials."
                        style = "danger"
                        
                    edit_bot_message(chat_id, prompt_id, final_text, {
                        "inline_keyboard": [[{"text": " Back to Panel details", "callback_data": f"adm_pnl_view:{p_idx}", "style": style, "icon_custom_emoji_id": "5267490665117275176"}]]
                    })
                else:
                    res_text_edit = f"{get_pemoji('done', '✅')} <b>Configuration Saved!</b>\n\nAPI link updated successfully."
                    kb_edit = {"inline_keyboard": [[{"text": " Back to Panel details", "callback_data": f"adm_pnl_view:{p_idx}", "style": "primary", "icon_custom_emoji_id": "5267490665117275176"}]]}
                    if prompt_id:
                        edit_bot_message(chat_id, prompt_id, res_text_edit, kb_edit)
                    else:
                        send_bot_message(chat_id, res_text_edit, kb_edit)
                return
            
    # --- New Panel Creation: Step 1 — Name ---
    if state.startswith("add_pnl_name:"):
        ptype = state.split(":")[1]
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        pname = text.strip()
        if not pname:
            edit_bot_message(chat_id, prompt_id, f"{get_pemoji('error', '❌')} নাম খালি রাখা যাবে না।",
                {"inline_keyboard": [[{"text": " Back", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
            return
        panel_creation_temp[chat_id] = {"type": ptype, "name": pname}
        user_conversations[chat_id] = f"add_pnl_url:{ptype}"
        user_prompts[chat_id] = prompt_id
        edit_bot_message(chat_id, prompt_id,
            f"{get_pemoji('note', '📝')} <b>Panel: {escape_html(pname)}</b>\n\n"
            f"এখন প্যানেলের <b>Base URL</b> দিন\n"
            f"(যেমন: <code>https://yesms.online</code> বা <code>https://hadipanel.com</code>):",
            {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    # --- New Panel Creation: Step 2 — Base URL ---
    if state.startswith("add_pnl_url:"):
        ptype = state.split(":")[1]
        prompt_id = user_prompts.get(chat_id)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        base_url = text.strip().rstrip("/")
        cancel_kb = {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
        if not base_url.startswith(("http://", "https://")):
            edit_bot_message(chat_id, prompt_id,
                f"{get_pemoji('error', '❌')} Invalid URL। <code>http://</code> বা <code>https://</code> দিয়ে শুরু করুন:", cancel_kb)
            return
        tmp = panel_creation_temp.get(chat_id, {})
        pname = tmp.get("name", "New Panel")
        user_conversations.pop(chat_id, None)
        user_prompts.pop(chat_id, None)
        panel_creation_temp[chat_id] = {"type": ptype, "name": pname, "url": base_url}
        user_conversations[chat_id] = f"add_pnl_key:{ptype}"
        user_prompts[chat_id] = prompt_id
        edit_bot_message(chat_id, prompt_id,
            f"{get_pemoji('note', '📝')} <b>Panel: {escape_html(pname)}</b>\n"
            f"URL: <code>{escape_html(base_url)}</code>\n\n"
            f"এখন <b>API Token / Secret Key</b> দিন:",
            cancel_kb)
        return

    # --- New Panel Creation: Step 3 — API Token ---
    if state.startswith("add_pnl_key:"):
        ptype = state.split(":")[1]
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        api_token = text.strip()
        if not api_token:
            edit_bot_message(chat_id, prompt_id,
                f"{get_pemoji('error', '❌')} Token খালি রাখা যাবে না। আবার পাঠান:",
                {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
            user_conversations[chat_id] = f"add_pnl_key:{ptype}"
            user_prompts[chat_id] = prompt_id
            return

        tmp = panel_creation_temp.get(chat_id, {})
        tmp["token"] = api_token
        panel_creation_temp[chat_id] = tmp
        base_url = tmp.get("url", "")

        # সব ধরনের প্যানেলের জন্যই বাকি ৩টা API endpoint চাওয়া হবে
        default_gn = f"{base_url}/getnum"
        user_conversations[chat_id] = f"add_pnl_gn:{ptype}"
        user_prompts[chat_id] = prompt_id
        edit_bot_message(chat_id, prompt_id,
            f"{get_pemoji('note', '📝')} <b>Panel: {escape_html(tmp.get('name', ''))}</b>\n\n"
            f"এখন <b>Get Number API URL</b> দিন:\n"
            f"(ডিফল্ট: <code>{escape_html(default_gn)}</code>)",
            {"inline_keyboard": [
                [{"text": " Use Default", "callback_data": "adm_pnl_default:gn", "style": "success", "icon_custom_emoji_id": "5366231924597604153"}],
                [{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
            ]})
        return

    # --- New Panel Creation: Step 4 — Get Number API ---
    if state.startswith("add_pnl_gn:"):
        ptype = state.split(":")[1]
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        gn_url = text.strip()
        if not gn_url:
            edit_bot_message(chat_id, prompt_id,
                f"{get_pemoji('error', '❌')} URL খালি রাখা যাবে না। আবার পাঠান:",
                {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
            user_conversations[chat_id] = f"add_pnl_gn:{ptype}"
            user_prompts[chat_id] = prompt_id
            return
        tmp = panel_creation_temp.get(chat_id, {})
        tmp["getNumberUrl"] = gn_url
        panel_creation_temp[chat_id] = tmp
        prompt_for_get_message(chat_id, prompt_id, tmp)
        return

    # --- New Panel Creation: Step 5 — Get Message API ---
    if state.startswith("add_pnl_gm:"):
        ptype = state.split(":")[1]
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        gm_url = text.strip()
        if not gm_url:
            edit_bot_message(chat_id, prompt_id,
                f"{get_pemoji('error', '❌')} URL খালি রাখা যাবে না। আবার পাঠান:",
                {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
            user_conversations[chat_id] = f"add_pnl_gm:{ptype}"
            user_prompts[chat_id] = prompt_id
            return
        tmp = panel_creation_temp.get(chat_id, {})
        tmp["getMessageUrl"] = gm_url
        panel_creation_temp[chat_id] = tmp
        prompt_for_traffic(chat_id, prompt_id, tmp)
        return

    # --- New Panel Creation: Step 6 — Traffic API → Create Panel ---
    if state.startswith("add_pnl_tr:"):
        ptype = state.split(":")[1]
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        tr_url = text.strip()
        if not tr_url:
            edit_bot_message(chat_id, prompt_id,
                f"{get_pemoji('error', '❌')} URL খালি রাখা যাবে না। আবার পাঠান:",
                {"inline_keyboard": [[{"text": " Cancel", "callback_data": "adm_pnl_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
            user_conversations[chat_id] = f"add_pnl_tr:{ptype}"
            user_prompts[chat_id] = prompt_id
            return
        tmp = panel_creation_temp.get(chat_id, {})
        tmp["trafficUrl"] = tr_url
        panel_creation_temp[chat_id] = tmp
        finalize_panel_creation(chat_id, prompt_id)
        return

    if not text:
        return

    # 🚀 Track Unique Users for Admin DB
    is_new_user = chat_id not in admin_db.get("users", []) and str(chat_id) not in admin_db.get("users", [])
    if is_new_user:
        if "users" not in admin_db:
            admin_db["users"] = []
        admin_db["users"].append(chat_id)
        save_admin_db()
        # Background Auto-Sync to Firebase
        threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
        
    lower = text.lower()
    logger.info(f"Inbound chat message [ID={chat_id}]: '{text}'")

    # 📝 /start এর সাথে আসা ref_ প্যারামিটার ফোর্স জয়েন চেকের আগেই ধরে রাখো,
    # নাহলে চ্যানেলে জয়েন না-করা নতুন ইউজারের রেফারেল হারিয়ে যায় (আগে এখানেই বাগ ছিল)
    if lower.startswith("/start"):
        raw_parts = text.split()
        if len(raw_parts) > 1 and raw_parts[1].startswith("ref_"):
            try:
                referrer_id = raw_parts[1].replace("ref_", "").strip()
                if referrer_id.isdigit() and is_new_user:
                    pending_referrals[chat_id] = referrer_id
            except Exception:
                pass

    # 🛡️ Force Join Check Middleware
    if not check_force_join(chat_id):
        return

    # ✅ Force Join পাস হলে (বা লাগবেই না), জমা রাখা রেফারেল থাকলে এখন প্রসেস করো
    ref_id = pending_referrals.pop(chat_id, None)
    if ref_id:
        threading.Thread(target=process_referral, args=(chat_id, ref_id, True), daemon=True).start()

    # Handle Admin Panel Option
    if "admin panel" in lower or lower == "/admin":
        render_admin_panel(chat_id)
        return

    # Handle Start/Menu commands ONLY
    if lower.startswith("/start") or lower in ["/help", "/menu"]:
        raw_parts = text.split()
        text_start = (
            "╔═══════════╗\n"
            f"       {get_pemoji('dashboard', '📊')} <b>NUMBER BOT</b>\n"
            "╚═══════════╝\n"
            f"{get_pemoji('rocket', '🚀')} Welcome to Number & OTP Service\n"
            "━━━━━━━━━━━━\n"
            f"{get_pemoji('done', '✅')} Choose an option below\n"
            "to continue using the bot.\n"
            "━━━━━━━━━━━━\n"
            f"{get_pemoji('gem', '💎')} Premium OTP Service"
        )
        # শুধু ওয়েলকাম মেসেজ এবং নিচের কীবোর্ড দেবে
        send_bot_message(chat_id, text_start, get_bot_menu_keyboard(chat_id))
        return

    # Handle Refer button
    if "refer" in lower or lower == "/refer":
        render_refer_page(chat_id)
        return

    # Handle Get Number command ONLY
    if "get number" in lower:
        # শুধু Get Number এ চাপ দিলে সার্ভিস লিস্ট দেবে
        render_services_list(chat_id)
        return

    # Handle Master Menu Commands
    if "2fa setup" in lower or "2fa online" in lower or lower == "/2fa":
        user_conversations[chat_id] = "waiting_for_2fa"
        text_help = (
            "╔═══════════╗\n"
            f"     {get_pemoji('otp', '🔐')} <b>2FA ONLINE</b>\n"
            "╚═══════════╝\n"
            f"{get_pemoji('done', '📌')} Send your 2FA Secret Key\n"
            "to generate the 6-digit code.\n"
            "━━━━━━━━━━━━━\n"
            f"{get_pemoji('note', '📝')} Example: <code>JBSWY3DPEHPK3PXP</code>"
        )
        res = send_bot_message(chat_id, text_help, {"inline_keyboard": [[{"text": " Cancel", "callback_data": "cancel_2fa", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        # প্রম্পট মেসেজের আইডি সেভ করা হলো যাতে পরে এডিট করা যায়
        if res and res.get("result"):
            user_prompts[chat_id] = res["result"]["message_id"]
        return

    if "search range" in lower or "search number" in lower or lower == "/search":
        user_conversations[chat_id] = "waiting_for_search"
        text_help = (
            "╔═══════════╗\n"
            f"     {get_pemoji('search', '🔍')} <b>Search Number</b>\n"
            "╚═══════════╝\n"
            f"{get_pemoji('done', '📌')} Enter 3 to 11 digits  \n"
            "to search for a number.\n"
            "━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id='5395444784611480792'>📝</tg-emoji> Example:\n"
            "➥ 880\n"
            "➥ 9227373\n"
            "━━━━━━━━━━━━━\n"
            f"{get_pemoji('search', '🔍')} Fast Number Lookup System"
        )
        send_bot_message(chat_id, text_help, {"inline_keyboard": [[{"text": " Back", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]})
        return

    if lower.startswith("/search "):
        query = text[8:].strip()
        if query:
            q_sanit = query.replace("+", "").strip()
            # X বা * মুছে ফেলে শুধু মূল নাম্বার বের করা হচ্ছে
            base_digits = re.sub(r'[Xx*]', '', q_sanit)
            
            valid_panels = panels
            if not valid_panels:
                send_bot_message(chat_id, f"{get_pemoji('error', '❌')} No active panels available.")
                return
            chosen_panel_id = random.choice(valid_panels)["id"]
            
            # ৩ থেকে ১১ ডিজিট হলে XXX যুক্ত করে নতুন নাম্বার আনবে
            if base_digits.isdigit() and 3 <= len(base_digits) <= 11:
                trigger_buy_number(chat_id, base_digits + "XXX", chosen_panel_id)
            else:
                search_number_otp(chat_id, base_digits)
        else:
            send_bot_message(chat_id, "❌ Please specify a number to search. Usage: <code>/search 237620610123</code>")
        return

    if "traffic" in lower or lower == "/traffic":
        render_traffic_home(chat_id)
        return

    if "balance" in lower or "withdrawal" in lower or lower == "/balance" or lower == "/withdraw":
        render_user_balance(chat_id)
        return

    if "task" in lower or lower == "/task":
        render_user_task(chat_id)
        return

    if "support" in lower or lower == "/support":
        support_cfg = admin_db.get("redox_config", {})
        support_link = support_cfg.get("support_link", "")
        sup_text = f"{get_pemoji('support', '🫂')} Contact us for any help:"
        sup_kb = []
        if support_link:
            sup_kb.append([{"text": " Contact Support", "url": support_link, "style": "success", "icon_custom_emoji_id": "5201732344993576400"}])
        else:
            sup_kb.append([{"text": " Support not configured", "callback_data": "noop", "style": "primary", "icon_custom_emoji_id": "5201732344993576400"}])
        sup_kb.append([{"text": " Close", "callback_data": "usr_menu_home", "style": "danger", "icon_custom_emoji_id": "5420130255174145507"}])
        send_bot_message(chat_id, sup_text, {"inline_keyboard": sup_kb})
        return

    # Direct allocation hooks format buy/get/getnum
    if lower.startswith(("/getnum ", "/buy ", "/get ")):
        parts = text.split()
        if len(parts) > 1:
            q_rang = parts[-1].replace("+", "").strip()
            if 'x' in q_rang.lower():
                trigger_buy_number(chat_id, q_rang.upper())
            elif q_rang.isdigit() and len(q_rang) <= 9:
                trigger_buy_number(chat_id, q_rang + "XXX")
            else:
                trigger_buy_number(chat_id, q_rang)
        else:
            send_bot_message(chat_id, "❌ Please specify a range. Usage: <code>/getnum 237620610XXX</code>")
        return

    if user_conversations.get(chat_id) == "waiting_for_2fa":
        secret = text.strip()
        user_conversations.pop(chat_id, None)
        prompt_id = user_prompts.pop(chat_id, None)
        
        # ইউজারের পাঠানো মেসেজটি (Secret Key) ডিলিট করে দেওয়া হচ্ছে
        call_telegram("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
        
        code = get_totp_token(secret)
        if code:
            msg_text = (
                f"╔═══════════╗\n"
                f"     {get_pemoji('otp', '🔐')} <b>2FA CODE GENERATED</b>\n"
                f"╚═══════════╝\n"
                f"<b>Secret:</b> <code>{secret}</code>\n"
                f"━━━━━━━━━━━━━\n"
                f"{get_pemoji('done', '✅')} <b>Code:</b> <code>{code}</code>\n"
                f"<i>(This code is valid for 30 seconds)</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": " Refresh Code", "callback_data": f"refresh_2fa:{secret}", "style": "success", "icon_custom_emoji_id": "5465368548702446780"}],
                [{"text": " Close", "callback_data": "cancel_2fa", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]
            ]}
            if prompt_id:
                edit_bot_message(chat_id, prompt_id, msg_text, kb)
            else:
                send_bot_message(chat_id, msg_text, kb)
        else:
            err_text = f"{get_pemoji('error', '❌')} Invalid 2FA Secret Key format. Please ensure you entered the correct key."
            err_kb = {"inline_keyboard": [[{"text": " Close", "callback_data": "cancel_2fa", "style": "danger", "icon_custom_emoji_id": "5267490665117275176"}]]}
            if prompt_id:
                edit_bot_message(chat_id, prompt_id, err_text, err_kb)
            else:
                send_bot_message(chat_id, err_text, err_kb)
        return

    # Process raw numerical values ONLY IF in search state
    if user_conversations.get(chat_id) == "waiting_for_search":
        user_conversations.pop(chat_id, None)  # ইনপুট নেওয়ার পর state ক্লিয়ার করে দেবে
        clean_text = text.replace("+", "").strip()
        # X বা * মুছে ফেলে শুধু মূল নাম্বার বের করা হচ্ছে
        base_digits = re.sub(r'[Xx*]', '', clean_text)

        valid_panels = panels
        if not valid_panels:
            send_bot_message(chat_id, f"{get_pemoji('error', '❌')} No active panels available.")
            return
        chosen_panel_id = random.choice(valid_panels)["id"]

        if base_digits.isdigit():
            # ৩ থেকে ১১ ডিজিট হলে XXX যুক্ত করে নতুন নাম্বার আনবে
            if 3 <= len(base_digits) <= 11:
                trigger_buy_number(chat_id, base_digits + "XXX", chosen_panel_id)
            else:
                search_number_otp(chat_id, base_digits)
            return
        else:
            send_bot_message(chat_id, "❌ Invalid format. Please enter a valid number or range.")
            return

    # General unknown prompt Fallback (Disabled)
    pass

# ----------------------------------------------------
# Background Panel Periodic SMS Forwarder Checks Thread
# ----------------------------------------------------

def check_cdrs_for_panel(panel):
    global local_traffic_stats, local_raw_logs_cache
    session = get_session(panel["id"])
    baseUrl = normalize_base_url(panel["url"])

    try:
        clean_base = get_clean_base_url(panel, baseUrl)
        logs_url = panel.get("trafficUrl") or f"{clean_base}/console"
        otp_url = panel.get("getMessageUrl") or f"{clean_base}/success-otp"
        headers = {"Content-Type": "application/json", "mauthapi": panel.get("sessionCookie", "MKJGS2MSZYB")}
        
        # 1. Traffic Fetch
        res = session.get(logs_url, headers=headers, timeout=20)
        if res.status_code == 200:
            data = res.json()
            hits = data.get("data", {}).get("hits", [])
            if isinstance(hits, list):
                ref_time = get_current_cest_time()
                if panel.get("is_traffic_active", True):
                    for log in hits:
                        log_id = f"{log.get('time')}_{log.get('range')}_{str(log.get('message', ''))[:5]}"
                        if log_id: local_raw_logs_cache[log_id] = {
                            "time": get_current_cest_time(),
                            "app_name": log.get("sid", "OTP"),
                            "number": log.get("range", ""),
                            "range": log.get("range", "")
                        }
                    
                new_stats = {}
                keys_to_delete = []
                for log_id, log_data in local_raw_logs_cache.items():
                    if get_seconds_difference(log_data.get("time", ""), ref_time) <= 600:
                        display_service = get_service_display_name(log_data.get("app_name") or "Unknown")
                        num = log_data.get("number") or ""
                        c_code = get_country_code(num)
                        range_val = log_data.get("range") or get_range_from_number(num)

                        new_stats.setdefault(display_service, {}).setdefault(c_code, {"success": 0, "ranges": {}})
                        new_stats[display_service][c_code]["success"] += 1
                        new_stats[display_service][c_code]["ranges"][range_val] = new_stats[display_service][c_code]["ranges"].get(range_val, 0) + 1
                    else:
                        keys_to_delete.append(log_id)
                for k in keys_to_delete: del local_raw_logs_cache[k]
                local_traffic_stats = new_stats
        
        # 2. OTP Fetch
        otp_res = session.get(otp_url, headers=headers, timeout=20)
        if otp_res.status_code == 200:
            otp_data = otp_res.json()
            otps = otp_data.get("data", {}).get("otps", [])
            if isinstance(otps, list):
                updated = False
                if "lastSeenGetnumIds" not in panel or not isinstance(panel["lastSeenGetnumIds"], list):
                    panel["lastSeenGetnumIds"] = []
                
                is_initial = len(panel["lastSeenGetnumIds"]) == 0

                for item in otps:
                    unique_key = str(item.get("otp_id", ""))
                    msg = str(item.get("message", "")).strip()
                    num = str(item.get("number", ""))
                    
                    if unique_key and msg and unique_key not in panel["lastSeenGetnumIds"]:
                        if is_initial:
                            panel["lastSeenGetnumIds"].append(unique_key)
                            updated = True
                        else:
                            logger.info(f"[{panel['name']}] Forwarding Stex API SMS: {num}")
                            process_and_send_sms(panel['name'], f"+{num}", "OTP", msg)
                            panel["lastSeenGetnumIds"].append(unique_key)
                            updated = True

                if len(panel["lastSeenGetnumIds"]) > 200: panel["lastSeenGetnumIds"] = panel["lastSeenGetnumIds"][-200:]
                if updated: save_panels_to_file(panels)

    except Exception as e:
        logger.error(f"[{panel['name']}] Error polling Stex API: {e}")

def monitor_loop():
    logger.info("Background Panel Monitoring Loop Thread started successfully.")
    sync_counter = 0
    while True:
        try:
            for panel in panels:
                check_cdrs_for_panel(panel)
            
            # 🚀 Auto Sync to Firebase every ~5 minutes (30 loops * 10s)
            sync_counter += 1
            if sync_counter >= 30:
                threading.Thread(target=sync_essential_data_to_firestore, daemon=True).start()
                sync_counter = 0
                
        except Exception as e:
            logger.error(f"Global panel check monitor loop exception: {e}")
        time.sleep(10)

# ----------------------------------------------------
# Main Program Entry Point
# ----------------------------------------------------

def main():
    logger.info("Initializing Voltx API Unified Bot...")
    
    # Run immediate validation of panel logins
    for panel in panels:
        threading.Thread(target=login_to_panel, args=(panel,), daemon=True).start()

    # Start automated background checker thread
    threading.Thread(target=monitor_loop, daemon=True).start()

    # 📊 Real-Time Stats Auto-Post checker thread (আসল ডেটা দিয়ে OTP গ্রুপে পোস্ট করে)
    threading.Thread(target=stats_broadcast_loop, daemon=True).start()

    # Empty old commands in getUpdates queue to prevent old triggers
    call_telegram("getUpdates", {"offset": -1, "timeout": 0})
    logger.info("REDOX Telegram Long-Polling Engine online and watching.")

    offset = None
    while True:
        try:
            payload = {"timeout": 30}
            if offset:
                payload["offset"] = offset

            updates = call_telegram("getUpdates", payload)
            if updates and updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1

                    # Core processing routers (Multi-threading added for 0 lag)
                    if "message" in update:
                        threading.Thread(target=handle_message, args=(update["message"],)).start()
                    elif "callback_query" in update:
                        threading.Thread(target=handle_callback_query, args=(update["callback_query"],)).start()
                    elif "chat_join_request" in update:
                        threading.Thread(target=handle_join_request, args=(update["chat_join_request"],)).start()

            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down bot. Enjoy your day!")
            break
        except Exception as e:
            logger.error(f"Main polling loop error: {e}")
            time.sleep(5)

# ══════════════════════════════════════════════
# 🌐 KEEP ALIVE (Replit ঘুমাতে না দেওয়ার জন্য — UptimeRobot ping করবে এই সার্ভারে)
# ══════════════════════════════════════════════
def run_keep_alive_server():
    try:
        from flask import Flask
        keep_alive_app = Flask('')

        @keep_alive_app.route('/')
        def home():
            return "Bot is alive! ✅"

        keep_alive_app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Keep-alive server error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_keep_alive_server, daemon=True).start()
    main()
