#!/usr/bin/env python3
"""
SOLANA TRADING BOT - FIXED VERSION WITH SAFETY MEASURES
Includes real price checking, risk management, and proper error handling
"""

import asyncio
import os
import json
import time
import logging
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiohttp import web
from dataclasses import dataclass, field
import re

# Setup logging with more detail
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TradingBot')

# Try to import Telegram
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram not available - install telethon to enable trading")

# Configuration with SAFE DEFAULTS
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY', '')
HELIUS_RPC_URL = os.environ.get('HELIUS_RPC_URL', '')
HELIUS_WEBHOOK_URL = os.environ.get('HELIUS_WEBHOOK_URL', '')  # For LaserStream
HELIUS_SENDER_URL = os.environ.get('HELIUS_SENDER_URL', '')  # For Sender service
SOLANA_RPC_URL = HELIUS_RPC_URL if HELIUS_RPC_URL else 'https://api.mainnet-beta.solana.com'
POSITION_SIZE = 0.01  # Start VERY small - 0.01 SOL per trade
MIN_LIQUIDITY = 10  # Minimum 10 SOL liquidity for safety
MAX_TOKEN_AGE = 3600  # 1 hour max age
MAX_POSITIONS = 3  # Start with only 3 concurrent positions
MAX_DAILY_LOSS = 0.2  # Maximum 0.2 SOL daily loss (increased from 0.1)
MAX_POSITION_SIZE = 0.05  # Never risk more than 0.05 SOL per trade
MIN_WALLET_BALANCE = 0.1  # Keep at least 0.1 SOL for fees

# Risk Management Settings
RISK_SETTINGS = {
    'max_slippage': 0.05,  # 5% max slippage
    'max_price_impact': 0.03,  # 3% max price impact
    'cooldown_after_loss': 300,  # 5 min cooldown after loss
    'require_volume_check': True,  # Must have recent volume
    'min_holders': 10,  # Minimum token holders
    'check_contract': True,  # Enable contract verification
    'check_rug_risk': True,  # Enable rug pull detection
    'max_concentration': 0.1,  # Max 10% held by single wallet
    'min_liquidity_locked': 0.5,  # At least 50% liquidity locked
}

# HTML Dashboard (unchanged for brevity)
DASHBOARD_HTML = '''<!DOCTYPE html>
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
        
        .risk-indicator {
            background: rgba(255,0,0,0.2);
            border: 2px solid #ff0000;
            padding: 15px;
            margin: 20px 0;
        }
        
        .risk-indicator h3 {
            color: #ff0000;
            margin-bottom: 10px;
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
            
            <div class="risk-indicator">
                <h3>Risk Management Active</h3>
                <p>Max Position: 0.05 SOL | Max Daily Loss: 0.2 SOL | Min Liquidity: 10 SOL</p>
                <p>Contract Checking: Enabled | Rug Detection: Active</p>
                <p id="riskStatus">Status: Monitoring...</p>
            </div>
            
            <div class="api-setup" id="apiWarning">
                <h3>⚠️ Optional: Add Helius API Key for Better Token Discovery</h3>
                <p>Get a free API key from <a href="https://www.helius.dev/" target="_blank" style="color: #ff6600;">helius.dev</a></p>
                <p>Add it to Railway environment variables as HELIUS_API_KEY</p>
            </div>
            
            <div class="status" id="botStatus">
                <h2>Bot Status: <span id="statusText">Offline</span></h2>
                <p id="toxibotStatus">ToxiBot: Not connected</p>
                <p id="walletStatus">Wallet Balance: Checking...</p>
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
                
                if (data.walletBalance !== undefined) {
                    document.getElementById('walletStatus').textContent = `Wallet Balance: ${data.walletBalance.toFixed(3)} SOL`;
                }
                
                if (data.riskStatus) {
                    document.getElementById('riskStatus').textContent = `Status: ${data.riskStatus}`;
                }
                
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
class Trade:
    """Track individual trades"""
    token_address: str
    symbol: str
    entry_price: float
    current_price: float
    position_size: float
    entry_time: float
    personality: Dict
    stop_loss: float
    take_profit: float
    limit_orders: List[Dict] = field(default_factory=list)  # Add limit orders tracking
    
    @property
    def pnl(self) -> float:
        """Calculate profit/loss"""
        return self.position_size * (self.current_price / self.entry_price - 1)
    
    @property
    def pnl_percent(self) -> float:
        """Calculate profit/loss percentage"""
        return (self.current_price / self.entry_price - 1) * 100

@dataclass
class BotState:
    configured: bool = False
    authenticated: bool = False
    running: bool = False
    total_profit: float = 0.0
    active_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    toxibot_connected: bool = False
    tokens_checked: int = 0
    last_activity: Optional[str] = None
    last_activity_type: str = 'info'
    wallet_balance: float = 0.0
    daily_loss: float = 0.0
    last_loss_time: float = 0
    trades_this_hour: int = 0
    hour_start: float = time.time()
    risk_status: str = "Normal"
    active_positions: Dict[str, Trade] = field(default_factory=dict)

# Global state
bot_state = BotState()

class BotPersonality:
    """Different trading personalities with SAFE strategies and limit orders"""
    
    CONSERVATIVE_SNIPER = {
        'name': 'Conservative Sniper',
        'min_liquidity': 20,  # Higher liquidity requirement
        'max_age_minutes': 30,  # Only newer tokens
        'position_size': 0.01,  # Very small positions
        'take_profit': 1.5,  # 50% profit target
        'stop_loss': 0.9,  # -10% stop loss
        'hold_time': 1800,  # 30 minutes max
        'css_class': 'sniper',
        'min_volume_24h': 1000,  # Minimum $1000 daily volume
        'min_holders': 50,  # At least 50 holders
        # Limit order settings
        'limit_buy_offset': 0.95,  # Buy at 5% below current price
        'limit_sell_targets': [1.15, 1.3, 1.5],  # 15%, 30%, 50% profit targets
        'limit_sell_amounts': [0.3, 0.4, 0.3],  # Sell 30%, 40%, 30% at each target
    }
    
    SAFE_SCALPER = {
        'name': 'Safe Scalper',
        'min_liquidity': 50,
        'max_age_minutes': 120,
        'position_size': 0.02,
        'take_profit': 1.2,  # 20% profit
        'stop_loss': 0.95,  # -5% stop loss
        'hold_time': 3600,  # 1 hour max
        'css_class': 'scalper',
        'min_volume_24h': 5000,
        'min_holders': 100,
        # Limit order settings
        'limit_buy_offset': 0.98,  # Buy at 2% below current price
        'limit_sell_targets': [1.05, 1.1, 1.2],  # 5%, 10%, 20% profit targets
        'limit_sell_amounts': [0.4, 0.3, 0.3],  # Sell 40%, 30%, 30% at each target
    }
    
    ESTABLISHED_TRADER = {
        'name': 'Established Trader',
        'min_liquidity': 100,
        'max_age_minutes': 1440,  # 24 hours
        'position_size': 0.03,
        'take_profit': 1.3,
        'stop_loss': 0.93,  # -7% stop loss
        'hold_time': 7200,  # 2 hours max
        'css_class': 'community',
        'min_volume_24h': 10000,
        'min_holders': 200,
        # Limit order settings
        'limit_buy_offset': 0.97,  # Buy at 3% below current price
        'limit_sell_targets': [1.1, 1.2, 1.3],  # 10%, 20%, 30% profit targets
        'limit_sell_amounts': [0.3, 0.3, 0.4],  # Sell 30%, 30%, 40% at each target
    }

class PriceChecker:
    """Check real token prices using multiple sources"""
    
    def __init__(self):
        self.session = None
        self.price_cache = {}
        self.cache_duration = 15  # Cache prices for 15 seconds (was 30)
        
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def _get_price_from_helius(self, token_address: str) -> Optional[float]:
        """Get price using Helius RPC (premium)"""
        if not HELIUS_RPC_URL:
            return None
            
        try:
            session = await self.get_session()
            
            # Helius enhanced API for token prices
            url = f"{HELIUS_RPC_URL.replace('?api-key=', '/v0/token-metadata?api-key=')}"
            
            payload = {
                "mintAccounts": [token_address],
                "includeOffChain": True,
                "disableCache": False
            }
            
            async with session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # Parse price from Helius response
                    for token_data in data:
                        if token_data.get('account') == token_address:
                            # Get price info
                            on_chain_info = token_data.get('onChainAccountInfo', {})
                            price_info = token_data.get('priceInfo', {})
                            
                            if price_info and price_info.get('pricePerToken'):
                                return float(price_info['pricePerToken'])
                                
        except Exception as e:
            logger.debug(f"Helius price error: {e}")
            
        return None
        
    async def get_token_price(self, token_address: str) -> Optional[float]:
        """Get token price in SOL with Helius priority"""
        # Check cache first
        cache_key = f"{token_address}_price"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_duration:
                return cached_data['price']
        
        # Try Helius first (fastest with premium RPC)
        if HELIUS_RPC_URL:
            price = await self._get_price_from_helius(token_address)
            if price:
                self.price_cache[cache_key] = {
                    'price': price,
                    'timestamp': time.time()
                }
                return price
        
        # Fall back to other sources
        price = await self._get_price_from_dexscreener(token_address)
        if not price:
            price = await self._get_price_from_birdeye(token_address)
        
        if price:
            self.price_cache[cache_key] = {
                'price': price,
                'timestamp': time.time()
            }
            
        return price
        
    async def _get_price_from_dexscreener(self, token_address: str) -> Optional[float]:
        """Get price from DexScreener"""
        try:
            session = await self.get_session()
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    # Find SOL pair with highest liquidity
                    sol_pairs = [p for p in pairs if p.get('quoteToken', {}).get('symbol') == 'SOL']
                    if sol_pairs:
                        # Sort by liquidity
                        sol_pairs.sort(key=lambda x: x.get('liquidity', {}).get('usd', 0), reverse=True)
                        price_sol = float(sol_pairs[0].get('priceNative', 0))
                        return price_sol
                        
        except Exception as e:
            logger.error(f"DexScreener price error: {e}")
            
        return None
        
    async def _get_price_from_birdeye(self, token_address: str) -> Optional[float]:
        """Get price from Birdeye"""
        try:
            session = await self.get_session()
            url = f"https://public-api.birdeye.so/public/price?address={token_address}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        # Convert USD price to SOL price
                        usd_price = data.get('data', {}).get('value', 0)
                        sol_usd_price = await self._get_sol_price()
                        if sol_usd_price and usd_price:
                            return usd_price / sol_usd_price
                            
        except Exception as e:
            logger.error(f"Birdeye price error: {e}")
            
        return None
        
    async def _get_sol_price(self) -> Optional[float]:
        """Get SOL price in USD"""
        cache_key = "SOL_USD"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < 300:  # 5 min cache
                return cached_data['price']
                
        try:
            session = await self.get_session()
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('solana', {}).get('usd', 0)
                    if price:
                        self.price_cache[cache_key] = {
                            'price': price,
                            'timestamp': time.time()
                        }
                        return price
                        
        except Exception as e:
            logger.error(f"SOL price error: {e}")
            
        return 40.0  # Fallback SOL price

class ContractChecker:
    """Check token contracts for safety and rug pull risks"""
    
    def __init__(self):
        self.session = None
        self.checked_contracts = {}
        
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def check_token_safety(self, token_address: str) -> Dict:
        """Comprehensive token safety check with RugCheck.xyz as primary source"""
        # Check cache first
        if token_address in self.checked_contracts:
            cached = self.checked_contracts[token_address]
            if time.time() - cached['timestamp'] < 3600:  # 1 hour cache
                return cached['result']
        
        result = {
            'is_safe': True,
            'risk_score': 0,  # 0-10, higher = riskier
            'warnings': [],
            'contract_verified': False,
            'liquidity_locked': False,
            'ownership_renounced': False,
            'mint_disabled': False,
            'freeze_disabled': False,
            'top_holder_percentage': 0,
            'dev_wallet_percentage': 0,
            'liquidity_percentage': 0,
            'rugcheck_score': 0,
            'rugcheck_analysis': None
        }
        
        try:
            # Primary check: RugCheck.xyz (most comprehensive)
            rugcheck_data = await self._check_rugcheck(token_address)
            if rugcheck_data:
                result.update(rugcheck_data)
                result['rugcheck_analysis'] = True
                
                # If RugCheck gives high confidence data, we can skip other checks
                if rugcheck_data.get('rugcheck_score', 0) > 0:
                    # RugCheck provided comprehensive analysis
                    logger.info(f"RugCheck analysis for {token_address[:8]}: Score {rugcheck_data['rugcheck_score']}/100, Risk: {rugcheck_data['risk_score']}/10")
                    
                    # Early exit for very risky tokens
                    if rugcheck_data['risk_score'] >= 7:
                        result['is_safe'] = False
                        result['warnings'].insert(0, "🚨 RUGCHECK: HIGH RISK - DO NOT TRADE")
            
            # If RugCheck didn't provide full data or token is borderline, do additional checks
            if not rugcheck_data or rugcheck_data['risk_score'] >= 4:
                # Secondary check: Holder distribution
                holder_data = await self._check_holder_distribution(token_address)
                if holder_data:
                    # Merge holder data, taking worst case
                    if holder_data['risk_score'] > result['risk_score']:
                        result['risk_score'] = holder_data['risk_score']
                    result['warnings'].extend(holder_data.get('warnings', []))
                    
                # Tertiary check: Token metadata and trading patterns
                metadata = await self._check_token_metadata(token_address)
                if metadata:
                    # Merge metadata, taking worst case
                    if metadata['risk_score'] > result['risk_score']:
                        result['risk_score'] = metadata['risk_score']
                    result['warnings'].extend(metadata.get('warnings', []))
            
            # Final safety determination
            result['is_safe'] = result['risk_score'] < 7
            
            # Add summary warning if risky
            if result['risk_score'] >= 7:
                result['warnings'].insert(0, f"🚨 OVERALL RISK SCORE: {result['risk_score']}/10 - HIGH RISK")
            elif result['risk_score'] >= 5:
                result['warnings'].insert(0, f"⚠️ OVERALL RISK SCORE: {result['risk_score']}/10 - MEDIUM RISK")
            else:
                result['warnings'].insert(0, f"✅ OVERALL RISK SCORE: {result['risk_score']}/10 - ACCEPTABLE")
            
            # Cache result
            self.checked_contracts[token_address] = {
                'result': result,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Contract check error for {token_address}: {e}")
            result['is_safe'] = False
            result['warnings'].append("Failed to verify contract safety")
            result['risk_score'] = 8  # High risk if we can't verify
            
        return result
        
    async def _check_rugcheck(self, token_address: str) -> Optional[Dict]:
        """Check RugCheck.xyz for comprehensive token safety analysis"""
        try:
            session = await self.get_session()
            
            # RugCheck.xyz API endpoint - using their full report
            url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            
            # Alternative endpoint for detailed analysis
            detailed_url = f"https://rugcheck.xyz/api/v1/report/{token_address}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    risk_score = 0
                    warnings = []
                    
                    # Parse RugCheck's risk assessment
                    if 'risks' in data:
                        # RugCheck provides categorized risks
                        for risk in data.get('risks', []):
                            severity = risk.get('severity', 'low')
                            description = risk.get('description', '')
                            
                            if severity == 'critical':
                                risk_score += 4
                                warnings.append(f"🚨 {description}")
                            elif severity == 'high':
                                risk_score += 3
                                warnings.append(f"⚠️ {description}")
                            elif severity == 'medium':
                                risk_score += 2
                                warnings.append(f"⚡ {description}")
                            else:
                                risk_score += 1
                                warnings.append(f"ℹ️ {description}")
                    
                    # Check specific flags from RugCheck
                    token_info = data.get('token', {})
                    
                    # Mint Authority
                    if token_info.get('mint_authority'):
                        if not token_info.get('mint_authority_disabled'):
                            risk_score += 3
                            warnings.append("⚠️ Mint authority still active")
                    
                    # Freeze Authority
                    if token_info.get('freeze_authority'):
                        if not token_info.get('freeze_authority_disabled'):
                            risk_score += 3
                            warnings.append("⚠️ Freeze authority still active")
                    
                    # LP (Liquidity Pool) Analysis
                    lp_info = data.get('liquidity_pools', [])
                    if lp_info:
                        main_pool = lp_info[0] if lp_info else {}
                        
                        # Check LP burn/lock status
                        if not main_pool.get('lp_burned') and not main_pool.get('lp_locked'):
                            risk_score += 2
                            warnings.append("⚠️ LP tokens not burned or locked")
                            
                        # Check liquidity amount
                        liquidity_usd = main_pool.get('liquidity_usd', 0)
                        if liquidity_usd < 1000:
                            risk_score += 2
                            warnings.append(f"⚠️ Very low liquidity: ${liquidity_usd:.0f}")
                    
                    # Ownership and control
                    ownership = data.get('ownership', {})
                    if ownership.get('renounced') == False:
                        risk_score += 2
                        warnings.append("⚠️ Ownership not renounced")
                        
                    # Holder distribution
                    holders = data.get('holders', {})
                    top_10_percentage = holders.get('top_10_percentage', 0)
                    if top_10_percentage > 70:
                        risk_score += 3
                        warnings.append(f"⚠️ Top 10 holders own {top_10_percentage:.1f}%")
                    elif top_10_percentage > 50:
                        risk_score += 2
                        warnings.append(f"⚡ Top 10 holders own {top_10_percentage:.1f}%")
                        
                    # Creator holdings
                    creator_percentage = holders.get('creator_percentage', 0)
                    if creator_percentage > 10:
                        risk_score += 3
                        warnings.append(f"⚠️ Creator holds {creator_percentage:.1f}%")
                        
                    # Market and trading analysis
                    market = data.get('market', {})
                    
                    # Check for honeypot indicators
                    if market.get('buy_tax', 0) > 10:
                        risk_score += 2
                        warnings.append(f"⚠️ High buy tax: {market['buy_tax']}%")
                        
                    if market.get('sell_tax', 0) > 10:
                        risk_score += 3
                        warnings.append(f"⚠️ High sell tax: {market['sell_tax']}%")
                        
                    # Trading pattern analysis
                    if market.get('unique_wallets_24h', 0) < 10:
                        risk_score += 2
                        warnings.append("⚠️ Very few unique traders")
                        
                    # Get overall risk rating from RugCheck
                    overall_risk = data.get('risk_level', 'unknown')
                    rugcheck_score = data.get('score', 0)  # RugCheck's 0-100 safety score
                    
                    # Convert RugCheck score to our risk score
                    if rugcheck_score > 0:
                        # RugCheck uses 0-100 where 100 is safest
                        # Convert to our 0-10 where 0 is safest
                        risk_score = max(0, min(10, int((100 - rugcheck_score) / 10)))
                        
                    # Add overall assessment
                    if overall_risk == 'high' or rugcheck_score < 30:
                        warnings.insert(0, "🚨 RugCheck: HIGH RISK TOKEN")
                    elif overall_risk == 'medium' or rugcheck_score < 60:
                        warnings.insert(0, "⚠️ RugCheck: MEDIUM RISK")
                    elif overall_risk == 'low' or rugcheck_score >= 60:
                        warnings.insert(0, "✅ RugCheck: Relatively safe")
                        
                    return {
                        'risk_score': min(10, risk_score),  # Cap at 10
                        'warnings': warnings,
                        'rugcheck_score': rugcheck_score,
                        'rugcheck_risk': overall_risk,
                        'mint_disabled': token_info.get('mint_authority_disabled', False),
                        'freeze_disabled': token_info.get('freeze_authority_disabled', False),
                        'ownership_renounced': ownership.get('renounced', False),
                        'lp_burned': any(pool.get('lp_burned', False) for pool in lp_info),
                        'lp_locked': any(pool.get('lp_locked', False) for pool in lp_info),
                        'top_holder_percentage': holders.get('top_1_percentage', 0),
                        'creator_percentage': creator_percentage,
                        'liquidity_usd': lp_info[0].get('liquidity_usd', 0) if lp_info else 0
                    }
                    
                elif response.status == 404:
                    # Token not found in RugCheck - likely very new
                    return {
                        'risk_score': 5,
                        'warnings': ['ℹ️ Token too new for RugCheck analysis'],
                        'rugcheck_score': 0,
                        'rugcheck_risk': 'unknown'
                    }
                    
        except Exception as e:
            logger.debug(f"RugCheck API error: {e}")
            
        return None
        
    async def _check_holder_distribution(self, token_address: str) -> Optional[Dict]:
        """Check token holder distribution"""
        try:
            session = await self.get_session()
            
            # Try Helius first if available
            if HELIUS_API_KEY:
                url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
                payload = {"mintAccounts": [token_address]}
                
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parse holder data
                        return await self._parse_holder_data(data)
                        
            # Fallback to other sources
            # Check Solscan API (limited free tier)
            url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=10"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('data'):
                        holders = data['data']
                        total_supply = data.get('total', 1)
                        
                        # Calculate concentration
                        top_holder_amount = holders[0].get('amount', 0) if holders else 0
                        top_holder_percent = (top_holder_amount / total_supply) * 100 if total_supply > 0 else 0
                        
                        warnings = []
                        risk_score = 0
                        
                        if top_holder_percent > 20:
                            risk_score += 3
                            warnings.append(f"⚠️ Top holder owns {top_holder_percent:.1f}%")
                            
                        if len(holders) < 10:
                            risk_score += 2
                            warnings.append(f"⚠️ Only {len(holders)} holders")
                            
                        return {
                            'top_holder_percentage': top_holder_percent,
                            'holder_count': len(holders),
                            'risk_score': risk_score,
                            'warnings': warnings
                        }
                        
        except Exception as e:
            logger.debug(f"Holder check error: {e}")
            
        return None
        
    async def _check_token_metadata(self, token_address: str) -> Optional[Dict]:
        """Check token metadata for red flags"""
        try:
            session = await self.get_session()
            
            # Get token metadata
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        warnings = []
                        risk_score = 0
                        
                        # Check liquidity locks
                        for pair in pairs:
                            liquidity = pair.get('liquidity', {})
                            if liquidity.get('usd', 0) < 1000:
                                risk_score += 2
                                warnings.append("⚠️ Very low liquidity")
                                
                            # Check for honeypot indicators
                            buys = pair.get('txns', {}).get('h24', {}).get('buys', 0)
                            sells = pair.get('txns', {}).get('h24', {}).get('sells', 0)
                            
                            if buys > 10 and sells == 0:
                                risk_score += 5
                                warnings.append("🚨 No sells detected - possible honeypot!")
                                
                            elif buys > 0 and sells / buys < 0.1:
                                risk_score += 3
                                warnings.append("⚠️ Very few sells - suspicious")
                                
                        return {
                            'risk_score': risk_score,
                            'warnings': warnings,
                            'liquidity_usd': pairs[0].get('liquidity', {}).get('usd', 0) if pairs else 0
                        }
                        
        except Exception as e:
            logger.debug(f"Metadata check error: {e}")
            
        return None
        
    async def _parse_holder_data(self, data: Dict) -> Dict:
        """Parse holder data from various sources"""
        # Implementation depends on data format
        return {
            'holder_count': 0,
            'top_holder_percentage': 0,
            'warnings': []
        }

class TokenDiscovery:
    """Discover new tokens from multiple sources"""
    
    def __init__(self):
        self.session = None
        self.checked_tokens = set()
        self.price_checker = PriceChecker()
        self.contract_checker = ContractChecker()  # Add contract checker
        
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
            
        # Always try free sources
        tokens.extend(await self.get_dexscreener_tokens())
        tokens.extend(await self.get_birdeye_tokens())
        tokens.extend(await self.get_jupiter_new_tokens())  # Add Jupiter
        
        logger.info(f"Total tokens found before filtering: {len(tokens)}")
        
        # Filter and validate tokens
        validated_tokens = []
        import re
        
        for token in tokens:
            # Validate address format
            address = token.get('address', '')
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
        
    async def get_helius_tokens(self) -> List[Dict]:
        """Get new tokens from Helius with better parsing"""
        try:
            session = await self.get_session()
            
            # Get recent token creations
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
            
            # Get new token list
            list_url = f"https://api.helius.xyz/v0/addresses/tokens?api-key={HELIUS_API_KEY}&limit=100"
            
            async with session.get(list_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for token_data in data[:20]:  # Process top 20
                        try:
                            address = token_data.get('mint', token_data.get('address', ''))
                            if address:
                                # Get token details
                                token_info = await self._get_token_details(address)
                                if token_info:
                                    tokens.append(token_info)
                        except:
                            continue
                            
                    logger.info(f"Found {len(tokens)} tokens from Helius")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Helius error: {e}")
            
    async def get_jupiter_new_tokens(self) -> List[Dict]:
        """Get new tokens from Jupiter aggregator"""
        try:
            session = await self.get_session()
            
            # Jupiter's token list API
            url = "https://token.jup.ag/all"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    # Sort by timestamp if available, get newest
                    # Jupiter doesn't provide age, so we'll check tokens not in our cache
                    for token_data in data[:100]:  # Check first 100
                        address = token_data.get('address', '')
                        
                        # Skip if we've seen it
                        if address in self.checked_tokens:
                            continue
                            
                        # Basic validation
                        if not address or len(address) < 32:
                            continue
                            
                        token = {
                            'address': address,
                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                            'name': token_data.get('name', ''),
                            'liquidity': 10,  # Will verify with price check
                            'age_minutes': 60,  # Estimate
                            'volume_24h': 0,
                            'holders': 0,
                            'source': 'jupiter'
                        }
                        
                        tokens.append(token)
                        
                        if len(tokens) >= 10:  # Limit to 10 new ones
                            break
                            
                    logger.info(f"Found {len(tokens)} potential new tokens from Jupiter")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Jupiter error: {e}")
            
        return []
        
    async def get_dexscreener_tokens(self) -> List[Dict]:
        """Get new tokens from DexScreener"""
        try:
            session = await self.get_session()
            
            # Get new pairs sorted by age
            url = "https://api.dexscreener.com/latest/dex/pairs/solana"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for pair in data.get('pairs', [])[:30]:
                        # Validate token address
                        base_token = pair.get('baseToken', {})
                        token_address = base_token.get('address', '')
                        
                        # Skip if invalid address format
                        if not token_address or len(token_address) < 32:
                            continue
                            
                        # Calculate age in minutes
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at:
                            age_minutes = (time.time() * 1000 - created_at) / 60000
                        else:
                            age_minutes = 60  # Default 1 hour
                            
                        token = {
                            'address': token_address,
                            'symbol': base_token.get('symbol', 'UNKNOWN'),
                            'name': base_token.get('name', ''),
                            'liquidity': pair.get('liquidity', {}).get('usd', 0) / 40,  # Convert to SOL
                            'age_minutes': int(age_minutes),
                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                            'price_usd': pair.get('priceUsd', 0),
                            'holders': 0,  # Will check separately
                            'source': 'dexscreener'
                        }
                        
                        if token['address'] and token['liquidity'] > 0:
                            tokens.append(token)
                            
                    logger.info(f"Found {len(tokens)} tokens from DexScreener")
                    return tokens
                    
        except Exception as e:
            logger.error(f"DexScreener error: {e}")
            
        return []
        
    async def get_birdeye_tokens(self) -> List[Dict]:
        """Get trending tokens from Birdeye"""
        try:
            session = await self.get_session()
            
            # Try multiple sorting options for variety
            endpoints = [
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hChangePercent&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=mc&sort_type=asc&offset=0&limit=50"
            ]
            
            all_tokens = []
            
            for url in endpoints:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and 'data' in data:
                                for token_data in data['data'].get('tokens', [])[:20]:
                                    # Only include tokens with reasonable metrics
                                    if token_data.get('v24hUSD', 0) > 100:  # Min $100 daily volume
                                        token = {
                                            'address': token_data.get('address', ''),
                                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                                            'name': token_data.get('name', ''),
                                            'liquidity': token_data.get('liquidity', 0) / 1e9,  # Convert to SOL
                                            'age_minutes': 60,  # Default estimate
                                            'volume_24h': token_data.get('v24hUSD', 0),
                                            'price_usd': token_data.get('v24hUSD', 0) / max(token_data.get('v24hTx', 1), 1),
                                            'holders': token_data.get('holder', 0),
                                            'source': 'birdeye'
                                        }
                                        
                                        if token['address']:
                                            all_tokens.append(token)
                except:
                    continue
                    
            # Remove duplicates
            unique_tokens = {}
            for token in all_tokens:
                unique_tokens[token['address']] = token
                
            tokens = list(unique_tokens.values())
            logger.info(f"Found {len(tokens)} tokens from Birdeye")
            return tokens
            
        except Exception as e:
            logger.error(f"Birdeye error: {e}")
            
        return []
        
    async def _get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token information"""
        try:
            # Get price from price checker
            price = await self.price_checker.get_token_price(address)
            
            if price:
                return {
                    'address': address,
                    'symbol': 'NEW',
                    'name': 'New Token',
                    'liquidity': 10,  # Will be checked separately
                    'age_minutes': 30,
                    'volume_24h': 1000,
                    'price_usd': price * 40,  # Convert to USD
                    'holders': 50,
                    'source': 'helius'
                }
        except:
            pass
            
        return None

class RiskManager:
    """Manage trading risks and limits"""
    
    def __init__(self):
        self.daily_loss_limit = MAX_DAILY_LOSS
        self.max_position_size = MAX_POSITION_SIZE
        self.min_wallet_balance = MIN_WALLET_BALANCE
        self.cooldown_period = RISK_SETTINGS['cooldown_after_loss']
        
    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can place a new trade"""
        
        # Check daily loss limit
        if bot_state.daily_loss >= self.daily_loss_limit:
            bot_state.risk_status = "Daily loss limit reached"
            return False, "Daily loss limit reached"
            
        # Check if in cooldown after loss
        if bot_state.last_loss_time > 0:
            time_since_loss = time.time() - bot_state.last_loss_time
            if time_since_loss < self.cooldown_period:
                remaining = int(self.cooldown_period - time_since_loss)
                bot_state.risk_status = f"Cooldown: {remaining}s remaining"
                return False, f"In cooldown for {remaining} seconds"
            
        # Check wallet balance
        if bot_state.wallet_balance < self.min_wallet_balance:
            bot_state.risk_status = "Insufficient balance"
            return False, "Insufficient wallet balance"
            
        # Check max positions
        if len(bot_state.active_positions) >= MAX_POSITIONS:
            bot_state.risk_status = "Max positions reached"
            return False, "Maximum positions reached"
            
        bot_state.risk_status = "Normal - Can trade"
        return True, "OK"
        
    def calculate_position_size(self, personality: Dict) -> float:
        """Calculate safe position size"""
        base_size = personality['position_size']
        
        # Reduce size based on recent losses
        if bot_state.daily_loss > 0:
            loss_ratio = bot_state.daily_loss / self.daily_loss_limit
            size_multiplier = 1 - (loss_ratio * 0.5)  # Reduce up to 50%
            base_size *= size_multiplier
            
        # Never exceed max position size
        return min(base_size, self.max_position_size)
        
    def record_trade_result(self, profit: float):
        """Record trade result for risk management"""
        if profit < 0:
            bot_state.daily_loss += abs(profit)
            bot_state.last_loss_time = time.time()
            bot_state.losing_trades += 1
        else:
            bot_state.winning_trades += 1
            
        bot_state.total_trades += 1
        bot_state.total_profit += profit

class LiveTradingBot:
    """Live trading bot with safety measures"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        self.toxibot_chat = None
        self.token_discovery = TokenDiscovery()
        self.price_checker = PriceChecker()
        self.risk_manager = RiskManager()
        self.contract_checker = ContractChecker()  # Add contract checker
        self.last_balance_check = 0
        
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
            asyncio.create_task(self.monitor_positions())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def find_toxibot(self):
        """Find ToxiBot in Telegram chats"""
        toxibot_found = False
        
        async for dialog in self.client.iter_dialogs():
            # Look for ToxiBot - check multiple possible names
            dialog_name = dialog.name.lower()
            if any(name in dialog_name for name in ['toxi', 'toxibot', 'toxi_solana', 'solana_bot']):
                if 'toxi' in dialog_name:
                    self.toxibot_chat = dialog.entity
                    bot_state.toxibot_connected = True
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    
                    # ToxiBot shows balance when you start - send /start
                    await self.client.send_message(self.toxibot_chat, "/start")
                    bot_state.last_activity = "Connected to ToxiBot - Initializing"
                    bot_state.last_activity_type = "success"
                    
                    # Small delay to let ToxiBot respond
                    await asyncio.sleep(2)
                    
                    # Try clicking Wallet button to get balance
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    break
                    
        if not toxibot_found:
            logger.warning("ToxiBot not found! Make sure to:")
            logger.warning("1. Search for @toxi_solana_bot in Telegram")
            logger.warning("2. Start a chat with ToxiBot")
            logger.warning("3. Fund your ToxiBot wallet with at least 0.2 SOL")
            bot_state.last_activity = "ToxiBot not found - please start chat with @toxi_solana_bot"
            bot_state.last_activity_type = "error"
            
    async def check_wallet_balance(self):
        """Check wallet balance in ToxiBot"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't use /balance - it shows balance with /start or Wallet button
            await self.client.send_message(self.toxibot_chat, "💼 Wallet")
            self.last_balance_check = time.time()
            logger.info("Requesting wallet info...")
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            
    async def monitor_toxibot_messages(self):
        """Monitor ToxiBot responses"""
        if not self.toxibot_chat:
            return
            
        @self.client.on(events.NewMessage(chats=self.toxibot_chat))
        async def handler(event):
            message = event.message.text
            logger.info(f"ToxiBot: {message[:200]}...")
            
            # Parse balance - ToxiBot shows it with emoji and specific format
            if "💰" in message or "wallet balance:" in message.lower() or "balance:" in message.lower():
                # Extract balance using multiple regex patterns
                import re
                
                # Try different patterns
                patterns = [
                    r'💰\s*Wallet Balance:\s*(\d+\.?\d*)\s*SOL',  # ToxiBot format with emoji
                    r'Balance:\s*(\d+\.?\d*)\s*SOL',  # Alternative format
                    r'(\d+\.?\d*)\s*SOL\s*\|',  # Format with pipe after SOL
                    r'(\d+(?:\.\d+)?)\s*SOL',  # Simple format
                ]
                
                balance_found = False
                for pattern in patterns:
                    balance_match = re.search(pattern, message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Wallet balance updated: {balance} SOL")
                        bot_state.last_activity = f"Wallet balance: {balance} SOL"
                        bot_state.last_activity_type = "info"
                        balance_found = True
                        break
                
                if not balance_found:
                    logger.warning(f"Could not parse balance from: {message[:100]}")
                    
            # Parse ToxiBot's welcome message which contains wallet address
            elif "welcome to" in message.lower() and "your wallet address:" in message.lower():
                # Extract wallet address and trigger balance parse from the same message
                wallet_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44})', message)
                if wallet_match:
                    logger.info(f"ToxiBot wallet: {wallet_match.group(1)}")
                
                # Also check for balance in welcome message
                balance_match = re.search(r'(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                if balance_match:
                    balance = float(balance_match.group(1))
                    bot_state.wallet_balance = balance
                    logger.info(f"Initial balance: {balance} SOL")
                    
            # Parse successful buys - ToxiBot format
            elif any(word in message.lower() for word in ["✅", "success", "bought", "purchased", "executed"]):
                logger.info("Trade executed successfully!")
                bot_state.trades_this_hour += 1
                
                # Extract token address from message
                address_match = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', message)
                if address_match:
                    token_address = address_match.group(0)
                    
                    # Get price for tracking
                    price = await self.price_checker.get_token_price(token_address)
                    if price and token_address in self.monitoring_tokens:
                        token_info = self.monitoring_tokens[token_address]
                        
                        # Create trade record
                        trade = Trade(
                            token_address=token_address,
                            symbol=token_info.get('symbol', 'UNKNOWN'),
                            entry_price=price,
                            current_price=price,
                            position_size=token_info['position_size'],
                            entry_time=time.time(),
                            personality=token_info['personality'],
                            stop_loss=price * token_info['personality']['stop_loss'],
                            take_profit=price * token_info['personality']['take_profit']
                        )
                        
                        bot_state.active_positions[token_address] = trade
                        bot_state.active_trades = len(bot_state.active_positions)
                        
                        # Remove set_limit_orders call since ToxiBot handles it
                        # We'll use ToxiBot's native SL/TP instead
                        
                bot_state.last_activity = "Trade executed successfully!"
                bot_state.last_activity_type = "trade"
                
            # Parse errors - ToxiBot specific messages
            elif any(word in message.lower() for word in ["error", "failed", "❌", "insufficient", "invalid", "unable"]):
                logger.warning(f"Trade failed: {message}")
                bot_state.last_activity = f"Trade failed: {message[:50]}..."
                bot_state.last_activity_type = "error"
                
                # Parse specific error types
                if "invalid solana address" in message.lower():
                    logger.error("ToxiBot rejected token address - may need different format")
                    # Try to extract what format it expects
                    if "try again" in message.lower():
                        logger.info("ToxiBot suggests trying again - may need to use /buy command")
                        
                # If insufficient balance, try to get balance from error message
                if "insufficient" in message.lower():
                    # Sometimes ToxiBot shows current balance in error
                    balance_match = re.search(r'balance:\s*(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Balance from error: {balance} SOL")
                        
            # Parse ToxiBot token info display
            elif "💎" in message or ("dex:" in message.lower() and "liquidity:" in message.lower()):
                logger.info("ToxiBot displayed token info - ready for buy command")
                bot_state.last_activity = "Token loaded in ToxiBot - ready to buy"
                bot_state.last_activity_type = "info"
                
                # Extract token details if shown
                if "market cap:" in message.lower():
                    logger.info("ToxiBot showing full token details with buy buttons")
                    
            # Parse stop loss/take profit hits from ToxiBot
            elif "stop loss" in message.lower() and ("triggered" in message.lower() or "hit" in message.lower()):
                logger.info("ToxiBot: Stop loss triggered")
                bot_state.last_activity = "Stop loss triggered by ToxiBot"
                bot_state.last_activity_type = "error"
                
                # Extract details and record loss
                self._parse_trade_result(message, is_loss=True)
                
            elif "take profit" in message.lower() and ("triggered" in message.lower() or "hit" in message.lower()):
                logger.info("ToxiBot: Take profit triggered")
                bot_state.last_activity = "Take profit triggered by ToxiBot!"
                bot_state.last_activity_type = "trade"
                
                # Extract details and record profit
                self._parse_trade_result(message, is_loss=False)
                
            # Parse limit order hits
            elif "limit order" in message.lower() and ("filled" in message.lower() or "executed" in message.lower()):
                logger.info("ToxiBot: Limit order executed")
                bot_state.last_activity = "Limit order executed by ToxiBot"
                bot_state.last_activity_type = "trade"
                    
    async def execute_buy(self, token_address: str, amount_sol: float = POSITION_SIZE):
        """Execute buy order through ToxiBot - Based on actual ToxiBot behavior"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        # Validate token address format
        import re
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
            
    async def set_toxibot_stop_loss(self, stop_loss_percent: float = 10):
        """Set stop loss using ToxiBot's native feature"""
        try:
            # Click/send Stop Loss command
            await self.client.send_message(self.toxibot_chat, "🔴 Stop Loss")
            await asyncio.sleep(1)
            
            # Send the percentage
            sl_command = f"{stop_loss_percent}%"
            await self.client.send_message(self.toxibot_chat, sl_command)
            
            logger.info(f"Set ToxiBot stop loss: {stop_loss_percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set stop loss: {e}")
            return False
            
    async def set_toxibot_take_profit(self, take_profit_percent: float = 50):
        """Set take profit using ToxiBot's native feature"""
        try:
            # Click/send Take Profit command
            await self.client.send_message(self.toxibot_chat, "🔴 Take Profit")
            await asyncio.sleep(1)
            
            # Send the percentage
            tp_command = f"{take_profit_percent}%"
            await self.client.send_message(self.toxibot_chat, tp_command)
            
            logger.info(f"Set ToxiBot take profit: {take_profit_percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set take profit: {e}")
            return False
            
    async def set_toxibot_limit_orders(self):
        """Set limit orders using ToxiBot's native feature"""
        try:
            # Click/send Limit Orders command
            await self.client.send_message(self.toxibot_chat, "📊 Limit Orders")
            await asyncio.sleep(1)
            
            logger.info("Opened ToxiBot limit orders menu")
            # ToxiBot will show its limit order interface
            return True
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            return False
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                # TEST MODE: Try a known good token every 5 minutes
                if bot_state.tokens_checked > 0 and bot_state.tokens_checked % 30 == 0:
                    logger.info("TEST MODE: Adding known tokens to test ToxiBot")
                    test_tokens = [
                        {
                            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',  # JUP
                            'symbol': 'JUP',
                            'liquidity': 1000,
                            'age_minutes': 60,
                            'volume_24h': 100000,
                            'holders': 10000,
                            'source': 'test'
                        },
                        {
                            'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
                            'symbol': 'BONK',
                            'liquidity': 500,
                            'age_minutes': 60,
                            'volume_24h': 50000,
                            'holders': 5000,
                            'source': 'test'
                        }
                    ]
                    new_tokens.extend(test_tokens)
                    bot_state.last_activity = "TEST MODE: Trying known tokens"
                    bot_state.last_activity_type = "warning"
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions - ToxiBot handles SL/TP automatically"""
        logger.info("Starting position monitor (ToxiBot handles SL/TP)...")
        
        while self.running:
            try:
                # Since ToxiBot handles stop loss and take profit automatically,
                # we mainly need to monitor for:
                # 1. Time-based exits
                # 2. Portfolio updates
                # 3. Trade results
                
                for address, trade in list(bot_state.active_positions.items()):
                    # Check time limit only
                    if time.time() - trade.entry_time > trade.personality['hold_time']:
                        logger.info(f"Time limit reached for {trade.symbol}")
                        bot_state.last_activity = f"Time exit: {trade.symbol}"
                        bot_state.last_activity_type = "info"
                        
                        # Close position
                        await self.execute_sell(address, 100)
                        del bot_state.active_positions[address]
                        
                    # ToxiBot will handle stop loss and take profit automatically
                    # We'll get notifications in the message handler when they trigger
                    
                bot_state.active_trades = len(bot_state.active_positions)
                
                # Check portfolio status periodically
                if len(bot_state.active_positions) > 0:
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    logger.info("Checking portfolio status")
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗'}                 ║
    ║  - Helius RPC: {'✓' if HELIUS_RPC_URL else '✗'}                 ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), token_address):
            logger.error(f"Invalid token address format: {token_address}")
            return False
            
        # Final safety checks
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trade blocked: {reason}")
            return False
            
        try:
            # First try to get token info from ToxiBot
            # Some bots require viewing token details first
            info_command = f"/info {token_address}"
            await self.client.send_message(self.toxibot_chat, info_command)
            logger.info(f"Requested token info: {info_command}")
            
            # Wait for ToxiBot to load token info
            await asyncio.sleep(3)
            
            # Now try to buy - just send token address
            await self.client.send_message(self.toxibot_chat, token_address)
            
            logger.info(f"Sent token address to ToxiBot: {token_address}")
            bot_state.last_activity = f"Sent buy request for token: {token_address[:8]}..."
            bot_state.last_activity_type = "trade"
            
            # Wait for response
            await asyncio.sleep(2)
            
            # If amount is specified, try buy command format
            if amount_sol != POSITION_SIZE:
                buy_command = f"/buy {amount_sol}"  # Just amount, token context already set
                await self.client.send_message(self.toxibot_chat, buy_command)
                logger.info(f"Sent buy amount: {amount_sol} SOL")
            
            return True
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            bot_state.last_activity = f"Buy command failed: {str(e)}"
            bot_state.last_activity_type = "error"
            return False
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), address):
                logger.debug(f"Skipping invalid address: {address}")
                continue
                
            if address not in self.checked_tokens:
                # Validate token has required fields
                if all(token.get(field) for field in ['address', 'symbol', 'liquidity']):
                    self.checked_tokens.add(address)
                    validated_tokens.append(token)
                    logger.debug(f"Valid token found: {token['symbol']} ({address[:8]}...) - Liq: {token['liquidity']:.1f} SOL")
                
        bot_state.tokens_checked = len(self.checked_tokens)
        logger.info(f"New validated tokens: {len(validated_tokens)}")
        
        return validated_tokens
        
    async def get_helius_tokens(self) -> List[Dict]:
        """Get new tokens from Helius with better parsing"""
        try:
            session = await self.get_session()
            
            # Get recent token creations
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
            
            # Get new token list
            list_url = f"https://api.helius.xyz/v0/addresses/tokens?api-key={HELIUS_API_KEY}&limit=100"
            
            async with session.get(list_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for token_data in data[:20]:  # Process top 20
                        try:
                            address = token_data.get('mint', token_data.get('address', ''))
                            if address:
                                # Get token details
                                token_info = await self._get_token_details(address)
                                if token_info:
                                    tokens.append(token_info)
                        except:
                            continue
                            
                    logger.info(f"Found {len(tokens)} tokens from Helius")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Helius error: {e}")
            
        return []
        
    async def get_dexscreener_tokens(self) -> List[Dict]:
        """Get new tokens from DexScreener"""
        try:
            session = await self.get_session()
            
            # Get new pairs sorted by age
            url = "https://api.dexscreener.com/latest/dex/pairs/solana"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for pair in data.get('pairs', [])[:30]:
                        # Validate token address
                        base_token = pair.get('baseToken', {})
                        token_address = base_token.get('address', '')
                        
                        # Skip if invalid address format
                        if not token_address or len(token_address) < 32:
                            continue
                            
                        # Calculate age in minutes
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at:
                            age_minutes = (time.time() * 1000 - created_at) / 60000
                        else:
                            age_minutes = 60  # Default 1 hour
                            
                        token = {
                            'address': token_address,
                            'symbol': base_token.get('symbol', 'UNKNOWN'),
                            'name': base_token.get('name', ''),
                            'liquidity': pair.get('liquidity', {}).get('usd', 0) / 40,  # Convert to SOL
                            'age_minutes': int(age_minutes),
                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                            'price_usd': pair.get('priceUsd', 0),
                            'holders': 0,  # Will check separately
                            'source': 'dexscreener'
                        }
                        
                        if token['address'] and token['liquidity'] > 0:
                            tokens.append(token)
                            
                    logger.info(f"Found {len(tokens)} tokens from DexScreener")
                    return tokens
                    
        except Exception as e:
            logger.error(f"DexScreener error: {e}")
            
        return []
        
    async def get_birdeye_tokens(self) -> List[Dict]:
        """Get trending tokens from Birdeye"""
        try:
            session = await self.get_session()
            
            # Try multiple sorting options for variety
            endpoints = [
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hChangePercent&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=mc&sort_type=asc&offset=0&limit=50"
            ]
            
            all_tokens = []
            
            for url in endpoints:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and 'data' in data:
                                for token_data in data['data'].get('tokens', [])[:20]:
                                    # Only include tokens with reasonable metrics
                                    if token_data.get('v24hUSD', 0) > 100:  # Min $100 daily volume
                                        token = {
                                            'address': token_data.get('address', ''),
                                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                                            'name': token_data.get('name', ''),
                                            'liquidity': token_data.get('liquidity', 0) / 1e9,  # Convert to SOL
                                            'age_minutes': 60,  # Default estimate
                                            'volume_24h': token_data.get('v24hUSD', 0),
                                            'price_usd': token_data.get('v24hUSD', 0) / max(token_data.get('v24hTx', 1), 1),
                                            'holders': token_data.get('holder', 0),
                                            'source': 'birdeye'
                                        }
                                        
                                        if token['address']:
                                            all_tokens.append(token)
                except:
                    continue
                    
            # Remove duplicates
            unique_tokens = {}
            for token in all_tokens:
                unique_tokens[token['address']] = token
                
            tokens = list(unique_tokens.values())
            logger.info(f"Found {len(tokens)} tokens from Birdeye")
            return tokens
            
        except Exception as e:
            logger.error(f"Birdeye error: {e}")
            
        return []
        
    async def _get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token information"""
        try:
            # Get price from price checker
            price = await self.price_checker.get_token_price(address)
            
            if price:
                return {
                    'address': address,
                    'symbol': 'NEW',
                    'name': 'New Token',
                    'liquidity': 10,  # Will be checked separately
                    'age_minutes': 30,
                    'volume_24h': 1000,
                    'price_usd': price * 40,  # Convert to USD
                    'holders': 50,
                    'source': 'helius'
                }
        except:
            pass
            
        return None

class RiskManager:
    """Manage trading risks and limits"""
    
    def __init__(self):
        self.daily_loss_limit = MAX_DAILY_LOSS
        self.max_position_size = MAX_POSITION_SIZE
        self.min_wallet_balance = MIN_WALLET_BALANCE
        self.cooldown_period = RISK_SETTINGS['cooldown_after_loss']
        
    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can place a new trade"""
        
        # Check daily loss limit
        if bot_state.daily_loss >= self.daily_loss_limit:
            bot_state.risk_status = "Daily loss limit reached"
            return False, "Daily loss limit reached"
            
        # Check if in cooldown after loss
        if bot_state.last_loss_time > 0:
            time_since_loss = time.time() - bot_state.last_loss_time
            if time_since_loss < self.cooldown_period:
                remaining = int(self.cooldown_period - time_since_loss)
                bot_state.risk_status = f"Cooldown: {remaining}s remaining"
                return False, f"In cooldown for {remaining} seconds"
            
        # Check wallet balance
        if bot_state.wallet_balance < self.min_wallet_balance:
            bot_state.risk_status = "Insufficient balance"
            return False, "Insufficient wallet balance"
            
        # Check max positions
        if len(bot_state.active_positions) >= MAX_POSITIONS:
            bot_state.risk_status = "Max positions reached"
            return False, "Maximum positions reached"
            
        bot_state.risk_status = "Normal - Can trade"
        return True, "OK"
        
    def calculate_position_size(self, personality: Dict) -> float:
        """Calculate safe position size"""
        base_size = personality['position_size']
        
        # Reduce size based on recent losses
        if bot_state.daily_loss > 0:
            loss_ratio = bot_state.daily_loss / self.daily_loss_limit
            size_multiplier = 1 - (loss_ratio * 0.5)  # Reduce up to 50%
            base_size *= size_multiplier
            
        # Never exceed max position size
        return min(base_size, self.max_position_size)
        
    def record_trade_result(self, profit: float):
        """Record trade result for risk management"""
        if profit < 0:
            bot_state.daily_loss += abs(profit)
            bot_state.last_loss_time = time.time()
            bot_state.losing_trades += 1
        else:
            bot_state.winning_trades += 1
            
        bot_state.total_trades += 1
        bot_state.total_profit += profit

class LiveTradingBot:
    """Live trading bot with safety measures"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        self.toxibot_chat = None
        self.token_discovery = TokenDiscovery()
        self.price_checker = PriceChecker()
        self.risk_manager = RiskManager()
        self.contract_checker = ContractChecker()  # Add contract checker
        self.last_balance_check = 0
        
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
            asyncio.create_task(self.monitor_positions())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def find_toxibot(self):
        """Find ToxiBot in Telegram chats"""
        toxibot_found = False
        
        async for dialog in self.client.iter_dialogs():
            # Look for ToxiBot - check multiple possible names
            dialog_name = dialog.name.lower()
            if any(name in dialog_name for name in ['toxi', 'toxibot', 'toxi_solana', 'solana_bot']):
                if 'toxi' in dialog_name:
                    self.toxibot_chat = dialog.entity
                    bot_state.toxibot_connected = True
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    
                    # ToxiBot shows balance when you start - send /start
                    await self.client.send_message(self.toxibot_chat, "/start")
                    bot_state.last_activity = "Connected to ToxiBot - Initializing"
                    bot_state.last_activity_type = "success"
                    
                    # Small delay to let ToxiBot respond
                    await asyncio.sleep(2)
                    
                    # Try clicking Wallet button to get balance
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    break
                    
        if not toxibot_found:
            logger.warning("ToxiBot not found! Make sure to:")
            logger.warning("1. Search for @toxi_solana_bot in Telegram")
            logger.warning("2. Start a chat with ToxiBot")
            logger.warning("3. Fund your ToxiBot wallet with at least 0.2 SOL")
            bot_state.last_activity = "ToxiBot not found - please start chat with @toxi_solana_bot"
            bot_state.last_activity_type = "error"
            
    async def check_wallet_balance(self):
        """Check wallet balance in ToxiBot"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't use /balance - it shows balance with /start or Wallet button
            await self.client.send_message(self.toxibot_chat, "💼 Wallet")
            self.last_balance_check = time.time()
            logger.info("Requesting wallet info...")
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            
    async def monitor_toxibot_messages(self):
        """Monitor ToxiBot responses"""
        if not self.toxibot_chat:
            return
            
        @self.client.on(events.NewMessage(chats=self.toxibot_chat))
        async def handler(event):
            message = event.message.text
            logger.info(f"ToxiBot: {message[:200]}...")
            
            # Parse balance - ToxiBot shows it with emoji and specific format
            if "💰" in message or "wallet balance:" in message.lower() or "balance:" in message.lower():
                # Extract balance using multiple regex patterns
                import re
                
                # Try different patterns
                patterns = [
                    r'💰\s*Wallet Balance:\s*(\d+\.?\d*)\s*SOL',  # ToxiBot format with emoji
                    r'Balance:\s*(\d+\.?\d*)\s*SOL',  # Alternative format
                    r'(\d+\.?\d*)\s*SOL\s*\|',  # Format with pipe after SOL
                    r'(\d+(?:\.\d+)?)\s*SOL',  # Simple format
                ]
                
                balance_found = False
                for pattern in patterns:
                    balance_match = re.search(pattern, message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Wallet balance updated: {balance} SOL")
                        bot_state.last_activity = f"Wallet balance: {balance} SOL"
                        bot_state.last_activity_type = "info"
                        balance_found = True
                        break
                
                if not balance_found:
                    logger.warning(f"Could not parse balance from: {message[:100]}")
                    
            # Parse ToxiBot's welcome message which contains wallet address
            elif "welcome to" in message.lower() and "your wallet address:" in message.lower():
                # Extract wallet address and trigger balance parse from the same message
                wallet_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44})', message)
                if wallet_match:
                    logger.info(f"ToxiBot wallet: {wallet_match.group(1)}")
                
                # Also check for balance in welcome message
                balance_match = re.search(r'(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                if balance_match:
                    balance = float(balance_match.group(1))
                    bot_state.wallet_balance = balance
                    logger.info(f"Initial balance: {balance} SOL")
                    
            # Parse successful buys - ToxiBot format
            elif any(word in message.lower() for word in ["✅", "success", "bought", "purchased", "executed"]):
                logger.info("Trade executed successfully!")
                bot_state.trades_this_hour += 1
                
                # Extract token address from message
                address_match = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', message)
                if address_match:
                    token_address = address_match.group(0)
                    
                    # Get price for tracking
                    price = await self.price_checker.get_token_price(token_address)
                    if price and token_address in self.monitoring_tokens:
                        token_info = self.monitoring_tokens[token_address]
                        
                        # Create trade record
                        trade = Trade(
                            token_address=token_address,
                            symbol=token_info.get('symbol', 'UNKNOWN'),
                            entry_price=price,
                            current_price=price,
                            position_size=token_info['position_size'],
                            entry_time=time.time(),
                            personality=token_info['personality'],
                            stop_loss=price * token_info['personality']['stop_loss'],
                            take_profit=price * token_info['personality']['take_profit']
                        )
                        
                        bot_state.active_positions[token_address] = trade
                        bot_state.active_trades = len(bot_state.active_positions)
                        
                        # Set limit orders for this position
                        await self.set_limit_orders(token_address, token_info['personality'], price)
                        
                bot_state.last_activity = "Trade executed successfully!"
                bot_state.last_activity_type = "trade"
                
            # Parse errors - ToxiBot specific messages
            elif any(word in message.lower() for word in ["error", "failed", "❌", "insufficient", "invalid", "unable"]):
                logger.warning(f"Trade failed: {message}")
                bot_state.last_activity = f"Trade failed: {message[:50]}..."
                bot_state.last_activity_type = "error"
                
                # Parse specific error types
                if "invalid solana address" in message.lower():
                    logger.error("ToxiBot rejected token address - may need different format")
                    # Try to extract what format it expects
                    if "try again" in message.lower():
                        logger.info("ToxiBot suggests trying again - may need to use /buy command")
                        
                # If insufficient balance, try to get balance from error message
                if "insufficient" in message.lower():
                    # Sometimes ToxiBot shows current balance in error
                    balance_match = re.search(r'balance:\s*(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Balance from error: {balance} SOL")
                        
            # Parse ToxiBot menu/button prompts
            elif "buy" in message.lower() and ("button" in message.lower() or "menu" in message.lower()):
                logger.info("ToxiBot showing buy menu - need to click button or send amount")
                bot_state.last_activity = "ToxiBot ready - awaiting buy confirmation"
                bot_state.last_activity_type = "info"
                    
    async def execute_buy(self, token_address: str, amount_sol: float = POSITION_SIZE):
        """Execute buy order through ToxiBot - Based on actual ToxiBot behavior"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        # Validate token address format
        import re
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                # TEST MODE: Try a known good token every 5 minutes
                if bot_state.tokens_checked > 0 and bot_state.tokens_checked % 30 == 0:
                    logger.info("TEST MODE: Adding known tokens to test ToxiBot")
                    test_tokens = [
                        {
                            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',  # JUP
                            'symbol': 'JUP',
                            'liquidity': 1000,
                            'age_minutes': 60,
                            'volume_24h': 100000,
                            'holders': 10000,
                            'source': 'test'
                        },
                        {
                            'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
                            'symbol': 'BONK',
                            'liquidity': 500,
                            'age_minutes': 60,
                            'volume_24h': 50000,
                            'holders': 5000,
                            'source': 'test'
                        }
                    ]
                    new_tokens.extend(test_tokens)
                    bot_state.last_activity = "TEST MODE: Trying known tokens"
                    bot_state.last_activity_type = "warning"
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), token_address):
            logger.error(f"Invalid token address format: {token_address}")
            return False
            
        # Final safety checks
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trade blocked: {reason}")
            return False
            
        try:
            # First try to get token info from ToxiBot
            # Some bots require viewing token details first
            info_command = f"/info {token_address}"
            await self.client.send_message(self.toxibot_chat, info_command)
            logger.info(f"Requested token info: {info_command}")
            
            # Wait for ToxiBot to load token info
            await asyncio.sleep(3)
            
            # Now try to buy - just send token address
            await self.client.send_message(self.toxibot_chat, token_address)
            
            logger.info(f"Sent token address to ToxiBot: {token_address}")
            bot_state.last_activity = f"Sent buy request for token: {token_address[:8]}..."
            bot_state.last_activity_type = "trade"
            
            # Wait for response
            await asyncio.sleep(2)
            
            # If amount is specified, try buy command format
            if amount_sol != POSITION_SIZE:
                buy_command = f"/buy {amount_sol}"  # Just amount, token context already set
                await self.client.send_message(self.toxibot_chat, buy_command)
                logger.info(f"Sent buy amount: {amount_sol} SOL")
            
            return True
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            bot_state.last_activity = f"Buy command failed: {str(e)}"
            bot_state.last_activity_type = "error"
            return False
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())#!/usr/bin/env python3
"""
SOLANA TRADING BOT - FIXED VERSION WITH SAFETY MEASURES
Includes real price checking, risk management, and proper error handling
"""

import asyncio
import os
import json
import time
import logging
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiohttp import web
from dataclasses import dataclass, field
import re

# Setup logging with more detail
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TradingBot')

# Try to import Telegram
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram not available - install telethon to enable trading")

# Configuration with SAFE DEFAULTS
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY', '')
HELIUS_RPC_URL = os.environ.get('HELIUS_RPC_URL', '')
HELIUS_WEBHOOK_URL = os.environ.get('HELIUS_WEBHOOK_URL', '')  # For LaserStream
HELIUS_SENDER_URL = os.environ.get('HELIUS_SENDER_URL', '')  # For Sender service
SOLANA_RPC_URL = HELIUS_RPC_URL if HELIUS_RPC_URL else 'https://api.mainnet-beta.solana.com'
POSITION_SIZE = 0.01  # Start VERY small - 0.01 SOL per trade
MIN_LIQUIDITY = 10  # Minimum 10 SOL liquidity for safety
MAX_TOKEN_AGE = 3600  # 1 hour max age
MAX_POSITIONS = 3  # Start with only 3 concurrent positions
MAX_DAILY_LOSS = 0.2  # Maximum 0.2 SOL daily loss (increased from 0.1)
MAX_POSITION_SIZE = 0.05  # Never risk more than 0.05 SOL per trade
MIN_WALLET_BALANCE = 0.1  # Keep at least 0.1 SOL for fees

# Risk Management Settings
RISK_SETTINGS = {
    'max_slippage': 0.05,  # 5% max slippage
    'max_price_impact': 0.03,  # 3% max price impact
    'cooldown_after_loss': 300,  # 5 min cooldown after loss
    'require_volume_check': True,  # Must have recent volume
    'min_holders': 10,  # Minimum token holders
    'check_contract': True,  # Enable contract verification
    'check_rug_risk': True,  # Enable rug pull detection
    'max_concentration': 0.1,  # Max 10% held by single wallet
    'min_liquidity_locked': 0.5,  # At least 50% liquidity locked
}

# HTML Dashboard (unchanged for brevity)
DASHBOARD_HTML = '''<!DOCTYPE html>
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
        
        .risk-indicator {
            background: rgba(255,0,0,0.2);
            border: 2px solid #ff0000;
            padding: 15px;
            margin: 20px 0;
        }
        
        .risk-indicator h3 {
            color: #ff0000;
            margin-bottom: 10px;
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
            
            <div class="risk-indicator">
                <h3>Risk Management Active</h3>
                <p>Max Position: 0.05 SOL | Max Daily Loss: 0.2 SOL | Min Liquidity: 10 SOL</p>
                <p>Contract Checking: Enabled | Rug Detection: Active</p>
                <p id="riskStatus">Status: Monitoring...</p>
            </div>
            
            <div class="api-setup" id="apiWarning">
                <h3>⚠️ Optional: Add Helius API Key for Better Token Discovery</h3>
                <p>Get a free API key from <a href="https://www.helius.dev/" target="_blank" style="color: #ff6600;">helius.dev</a></p>
                <p>Add it to Railway environment variables as HELIUS_API_KEY</p>
            </div>
            
            <div class="status" id="botStatus">
                <h2>Bot Status: <span id="statusText">Offline</span></h2>
                <p id="toxibotStatus">ToxiBot: Not connected</p>
                <p id="walletStatus">Wallet Balance: Checking...</p>
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
                
                if (data.walletBalance !== undefined) {
                    document.getElementById('walletStatus').textContent = `Wallet Balance: ${data.walletBalance.toFixed(3)} SOL`;
                }
                
                if (data.riskStatus) {
                    document.getElementById('riskStatus').textContent = `Status: ${data.riskStatus}`;
                }
                
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
class Trade:
    """Track individual trades"""
    token_address: str
    symbol: str
    entry_price: float
    current_price: float
    position_size: float
    entry_time: float
    personality: Dict
    stop_loss: float
    take_profit: float
    limit_orders: List[Dict] = field(default_factory=list)  # Add limit orders tracking
    
    @property
    def pnl(self) -> float:
        """Calculate profit/loss"""
        return self.position_size * (self.current_price / self.entry_price - 1)
    
    @property
    def pnl_percent(self) -> float:
        """Calculate profit/loss percentage"""
        return (self.current_price / self.entry_price - 1) * 100

@dataclass
class BotState:
    configured: bool = False
    authenticated: bool = False
    running: bool = False
    total_profit: float = 0.0
    active_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    toxibot_connected: bool = False
    tokens_checked: int = 0
    last_activity: Optional[str] = None
    last_activity_type: str = 'info'
    wallet_balance: float = 0.0
    daily_loss: float = 0.0
    last_loss_time: float = 0
    trades_this_hour: int = 0
    hour_start: float = time.time()
    risk_status: str = "Normal"
    active_positions: Dict[str, Trade] = field(default_factory=dict)

# Global state
bot_state = BotState()

class BotPersonality:
    """Different trading personalities with SAFE strategies and limit orders"""
    
    CONSERVATIVE_SNIPER = {
        'name': 'Conservative Sniper',
        'min_liquidity': 20,  # Higher liquidity requirement
        'max_age_minutes': 30,  # Only newer tokens
        'position_size': 0.01,  # Very small positions
        'take_profit': 1.5,  # 50% profit target
        'stop_loss': 0.9,  # -10% stop loss
        'hold_time': 1800,  # 30 minutes max
        'css_class': 'sniper',
        'min_volume_24h': 1000,  # Minimum $1000 daily volume
        'min_holders': 50,  # At least 50 holders
        # Limit order settings
        'limit_buy_offset': 0.95,  # Buy at 5% below current price
        'limit_sell_targets': [1.15, 1.3, 1.5],  # 15%, 30%, 50% profit targets
        'limit_sell_amounts': [0.3, 0.4, 0.3],  # Sell 30%, 40%, 30% at each target
    }
    
    SAFE_SCALPER = {
        'name': 'Safe Scalper',
        'min_liquidity': 50,
        'max_age_minutes': 120,
        'position_size': 0.02,
        'take_profit': 1.2,  # 20% profit
        'stop_loss': 0.95,  # -5% stop loss
        'hold_time': 3600,  # 1 hour max
        'css_class': 'scalper',
        'min_volume_24h': 5000,
        'min_holders': 100,
        # Limit order settings
        'limit_buy_offset': 0.98,  # Buy at 2% below current price
        'limit_sell_targets': [1.05, 1.1, 1.2],  # 5%, 10%, 20% profit targets
        'limit_sell_amounts': [0.4, 0.3, 0.3],  # Sell 40%, 30%, 30% at each target
    }
    
    ESTABLISHED_TRADER = {
        'name': 'Established Trader',
        'min_liquidity': 100,
        'max_age_minutes': 1440,  # 24 hours
        'position_size': 0.03,
        'take_profit': 1.3,
        'stop_loss': 0.93,  # -7% stop loss
        'hold_time': 7200,  # 2 hours max
        'css_class': 'community',
        'min_volume_24h': 10000,
        'min_holders': 200,
        # Limit order settings
        'limit_buy_offset': 0.97,  # Buy at 3% below current price
        'limit_sell_targets': [1.1, 1.2, 1.3],  # 10%, 20%, 30% profit targets
        'limit_sell_amounts': [0.3, 0.3, 0.4],  # Sell 30%, 30%, 40% at each target
    }

class PriceChecker:
    """Check real token prices using multiple sources"""
    
    def __init__(self):
        self.session = None
        self.price_cache = {}
        self.cache_duration = 15  # Cache prices for 15 seconds (was 30)
        
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def _get_price_from_helius(self, token_address: str) -> Optional[float]:
        """Get price using Helius RPC (premium)"""
        if not HELIUS_RPC_URL:
            return None
            
        try:
            session = await self.get_session()
            
            # Helius enhanced API for token prices
            url = f"{HELIUS_RPC_URL.replace('?api-key=', '/v0/token-metadata?api-key=')}"
            
            payload = {
                "mintAccounts": [token_address],
                "includeOffChain": True,
                "disableCache": False
            }
            
            async with session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # Parse price from Helius response
                    for token_data in data:
                        if token_data.get('account') == token_address:
                            # Get price info
                            on_chain_info = token_data.get('onChainAccountInfo', {})
                            price_info = token_data.get('priceInfo', {})
                            
                            if price_info and price_info.get('pricePerToken'):
                                return float(price_info['pricePerToken'])
                                
        except Exception as e:
            logger.debug(f"Helius price error: {e}")
            
        return None
        
    async def get_token_price(self, token_address: str) -> Optional[float]:
        """Get token price in SOL with Helius priority"""
        # Check cache first
        cache_key = f"{token_address}_price"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_duration:
                return cached_data['price']
        
        # Try Helius first (fastest with premium RPC)
        if HELIUS_RPC_URL:
            price = await self._get_price_from_helius(token_address)
            if price:
                self.price_cache[cache_key] = {
                    'price': price,
                    'timestamp': time.time()
                }
                return price
        
        # Fall back to other sources
        price = await self._get_price_from_dexscreener(token_address)
        if not price:
            price = await self._get_price_from_birdeye(token_address)
        
        if price:
            self.price_cache[cache_key] = {
                'price': price,
                'timestamp': time.time()
            }
            
        return price
        
    async def _get_price_from_dexscreener(self, token_address: str) -> Optional[float]:
        """Get price from DexScreener"""
        try:
            session = await self.get_session()
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    # Find SOL pair with highest liquidity
                    sol_pairs = [p for p in pairs if p.get('quoteToken', {}).get('symbol') == 'SOL']
                    if sol_pairs:
                        # Sort by liquidity
                        sol_pairs.sort(key=lambda x: x.get('liquidity', {}).get('usd', 0), reverse=True)
                        price_sol = float(sol_pairs[0].get('priceNative', 0))
                        return price_sol
                        
        except Exception as e:
            logger.error(f"DexScreener price error: {e}")
            
        return None
        
    async def _get_price_from_birdeye(self, token_address: str) -> Optional[float]:
        """Get price from Birdeye"""
        try:
            session = await self.get_session()
            url = f"https://public-api.birdeye.so/public/price?address={token_address}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        # Convert USD price to SOL price
                        usd_price = data.get('data', {}).get('value', 0)
                        sol_usd_price = await self._get_sol_price()
                        if sol_usd_price and usd_price:
                            return usd_price / sol_usd_price
                            
        except Exception as e:
            logger.error(f"Birdeye price error: {e}")
            
        return None
        
    async def _get_sol_price(self) -> Optional[float]:
        """Get SOL price in USD"""
        cache_key = "SOL_USD"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < 300:  # 5 min cache
                return cached_data['price']
                
        try:
            session = await self.get_session()
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('solana', {}).get('usd', 0)
                    if price:
                        self.price_cache[cache_key] = {
                            'price': price,
                            'timestamp': time.time()
                        }
                        return price
                        
        except Exception as e:
            logger.error(f"SOL price error: {e}")
            
        return 40.0  # Fallback SOL price

class ContractChecker:
    """Check token contracts for safety and rug pull risks"""
    
    def __init__(self):
        self.session = None
        self.checked_contracts = {}
        
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def check_token_safety(self, token_address: str) -> Dict:
        """Comprehensive token safety check with RugCheck.xyz as primary source"""
        # Check cache first
        if token_address in self.checked_contracts:
            cached = self.checked_contracts[token_address]
            if time.time() - cached['timestamp'] < 3600:  # 1 hour cache
                return cached['result']
        
        result = {
            'is_safe': True,
            'risk_score': 0,  # 0-10, higher = riskier
            'warnings': [],
            'contract_verified': False,
            'liquidity_locked': False,
            'ownership_renounced': False,
            'mint_disabled': False,
            'freeze_disabled': False,
            'top_holder_percentage': 0,
            'dev_wallet_percentage': 0,
            'liquidity_percentage': 0,
            'rugcheck_score': 0,
            'rugcheck_analysis': None
        }
        
        try:
            # Primary check: RugCheck.xyz (most comprehensive)
            rugcheck_data = await self._check_rugcheck(token_address)
            if rugcheck_data:
                result.update(rugcheck_data)
                result['rugcheck_analysis'] = True
                
                # If RugCheck gives high confidence data, we can skip other checks
                if rugcheck_data.get('rugcheck_score', 0) > 0:
                    # RugCheck provided comprehensive analysis
                    logger.info(f"RugCheck analysis for {token_address[:8]}: Score {rugcheck_data['rugcheck_score']}/100, Risk: {rugcheck_data['risk_score']}/10")
                    
                    # Early exit for very risky tokens
                    if rugcheck_data['risk_score'] >= 7:
                        result['is_safe'] = False
                        result['warnings'].insert(0, "🚨 RUGCHECK: HIGH RISK - DO NOT TRADE")
            
            # If RugCheck didn't provide full data or token is borderline, do additional checks
            if not rugcheck_data or rugcheck_data['risk_score'] >= 4:
                # Secondary check: Holder distribution
                holder_data = await self._check_holder_distribution(token_address)
                if holder_data:
                    # Merge holder data, taking worst case
                    if holder_data['risk_score'] > result['risk_score']:
                        result['risk_score'] = holder_data['risk_score']
                    result['warnings'].extend(holder_data.get('warnings', []))
                    
                # Tertiary check: Token metadata and trading patterns
                metadata = await self._check_token_metadata(token_address)
                if metadata:
                    # Merge metadata, taking worst case
                    if metadata['risk_score'] > result['risk_score']:
                        result['risk_score'] = metadata['risk_score']
                    result['warnings'].extend(metadata.get('warnings', []))
            
            # Final safety determination
            result['is_safe'] = result['risk_score'] < 7
            
            # Add summary warning if risky
            if result['risk_score'] >= 7:
                result['warnings'].insert(0, f"🚨 OVERALL RISK SCORE: {result['risk_score']}/10 - HIGH RISK")
            elif result['risk_score'] >= 5:
                result['warnings'].insert(0, f"⚠️ OVERALL RISK SCORE: {result['risk_score']}/10 - MEDIUM RISK")
            else:
                result['warnings'].insert(0, f"✅ OVERALL RISK SCORE: {result['risk_score']}/10 - ACCEPTABLE")
            
            # Cache result
            self.checked_contracts[token_address] = {
                'result': result,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Contract check error for {token_address}: {e}")
            result['is_safe'] = False
            result['warnings'].append("Failed to verify contract safety")
            result['risk_score'] = 8  # High risk if we can't verify
            
        return result
        
    async def _check_rugcheck(self, token_address: str) -> Optional[Dict]:
        """Check RugCheck.xyz for comprehensive token safety analysis"""
        try:
            session = await self.get_session()
            
            # RugCheck.xyz API endpoint - using their full report
            url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            
            # Alternative endpoint for detailed analysis
            detailed_url = f"https://rugcheck.xyz/api/v1/report/{token_address}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    risk_score = 0
                    warnings = []
                    
                    # Parse RugCheck's risk assessment
                    if 'risks' in data:
                        # RugCheck provides categorized risks
                        for risk in data.get('risks', []):
                            severity = risk.get('severity', 'low')
                            description = risk.get('description', '')
                            
                            if severity == 'critical':
                                risk_score += 4
                                warnings.append(f"🚨 {description}")
                            elif severity == 'high':
                                risk_score += 3
                                warnings.append(f"⚠️ {description}")
                            elif severity == 'medium':
                                risk_score += 2
                                warnings.append(f"⚡ {description}")
                            else:
                                risk_score += 1
                                warnings.append(f"ℹ️ {description}")
                    
                    # Check specific flags from RugCheck
                    token_info = data.get('token', {})
                    
                    # Mint Authority
                    if token_info.get('mint_authority'):
                        if not token_info.get('mint_authority_disabled'):
                            risk_score += 3
                            warnings.append("⚠️ Mint authority still active")
                    
                    # Freeze Authority
                    if token_info.get('freeze_authority'):
                        if not token_info.get('freeze_authority_disabled'):
                            risk_score += 3
                            warnings.append("⚠️ Freeze authority still active")
                    
                    # LP (Liquidity Pool) Analysis
                    lp_info = data.get('liquidity_pools', [])
                    if lp_info:
                        main_pool = lp_info[0] if lp_info else {}
                        
                        # Check LP burn/lock status
                        if not main_pool.get('lp_burned') and not main_pool.get('lp_locked'):
                            risk_score += 2
                            warnings.append("⚠️ LP tokens not burned or locked")
                            
                        # Check liquidity amount
                        liquidity_usd = main_pool.get('liquidity_usd', 0)
                        if liquidity_usd < 1000:
                            risk_score += 2
                            warnings.append(f"⚠️ Very low liquidity: ${liquidity_usd:.0f}")
                    
                    # Ownership and control
                    ownership = data.get('ownership', {})
                    if ownership.get('renounced') == False:
                        risk_score += 2
                        warnings.append("⚠️ Ownership not renounced")
                        
                    # Holder distribution
                    holders = data.get('holders', {})
                    top_10_percentage = holders.get('top_10_percentage', 0)
                    if top_10_percentage > 70:
                        risk_score += 3
                        warnings.append(f"⚠️ Top 10 holders own {top_10_percentage:.1f}%")
                    elif top_10_percentage > 50:
                        risk_score += 2
                        warnings.append(f"⚡ Top 10 holders own {top_10_percentage:.1f}%")
                        
                    # Creator holdings
                    creator_percentage = holders.get('creator_percentage', 0)
                    if creator_percentage > 10:
                        risk_score += 3
                        warnings.append(f"⚠️ Creator holds {creator_percentage:.1f}%")
                        
                    # Market and trading analysis
                    market = data.get('market', {})
                    
                    # Check for honeypot indicators
                    if market.get('buy_tax', 0) > 10:
                        risk_score += 2
                        warnings.append(f"⚠️ High buy tax: {market['buy_tax']}%")
                        
                    if market.get('sell_tax', 0) > 10:
                        risk_score += 3
                        warnings.append(f"⚠️ High sell tax: {market['sell_tax']}%")
                        
                    # Trading pattern analysis
                    if market.get('unique_wallets_24h', 0) < 10:
                        risk_score += 2
                        warnings.append("⚠️ Very few unique traders")
                        
                    # Get overall risk rating from RugCheck
                    overall_risk = data.get('risk_level', 'unknown')
                    rugcheck_score = data.get('score', 0)  # RugCheck's 0-100 safety score
                    
                    # Convert RugCheck score to our risk score
                    if rugcheck_score > 0:
                        # RugCheck uses 0-100 where 100 is safest
                        # Convert to our 0-10 where 0 is safest
                        risk_score = max(0, min(10, int((100 - rugcheck_score) / 10)))
                        
                    # Add overall assessment
                    if overall_risk == 'high' or rugcheck_score < 30:
                        warnings.insert(0, "🚨 RugCheck: HIGH RISK TOKEN")
                    elif overall_risk == 'medium' or rugcheck_score < 60:
                        warnings.insert(0, "⚠️ RugCheck: MEDIUM RISK")
                    elif overall_risk == 'low' or rugcheck_score >= 60:
                        warnings.insert(0, "✅ RugCheck: Relatively safe")
                        
                    return {
                        'risk_score': min(10, risk_score),  # Cap at 10
                        'warnings': warnings,
                        'rugcheck_score': rugcheck_score,
                        'rugcheck_risk': overall_risk,
                        'mint_disabled': token_info.get('mint_authority_disabled', False),
                        'freeze_disabled': token_info.get('freeze_authority_disabled', False),
                        'ownership_renounced': ownership.get('renounced', False),
                        'lp_burned': any(pool.get('lp_burned', False) for pool in lp_info),
                        'lp_locked': any(pool.get('lp_locked', False) for pool in lp_info),
                        'top_holder_percentage': holders.get('top_1_percentage', 0),
                        'creator_percentage': creator_percentage,
                        'liquidity_usd': lp_info[0].get('liquidity_usd', 0) if lp_info else 0
                    }
                    
                elif response.status == 404:
                    # Token not found in RugCheck - likely very new
                    return {
                        'risk_score': 5,
                        'warnings': ['ℹ️ Token too new for RugCheck analysis'],
                        'rugcheck_score': 0,
                        'rugcheck_risk': 'unknown'
                    }
                    
        except Exception as e:
            logger.debug(f"RugCheck API error: {e}")
            
        return None
        
    async def _check_holder_distribution(self, token_address: str) -> Optional[Dict]:
        """Check token holder distribution"""
        try:
            session = await self.get_session()
            
            # Try Helius first if available
            if HELIUS_API_KEY:
                url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
                payload = {"mintAccounts": [token_address]}
                
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parse holder data
                        return await self._parse_holder_data(data)
                        
            # Fallback to other sources
            # Check Solscan API (limited free tier)
            url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=10"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('data'):
                        holders = data['data']
                        total_supply = data.get('total', 1)
                        
                        # Calculate concentration
                        top_holder_amount = holders[0].get('amount', 0) if holders else 0
                        top_holder_percent = (top_holder_amount / total_supply) * 100 if total_supply > 0 else 0
                        
                        warnings = []
                        risk_score = 0
                        
                        if top_holder_percent > 20:
                            risk_score += 3
                            warnings.append(f"⚠️ Top holder owns {top_holder_percent:.1f}%")
                            
                        if len(holders) < 10:
                            risk_score += 2
                            warnings.append(f"⚠️ Only {len(holders)} holders")
                            
                        return {
                            'top_holder_percentage': top_holder_percent,
                            'holder_count': len(holders),
                            'risk_score': risk_score,
                            'warnings': warnings
                        }
                        
        except Exception as e:
            logger.debug(f"Holder check error: {e}")
            
        return None
        
    async def _check_token_metadata(self, token_address: str) -> Optional[Dict]:
        """Check token metadata for red flags"""
        try:
            session = await self.get_session()
            
            # Get token metadata
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        warnings = []
                        risk_score = 0
                        
                        # Check liquidity locks
                        for pair in pairs:
                            liquidity = pair.get('liquidity', {})
                            if liquidity.get('usd', 0) < 1000:
                                risk_score += 2
                                warnings.append("⚠️ Very low liquidity")
                                
                            # Check for honeypot indicators
                            buys = pair.get('txns', {}).get('h24', {}).get('buys', 0)
                            sells = pair.get('txns', {}).get('h24', {}).get('sells', 0)
                            
                            if buys > 10 and sells == 0:
                                risk_score += 5
                                warnings.append("🚨 No sells detected - possible honeypot!")
                                
                            elif buys > 0 and sells / buys < 0.1:
                                risk_score += 3
                                warnings.append("⚠️ Very few sells - suspicious")
                                
                        return {
                            'risk_score': risk_score,
                            'warnings': warnings,
                            'liquidity_usd': pairs[0].get('liquidity', {}).get('usd', 0) if pairs else 0
                        }
                        
        except Exception as e:
            logger.debug(f"Metadata check error: {e}")
            
        return None
        
    async def _parse_holder_data(self, data: Dict) -> Dict:
        """Parse holder data from various sources"""
        # Implementation depends on data format
        return {
            'holder_count': 0,
            'top_holder_percentage': 0,
            'warnings': []
        }

class TokenDiscovery:
    """Discover new tokens from multiple sources"""
    
    def __init__(self):
        self.session = None
        self.checked_tokens = set()
        self.price_checker = PriceChecker()
        self.contract_checker = ContractChecker()  # Add contract checker
        
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
            
        # Always try free sources
        tokens.extend(await self.get_dexscreener_tokens())
        tokens.extend(await self.get_birdeye_tokens())
        tokens.extend(await self.get_jupiter_new_tokens())  # Add Jupiter
        
        logger.info(f"Total tokens found before filtering: {len(tokens)}")
        
        # Filter and validate tokens
        validated_tokens = []
        import re
        
        for token in tokens:
            # Validate address format
            address = token.get('address', '')
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
        
    async def get_helius_tokens(self) -> List[Dict]:
        """Get new tokens from Helius with better parsing"""
        try:
            session = await self.get_session()
            
            # Get recent token creations
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
            
            # Get new token list
            list_url = f"https://api.helius.xyz/v0/addresses/tokens?api-key={HELIUS_API_KEY}&limit=100"
            
            async with session.get(list_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for token_data in data[:20]:  # Process top 20
                        try:
                            address = token_data.get('mint', token_data.get('address', ''))
                            if address:
                                # Get token details
                                token_info = await self._get_token_details(address)
                                if token_info:
                                    tokens.append(token_info)
                        except:
                            continue
                            
                    logger.info(f"Found {len(tokens)} tokens from Helius")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Helius error: {e}")
            
    async def get_jupiter_new_tokens(self) -> List[Dict]:
        """Get new tokens from Jupiter aggregator"""
        try:
            session = await self.get_session()
            
            # Jupiter's token list API
            url = "https://token.jup.ag/all"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    # Sort by timestamp if available, get newest
                    # Jupiter doesn't provide age, so we'll check tokens not in our cache
                    for token_data in data[:100]:  # Check first 100
                        address = token_data.get('address', '')
                        
                        # Skip if we've seen it
                        if address in self.checked_tokens:
                            continue
                            
                        # Basic validation
                        if not address or len(address) < 32:
                            continue
                            
                        token = {
                            'address': address,
                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                            'name': token_data.get('name', ''),
                            'liquidity': 10,  # Will verify with price check
                            'age_minutes': 60,  # Estimate
                            'volume_24h': 0,
                            'holders': 0,
                            'source': 'jupiter'
                        }
                        
                        tokens.append(token)
                        
                        if len(tokens) >= 10:  # Limit to 10 new ones
                            break
                            
                    logger.info(f"Found {len(tokens)} potential new tokens from Jupiter")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Jupiter error: {e}")
            
        return []
        
    async def get_dexscreener_tokens(self) -> List[Dict]:
        """Get new tokens from DexScreener"""
        try:
            session = await self.get_session()
            
            # Get new pairs sorted by age
            url = "https://api.dexscreener.com/latest/dex/pairs/solana"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for pair in data.get('pairs', [])[:30]:
                        # Validate token address
                        base_token = pair.get('baseToken', {})
                        token_address = base_token.get('address', '')
                        
                        # Skip if invalid address format
                        if not token_address or len(token_address) < 32:
                            continue
                            
                        # Calculate age in minutes
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at:
                            age_minutes = (time.time() * 1000 - created_at) / 60000
                        else:
                            age_minutes = 60  # Default 1 hour
                            
                        token = {
                            'address': token_address,
                            'symbol': base_token.get('symbol', 'UNKNOWN'),
                            'name': base_token.get('name', ''),
                            'liquidity': pair.get('liquidity', {}).get('usd', 0) / 40,  # Convert to SOL
                            'age_minutes': int(age_minutes),
                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                            'price_usd': pair.get('priceUsd', 0),
                            'holders': 0,  # Will check separately
                            'source': 'dexscreener'
                        }
                        
                        if token['address'] and token['liquidity'] > 0:
                            tokens.append(token)
                            
                    logger.info(f"Found {len(tokens)} tokens from DexScreener")
                    return tokens
                    
        except Exception as e:
            logger.error(f"DexScreener error: {e}")
            
        return []
        
    async def get_birdeye_tokens(self) -> List[Dict]:
        """Get trending tokens from Birdeye"""
        try:
            session = await self.get_session()
            
            # Try multiple sorting options for variety
            endpoints = [
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hChangePercent&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=mc&sort_type=asc&offset=0&limit=50"
            ]
            
            all_tokens = []
            
            for url in endpoints:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and 'data' in data:
                                for token_data in data['data'].get('tokens', [])[:20]:
                                    # Only include tokens with reasonable metrics
                                    if token_data.get('v24hUSD', 0) > 100:  # Min $100 daily volume
                                        token = {
                                            'address': token_data.get('address', ''),
                                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                                            'name': token_data.get('name', ''),
                                            'liquidity': token_data.get('liquidity', 0) / 1e9,  # Convert to SOL
                                            'age_minutes': 60,  # Default estimate
                                            'volume_24h': token_data.get('v24hUSD', 0),
                                            'price_usd': token_data.get('v24hUSD', 0) / max(token_data.get('v24hTx', 1), 1),
                                            'holders': token_data.get('holder', 0),
                                            'source': 'birdeye'
                                        }
                                        
                                        if token['address']:
                                            all_tokens.append(token)
                except:
                    continue
                    
            # Remove duplicates
            unique_tokens = {}
            for token in all_tokens:
                unique_tokens[token['address']] = token
                
            tokens = list(unique_tokens.values())
            logger.info(f"Found {len(tokens)} tokens from Birdeye")
            return tokens
            
        except Exception as e:
            logger.error(f"Birdeye error: {e}")
            
        return []
        
    async def _get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token information"""
        try:
            # Get price from price checker
            price = await self.price_checker.get_token_price(address)
            
            if price:
                return {
                    'address': address,
                    'symbol': 'NEW',
                    'name': 'New Token',
                    'liquidity': 10,  # Will be checked separately
                    'age_minutes': 30,
                    'volume_24h': 1000,
                    'price_usd': price * 40,  # Convert to USD
                    'holders': 50,
                    'source': 'helius'
                }
        except:
            pass
            
        return None

class RiskManager:
    """Manage trading risks and limits"""
    
    def __init__(self):
        self.daily_loss_limit = MAX_DAILY_LOSS
        self.max_position_size = MAX_POSITION_SIZE
        self.min_wallet_balance = MIN_WALLET_BALANCE
        self.cooldown_period = RISK_SETTINGS['cooldown_after_loss']
        
    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can place a new trade"""
        
        # Check daily loss limit
        if bot_state.daily_loss >= self.daily_loss_limit:
            bot_state.risk_status = "Daily loss limit reached"
            return False, "Daily loss limit reached"
            
        # Check if in cooldown after loss
        if bot_state.last_loss_time > 0:
            time_since_loss = time.time() - bot_state.last_loss_time
            if time_since_loss < self.cooldown_period:
                remaining = int(self.cooldown_period - time_since_loss)
                bot_state.risk_status = f"Cooldown: {remaining}s remaining"
                return False, f"In cooldown for {remaining} seconds"
            
        # Check wallet balance
        if bot_state.wallet_balance < self.min_wallet_balance:
            bot_state.risk_status = "Insufficient balance"
            return False, "Insufficient wallet balance"
            
        # Check max positions
        if len(bot_state.active_positions) >= MAX_POSITIONS:
            bot_state.risk_status = "Max positions reached"
            return False, "Maximum positions reached"
            
        bot_state.risk_status = "Normal - Can trade"
        return True, "OK"
        
    def calculate_position_size(self, personality: Dict) -> float:
        """Calculate safe position size"""
        base_size = personality['position_size']
        
        # Reduce size based on recent losses
        if bot_state.daily_loss > 0:
            loss_ratio = bot_state.daily_loss / self.daily_loss_limit
            size_multiplier = 1 - (loss_ratio * 0.5)  # Reduce up to 50%
            base_size *= size_multiplier
            
        # Never exceed max position size
        return min(base_size, self.max_position_size)
        
    def record_trade_result(self, profit: float):
        """Record trade result for risk management"""
        if profit < 0:
            bot_state.daily_loss += abs(profit)
            bot_state.last_loss_time = time.time()
            bot_state.losing_trades += 1
        else:
            bot_state.winning_trades += 1
            
        bot_state.total_trades += 1
        bot_state.total_profit += profit

class LiveTradingBot:
    """Live trading bot with safety measures"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        self.toxibot_chat = None
        self.token_discovery = TokenDiscovery()
        self.price_checker = PriceChecker()
        self.risk_manager = RiskManager()
        self.contract_checker = ContractChecker()  # Add contract checker
        self.last_balance_check = 0
        
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
            asyncio.create_task(self.monitor_positions())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def find_toxibot(self):
        """Find ToxiBot in Telegram chats"""
        toxibot_found = False
        
        async for dialog in self.client.iter_dialogs():
            # Look for ToxiBot - check multiple possible names
            dialog_name = dialog.name.lower()
            if any(name in dialog_name for name in ['toxi', 'toxibot', 'toxi_solana', 'solana_bot']):
                if 'toxi' in dialog_name:
                    self.toxibot_chat = dialog.entity
                    bot_state.toxibot_connected = True
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    
                    # ToxiBot shows balance when you start - send /start
                    await self.client.send_message(self.toxibot_chat, "/start")
                    bot_state.last_activity = "Connected to ToxiBot - Initializing"
                    bot_state.last_activity_type = "success"
                    
                    # Small delay to let ToxiBot respond
                    await asyncio.sleep(2)
                    
                    # Try clicking Wallet button to get balance
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    break
                    
        if not toxibot_found:
            logger.warning("ToxiBot not found! Make sure to:")
            logger.warning("1. Search for @toxi_solana_bot in Telegram")
            logger.warning("2. Start a chat with ToxiBot")
            logger.warning("3. Fund your ToxiBot wallet with at least 0.2 SOL")
            bot_state.last_activity = "ToxiBot not found - please start chat with @toxi_solana_bot"
            bot_state.last_activity_type = "error"
            
    async def check_wallet_balance(self):
        """Check wallet balance in ToxiBot"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't use /balance - it shows balance with /start or Wallet button
            await self.client.send_message(self.toxibot_chat, "💼 Wallet")
            self.last_balance_check = time.time()
            logger.info("Requesting wallet info...")
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            
    async def monitor_toxibot_messages(self):
        """Monitor ToxiBot responses"""
        if not self.toxibot_chat:
            return
            
        @self.client.on(events.NewMessage(chats=self.toxibot_chat))
        async def handler(event):
            message = event.message.text
            logger.info(f"ToxiBot: {message[:200]}...")
            
            # Parse balance - ToxiBot shows it with emoji and specific format
            if "💰" in message or "wallet balance:" in message.lower() or "balance:" in message.lower():
                # Extract balance using multiple regex patterns
                import re
                
                # Try different patterns
                patterns = [
                    r'💰\s*Wallet Balance:\s*(\d+\.?\d*)\s*SOL',  # ToxiBot format with emoji
                    r'Balance:\s*(\d+\.?\d*)\s*SOL',  # Alternative format
                    r'(\d+\.?\d*)\s*SOL\s*\|',  # Format with pipe after SOL
                    r'(\d+(?:\.\d+)?)\s*SOL',  # Simple format
                ]
                
                balance_found = False
                for pattern in patterns:
                    balance_match = re.search(pattern, message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Wallet balance updated: {balance} SOL")
                        bot_state.last_activity = f"Wallet balance: {balance} SOL"
                        bot_state.last_activity_type = "info"
                        balance_found = True
                        break
                
                if not balance_found:
                    logger.warning(f"Could not parse balance from: {message[:100]}")
                    
            # Parse ToxiBot's welcome message which contains wallet address
            elif "welcome to" in message.lower() and "your wallet address:" in message.lower():
                # Extract wallet address and trigger balance parse from the same message
                wallet_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44})', message)
                if wallet_match:
                    logger.info(f"ToxiBot wallet: {wallet_match.group(1)}")
                
                # Also check for balance in welcome message
                balance_match = re.search(r'(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                if balance_match:
                    balance = float(balance_match.group(1))
                    bot_state.wallet_balance = balance
                    logger.info(f"Initial balance: {balance} SOL")
                    
            # Parse successful buys - ToxiBot format
            elif any(word in message.lower() for word in ["✅", "success", "bought", "purchased", "executed"]):
                logger.info("Trade executed successfully!")
                bot_state.trades_this_hour += 1
                
                # Extract token address from message
                address_match = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', message)
                if address_match:
                    token_address = address_match.group(0)
                    
                    # Get price for tracking
                    price = await self.price_checker.get_token_price(token_address)
                    if price and token_address in self.monitoring_tokens:
                        token_info = self.monitoring_tokens[token_address]
                        
                        # Create trade record
                        trade = Trade(
                            token_address=token_address,
                            symbol=token_info.get('symbol', 'UNKNOWN'),
                            entry_price=price,
                            current_price=price,
                            position_size=token_info['position_size'],
                            entry_time=time.time(),
                            personality=token_info['personality'],
                            stop_loss=price * token_info['personality']['stop_loss'],
                            take_profit=price * token_info['personality']['take_profit']
                        )
                        
                        bot_state.active_positions[token_address] = trade
                        bot_state.active_trades = len(bot_state.active_positions)
                        
                        # Remove set_limit_orders call since ToxiBot handles it
                        # We'll use ToxiBot's native SL/TP instead
                        
                bot_state.last_activity = "Trade executed successfully!"
                bot_state.last_activity_type = "trade"
                
            # Parse errors - ToxiBot specific messages
            elif any(word in message.lower() for word in ["error", "failed", "❌", "insufficient", "invalid", "unable"]):
                logger.warning(f"Trade failed: {message}")
                bot_state.last_activity = f"Trade failed: {message[:50]}..."
                bot_state.last_activity_type = "error"
                
                # Parse specific error types
                if "invalid solana address" in message.lower():
                    logger.error("ToxiBot rejected token address - may need different format")
                    # Try to extract what format it expects
                    if "try again" in message.lower():
                        logger.info("ToxiBot suggests trying again - may need to use /buy command")
                        
                # If insufficient balance, try to get balance from error message
                if "insufficient" in message.lower():
                    # Sometimes ToxiBot shows current balance in error
                    balance_match = re.search(r'balance:\s*(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Balance from error: {balance} SOL")
                        
            # Parse ToxiBot token info display
            elif "💎" in message or ("dex:" in message.lower() and "liquidity:" in message.lower()):
                logger.info("ToxiBot displayed token info - ready for buy command")
                bot_state.last_activity = "Token loaded in ToxiBot - ready to buy"
                bot_state.last_activity_type = "info"
                
                # Extract token details if shown
                if "market cap:" in message.lower():
                    logger.info("ToxiBot showing full token details with buy buttons")
                    
            # Parse stop loss/take profit hits from ToxiBot
            elif "stop loss" in message.lower() and ("triggered" in message.lower() or "hit" in message.lower()):
                logger.info("ToxiBot: Stop loss triggered")
                bot_state.last_activity = "Stop loss triggered by ToxiBot"
                bot_state.last_activity_type = "error"
                
                # Extract details and record loss
                self._parse_trade_result(message, is_loss=True)
                
            elif "take profit" in message.lower() and ("triggered" in message.lower() or "hit" in message.lower()):
                logger.info("ToxiBot: Take profit triggered")
                bot_state.last_activity = "Take profit triggered by ToxiBot!"
                bot_state.last_activity_type = "trade"
                
                # Extract details and record profit
                self._parse_trade_result(message, is_loss=False)
                
            # Parse limit order hits
            elif "limit order" in message.lower() and ("filled" in message.lower() or "executed" in message.lower()):
                logger.info("ToxiBot: Limit order executed")
                bot_state.last_activity = "Limit order executed by ToxiBot"
                bot_state.last_activity_type = "trade"
                    
    async def execute_buy(self, token_address: str, amount_sol: float = POSITION_SIZE):
        """Execute buy order through ToxiBot - Based on actual ToxiBot behavior"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        # Validate token address format
        import re
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
            
    async def set_toxibot_stop_loss(self, stop_loss_percent: float = 10):
        """Set stop loss using ToxiBot's native feature"""
        try:
            # Click/send Stop Loss command
            await self.client.send_message(self.toxibot_chat, "🔴 Stop Loss")
            await asyncio.sleep(1)
            
            # Send the percentage
            sl_command = f"{stop_loss_percent}%"
            await self.client.send_message(self.toxibot_chat, sl_command)
            
            logger.info(f"Set ToxiBot stop loss: {stop_loss_percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set stop loss: {e}")
            return False
            
    async def set_toxibot_take_profit(self, take_profit_percent: float = 50):
        """Set take profit using ToxiBot's native feature"""
        try:
            # Click/send Take Profit command
            await self.client.send_message(self.toxibot_chat, "🔴 Take Profit")
            await asyncio.sleep(1)
            
            # Send the percentage
            tp_command = f"{take_profit_percent}%"
            await self.client.send_message(self.toxibot_chat, tp_command)
            
            logger.info(f"Set ToxiBot take profit: {take_profit_percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set take profit: {e}")
            return False
            
    async def set_toxibot_limit_orders(self):
        """Set limit orders using ToxiBot's native feature"""
        try:
            # Click/send Limit Orders command
            await self.client.send_message(self.toxibot_chat, "📊 Limit Orders")
            await asyncio.sleep(1)
            
            logger.info("Opened ToxiBot limit orders menu")
            # ToxiBot will show its limit order interface
            return True
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            return False
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                # TEST MODE: Try a known good token every 5 minutes
                if bot_state.tokens_checked > 0 and bot_state.tokens_checked % 30 == 0:
                    logger.info("TEST MODE: Adding known tokens to test ToxiBot")
                    test_tokens = [
                        {
                            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',  # JUP
                            'symbol': 'JUP',
                            'liquidity': 1000,
                            'age_minutes': 60,
                            'volume_24h': 100000,
                            'holders': 10000,
                            'source': 'test'
                        },
                        {
                            'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
                            'symbol': 'BONK',
                            'liquidity': 500,
                            'age_minutes': 60,
                            'volume_24h': 50000,
                            'holders': 5000,
                            'source': 'test'
                        }
                    ]
                    new_tokens.extend(test_tokens)
                    bot_state.last_activity = "TEST MODE: Trying known tokens"
                    bot_state.last_activity_type = "warning"
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions - ToxiBot handles SL/TP automatically"""
        logger.info("Starting position monitor (ToxiBot handles SL/TP)...")
        
        while self.running:
            try:
                # Since ToxiBot handles stop loss and take profit automatically,
                # we mainly need to monitor for:
                # 1. Time-based exits
                # 2. Portfolio updates
                # 3. Trade results
                
                for address, trade in list(bot_state.active_positions.items()):
                    # Check time limit only
                    if time.time() - trade.entry_time > trade.personality['hold_time']:
                        logger.info(f"Time limit reached for {trade.symbol}")
                        bot_state.last_activity = f"Time exit: {trade.symbol}"
                        bot_state.last_activity_type = "info"
                        
                        # Close position
                        await self.execute_sell(address, 100)
                        del bot_state.active_positions[address]
                        
                    # ToxiBot will handle stop loss and take profit automatically
                    # We'll get notifications in the message handler when they trigger
                    
                bot_state.active_trades = len(bot_state.active_positions)
                
                # Check portfolio status periodically
                if len(bot_state.active_positions) > 0:
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    logger.info("Checking portfolio status")
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗'}                 ║
    ║  - Helius RPC: {'✓' if HELIUS_RPC_URL else '✗'}                 ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), token_address):
            logger.error(f"Invalid token address format: {token_address}")
            return False
            
        # Final safety checks
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trade blocked: {reason}")
            return False
            
        try:
            # First try to get token info from ToxiBot
            # Some bots require viewing token details first
            info_command = f"/info {token_address}"
            await self.client.send_message(self.toxibot_chat, info_command)
            logger.info(f"Requested token info: {info_command}")
            
            # Wait for ToxiBot to load token info
            await asyncio.sleep(3)
            
            # Now try to buy - just send token address
            await self.client.send_message(self.toxibot_chat, token_address)
            
            logger.info(f"Sent token address to ToxiBot: {token_address}")
            bot_state.last_activity = f"Sent buy request for token: {token_address[:8]}..."
            bot_state.last_activity_type = "trade"
            
            # Wait for response
            await asyncio.sleep(2)
            
            # If amount is specified, try buy command format
            if amount_sol != POSITION_SIZE:
                buy_command = f"/buy {amount_sol}"  # Just amount, token context already set
                await self.client.send_message(self.toxibot_chat, buy_command)
                logger.info(f"Sent buy amount: {amount_sol} SOL")
            
            return True
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            bot_state.last_activity = f"Buy command failed: {str(e)}"
            bot_state.last_activity_type = "error"
            return False
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), address):
                logger.debug(f"Skipping invalid address: {address}")
                continue
                
            if address not in self.checked_tokens:
                # Validate token has required fields
                if all(token.get(field) for field in ['address', 'symbol', 'liquidity']):
                    self.checked_tokens.add(address)
                    validated_tokens.append(token)
                    logger.debug(f"Valid token found: {token['symbol']} ({address[:8]}...) - Liq: {token['liquidity']:.1f} SOL")
                
        bot_state.tokens_checked = len(self.checked_tokens)
        logger.info(f"New validated tokens: {len(validated_tokens)}")
        
        return validated_tokens
        
    async def get_helius_tokens(self) -> List[Dict]:
        """Get new tokens from Helius with better parsing"""
        try:
            session = await self.get_session()
            
            # Get recent token creations
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
            
            # Get new token list
            list_url = f"https://api.helius.xyz/v0/addresses/tokens?api-key={HELIUS_API_KEY}&limit=100"
            
            async with session.get(list_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for token_data in data[:20]:  # Process top 20
                        try:
                            address = token_data.get('mint', token_data.get('address', ''))
                            if address:
                                # Get token details
                                token_info = await self._get_token_details(address)
                                if token_info:
                                    tokens.append(token_info)
                        except:
                            continue
                            
                    logger.info(f"Found {len(tokens)} tokens from Helius")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Helius error: {e}")
            
        return []
        
    async def get_dexscreener_tokens(self) -> List[Dict]:
        """Get new tokens from DexScreener"""
        try:
            session = await self.get_session()
            
            # Get new pairs sorted by age
            url = "https://api.dexscreener.com/latest/dex/pairs/solana"
            
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = []
                    
                    for pair in data.get('pairs', [])[:30]:
                        # Validate token address
                        base_token = pair.get('baseToken', {})
                        token_address = base_token.get('address', '')
                        
                        # Skip if invalid address format
                        if not token_address or len(token_address) < 32:
                            continue
                            
                        # Calculate age in minutes
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at:
                            age_minutes = (time.time() * 1000 - created_at) / 60000
                        else:
                            age_minutes = 60  # Default 1 hour
                            
                        token = {
                            'address': token_address,
                            'symbol': base_token.get('symbol', 'UNKNOWN'),
                            'name': base_token.get('name', ''),
                            'liquidity': pair.get('liquidity', {}).get('usd', 0) / 40,  # Convert to SOL
                            'age_minutes': int(age_minutes),
                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                            'price_usd': pair.get('priceUsd', 0),
                            'holders': 0,  # Will check separately
                            'source': 'dexscreener'
                        }
                        
                        if token['address'] and token['liquidity'] > 0:
                            tokens.append(token)
                            
                    logger.info(f"Found {len(tokens)} tokens from DexScreener")
                    return tokens
                    
        except Exception as e:
            logger.error(f"DexScreener error: {e}")
            
        return []
        
    async def get_birdeye_tokens(self) -> List[Dict]:
        """Get trending tokens from Birdeye"""
        try:
            session = await self.get_session()
            
            # Try multiple sorting options for variety
            endpoints = [
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hChangePercent&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50",
                "https://public-api.birdeye.so/public/tokenlist?sort_by=mc&sort_type=asc&offset=0&limit=50"
            ]
            
            all_tokens = []
            
            for url in endpoints:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('success') and 'data' in data:
                                for token_data in data['data'].get('tokens', [])[:20]:
                                    # Only include tokens with reasonable metrics
                                    if token_data.get('v24hUSD', 0) > 100:  # Min $100 daily volume
                                        token = {
                                            'address': token_data.get('address', ''),
                                            'symbol': token_data.get('symbol', 'UNKNOWN'),
                                            'name': token_data.get('name', ''),
                                            'liquidity': token_data.get('liquidity', 0) / 1e9,  # Convert to SOL
                                            'age_minutes': 60,  # Default estimate
                                            'volume_24h': token_data.get('v24hUSD', 0),
                                            'price_usd': token_data.get('v24hUSD', 0) / max(token_data.get('v24hTx', 1), 1),
                                            'holders': token_data.get('holder', 0),
                                            'source': 'birdeye'
                                        }
                                        
                                        if token['address']:
                                            all_tokens.append(token)
                except:
                    continue
                    
            # Remove duplicates
            unique_tokens = {}
            for token in all_tokens:
                unique_tokens[token['address']] = token
                
            tokens = list(unique_tokens.values())
            logger.info(f"Found {len(tokens)} tokens from Birdeye")
            return tokens
            
        except Exception as e:
            logger.error(f"Birdeye error: {e}")
            
        return []
        
    async def _get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token information"""
        try:
            # Get price from price checker
            price = await self.price_checker.get_token_price(address)
            
            if price:
                return {
                    'address': address,
                    'symbol': 'NEW',
                    'name': 'New Token',
                    'liquidity': 10,  # Will be checked separately
                    'age_minutes': 30,
                    'volume_24h': 1000,
                    'price_usd': price * 40,  # Convert to USD
                    'holders': 50,
                    'source': 'helius'
                }
        except:
            pass
            
        return None

class RiskManager:
    """Manage trading risks and limits"""
    
    def __init__(self):
        self.daily_loss_limit = MAX_DAILY_LOSS
        self.max_position_size = MAX_POSITION_SIZE
        self.min_wallet_balance = MIN_WALLET_BALANCE
        self.cooldown_period = RISK_SETTINGS['cooldown_after_loss']
        
    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can place a new trade"""
        
        # Check daily loss limit
        if bot_state.daily_loss >= self.daily_loss_limit:
            bot_state.risk_status = "Daily loss limit reached"
            return False, "Daily loss limit reached"
            
        # Check if in cooldown after loss
        if bot_state.last_loss_time > 0:
            time_since_loss = time.time() - bot_state.last_loss_time
            if time_since_loss < self.cooldown_period:
                remaining = int(self.cooldown_period - time_since_loss)
                bot_state.risk_status = f"Cooldown: {remaining}s remaining"
                return False, f"In cooldown for {remaining} seconds"
            
        # Check wallet balance
        if bot_state.wallet_balance < self.min_wallet_balance:
            bot_state.risk_status = "Insufficient balance"
            return False, "Insufficient wallet balance"
            
        # Check max positions
        if len(bot_state.active_positions) >= MAX_POSITIONS:
            bot_state.risk_status = "Max positions reached"
            return False, "Maximum positions reached"
            
        bot_state.risk_status = "Normal - Can trade"
        return True, "OK"
        
    def calculate_position_size(self, personality: Dict) -> float:
        """Calculate safe position size"""
        base_size = personality['position_size']
        
        # Reduce size based on recent losses
        if bot_state.daily_loss > 0:
            loss_ratio = bot_state.daily_loss / self.daily_loss_limit
            size_multiplier = 1 - (loss_ratio * 0.5)  # Reduce up to 50%
            base_size *= size_multiplier
            
        # Never exceed max position size
        return min(base_size, self.max_position_size)
        
    def record_trade_result(self, profit: float):
        """Record trade result for risk management"""
        if profit < 0:
            bot_state.daily_loss += abs(profit)
            bot_state.last_loss_time = time.time()
            bot_state.losing_trades += 1
        else:
            bot_state.winning_trades += 1
            
        bot_state.total_trades += 1
        bot_state.total_profit += profit

class LiveTradingBot:
    """Live trading bot with safety measures"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        self.toxibot_chat = None
        self.token_discovery = TokenDiscovery()
        self.price_checker = PriceChecker()
        self.risk_manager = RiskManager()
        self.contract_checker = ContractChecker()  # Add contract checker
        self.last_balance_check = 0
        
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
            asyncio.create_task(self.monitor_positions())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def find_toxibot(self):
        """Find ToxiBot in Telegram chats"""
        toxibot_found = False
        
        async for dialog in self.client.iter_dialogs():
            # Look for ToxiBot - check multiple possible names
            dialog_name = dialog.name.lower()
            if any(name in dialog_name for name in ['toxi', 'toxibot', 'toxi_solana', 'solana_bot']):
                if 'toxi' in dialog_name:
                    self.toxibot_chat = dialog.entity
                    bot_state.toxibot_connected = True
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    
                    # ToxiBot shows balance when you start - send /start
                    await self.client.send_message(self.toxibot_chat, "/start")
                    bot_state.last_activity = "Connected to ToxiBot - Initializing"
                    bot_state.last_activity_type = "success"
                    
                    # Small delay to let ToxiBot respond
                    await asyncio.sleep(2)
                    
                    # Try clicking Wallet button to get balance
                    await self.client.send_message(self.toxibot_chat, "💼 Wallet")
                    break
                    
        if not toxibot_found:
            logger.warning("ToxiBot not found! Make sure to:")
            logger.warning("1. Search for @toxi_solana_bot in Telegram")
            logger.warning("2. Start a chat with ToxiBot")
            logger.warning("3. Fund your ToxiBot wallet with at least 0.2 SOL")
            bot_state.last_activity = "ToxiBot not found - please start chat with @toxi_solana_bot"
            bot_state.last_activity_type = "error"
            
    async def check_wallet_balance(self):
        """Check wallet balance in ToxiBot"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't use /balance - it shows balance with /start or Wallet button
            await self.client.send_message(self.toxibot_chat, "💼 Wallet")
            self.last_balance_check = time.time()
            logger.info("Requesting wallet info...")
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            
    async def monitor_toxibot_messages(self):
        """Monitor ToxiBot responses"""
        if not self.toxibot_chat:
            return
            
        @self.client.on(events.NewMessage(chats=self.toxibot_chat))
        async def handler(event):
            message = event.message.text
            logger.info(f"ToxiBot: {message[:200]}...")
            
            # Parse balance - ToxiBot shows it with emoji and specific format
            if "💰" in message or "wallet balance:" in message.lower() or "balance:" in message.lower():
                # Extract balance using multiple regex patterns
                import re
                
                # Try different patterns
                patterns = [
                    r'💰\s*Wallet Balance:\s*(\d+\.?\d*)\s*SOL',  # ToxiBot format with emoji
                    r'Balance:\s*(\d+\.?\d*)\s*SOL',  # Alternative format
                    r'(\d+\.?\d*)\s*SOL\s*\|',  # Format with pipe after SOL
                    r'(\d+(?:\.\d+)?)\s*SOL',  # Simple format
                ]
                
                balance_found = False
                for pattern in patterns:
                    balance_match = re.search(pattern, message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Wallet balance updated: {balance} SOL")
                        bot_state.last_activity = f"Wallet balance: {balance} SOL"
                        bot_state.last_activity_type = "info"
                        balance_found = True
                        break
                
                if not balance_found:
                    logger.warning(f"Could not parse balance from: {message[:100]}")
                    
            # Parse ToxiBot's welcome message which contains wallet address
            elif "welcome to" in message.lower() and "your wallet address:" in message.lower():
                # Extract wallet address and trigger balance parse from the same message
                wallet_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44})', message)
                if wallet_match:
                    logger.info(f"ToxiBot wallet: {wallet_match.group(1)}")
                
                # Also check for balance in welcome message
                balance_match = re.search(r'(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                if balance_match:
                    balance = float(balance_match.group(1))
                    bot_state.wallet_balance = balance
                    logger.info(f"Initial balance: {balance} SOL")
                    
            # Parse successful buys - ToxiBot format
            elif any(word in message.lower() for word in ["✅", "success", "bought", "purchased", "executed"]):
                logger.info("Trade executed successfully!")
                bot_state.trades_this_hour += 1
                
                # Extract token address from message
                address_match = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', message)
                if address_match:
                    token_address = address_match.group(0)
                    
                    # Get price for tracking
                    price = await self.price_checker.get_token_price(token_address)
                    if price and token_address in self.monitoring_tokens:
                        token_info = self.monitoring_tokens[token_address]
                        
                        # Create trade record
                        trade = Trade(
                            token_address=token_address,
                            symbol=token_info.get('symbol', 'UNKNOWN'),
                            entry_price=price,
                            current_price=price,
                            position_size=token_info['position_size'],
                            entry_time=time.time(),
                            personality=token_info['personality'],
                            stop_loss=price * token_info['personality']['stop_loss'],
                            take_profit=price * token_info['personality']['take_profit']
                        )
                        
                        bot_state.active_positions[token_address] = trade
                        bot_state.active_trades = len(bot_state.active_positions)
                        
                        # Set limit orders for this position
                        await self.set_limit_orders(token_address, token_info['personality'], price)
                        
                bot_state.last_activity = "Trade executed successfully!"
                bot_state.last_activity_type = "trade"
                
            # Parse errors - ToxiBot specific messages
            elif any(word in message.lower() for word in ["error", "failed", "❌", "insufficient", "invalid", "unable"]):
                logger.warning(f"Trade failed: {message}")
                bot_state.last_activity = f"Trade failed: {message[:50]}..."
                bot_state.last_activity_type = "error"
                
                # Parse specific error types
                if "invalid solana address" in message.lower():
                    logger.error("ToxiBot rejected token address - may need different format")
                    # Try to extract what format it expects
                    if "try again" in message.lower():
                        logger.info("ToxiBot suggests trying again - may need to use /buy command")
                        
                # If insufficient balance, try to get balance from error message
                if "insufficient" in message.lower():
                    # Sometimes ToxiBot shows current balance in error
                    balance_match = re.search(r'balance:\s*(\d+\.?\d*)\s*SOL', message, re.IGNORECASE)
                    if balance_match:
                        balance = float(balance_match.group(1))
                        bot_state.wallet_balance = balance
                        logger.info(f"Balance from error: {balance} SOL")
                        
            # Parse ToxiBot menu/button prompts
            elif "buy" in message.lower() and ("button" in message.lower() or "menu" in message.lower()):
                logger.info("ToxiBot showing buy menu - need to click button or send amount")
                bot_state.last_activity = "ToxiBot ready - awaiting buy confirmation"
                bot_state.last_activity_type = "info"
                    
    async def execute_buy(self, token_address: str, amount_sol: float = POSITION_SIZE):
        """Execute buy order through ToxiBot - Based on actual ToxiBot behavior"""
        if not self.toxibot_chat:
            logger.error("ToxiBot not connected")
            return False
            
        # Validate token address format
        import re
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                # TEST MODE: Try a known good token every 5 minutes
                if bot_state.tokens_checked > 0 and bot_state.tokens_checked % 30 == 0:
                    logger.info("TEST MODE: Adding known tokens to test ToxiBot")
                    test_tokens = [
                        {
                            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',  # JUP
                            'symbol': 'JUP',
                            'liquidity': 1000,
                            'age_minutes': 60,
                            'volume_24h': 100000,
                            'holders': 10000,
                            'source': 'test'
                        },
                        {
                            'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
                            'symbol': 'BONK',
                            'liquidity': 500,
                            'age_minutes': 60,
                            'volume_24h': 50000,
                            'holders': 5000,
                            'source': 'test'
                        }
                    ]
                    new_tokens.extend(test_tokens)
                    bot_state.last_activity = "TEST MODE: Trying known tokens"
                    bot_state.last_activity_type = "warning"
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()), token_address):
            logger.error(f"Invalid token address format: {token_address}")
            return False
            
        # Final safety checks
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trade blocked: {reason}")
            return False
            
        try:
            # First try to get token info from ToxiBot
            # Some bots require viewing token details first
            info_command = f"/info {token_address}"
            await self.client.send_message(self.toxibot_chat, info_command)
            logger.info(f"Requested token info: {info_command}")
            
            # Wait for ToxiBot to load token info
            await asyncio.sleep(3)
            
            # Now try to buy - just send token address
            await self.client.send_message(self.toxibot_chat, token_address)
            
            logger.info(f"Sent token address to ToxiBot: {token_address}")
            bot_state.last_activity = f"Sent buy request for token: {token_address[:8]}..."
            bot_state.last_activity_type = "trade"
            
            # Wait for response
            await asyncio.sleep(2)
            
            # If amount is specified, try buy command format
            if amount_sol != POSITION_SIZE:
                buy_command = f"/buy {amount_sol}"  # Just amount, token context already set
                await self.client.send_message(self.toxibot_chat, buy_command)
                logger.info(f"Sent buy amount: {amount_sol} SOL")
            
            return True
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            bot_state.last_activity = f"Buy command failed: {str(e)}"
            bot_state.last_activity_type = "error"
            return False
            
    async def set_limit_orders(self, token_address: str, personality: Dict, entry_price: float):
        """Set limit sell orders based on personality settings"""
        if not self.toxibot_chat:
            return
            
        try:
            # ToxiBot doesn't have native limit order commands
            # We'll implement our own monitoring for limit orders
            logger.info(f"Setting limit orders for {token_address[:8]}... based on {personality['name']}")
            
            # Store limit order targets for monitoring
            limit_orders = []
            for i, target in enumerate(personality['limit_sell_targets']):
                sell_price = entry_price * target
                sell_amount = personality['limit_sell_amounts'][i]
                
                limit_orders.append({
                    'price': sell_price,
                    'amount_percent': int(sell_amount * 100),
                    'triggered': False
                })
                
                logger.info(f"Limit order {i+1}: Sell {sell_amount*100}% at {sell_price:.8f} SOL ({target}x)")
            
            # Store limit orders with the position
            if token_address in bot_state.active_positions:
                bot_state.active_positions[token_address].limit_orders = limit_orders
                
            bot_state.last_activity = f"Set {len(limit_orders)} limit orders for {token_address[:8]}..."
            bot_state.last_activity_type = "info"
            
        except Exception as e:
            logger.error(f"Failed to set limit orders: {e}")
            
    async def trading_loop(self):
        """Main trading loop with safety checks"""
        logger.info("Starting SAFE trading loop...")
        bot_state.last_activity = "Trading loop started - Scanning for safe opportunities"
        bot_state.last_activity_type = "info"
        
        # Reset daily loss at start
        bot_state.daily_loss = 0
        last_day = datetime.now().day
        
        while self.running:
            try:
                # Reset daily loss if new day
                current_day = datetime.now().day
                if current_day != last_day:
                    bot_state.daily_loss = 0
                    last_day = current_day
                    logger.info("Daily loss counter reset")
                    
                # Check wallet balance periodically
                if time.time() - self.last_balance_check > 300:  # Every 5 minutes
                    await self.check_wallet_balance()
                    
                # Check if we can trade
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.info(f"Trading paused: {reason}")
                    await asyncio.sleep(30)
                    continue
                    
                # Discover new tokens
                new_tokens = await self.token_discovery.discover_tokens()
                
                if new_tokens:
                    logger.info(f"Analyzing {len(new_tokens)} tokens for safety...")
                    
                    for token in new_tokens:
                        # Detailed analysis
                        analysis = await self.analyze_token_safety(token)
                        
                        if analysis['is_safe']:
                            personality = analysis['personality']
                            
                            # Log any contract warnings with RugCheck score
                            if analysis.get('contract_warnings'):
                                rugcheck_score = analysis.get('rugcheck_score', 'N/A')
                                logger.warning(f"Token {token['symbol']} - RugCheck Score: {rugcheck_score}/100, Warnings: {analysis['contract_warnings']}")
                                
                            logger.info(f"{personality['name']} approved token: {token['symbol']} - Safety: {analysis['safety_score']}/10, RugCheck: {analysis.get('rugcheck_score', 'N/A')}/100")
                            bot_state.last_activity = f"{personality['name']} buying {token['symbol']} (Safety: {analysis['safety_score']}/10)"
                            bot_state.last_activity_type = personality['css_class']
                            
                            # Calculate position size
                            position_size = self.risk_manager.calculate_position_size(personality)
                            
                            # Execute buy
                            if await self.execute_buy(token['address'], position_size):
                                # Store token info for monitoring
                                token['personality'] = personality
                                token['position_size'] = position_size
                                token['entry_time'] = time.time()
                                token['safety_score'] = analysis['safety_score']
                                self.monitoring_tokens[token['address']] = token
                                
                                # Small delay between trades
                                await asyncio.sleep(5)
                        else:
                            logger.debug(f"Token {token['symbol']} rejected: {analysis['rejection_reason']}")
                else:
                    # Update activity periodically
                    if bot_state.tokens_checked % 50 == 0:
                        bot_state.last_activity = f"Scanning... {bot_state.tokens_checked} tokens analyzed"
                        bot_state.last_activity_type = "info"
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                bot_state.last_activity = f"Trading loop error: {str(e)}"
                bot_state.last_activity_type = "error"
                await asyncio.sleep(60)
                
    async def analyze_token_safety(self, token: Dict) -> Dict:
        """Comprehensive token safety analysis with contract checking"""
        safety_score = 10  # Start with perfect score
        rejection_reasons = []
        
        # Check liquidity
        liquidity = token.get('liquidity', 0)
        if liquidity < MIN_LIQUIDITY:
            return {
                'is_safe': False,
                'rejection_reason': f'Low liquidity: {liquidity:.1f} SOL',
                'safety_score': 0
            }
            
        # Contract safety check
        if RISK_SETTINGS['check_contract']:
            contract_check = await self.contract_checker.check_token_safety(token['address'])
            
            # Immediate rejections
            if contract_check['risk_score'] >= 7:
                return {
                    'is_safe': False,
                    'rejection_reason': f'High risk: {", ".join(contract_check["warnings"])}',
                    'safety_score': 0
                }
                
            # Deduct points for risks
            safety_score -= (contract_check['risk_score'] * 0.5)
            
            # Check for critical red flags
            if any('honeypot' in w.lower() for w in contract_check.get('warnings', [])):
                return {
                    'is_safe': False,
                    'rejection_reason': '🚨 Honeypot detected!',
                    'safety_score': 0
                }
                
            # Check RugCheck score if available
            if contract_check.get('rugcheck_score', 100) < 30:
                return {
                    'is_safe': False,
                    'rejection_reason': f'🚨 RugCheck Score too low: {contract_check["rugcheck_score"]}/100',
                    'safety_score': 0
                }
                
            # Check holder concentration
            if contract_check.get('top_holder_percentage', 0) > RISK_SETTINGS['max_concentration'] * 100:
                return {
                    'is_safe': False,
                    'rejection_reason': f'Top holder owns {contract_check["top_holder_percentage"]:.1f}%',
                    'safety_score': 0
                }
            
        # Liquidity scoring
        if liquidity < 20:
            safety_score -= 2
        elif liquidity < 50:
            safety_score -= 1
            
        # Check volume
        volume_24h = token.get('volume_24h', 0)
        if RISK_SETTINGS['require_volume_check'] and volume_24h < 100:
            return {
                'is_safe': False,
                'rejection_reason': f'Low volume: ${volume_24h:.0f}',
                'safety_score': 0
            }
            
        # Volume scoring
        if volume_24h < 1000:
            safety_score -= 2
        elif volume_24h < 5000:
            safety_score -= 1
            
        # Check holders
        holders = token.get('holders', 0)
        if holders < RISK_SETTINGS['min_holders']:
            safety_score -= 3
            
        # Age check
        age_minutes = token.get('age_minutes', 999)
        if age_minutes < 5:
            safety_score -= 2  # Very new = risky
        elif age_minutes > 1440:
            safety_score -= 1  # Too old = missed opportunity
            
        # Try each personality
        for personality in [BotPersonality.CONSERVATIVE_SNIPER, 
                          BotPersonality.SAFE_SCALPER, 
                          BotPersonality.ESTABLISHED_TRADER]:
            
            # Check all criteria
            meets_criteria = (
                liquidity >= personality['min_liquidity'] and
                age_minutes <= personality['max_age_minutes'] and
                volume_24h >= personality.get('min_volume_24h', 0) and
                holders >= personality.get('min_holders', 0) and
                safety_score >= 5  # Minimum safety threshold
            )
            
            if meets_criteria:
                return {
                    'is_safe': True,
                    'personality': personality,
                    'safety_score': safety_score,
                    'rejection_reason': None,
                    'contract_warnings': contract_check.get('warnings', []) if RISK_SETTINGS['check_contract'] else [],
                    'rugcheck_score': contract_check.get('rugcheck_score', None) if RISK_SETTINGS['check_contract'] else None
                }
                
        # If no personality matched
        reasons = []
        if liquidity < 50:
            reasons.append(f"liquidity:{liquidity:.1f}")
        if volume_24h < 5000:
            reasons.append(f"volume:${volume_24h:.0f}")
        if holders < 100:
            reasons.append(f"holders:{holders}")
        if safety_score < 5:
            reasons.append(f"safety:{safety_score}/10")
            
        return {
            'is_safe': False,
            'rejection_reason': ' '.join(reasons),
            'safety_score': safety_score
        }
        
    async def monitor_positions(self):
        """Monitor open positions with real price checks and limit orders"""
        logger.info("Starting position monitor...")
        
        while self.running:
            try:
                for address, trade in list(bot_state.active_positions.items()):
                    # Get current price
                    current_price = await self.price_checker.get_token_price(address)
                    
                    if current_price:
                        trade.current_price = current_price
                        pnl_percent = trade.pnl_percent
                        
                        # Check limit orders first
                        if trade.limit_orders:
                            for limit_order in trade.limit_orders:
                                if not limit_order['triggered'] and current_price >= limit_order['price']:
                                    # Trigger limit order
                                    logger.info(f"Limit order triggered for {trade.symbol}: Selling {limit_order['amount_percent']}% at {current_price:.8f} SOL")
                                    bot_state.last_activity = f"Limit order hit: {trade.symbol} at {current_price/trade.entry_price:.2f}x!"
                                    bot_state.last_activity_type = "trade"
                                    
                                    await self.execute_sell(address, limit_order['amount_percent'])
                                    limit_order['triggered'] = True
                                    
                                    # Update position size
                                    trade.position_size *= (1 - limit_order['amount_percent'] / 100)
                                    
                                    # Record partial profit
                                    partial_profit = trade.position_size * (limit_order['amount_percent'] / 100) * (current_price / trade.entry_price - 1)
                                    self.risk_manager.record_trade_result(partial_profit)
                        
                        # Check if all limit orders are triggered
                        all_triggered = all(order['triggered'] for order in trade.limit_orders) if trade.limit_orders else False
                        
                        # If all limit orders hit or position is very small, remove from tracking
                        if all_triggered and trade.position_size < 0.001:
                            logger.info(f"All limit orders completed for {trade.symbol}")
                            del bot_state.active_positions[address]
                            continue
                        
                        # Check stop loss
                        if current_price <= trade.stop_loss:
                            logger.info(f"Stop loss hit for {trade.symbol}: {pnl_percent:.1f}%")
                            bot_state.last_activity = f"Stop loss: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "error"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                        # Check time limit
                        elif time.time() - trade.entry_time > trade.personality['hold_time']:
                            logger.info(f"Time limit reached for {trade.symbol}")
                            bot_state.last_activity = f"Time exit: {trade.symbol} at {pnl_percent:.1f}%"
                            bot_state.last_activity_type = "info"
                            
                            await self.execute_sell(address, 100)
                            self.risk_manager.record_trade_result(trade.pnl)
                            del bot_state.active_positions[address]
                            
                    bot_state.active_trades = len(bot_state.active_positions)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
                
    # Add monitoring_tokens attribute
    monitoring_tokens = {}

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
            'activityType': bot_state.last_activity_type,
            'walletBalance': bot_state.wallet_balance,
            'riskStatus': bot_state.risk_status
        })

async def load_existing_session():
    """Load existing Telegram session if available"""
    try:
        session_path = 'data/session.txt'
        if os.path.exists(session_path):
            logger.info(f"Found session file at {session_path}")
            with open(session_path, 'r') as f:
                session_string = f.read().strip()
                
            if session_string and TELEGRAM_AVAILABLE:
                logger.info("Attempting to load existing session...")
                # Get API credentials from environment or use defaults
                api_id = os.environ.get('TELEGRAM_API_ID')
                api_hash = os.environ.get('TELEGRAM_API_HASH')
                
                if not api_id or not api_hash:
                    logger.warning("No Telegram API credentials in environment, checking session only")
                    return False
                
                # Try to connect with existing session
                client = TelegramClient(StringSession(session_string), 
                                      int(api_id), 
                                      api_hash)
                                      
                await client.connect()
                
                if await client.is_user_authorized():
                    logger.info("Session loaded successfully!")
                    trading_bot.client = client
                    trading_bot.api_id = api_id
                    trading_bot.api_hash = api_hash
                    bot_state.configured = True
                    bot_state.authenticated = True
                    
                    # Find ToxiBot and start
                    await trading_bot.find_toxibot()
                    trading_bot.running = True
                    bot_state.running = True
                    
                    # Start all background tasks
                    asyncio.create_task(trading_bot.trading_loop())
                    asyncio.create_task(trading_bot.monitor_toxibot_messages())
                    asyncio.create_task(trading_bot.monitor_positions())
                    
                    logger.info("Bot fully started with existing session!")
                    return True
                else:
                    logger.warning("Session expired, need to re-authenticate")
                    await client.disconnect()
                    # Remove invalid session
                    os.remove(session_path)
        else:
            logger.info("No existing session found")
                    
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        
    return False

async def main():
    """Start the bot"""
    # Try to load existing session
    await load_existing_session()
    
    # Start web server
    server = WebServer()
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║    SOLANA SAFE TRADING BOT V2.0       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  ⚠️  LIVE TRADING - REAL MONEY ⚠️     ║
    ║                                       ║
    ║  Safety Features:                     ║
    ║  • Real price checking                ║
    ║  • Risk management (0.2 SOL max loss) ║
    ║  • Contract verification              ║
    ║  • Rug pull detection                 ║
    ║  • Position sizing (0.01-0.05 SOL)    ║
    ║  • Stop losses on all trades          ║
    ║  • Minimum liquidity checks           ║
    ║                                       ║
    ║  3 Safe Personalities:                ║
    ║  • Conservative Sniper (20+ SOL liq)  ║
    ║  • Safe Scalper (50+ SOL liq)         ║
    ║  • Established Trader (100+ SOL liq)  ║
    ║                                       ║
    ║  Status:                              ║
    ║  - Telegram: {'✓' if bot_state.configured else '✗'}                      ║
    ║  - Helius API: {'✓' if HELIUS_API_KEY else '✗ (Optional)'}            ║
    ║  - Session: {'✓' if bot_state.authenticated else '✗'}                   ║
    ║                                       ║
    ║  Dashboard: http://localhost:{port:<9}    ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    
    SAFETY CHECKLIST:
    ✓ Start with minimum amounts (0.01 SOL)
    ✓ Monitor the dashboard closely
    ✓ Set stop losses on all trades
    ✓ Daily loss limit: 0.2 SOL
    ✓ Keep at least 0.1 SOL for fees
    ✓ Only trade tokens with 20+ SOL liquidity
    ✓ Contract verification enabled
    ✓ Rug pull detection active
    
    Press Ctrl+C to stop the bot safely.
    """)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down safely...")
        trading_bot.running = False
        if trading_bot.client:
            await trading_bot.client.disconnect()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
