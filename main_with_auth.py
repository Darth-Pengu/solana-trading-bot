# main_with_auth.py - Complete bot with TRON dashboard and auth
import asyncio
import os
import json
import time
from datetime import datetime
from typing import Dict, Optional
import aiohttp
from aiohttp import web
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession

# Your existing bot imports would go here
# from your_bot import SolanaTradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TronSystem')

class TelegramAuthManager:
    """Handles Telegram authentication through web UI"""
    
    def __init__(self):
        self.client = None
        self.phone = None
        self.auth_state = 'pending'  # pending, code_sent, authenticated
        self.session_string = None
        
    async def request_code(self, phone: str):
        """Request verification code"""
        self.phone = phone
        
        try:
            # Initialize client
            api_id = int(os.getenv('TG_API_ID'))
            api_hash = os.getenv('TG_API_HASH')
            
            # Check for existing session
            session_file = 'session.txt'
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    self.session_string = f.read().strip()
                    
            self.client = TelegramClient(
                StringSession(self.session_string) if self.session_string else 'auth_session',
                api_id,
                api_hash
            )
            
            await self.client.connect()
            
            # Request code
            result = await self.client.send_code_request(phone)
            self.auth_state = 'code_sent'
            
            logger.info(f"Code sent to {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send code: {e}")
            return False
    
    async def verify_code(self, code: str):
        """Verify the code"""
        try:
            # Sign in with code
            await self.client.sign_in(self.phone, code)
            
            # Save session
            self.session_string = self.client.session.save()
            with open('session.txt', 'w') as f:
                f.write(self.session_string)
                
            self.auth_state = 'authenticated'
            logger.info("Authentication successful!")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify code: {e}")
            return False

class TronDashboard:
    """TRON-style dashboard with auth"""
    
    def __init__(self):
        self.app = web.Application()
        self.auth_manager = TelegramAuthManager()
        self.bot = None  # Will be initialized after auth
        self.setup_routes()
        
    def setup_routes(self):
        """Setup web routes"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_post('/api/request-code', self.request_code)
        self.app.router.add_post('/api/verify-code', self.verify_code)
        self.app.router.add_get('/api/stats', self.get_stats)
        self.app.router.add_get('/api/positions', self.get_positions)
        self.app.router.add_get('/api/activity', self.get_activity)
        
    async def index(self, request):
        """Serve the TRON dashboard"""
        # Read the HTML file
        html_path = 'tron_dashboard.html'
        
        # For Railway, include the HTML directly
        html_content = '''
        <!-- Paste the entire TRON dashboard HTML here -->
        '''
        
        # Replace phone number placeholder if available
        phone = os.getenv('TG_PHONE', '')
        html_content = html_content.replace('{{ PHONE_NUMBER }}', phone)
        
        return web.Response(text=html_content, content_type='text/html')
    
    async def request_code(self, request):
        """Handle code request"""
        try:
            data = await request.json()
            phone = data.get('phone')
            
            if not phone:
                return web.json_response({'error': 'Phone required'}, status=400)
                
            success = await self.auth_manager.request_code(phone)
            
            if success:
                return web.json_response({'status': 'code_sent'})
            else:
                return web.json_response({'error': 'Failed to send code'}, status=500)
                
        except Exception as e:
            logger.error(f"Request code error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def verify_code(self, request):
        """Handle code verification"""
        try:
            data = await request.json()
            code = data.get('code')
            
            if not code:
                return web.json_response({'error': 'Code required'}, status=400)
                
            success = await self.auth_manager.verify_code(code)
            
            if success:
                # Start the bot after successful auth
                await self.start_bot()
                return web.json_response({'status': 'authenticated'})
            else:
                return web.json_response({'error': 'Invalid code'}, status=400)
                
        except Exception as e:
            logger.error(f"Verify code error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def start_bot(self):
        """Start the trading bot after authentication"""
        logger.info("Starting trading bot...")
        
        # Import and start your actual bot here
        # self.bot = SolanaTradingBot()
        # asyncio.create_task(self.bot.run())
        
        # For now, just log
        logger.info("Bot would start here with authenticated Telegram session")
    
    async def get_stats(self, request):
        """Get bot statistics"""
        # Return actual stats from your bot
        stats = {
            'totalProfit': 0.284,
            'winRate': 67,
            'positions': 3,
            'uptime': time.time() - getattr(self, 'start_time', time.time())
        }
        return web.json_response(stats)
    
    async def get_positions(self, request):
        """Get current positions"""
        # Return actual positions from your bot
        positions = []
        return web.json_response(positions)
    
    async def get_activity(self, request):
        """Get recent activity"""
        # Return actual activity from your bot
        activity = []
        return web.json_response(activity)
    
    async def start(self):
        """Start the dashboard server"""
        port = int(os.environ.get('PORT', 8080))
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"""
        ═══════════════════════════════════════════
        ║         TRON TRADING SYSTEM             ║
        ═══════════════════════════════════════════
        ║                                         ║
        ║  Dashboard: http://localhost:{port}      ║
        ║  Railway: https://YOUR-APP.railway.app  ║
        ║                                         ║
        ║  Status: AWAITING AUTHENTICATION        ║
        ║                                         ║
        ═══════════════════════════════════════════
        """)

async def main():
    """Main entry point"""
    dashboard = TronDashboard()
    dashboard.start_time = time.time()
    
    # Start dashboard
    await dashboard.start()
    
    # Keep running
    while True:
        await asyncio.sleep(60)

if __name__ == '__main__':
    # Check environment variables
    required = ['TG_API_ID', 'TG_API_HASH']
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.info("Dashboard will run in demo mode")
    
    # Run the system
    asyncio.run(main())
