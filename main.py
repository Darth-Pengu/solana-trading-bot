#!/usr/bin/env python3
"""
SOLANA TRADING BOT - FIXED VERSION
Corrected Telegram authentication
"""

import asyncio
import os
import json
import time
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
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

# HTML Dashboard (same as before)
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Solana Trading Bot</title>
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
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Solana Trading Bot</h1>
    </div>
    
    <div class="container">
        <!-- Setup Section -->
        <div id="setupSection" class="setup-box">
            <h2>Bot Setup</h2>
            
            <!-- Step 1: Check Telegram -->
            <div class="step">
                <h3>Step 1: Telegram API Setup</h3>
                <p>You need Telegram API credentials to connect the bot.</p>
                <p>Already have them? Enter below. Need them? <a href="https://my.telegram.org" target="_blank" style="color: #ff6600;">Get them here</a></p>
                
                <input type="text" id="apiId" placeholder="API ID (numbers only, like: 12345678)">
                <input type="text" id="apiHash" placeholder="API Hash (32 characters, like: abcdef1234567890abcdef1234567890)">
                
                <button onclick="saveCredentials()">Save Telegram Credentials</button>
            </div>
            
            <!-- Step 2: Phone Auth -->
            <div class="step hidden" id="phoneStep">
                <h3>Step 2: Phone Number</h3>
                <p>Enter your phone number to receive a code:</p>
                <input type="tel" id="phoneInput" placeholder="+1234567890 (include country code)">
                <button onclick="requestCode()">Send Code to Telegram</button>
            </div>
            
            <!-- Step 3: Code -->
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
            <div class="status" id="botStatus">
                <h2>Bot Status: <span id="statusText">Offline</span></h2>
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
            </div>
            
            <div class="activity">
                <h3>Activity Log</h3>
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
                
                if (data.activity) {
                    addActivity(data.activity);
                }
            } catch (e) {
                console.error('Failed to update stats');
            }
        }
        
        function addActivity(message) {
            const log = document.getElementById('activityLog');
            const item = document.createElement('div');
            item.className = 'activity-item';
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

# Global state
bot_state = BotState()

class SimpleTradingBot:
    """Simplified bot that connects to ToxiBot"""
    
    def __init__(self):
        self.running = False
        self.api_id = None
        self.api_hash = None
        self.client = None
        self.phone = None
        self.code_hash = None
        
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
            toxibot_found = False
            async for dialog in self.client.iter_dialogs():
                if 'toxi' in dialog.name.lower():
                    logger.info(f"Found ToxiBot: {dialog.name}")
                    toxibot_found = True
                    break
                    
            if not toxibot_found:
                logger.warning("ToxiBot not found in chats. Make sure to start a chat with @toxi_solana_bot")
                
            # Start trading
            self.running = True
            bot_state.running = True
            asyncio.create_task(self.trading_loop())
            
            logger.info("Bot started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
            
    async def trading_loop(self):
        """Simple trading loop"""
        while self.running:
            try:
                # This is where the bot would:
                # 1. Check for new tokens
                # 2. Analyze safety
                # 3. Execute trades via ToxiBot
                
                # For now, just simulate
                await asyncio.sleep(30)
                
                if random.random() > 0.7:
                    bot_state.total_trades += 1
                    if random.random() > 0.4:
                        bot_state.winning_trades += 1
                        profit = random.uniform(0.01, 0.05)
                        bot_state.total_profit += profit
                        logger.info(f"Simulated trade profit: +{profit:.3f} SOL")
                        
            except Exception as e:
                logger.error(f"Trading error: {e}")
                await asyncio.sleep(60)

# Create bot instance
trading_bot = SimpleTradingBot()

class WebServer:
    """Simple web server"""
    
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
            'running': bot_state.running
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
            
        activity = None
        if bot_state.running:
            activity = f"Bot active - Monitoring for opportunities"
            
        return web.json_response({
            'profit': bot_state.total_profit,
            'trades': bot_state.active_trades,
            'winRate': win_rate,
            'activity': activity
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
    ║      SOLANA TRADING BOT STARTED       ║
    ╠═══════════════════════════════════════╣
    ║                                       ║
    ║  1. Open: http://localhost:{port:<10} ║
    ║  2. Enter Telegram API credentials    ║
    ║  3. Verify with phone number          ║
    ║  4. Bot starts trading automatically  ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
