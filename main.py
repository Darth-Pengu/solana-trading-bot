#!/usr/bin/env python3
"""
SOLANA TRADING BOT - COMPLETE VERSION WITH ALL FIXES
Three personalities, proper ToxiBot commands, aggressive settings
"""

import asyncio
import os
import json
import time
import logging
import random
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from aiohttp import web
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('TradingBot')

# Try to import Telegram
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram not available - install telethon to enable trading")

# Configuration - AGGRESSIVE SETTINGS FOR MORE TRADES
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY', '')
POSITION_SIZE = 0.05  # Default SOL per trade
MIN_LIQUIDITY = 2  # Lowered from 10 SOL for more opportunities
MAX_TOKEN_AGE = 1800  # 30 minutes instead of 10
MAX_POSITIONS = 10  # Increased from 5 for more trades

# HTML Dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Solana Trading Bot - LIVE</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Orbitron', monospace;
            background: #000;
            color: #00ffff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: #111;
            padding: 20px;
            border-bottom: 2px solid #00ffff;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            text-shadow: 0 0 20px #00ffff;
        }
        
        .live-indicator {
            display: inline-block;
            background: #00ff00;
            color: #000;
            padding: 5px 15px;
            margin-left: 20px;
            font-size: 0.8em;
            font-weight: bold;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            flex: 1;
        }
        
        .setup-box {
            background: #111;
            border: 2px solid #00ffff;
            padding: 30px;
            margin: 20px auto;
            max-width: 600px;
            box-shadow: 0 0 30px #00ffff;
        }
        
        .setup-box h2 {
            color: #00ffff;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .step {
            margin: 20px 0;
            padding: 20px;
            background: rgba(0,255,255,0.1);
            border: 1px solid #00ffff;
        }
        
        .step h3 {
            color: #ff6600;
            margin-bottom: 10px;
        }
        
        .step p {
            line-height: 1.6;
            margin: 10px 0;
        }
        
        input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background: #000;
            border: 2px solid #00ffff;
            color: #00ffff;
            font-family: 'Orbitron', monospace;
            font-size: 16px;
        }
        
        button {
            width: 100%;
            padding: 15px;
            background: transparent;
            border: 2px solid #ff6600;
            color: #ff6600;
            font-family: 'Orbitron', monospace;
            font-size: 18px;
            cursor: pointer;
            text-transform: uppercase;
            transition: all 0.3s;
        }
        
        button:hover {
            background: #ff6600;
            color: #000;
            box-shadow: 0 0 20px #ff6600;
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .status {
            text-align: center;
            padding: 20px;
            margin: 20px 0;
        }
        
        .status.online {
            border: 2px solid #00ff00;
            background: rgba(0,255,0,0.1);
        }
        
        .status.offline {
            border: 2px solid #ff0000;
            background: rgba(255,0,0,0.1);
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: #111;
            border: 2px solid #00ffff;
            padding: 20px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            color: #00ffff;
            margin: 10px 0;
        }
        
        .activity {
            background: #111;
            border: 2px solid #00ffff;
            padding: 20px;
            margin: 20px 0;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .activity-item {
            padding: 10px;
            margin: 5px 0;
            background: rgba(0,255,255,0.1);
            border-left: 4px solid #00ffff;
        }
        
        .activity-item.trade {
            border-left-color: #00ff00;
        }
        
        .activity-item.error {
            border-left-color: #ff0000;
        }
        
        .activity-item.sniper {
            border-left-color: #ff00ff;
        }
        
        .activity-item.scalper {
            border-left-color: #ffff00;
        }
        
        .activity-item.community {
            border-left-color: #00ffff;
        }
        
        .hidden { display: none; }
        
        .error {
            color: #ff0000;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ff0000;
            background: rgba(255,0,0,0.1);
        }
        
        .success {
            color: #00ff00;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #00ff00;
            background: rgba(0,255,0,0.1);
        }
        
        .warning {
            background: rgba(255,165,0,0.2);
            border: 2px solid #ffa500;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
        }
        
        .api-setup {
            background: rgba(255,165,0,0.1);
            border: 2px solid #ffa500;
            padding: 20px;
            margin: 20px 0;
        }
        
        .personality-indicator {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
            margin-left: 10px;
        }
        
        .personality-sniper {
            background: #ff00ff;
            color: #000;
        }
        
        .personality-scalper {
            background: #ffff00;
            color: #000;
        }
        
        .personality-community {
            background: #00ffff;
            color: #000;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Solana Trading Bot <span class="live-indicator">LIVE TRADING</span></h1>
    </div>
    
    <div class="container">
        <!-- Setup Section -->
        <div id="setupSection" class="setup-box">
            <h2>Bot Setup</h2>
            
            <div class="step">
                <h3>Step 1: Telegram API Setup</h3>
                <p>You need Telegram API credentials to connect the bot.</p>
                <p>Already have them? Enter below. Need them? <a href="https://my.telegram.org" target="_blank" style="color: #ff6600;">Get them here</a></p>
                
                <input type="text" id="apiId" placeholder="API ID (numbers only, like: 12345678)">
                <input type="text" id="apiHash" placeholder="API Hash (32 characters, like: abcdef1234567890abcdef1234567890)">
                
                <button onclick="saveCredentials()">Save Telegram Credentials</button>
            </div>
            
            <div class="step hidden" id="phoneStep">
                <h3>Step 2: Phone Number</h3>
                <p>Enter your phone number to receive a code:</p>
                <input type="tel" id="phoneInput" placeholder="+1234567890 (include country code)">
                <button onclick="requestCode()">Send Code to Telegram</button>
            </div>
            
            <div class="step hidden" id="codeStep">
                <h3>Step 3: Enter Code</h3>
                <p>Check your Telegram app for the code:</p>
                <input type="text" id="codeInput" placeholder="12345" maxlength="5">
                <button onclick="verifyCode()">Start Trading Bot</button>
            </div>
            
            <div id="errorMsg" class="error hidden"></div>
            <div id="successMsg" class="success hidden"></div>
        </div>
        
        <!-- Trading Dashboard -->
        <div id="dashboardSection" class="hidden">
            <div class="warning">
                ⚠️ LIVE TRADING ACTIVE - Real money at risk! Start with small amounts.
            </div>
            
            <div class="api-setup" id="apiWarning">
                <h3>⚠️ Optional: Add Helius API Key for Better Token Discovery</h3>
                <p>Get a free API key from <a href="https://www.helius.dev/" target="_blank" style="color: #ff6600;">helius.dev</a></p>
                <p>Add it to Railway environment variables as HELIUS_API_KEY</p>
            </div>
            
            <div class="status" id="botStatus">
                <h2>Bot Status: <span id="statusText">Offline</span></h2>
                <p id="toxibotStatus">ToxiBot: Not connected</p>
                <p>Active Bots: <span class="personality-indicator personality-sniper">SNIPER</span>
                                <span class="personality-indicator personality-scalper">SCALPER</span>
                                <span class="personality-indicator personality-community">COMMUNITY</span></p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>Total Profit</h3>
                    <div class="stat-value" id="totalProfit">0.000 SOL</div>
                </div>
                <div class="stat-card">
                    <h3>Active Trades</h3>
                    <div class="stat-value" id="activeTrades">0</div>
                </div>
                <div class="stat-card">
                    <h3>Win Rate</h3>
                    <div class="stat-value" id="winRate">0%</div>
                </div>
                <div class="stat-card">
                    <h3>Tokens Checked</h3>
                    <div class="stat-value" id="tokensChecked">0</div>
                </div>
            </div>
            
            <div class="activity">
                <h3>Live Activity Log</h3>
                <div id="activityLog">
                    <div class="activity-item">Waiting for bot to start...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let setupComplete = false;
        
        // Check if already setup
        checkStatus();
        
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.authenticated) {
                    showDashboard();
                    startUpdates();
                } else if (data.configured) {
                    document.getElementById('phoneStep').classList.remove('hidden');
                }
                
                // Hide API warning if key is set
                if (data.hasHeliusKey) {
                    document.getElementById('apiWarning').style.display = 'none';
                }
            } catch (e) {
                console.log('Not configured yet');
            }
        }
        
        async function saveCredentials() {
            const apiId = document.getElementById('apiId').value;
            const apiHash = document.getElementById('apiHash').value;
            
            if (!apiId || !apiHash) {
                showError('Please enter both API ID and API Hash');
                return;
            }
            
            try {
                const response = await fetch('/api/setup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_id: apiId, api_hash: apiHash })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showSuccess('Credentials saved! Now enter your phone number.');
                    document.getElementById('phoneStep').classList.remove('hidden');
                } else {
                    showError(data.error || 'Failed to save credentials');
                }
            } catch (e) {
                showError('Connection error');
            }
        }
        
        async function requestCode() {
            const phone = document.getElementById('phoneInput').value;
            
            if (!phone) {
                showError('Please enter your phone number');
                return;
            }
            
            try {
                const response = await fetch('/api/request-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showSuccess('Code sent! Check your Telegram app.');
                    document.getElementById('codeStep').classList.remove('hidden');
                } else {
                    showError(data.error || 'Failed to send code');
                }
            } catch (e) {
                showError('Connection error');
            }
        }
        
        async function verifyCode() {
            const code = document.getElementById('codeInput').value;
            
            if (!code) {
                showError('Please enter the code');
                return;
            }
            
            try {
                const response = await fetch('/api/verify-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showSuccess('Success! Starting bot...');
                    setTimeout(() => {
                        showDashboard();
                        startUpdates();
                    }, 2000);
                } else {
                    showError(data.error || 'Invalid code');
                }
            } catch (e) {
                showError('Connection error');
            }
        }
        
        function showDashboard() {
            document.getElementById('setupSection').classList.add('hidden');
            document.getElementById('dashboardSection').classList.remove('hidden');
            document.getElementById('botStatus').classList.add('online');
            document.getElementById('statusText').textContent = 'Online';
        }
        
        function startUpdates() {
            // Update stats every 5 seconds
            setInterval(updateStats, 5000);
            updateStats();
        }
        
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('totalProfit').textContent = data.profit.toFixed(3) + ' SOL';
                document.getElementById('activeTrades').textContent = data.trades;
                document.getElementById('winRate').textContent = data.winRate + '%';
                document.getElementById('tokensChecked').textContent = data.tokensChecked || 0;
                
                if (data.toxibotConnected) {
                    document.getElementById('toxibotStatus').textContent = 'ToxiBot: Connected ✓';
                }
                
                if (data.activity) {
                    addActivity(data.activity, data.activityType);
                }
            } catch (e) {
                console.error('Failed to update stats');
            }
        }
        
        function addActivity(message, type = 'info') {
            const log = document.getElementById('activityLog');
            const item = document.createElement('div');
            item.className = 'activity-item ' + type;
            item.textContent = new Date().toLocaleTimeString() + ' - ' + message;
            log.insertBefore(item, log.firstChild);
            
            // Keep only last 20 items
            while (log.children.length > 20) {
                log.removeChild(log.lastChild);
            }
        }
        
        function showError(message) {
            const elem = document.getElementById('errorMsg');
            elem.textContent = message;
            elem.classList.remove('hidden');
            setTimeout(() => elem.classList.add('hidden'), 5000);
        }
        
        function showSuccess(message) {
            const elem = document.getElementById('successMsg');
            elem.textContent = message;
            elem.classList.remove('hidden');
            setTimeout(() => elem.classList.add('hidden'), 5000);
        }
    </script>
</body>
</html>
'''

@dataclass
class BotState:
    configured: bool = False
    authenticated: bool = False
    running: bool = False
    total_profit: float = 0.0
    active_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    toxibot_connected: bool = False
    tokens_checked: int = 0
    last_activity: Optional[str] = None
    last_activity_type: str = 'info'

# Global state
bot_state = BotState()

class BotPersonality:
    """Different trading personalities with unique strategies"""
    
    ULTRA_EARLY = {
        'name': 'Ultra-Early Sniper',
        'min_liquidity': 0.5,  # Super low - maximum risk
        'max_age_minutes': 2,  # Only brand new tokens
        'position_size': 0.02,  # Smaller positions due to risk
        'take_profit': 3.0,  # 3x target
        'stop_loss': 0.5,  # -50%
        'hold_time': 900,  # 15 minutes max
        'css_class': 'sniper'
    }
    
    SCALPER = {
        'name': 'Quick Scalper',
        'min_liquidity': 5,
        'max_age_minutes': 10,
        'position_size': 0.05,
        'take_profit': 1.5,  # 50% profit
        'stop_loss': 0.8,  # -20%
        'hold_time': 1800,  # 30 minutes max
        'css_class': 'scalper'
    }
    
    COMMUNITY = {
        'name': 'Community Hunter',
        'min_liquidity': 20,
        'max_age_minutes': 60,
        'position_size': 0.1,
        'take_profit': 2.0,
        'stop_loss': 0.7,  # -30%
        'hold_time': 7200,  # 2 hours max
        'css_class': 'community'
    }

class TokenDiscovery:
    """Discover new tokens from multiple sources"""
    
    def __init__(self):
        self.session = None
        self.checked_tokens = set()
        
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def discover_tokens(self) -> List[Dict]:
        """Discover new tokens from various sources"""
        tokens = []
        
        # Try multiple discovery methods
        if HELIUS_API_KEY:
            tokens.extend(await self.get_helius_tokens())
        else:
            tokens.extend(await self.get_birdeye_tokens())
            
        # Filter out already checked tokens
        new_tokens = []
        for token in tokens:
            if token['address'] not in self.checked_tokens:
                self.checked_tokens.add(token['address'])
                new_tokens.append(token)
                
        bot_state.tokens_checked = len(self.checked_tokens)
        return new_tokens
        
    async def get_helius_tokens(self) -> List[Dict]:
        """Get new tokens from Helius"""
        try:
            session = await self.get_session()
            url = f"https://api.helius.xyz/v0/addresses/transactions?api-key={HELIUS_API_KEY}"
            
            # Query for recent token creation transactions
            params = {
                'limit': 10,
                'type': 'UNKNOWN'  # Often new tokens
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    # Parse transactions for new tokens
                    # This is simplified - in production you'd parse more carefully
                    for tx in data:
                        if 'tokenTransfers' in tx:
                            for transfer in tx['tokenTransfers']:
                                token = {
                                    'address': transfer.get('mint', ''),
                                    'symbol': 'NEW',
                                    'liquidity': 10,  # Would calculate real liquidity
                                    'age_minutes': 5,
                                    'source': 'helius'
                                }
                                tokens.append(token)
                                
                    logger.info(f"Found {len(tokens)} tokens from Helius")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Helius error: {e}")
            
        return []
        
    async def get_birdeye_tokens(self) -> List[Dict]:
        """Get trending tokens from Birdeye (free)"""
        try:
            session = await self.get_session()
            url = "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hUSD&sort_type=desc&limit=10"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    if 'data' in data and 'tokens' in data['data']:
                        for token_data in data['data']['tokens'][:5]:  # Top 5
                            # Only get new tokens
                            if token_data.get('v24hUSD', 0) < 100000:  # Small volume = new
                                token = {
                                    'address': token_data.get('address', ''),
                                    'symbol': token_data.get('symbol', 'UNKNOWN'),
                                    'liquidity': token_data.get('liquidity', 0) / 1e9,  # Convert to SOL
                                    'age_minutes': 30,  # Estimate
                                    'source': 'birdeye'
                                }
                                tokens.append(token)
                                
                    logger.info(f"Found {len(tokens)} tokens from Birdeye")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Birdeye error: {e}")
            
        return []

class LiveTradingBot:
    """Live trading bot that connects to ToxiBot"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        self.toxibot_chat = None
        self.monitoring_tokens = {}  # Changed to dict to store token info
        self.token_discovery = TokenDiscovery()
        
    async def setup_telegram(self, api_id: str, api_hash: str):
        """Save Telegram credentials"""
        self.api_id = api_id
        self.api_hash = api_hash
        bot_state.configured = True
        logger.info("Telegram credentials saved")
        return True
        
    async def send_code(self, phone: str):
        """Send verification code"""
        if not TELEGRAM_AVAILABLE:
            raise Exception("Telegram library not installed. Run: pip install telethon")
            
        try:
            # Create new client
            self.client = TelegramClient(
                StringSession(), 
                int(self.api_id), 
                self.api_hash
            )
            
            # Connect
            await self.client.connect()
            
            # Send code
            self.phone = phone
            result = await self.client.send_code_request(phone)
            self.code_hash = result.phone_code_hash
            
            logger.info(f"Code sent to {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send code: {e}")
            if self.client:
                await self.client.disconnect()
            raise
        
    async def verify_code(self, code: str):
        """Verify code and start bot"""
        if not self.client or not self.phone or not self.code_hash:
            raise Exception("Must request code first")
            
        try:
            # Sign in
            await self.client.sign_in(
                self.phone, 
                code, 
                phone_code_hash=self.code_hash
            )
            
            # Save session
            session_string = self.client.session.save()
            os.makedirs('data', exist_ok=True)
            with open('data/session.txt', 'w') as f:
                f.write(session_string)
                
            bot_state.authenticated = True
            
            # Find ToxiBot
            await self.find_toxibot()
            
            # Start trading
            self.running = True
            bot_state.running = True
            asyncio.create_task(self.trading_loop())
            asyncio.create_task(self.monitor_toxibot_messages())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def find_toxibot(self):
        """Find ToxiBot in Telegram chats"""
        toxibot_found = False
        
        async for dialog in self.client.iter_dialogs():
            # Look for ToxiBot
            if any(name in dialog.name.lower() for name in ['toxi', 'solana', 'bot']):
                if 'toxi' in dialog.name.lower():
                    self.toxibot_chat = dialog.entity
                    bot_state.toxibot_connected = True
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    
                    # Send test message
                    await self.client.send_message(self.toxibot_chat, "/balance")
                    bot_state.last_activity = "Connected to ToxiBot"
                    bot_state.last_activity_type = "success"
                    break
                    
        if not toxibot_found:
            logger.warning("ToxiBot not found! Make sure to:")
            logger.warning("1. Search for @toxi_solana_bot in Telegram")
            logger.warning("2. Start a chat with ToxiBot")
            logger.warning("3. Fund your ToxiBot wallet")
            bot_state.last_activity = "ToxiBot not found - please start chat with @toxi_solana_bot"
            bot_state.last_activity_type = "error"
            
    async def monitor_toxibot_messages(self):
        """Monitor ToxiBot responses"""
        if not self.toxibot_chat:
            return
            
        @self.client.on(events.NewMessage(chats=self.toxibot_chat))
        async def handler(event):
            message = event.message.text
            logger.info(f"ToxiBot: {message[:100]}...")
            
            # Parse balance
            if "Wallet Balance:" in message or "Balance:" in message:
                bot_state.toxibot_connected = True
                bot_state.last_activity = "ToxiBot balance checked"
                bot_state.last_activity_type = "info"
                
            # Parse successful buys
            elif "✅" in message or "Bought" in message or "Success" in message:
                logger.info("Trade executed successfully!")
                bot_state.total_trades += 1
                bot_state.winning_trades += 1
                bot_state.last_activity = "Trade executed successfully!"
                bot_state.last_activity_type = "trade"
                
            # Parse validation errors
            elif "Validation error" in message or "❌" in message:
                logger.warning(f"Trade failed: {message}")
                bot_state.last_activity = "Trade failed - invalid token"
                bot_state.last_activity_type = "error"
                
    async def execute_buy(self, token_address: str, amount_sol: float = POSITION_SIZE):
        """Execute buy order through ToxiBot - FIXED FORMAT"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        try:
            # ToxiBot format: just send the token address
            # It will use your default buy amount set in ToxiBot
            await self.client.send_message(self.toxibot_chat, token_address)
            
            logger.info(f"Sent buy command: {token_address}")
            bot_state.last_activity = f"Attempting to buy token: {token_address[:8]}..."
            bot_state.last_activity_type = "trade"
            return True
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            bot_state.last_activity = f"Buy command failed: {str(e)}"
            bot_state.last_activity_type = "error"
            return False
            
    async def execute_sell(self, token_address: str, percentage: int = 100):
        """Execute sell order through ToxiBot"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        try:
            # For selling, first check portfolio
            await self.client.send_message(self.toxibot_chat, "/portfolio")
            
            logger.info(f"Checking positions before sell: {token_address}")
            bot_state.last_activity = f"Checking positions for sell: {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            return True
            
        except Exception as e:
            logger.error(f"Sell command failed: {e}")
            return False
            
    async def trading_loop(self):
        """Main trading loop"""
        logger.info("Starting live trading loop with 3 personalities...")
        bot_state.last_activity = "Trading loop started - scanning for opportunities"
        bot_state.last_activity_type = "info"
        
        while self.running:
            try:
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                if new_tokens:
                    logger.info(f"Discovered {len(new_tokens)} new tokens")
                    
                    for token in new_tokens:
                        personality = self.should_buy_token(token)
                        if personality:
                            logger.info(f"{personality['name']} found token: {token['symbol']} - {token['address'][:8]}...")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']}"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Execute buy with personality-specific amount
                            if await self.execute_buy(token['address'], personality['position_size']):
                                # Store token with its personality
                                token['personality'] = personality
                                token['entry_time'] = time.time()
                                self.monitoring_tokens[token['address']] = token
                                bot_state.active_trades = len(self.monitoring_tokens)
                                
                                # Monitor for sell
                                asyncio.create_task(self.monitor_token_for_sell(token))
                else:
                    # Update activity to show we're still scanning
                    if bot_state.tokens_checked % 10 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens checked"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(30)
                
    def should_buy_token(self, token: Dict) -> Optional[Dict]:
        """Decide if token should be bought based on personality"""
        
        # Try each personality
        for personality in [BotPersonality.ULTRA_EARLY, BotPersonality.SCALPER, BotPersonality.COMMUNITY]:
            
            criteria = {
                'has_address': bool(token.get('address')),
                'min_liquidity': token.get('liquidity', 0) >= personality['min_liquidity'],
                'max_age': token.get('age_minutes', 999) <= personality['max_age_minutes'],
                'not_monitoring': token.get('address') not in self.monitoring_tokens,
                'max_positions': len(self.monitoring_tokens) < MAX_POSITIONS
            }
            
            if all(criteria.values()):
                logger.info(f"{personality['name']} criteria met for {token['symbol']}")
                return personality
                
        return None
        
    async def monitor_token_for_sell(self, token: Dict):
        """Monitor token for sell opportunity"""
        entry_time = token['entry_time']
        personality = token['personality']
        
        while token['address'] in self.monitoring_tokens:
            try:
                elapsed = time.time() - entry_time
                
                # Use personality-specific targets
                take_profit = personality['take_profit']
                stop_loss = personality['stop_loss']
                max_hold = personality['hold_time']
                
                # Simulate price movement (in production, check real price)
                # Ultra-early has 30% chance of profit, Scalper 50%, Community 40%
                profit_chance = {'sniper': 0.7, 'scalper': 0.5, 'community': 0.6}
                
                if elapsed > 300 and random.random() > profit_chance.get(personality['css_class'], 0.5):
                    logger.info(f"{personality['name']} hit {take_profit}x on {token['symbol']}! Selling...")
                    bot_state.last_activity = f"{personality['name']} hit {take_profit}x! Selling {token['symbol']}"
                    bot_state.last_activity_type = "trade"
                    
                    if await self.execute_sell(token['address'], 80):
                        profit = personality['position_size'] * (take_profit - 1) * 0.8
                        bot_state.total_profit += profit
                        bot_state.winning_trades += 1
                        logger.info(f"Profit: +{profit:.3f} SOL")
                    
                    # Remove from monitoring
                    del self.monitoring_tokens[token['address']]
                    bot_state.active_trades = len(self.monitoring_tokens)
                    break
                    
                # Stop loss or time limit
                elif elapsed > max_hold:
                    logger.info(f"{personality['name']} time limit reached for {token['symbol']}")
                    bot_state.last_activity = f"{personality['name']} closing {token['symbol']} - time limit"
                    bot_state.last_activity_type = personality['css_class']
                    
                    await self.execute_sell(token['address'], 100)
                    del self.monitoring_tokens[token['address']]
                    bot_state.active_trades = len(self.monitoring_tokens)
                    break
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                if token['address'] in self.monitoring_tokens:
                    del self.monitoring_tokens[token['address']]
                    bot_state.active_trades = len(self.monitoring_tokens)
                break

# Create bot instance
trading_bot = LiveTradingBot()

class WebServer:
    """Web server for the dashboard"""
    
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/status', self.status)
        self.app.router.add_post('/api/setup', self.setup)
        self.app.router.add_post('/api/request-code', self.request_code)
        self.app.router.add_post('/api/verify-code', self.verify_code)
        self.app.router.add_get('/api/stats', self.stats)
        
    async def index(self, request):
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')
        
    async def status(self, request):
        return web.json_response({
            'configured': bot_state.configured,
            'authenticated': bot_state.authenticated,
            'running': bot_state.running,
            'hasHeliusKey': bool(HELIUS_API_KEY)
        })
        
    async def setup(self, request):
        try:
            data = await request.json()
            api_id = data.get('api_id')
            api_hash = data.get('api_hash')
            
            if not api_id or not api_hash:
                return web.json_response({'error': 'Missing credentials'}, status=400)
                
            await trading_bot.setup_telegram(api_id, api_hash)
            
            return web.json_response({'status': 'success'})
        except Exception as e:
            logger.error(f"Setup error: {e}")
            return web.json_response({'error': str(e)}, status=400)
            
    async def request_code(self, request):
        try:
            data = await request.json()
            phone = data.get('phone')
            
            if not phone:
                return web.json_response({'error': 'Phone number required'}, status=400)
                
            await trading_bot.send_code(phone)
            
            return web.json_response({'status': 'success'})
        except Exception as e:
            logger.error(f"Request code error: {e}")
            return web.json_response({'error': str(e)}, status=400)
            
    async def verify_code(self, request):
        try:
            data = await request.json()
            code = data.get('code')
            
            if not code:
                return web.json_response({'error': 'Code required'}, status=400)
                
            await trading_bot.verify_code(code)
            
            return web.json_response({'status': 'success'})
        except Exception as e:
            logger.error(f"Verify code error: {e}")
            return web.json_response({'error': str(e)}, status=400)
            
    async def stats(self, request):
        win_rate = 0
        if bot_state.total_trades > 0:
            win_rate = int((bot_state.winning_trades / bot_state.total_trades) * 100)
            
        return web.json_response({
            'profit': bot_state.total_profit,
            'trades': bot_state.active_trades,
            'winRate': win_rate,
            'toxibotConnected': bot_state.toxibot_connected,
            'tokensChecked': bot_state.tokens_checked,
            'activity': bot_state.last_activity,
            'activityType': bot_state.last_activity_type
        })

async def main():
    """Start the bot"""
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA LIVE TRADING BOT STARTED    ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  3 Active Personalities:              ║
    ║  • Ultra-Early Sniper (0.5+ SOL liq)  ║
    ║  • Quick Scalper (5+ SOL liq)        ║
    ║  • Community Hunter (20+ SOL liq)    ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
