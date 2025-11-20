import os
import asyncio
import aiohttp
import json
import sqlite3
import random
import string
import csv
import io
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Your Bot Token
BOT_TOKEN = "8355267281:AAEKyaRl68v75tFUBg9C5yYqipjoR-lVFQU"
ADMIN_IDS = [8333354105]

PREMIUM_PLANS = {
    "10": {"credits": 10, "price": "₹20", "name": "10 Credits - ₹20"},
    "25": {"credits": 25, "price": "₹40", "name": "25 Credits - ₹40"}, 
    "50": {"credits": 50, "price": "₹70", "name": "50 Credits - ₹70"},
    "100": {"credits": 100, "price": "₹120", "name": "100 Credits - ₹120"},
    "250": {"credits": 250, "price": "₹250", "name": "250 Credits - ₹250"},
    "500": {"credits": 500, "price": "₹450", "name": "500 Credits - ₹450"},
    "1000": {"credits": 1000, "price": "₹800", "name": "1000 Credits - ₹800"}
}

# Create data directory if not exists
if not os.path.exists('search_data'):
    os.makedirs('search_data')

# Database setup
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Drop old tables if they exist
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS promo_codes")
    c.execute("DROP TABLE IF EXISTS promo_usage")
    c.execute("DROP TABLE IF EXISTS search_history")
    
    # Create new tables with all columns
    c.execute('''CREATE TABLE users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, credits INTEGER DEFAULT 0, 
                  is_blocked BOOLEAN DEFAULT FALSE, join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_daily_date DATE, total_searches INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE promo_codes 
                 (code TEXT PRIMARY KEY, credits INTEGER DEFAULT 0, max_uses INTEGER DEFAULT 1, 
                  used_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  expires_at TIMESTAMP, is_active BOOLEAN DEFAULT TRUE)''')
    c.execute('''CREATE TABLE promo_usage 
                 (user_id INTEGER, code TEXT, used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  PRIMARY KEY (user_id, code))''')
    c.execute('''CREATE TABLE search_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, number TEXT, 
                  search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, result_data TEXT)''')
    conn.commit()
    conn.close()
    print("Database initialized with all columns!")

def get_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, credits) VALUES (?, ?, 10)", (user_id, username))
    conn.commit()
    conn.close()

def update_credits(user_id, credits):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (credits, user_id))
    conn.commit()
    conn.close()

def increment_searches(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET total_searches = total_searches + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_search_history(user_id, number, result_data):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO search_history (user_id, number, result_data) VALUES (?, ?, ?)", 
              (user_id, number, json.dumps(result_data)))
    conn.commit()
    conn.close()

def save_search_to_file(user_id, username, number, result_data):
    """Save search result to a text file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"search_data/{number}_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"🔍 NUMBER SEARCH REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"📱 Searched Number: {number}\n")
        f.write(f"👤 User ID: {user_id}\n")
        f.write(f"👥 Username: @{username or 'Unknown'}\n")
        f.write(f"📅 Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        
        if result_data and isinstance(result_data, dict):
            info = result_data
            f.write("📊 INFORMATION FOUND:\n")
            f.write("-" * 30 + "\n")
            
            if info.get('number'):
                f.write(f"📱 Number: {info.get('number')}\n")
            
            if info.get('name'):
                f.write(f"👤 Name: {info.get('name')}\n")
            
            if info.get('operator'):
                f.write(f"📞 Operator: {info.get('operator')}\n")
            
            if info.get('circle'):
                f.write(f"🌐 Circle: {info.get('circle')}\n")
            
            if info.get('state'):
                f.write(f"🏠 State: {info.get('state')}\n")
            
            if info.get('series'):
                f.write(f"🔢 Series: {info.get('series')}\n")
            
            if info.get('number_type'):
                f.write(f"📋 Number Type: {info.get('number_type')}\n")
            
            if info.get('location'):
                f.write(f"📍 Location: {info.get('location')}\n")
        else:
            f.write("❌ No information found for this number.\n")
    
    return filename

def get_all_search_files():
    """Get all search data files"""
    if not os.path.exists('search_data'):
        return []
    
    files = []
    for filename in os.listdir('search_data'):
        if filename.endswith('.txt'):
            file_path = os.path.join('search_data', filename)
            file_stats = os.stat(file_path)
            files.append({
                'filename': filename,
                'path': file_path,
                'size': file_stats.st_size,
                'created_time': datetime.fromtimestamp(file_stats.st_ctime)
            })
    
    # Sort by creation time (newest first)
    files.sort(key=lambda x: x['created_time'], reverse=True)
    return files

def get_search_history_data():
    """Get all search history from database"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''SELECT sh.id, sh.user_id, u.username, sh.number, sh.search_date, sh.result_data
                 FROM search_history sh
                 LEFT JOIN users u ON sh.user_id = u.user_id
                 ORDER BY sh.search_date DESC''')
    searches = c.fetchall()
    conn.close()
    return searches

def set_credits(user_id, credits):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = ? WHERE user_id = ?", (credits, user_id))
    conn.commit()
    conn.close()

def give_daily_credits(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    today = datetime.now().date()
    
    # Check if user already got daily credits today
    c.execute("SELECT last_daily_date FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result and result[0]:
        last_date = datetime.fromisoformat(result[0]).date()
        if last_date == today:
            conn.close()
            return False  # Already claimed today
    
    # Give 10 daily credits (increased from 3 to 10)
    c.execute("UPDATE users SET credits = credits + 10, last_daily_date = ? WHERE user_id = ?", (today, user_id))
    conn.commit()
    conn.close()
    return True

def block_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unblock_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = FALSE WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_blocked(user_id):
    user = get_user(user_id)
    return user and user[3]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, credits, is_blocked, join_date, last_daily_date, total_searches FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_all_users_data():
    """Get complete users data with search history"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Get users with their search counts
    c.execute('''SELECT u.user_id, u.username, u.credits, u.is_blocked, u.join_date, 
                        u.last_daily_date, u.total_searches,
                        COUNT(DISTINCT sh.id) as total_searches_detailed,
                        COUNT(DISTINCT pu.code) as promo_used
                 FROM users u
                 LEFT JOIN search_history sh ON u.user_id = sh.user_id
                 LEFT JOIN promo_usage pu ON u.user_id = pu.user_id
                 GROUP BY u.user_id''')
    
    users_data = c.fetchall()
    conn.close()
    return users_data

def generate_promo_code(length=8):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def create_premium_promo_code(credits, max_uses=1, expires_days=30):
    code = generate_promo_code()
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    expires_at = datetime.now() + timedelta(days=expires_days)
    c.execute('''INSERT INTO promo_codes (code, credits, max_uses, expires_at) 
                 VALUES (?, ?, ?, ?)''', (code, credits, max_uses, expires_at))
    conn.commit()
    conn.close()
    return code

def use_promo_code(user_id, code):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Check if promo code exists
    c.execute('''SELECT credits, max_uses, used_count, expires_at, is_active 
                 FROM promo_codes WHERE code = ?''', (code,))
    promo_data = c.fetchone()
    
    if not promo_data: 
        conn.close()
        return False, "❌ Invalid promo code!"
    
    credits, max_uses, used_count, expires_at, is_active = promo_data
    
    # Check if promo code is active
    if not is_active: 
        conn.close()
        return False, "❌ This promo code has been deactivated!"
    
    # Check if promo code has expired
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at): 
        conn.close()
        return False, "❌ This promo code has expired!"
    
    # Check if usage limit reached
    if used_count >= max_uses: 
        conn.close()
        return False, "❌ This promo code has reached its usage limit!"
    
    # Check if user already used this code
    c.execute("SELECT 1 FROM promo_usage WHERE user_id = ? AND code = ?", (user_id, code))
    if c.fetchone(): 
        conn.close()
        return False, "❌ You have already used this promo code!"
    
    # Apply promo code
    try:
        c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
        c.execute("INSERT INTO promo_usage (user_id, code) VALUES (?, ?)", (user_id, code))
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (credits, user_id))
        conn.commit()
        conn.close()
        return True, f"✅ Promo code applied! 🎉\n💰 {credits} credits added to your account!"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"❌ Error applying promo code: {str(e)}"

def get_promo_codes():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''SELECT code, credits, max_uses, used_count, expires_at, is_active 
                 FROM promo_codes''')
    promos = c.fetchall()
    conn.close()
    return promos

def get_main_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("🔍 Number Information", callback_data="get_info")],
        [InlineKeyboardButton("💰 My Credits", callback_data="my_credits")],
        [InlineKeyboardButton("🎁 Daily Credits", callback_data="daily_credits")],
        [InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data="redeem_code")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/Rohit_x_official_1")]
    ]
    if is_admin(user_id): 
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_search_only_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Search Again", callback_data="get_info")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Users Data Export", callback_data="export_users_data")],
        [InlineKeyboardButton("📁 All Search Files", callback_data="admin_search_files")],
        [InlineKeyboardButton("🔍 Search History", callback_data="admin_search_history")],
        [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("🎫 Generate Premium Code", callback_data="generate_premium")],
        [InlineKeyboardButton("📋 Promo Codes List", callback_data="admin_promos")],
        [InlineKeyboardButton("🚫 Block User", callback_data="admin_block")],
        [InlineKeyboardButton("✅ Unblock User", callback_data="admin_unblock")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_premium_plans_keyboard():
    keyboard = []
    plans_list = list(PREMIUM_PLANS.items())
    for i in range(0, len(plans_list), 2):
        row = []
        for j in range(2):
            if i + j < len(plans_list):
                plan_id, plan_data = plans_list[i + j]
                row.append(InlineKeyboardButton(f"🎫 {plan_data['name']}", callback_data=f"generate_{plan_id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_buy_credits_keyboard():
    keyboard = []
    plans_list = list(PREMIUM_PLANS.items())
    for i in range(0, len(plans_list), 2):
        row = []
        for j in range(2):
            if i + j < len(plans_list):
                plan_id, plan_data = plans_list[i + j]
                row.append(InlineKeyboardButton(f"💳 {plan_data['name']}", callback_data=f"buy_{plan_id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("📞 Contact for Payment", url="https://t.me/Dark_x_gokjuu")])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])

async def export_users_to_csv():
    """Export all users data to CSV file"""
    users_data = get_all_users_data()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'User ID', 'Username', 'Credits', 'Status', 
        'Join Date', 'Last Daily', 'Total Searches',
        'Detailed Searches', 'Promo Codes Used'
    ])
    
    # Write data
    for user in users_data:
        user_id, username, credits, is_blocked, join_date, last_daily, total_searches, detailed_searches, promo_used = user
        
        status = "Blocked" if is_blocked else "Active"
        username = username or "No Username"
        last_daily = last_daily or "Never"
        
        writer.writerow([
            user_id, username, credits, status,
            join_date, last_daily, total_searches,
            detailed_searches, promo_used
        ])
    
    # Get CSV content
    csv_content = output.getvalue()
    output.close()
    
    return csv_content

async def export_search_history_to_csv():
    """Export all search history to CSV file"""
    search_data = get_search_history_data()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Search ID', 'User ID', 'Username', 'Number', 
        'Search Date', 'Results Count'
    ])
    
    # Write data
    for search in search_data:
        search_id, user_id, username, number, search_date, result_data = search
        
        # Parse result data to count results
        results_count = 0
        if result_data:
            try:
                data = json.loads(result_data)
                if data:
                    results_count = 1
            except:
                pass
        
        writer.writerow([
            search_id, user_id, username or 'Unknown', number,
            search_date, results_count
        ])
    
    # Get CSV content
    csv_content = output.getvalue()
    output.close()
    
    return csv_content

async def get_number_info_api(number):
    try:
        clean_number = ''.join(filter(str.isdigit, number))
        if len(clean_number) == 10: 
            mobile = clean_number
        elif len(clean_number) == 11 and clean_number.startswith('0'): 
            mobile = clean_number[1:]
        elif len(clean_number) == 12 and clean_number.startswith('91'): 
            mobile = clean_number[2:]
        else: 
            return False, "❌ Invalid Number Format"
        
        print(f"DEBUG: Calling Akash Hacker API with mobile: {mobile}")
        
        async with aiohttp.ClientSession() as session:
            api_url = f"https://akashhacker.gt.tc/?number={mobile}&key=AKASHHACKER"
            print(f"DEBUG: API URL: {api_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://akashhacker.gt.tc/',
                'Origin': 'https://akashhacker.gt.tc'
            }
            
            async with session.get(api_url, headers=headers, timeout=30) as response:
                print(f"DEBUG: API Response Status: {response.status}")
                
                if response.status == 200: 
                    # Try to parse as JSON first
                    try:
                        data = await response.json()
                        print(f"DEBUG: API JSON Response: {data}")
                        
                        # Check if API returned valid data
                        if data and isinstance(data, dict):
                            return True, data
                        else:
                            return False, "❌ No valid information found"
                            
                    except json.JSONDecodeError:
                        # If JSON fails, try to get text response
                        text_response = await response.text()
                        print(f"DEBUG: API Text Response: {text_response}")
                        
                        # Try to extract JSON from text if it contains JSON
                        if '{' in text_response and '}' in text_response:
                            try:
                                # Extract JSON part from text
                                start_idx = text_response.find('{')
                                end_idx = text_response.rfind('}') + 1
                                json_str = text_response[start_idx:end_idx]
                                data = json.loads(json_str)
                                return True, data
                            except:
                                pass
                        
                        if text_response and any(keyword in text_response.lower() for keyword in ['number', 'name', 'operator', 'circle']):
                            # Try to extract information from text
                            return True, {"raw_response": text_response}
                        else:
                            return False, "❌ No information found for this number"
                else: 
                    return False, f"❌ API Error: Status {response.status}"
                    
    except asyncio.TimeoutError:
        return False, "❌ API timeout: Please try again later"
    except Exception as e: 
        print(f"DEBUG: API Exception: {str(e)}")
        return False, f"❌ Error: {str(e)}"

def format_number_info(api_data, number):
    try:
        # Check if API returned proper data structure
        if api_data and isinstance(api_data, dict):
            info = api_data
            
            result_text = f"🔍 NUMBER INFORMATION REPORT\n"
            result_text += "━━━━━━━━━━━━━━━━━━━━\n"
            result_text += f"📱 Searched Number: {number}\n\n"
            
            # Display all available fields from the API response
            fields_displayed = 0
            
            # Number field
            if info.get('number'):
                result_text += f"📱 Number: {info.get('number')}\n"
                fields_displayed += 1
            elif info.get('mobile'):
                result_text += f"📱 Number: {info.get('mobile')}\n"
                fields_displayed += 1
            else:
                result_text += f"📱 Number: {number}\n"
            
            # Name field
            if info.get('name'):
                result_text += f"👤 Name: {info.get('name')}\n"
                fields_displayed += 1
            
            # Operator field
            if info.get('operator'):
                result_text += f"📞 Operator: {info.get('operator')}\n"
                fields_displayed += 1
            
            # Circle field
            if info.get('circle'):
                result_text += f"🌐 Circle: {info.get('circle')}\n"
                fields_displayed += 1
            
            # State field
            if info.get('state'):
                result_text += f"🏠 State: {info.get('state')}\n"
                fields_displayed += 1
            
            # Series field
            if info.get('series'):
                result_text += f"🔢 Series: {info.get('series')}\n"
                fields_displayed += 1
            
            # Number Type field
            if info.get('number_type'):
                result_text += f"📋 Number Type: {info.get('number_type')}\n"
                fields_displayed += 1
            
            # Location field
            if info.get('location'):
                result_text += f"📍 Location: {info.get('location')}\n"
                fields_displayed += 1
            
            # Address field
            if info.get('address'):
                address = info.get('address')
                # Clean up the address format
                if '!' in address:
                    address_parts = [part.strip() for part in address.split('!') if part.strip()]
                    clean_address = ', '.join([part for part in address_parts if part])
                    result_text += f"🏠 Address: {clean_address}\n"
                else:
                    result_text += f"🏠 Address: {address}\n"
                fields_displayed += 1
            
            # If raw response contains data but no structured fields
            if fields_displayed == 0 and info.get('raw_response'):
                result_text += f"📄 Raw Data: {info.get('raw_response')}\n"
            
            result_text += f"\n✅ Data fetched from Akash Hacker API\n"
            result_text += f"📊 Total Fields Found: {fields_displayed}"
            return result_text
        
        # If no results found
        else:
            return f"""🔍 NUMBER INFORMATION REPORT
━━━━━━━━━━━━━━━━━━━━
📱 Searched Number: {number}

❌ No information found for this number.
💡 Try with a different number or check the format."""
            
    except Exception as e:
        return f"""🔍 NUMBER INFORMATION REPORT
━━━━━━━━━━━━━━━━━━━━
📱 Searched Number: {number}

❌ Error formatting data: {str(e)}"""

async def show_hacker_animation(update: Update, context: ContextTypes.DEFAULT_TYPE, number: str):
    """Show professional hacker-style animation"""
    
    # Progress bar animation with system messages
    progress_steps = [
        "█░░░░░░░░░ System Initializing...",
        "██░░░░░░░░ Accessing Database...",
        "███░░░░░░░ Connecting to Server...",
        "████░░░░░░ Scanning Networks...", 
        "█████░░░░░ Bypassing Security...",
        "██████░░░░ Collecting Data...",
        "███████░░░ Processing Information...",
        "████████░░ Finalizing Report...",
        "█████████░ Target Acquired...",
        "██████████ SYSTEM BYPASS COMPLETE"
    ]
    
    # Send initial message
    message = await update.message.reply_text("🚀 *Starting Deep Scan...*", parse_mode='Markdown')
    await asyncio.sleep(0.5)
    
    # Show progress bar animation
    for progress in progress_steps:
        await asyncio.sleep(0.7)
        try:
            await message.edit_text(f"`{progress}`", parse_mode='Markdown')
        except:
            continue
    
    # Final preparing message
    await asyncio.sleep(0.5)
    await message.edit_text("⚡ *Finalizing Report...*", parse_mode='Markdown')
    await asyncio.sleep(0.5)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    create_user(user_id, username)
    
    welcome_text = """🤖 *Welcome to Number Information Bot!*

🔍 *Get detailed information about any phone number*
💰 *10 FREE credits daily for every user*
🎁 *Redeem promo codes for more credits*

*Features:*
• Number carrier information
• Location details  
• Owner information
• Multiple results from database

*Daily Bonus:* 🎁 10 FREE credits every day!

Use the buttons below to get started!"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(user_id),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        await update.message.reply_text("❌ You are blocked from using this bot.")
        return
    
    text = update.message.text.strip()
    user = get_user(user_id)
    
    if not user:
        create_user(user_id, update.effective_user.username or "Unknown")
        user = get_user(user_id)
    
    print(f"DEBUG: User {user_id} sent: {text}")
    print(f"DEBUG: waiting_for_number: {context.user_data.get('waiting_for_number')}")
    
    # Check if user is in number input mode
    if context.user_data.get('waiting_for_number'):
        print("DEBUG: Processing number search...")
        
        if user[2] <= 0:
            await update.message.reply_text(
                "❌ You don't have enough credits! Please buy more credits or claim daily credits.",
                reply_markup=get_main_keyboard(user_id)
            )
            context.user_data['waiting_for_number'] = False
            return
        
        # Show processing message
        processing_msg = await update.message.reply_text("🔄 Processing your request...")
        
        try:
            # Deduct credit
            update_credits(user_id, -1)
            increment_searches(user_id)
            
            # Show hacker animation
            await show_hacker_animation(update, context, text)
            
            success, result = await get_number_info_api(text)
            
            if success:
                # Save to database
                add_search_history(user_id, text, result)
                
                # Save to file
                filename = save_search_to_file(user_id, user[1], text, result)
                print(f"DEBUG: Search saved to file: {filename}")
                
                formatted_info = format_number_info(result, text)
                
                # Add credits info at bottom
                current_user = get_user(user_id)
                formatted_info += f"\n\n✦ Bot by: @Rohit-X\n\n🪙 Credits left: {current_user[2]}"
                
                # Send with only search button
                await update.message.reply_text(
                    formatted_info,
                    parse_mode='Markdown',
                    reply_markup=get_search_only_keyboard()
                )
            else:
                # Refund credit if API failed
                update_credits(user_id, 1)
                await update.message.reply_text(
                    f"❌ Failed to fetch information: {result}",
                    reply_markup=get_main_keyboard(user_id)
                )
            
        except Exception as e:
            # Refund credit if any error occurs
            update_credits(user_id, 1)
            await update.message.reply_text(
                f"❌ Error processing your request: {str(e)}",
                reply_markup=get_main_keyboard(user_id)
            )
        
        finally:
            context.user_data['waiting_for_number'] = False
            try:
                await processing_msg.delete()
            except:
                pass
    
    # Check if user is entering promo code
    elif context.user_data.get('waiting_for_promo'):
        print("DEBUG: Processing promo code...")
        success, message = use_promo_code(user_id, text.upper())
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
        context.user_data['waiting_for_promo'] = False
    
    else:
        # If no specific mode is active, show main menu
        await update.message.reply_text(
            "Please use the buttons below to interact with the bot:",
            reply_markup=get_main_keyboard(user_id)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if is_blocked(user_id):
        await query.edit_message_text("❌ You are blocked from using this bot.")
        return
    
    if data == "back_main":
        await query.edit_message_text(
            "🏠 *Main Menu*",
            reply_markup=get_main_keyboard(user_id),
            parse_mode='Markdown'
        )
    
    elif data == "get_info":
        user = get_user(user_id)
        if user[2] <= 0:
            await query.edit_message_text(
                "❌ You don't have enough credits!\n\n"
                "💡 You can:\n"
                "• Claim 🎁 Daily Credits (10 FREE)\n"  
                "• 💳 Buy more credits\n"
                "• 🎫 Redeem promo code",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Set the flag for number input
        context.user_data['waiting_for_number'] = True
        print(f"DEBUG: Set waiting_for_number to True for user {user_id}")
        
        await query.edit_message_text(
            "🔢 *Please enter the phone number:*\n\n"
            "*Formats accepted:*\n"
            "• 9876543210\n"
            "• 09876543210\n"
            "• 919876543210\n\n"
            "ℹ️ *1 credit will be deducted*",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == "my_credits":
        user = get_user(user_id)
        await query.edit_message_text(
            f"💰 *Your Credits*\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"👤 Username: @{user[1] or 'N/A'}\n"
            f"💎 Available Credits: *{user[2]}*\n"
            f"🔍 Total Searches: *{user[6]}*\n"
            f"📅 Joined: {user[4]}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
    
    elif data == "daily_credits":
        success = give_daily_credits(user_id)
        if success:
            current_user = get_user(user_id)
            await query.edit_message_text(
                f"🎁 *Daily Credits Claimed!*\n\n"
                f"✅ 10 credits added to your account!\n"
                f"💰 Total Credits: *{current_user[2]}*\n\n"
                f"🔄 Come back tomorrow for more free credits!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await query.edit_message_text(
                "❌ *Already Claimed Today!*\n\n"
                "You have already claimed your daily credits today.\n"
                "Please come back tomorrow for more free credits!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )
    
    elif data == "buy_credits":
        await query.edit_message_text(
            "💳 *Buy Credits*\n\n"
            "Select a plan to purchase credits:",
            parse_mode='Markdown',
            reply_markup=get_buy_credits_keyboard()
        )
    
    elif data == "redeem_code":
        context.user_data['waiting_for_promo'] = True
        print(f"DEBUG: Set waiting_for_promo to True for user {user_id}")
        await query.edit_message_text(
            "🎫 *Redeem Promo Code*\n\n"
            "Please enter your promo code:",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    # Admin panel handlers
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        await query.edit_message_text(
            "👑 *Admin Panel*\n\n"
            "Select an option:",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
    
    elif data == "export_users_data":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        
        # Show processing message
        processing_msg = await query.edit_message_text(
            "📊 *Exporting Users Data...*\n\n"
            "Please wait while we generate the report...",
            parse_mode='Markdown'
        )
        
        try:
            # Generate CSV file
            csv_content = await export_users_to_csv()
            
            # Create file in memory
            file_bytes = io.BytesIO(csv_content.encode('utf-8'))
            file_bytes.name = f"users_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Get stats
            users_data = get_all_users_data()
            total_users = len(users_data)
            active_users = len([u for u in users_data if not u[3]])  # Not blocked
            total_searches = sum([u[6] for u in users_data])  # Total searches
            
            # Send file with stats
            caption = f"""📊 *Users Data Export Complete*

👥 Total Users: {total_users}
✅ Active Users: {active_users}
🚫 Blocked Users: {total_users - active_users}
🔍 Total Searches: {total_searches}

📅 Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Update processing message
            await processing_msg.edit_text(
                "✅ *Users Data Exported Successfully!*\n\n"
                "📁 CSV file has been sent to you.",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ *Error exporting data:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
    
    elif data == "admin_search_files":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        
        # Show processing message
        processing_msg = await query.edit_message_text(
            "📁 *Collecting Search Files...*\n\n"
            "Please wait while we gather all search data files...",
            parse_mode='Markdown'
        )
        
        try:
            search_files = get_all_search_files()
            
            if not search_files:
                await processing_msg.edit_text(
                    "❌ *No Search Files Found!*\n\n"
                    "No search data files have been created yet.",
                    parse_mode='Markdown',
                    reply_markup=get_admin_keyboard()
                )
                return
            
            # Create ZIP file with all search files
            import zipfile
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_info in search_files:
                    zip_file.write(file_info['path'], file_info['filename'])
            
            zip_buffer.seek(0)
            zip_buffer.name = f"all_search_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            # Send ZIP file
            caption = f"""📁 *All Search Files Export*

📊 Total Files: {len(search_files)}
📅 Latest File: {search_files[0]['created_time'].strftime('%Y-%m-%d %H:%M:%S')}
📅 Oldest File: {search_files[-1]['created_time'].strftime('%Y-%m-%d %H:%M:%S')}

🔍 Contains all number search data in text files."""
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=zip_buffer,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Update processing message
            await processing_msg.edit_text(
                f"✅ *Search Files Exported Successfully!*\n\n"
                f"📦 Total files: {len(search_files)}\n"
                f"📁 ZIP file has been sent to you.",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ *Error exporting search files:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
    
    elif data == "admin_search_history":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        
        # Show processing message
        processing_msg = await query.edit_message_text(
            "🔍 *Exporting Search History...*\n\n"
            "Please wait while we generate the search history report...",
            parse_mode='Markdown'
        )
        
        try:
            # Generate CSV file
            csv_content = await export_search_history_to_csv()
            
            # Create file in memory
            file_bytes = io.BytesIO(csv_content.encode('utf-8'))
            file_bytes.name = f"search_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Get stats
            search_data = get_search_history_data()
            total_searches = len(search_data)
            unique_users = len(set([s[1] for s in search_data]))
            unique_numbers = len(set([s[3] for s in search_data]))
            
            # Send file with stats
            caption = f"""🔍 *Search History Export Complete*

📊 Total Searches: {total_searches}
👥 Unique Users: {unique_users}
📱 Unique Numbers: {unique_numbers}

📅 Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # Update processing message
            await processing_msg.edit_text(
                "✅ *Search History Exported Successfully!*\n\n"
                "📁 CSV file has been sent to you.",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ *Error exporting search history:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
    
    elif data == "generate_premium":
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        await query.edit_message_text(
            "🎫 *Generate Premium Code*\n\n"
            "Select a plan to generate promo code:",
            parse_mode='Markdown',
            reply_markup=get_premium_plans_keyboard()
        )
    
    # Handle plan selection for generation
    elif data.startswith("generate_"):
        if not is_admin(user_id):
            await query.edit_message_text("❌ Access denied!")
            return
        
        plan_id = data.replace("generate_", "")
        if plan_id in PREMIUM_PLANS:
            plan_data = PREMIUM_PLANS[plan_id]
            promo_code = create_premium_promo_code(plan_data['credits'])
            
            await query.edit_message_text(
                f"✅ *Premium Code Generated!*\n\n"
                f"📦 Plan: {plan_data['name']}\n"
                f"💰 Credits: {plan_data['credits']}\n"
                f"🎫 Code: `{promo_code}`\n\n"
                f"*Share this code with users!*",
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
    
    # Handle buy credits plan selection
    elif data.startswith("buy_"):
        plan_id = data.replace("buy_", "")
        if plan_id in PREMIUM_PLANS:
            plan_data = PREMIUM_PLANS[plan_id]
            await query.edit_message_text(
                f"💳 *Purchase {plan_data['name']}*\n\n"
                f"📦 Plan: {plan_data['name']}\n"
                f"💰 Credits: {plan_data['credits']}\n"
                f"💵 Price: {plan_data['price']}\n\n"
                f"📞 *Contact @gokuuuu_1 for payment*",
                parse_mode='Markdown',
                reply_markup=get_buy_credits_keyboard()
            )

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()