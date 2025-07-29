#!/usr/bin/env python3
"""
Fixed Solana Trading Bot - Works on Railway without input
"""

import asyncio
import os
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SolanaBot')

# Suppress SSL warnings
logging.getLogger('telethon.crypto.libssl').setLevel(logging.ERROR)

@dataclass
class Config:
    """Bot configuration"""
    # Telegram
    tg_api_id: str = os.getenv('TG_API_ID', '')
    tg_api_hash: str = os.getenv('TG_API_HASH', '')
    tg_phone: str = os.getenv('TG_PHONE', '')
    tg_session: str = os.getenv('TG_SESSION', '')  # Pre-made session string
    
    # Trading
    validation_mode: bool = True
    base_position_size: float = 0.05
    daily_loss_limit: float = 0.30

class SimplifiedBot:
    """Simplified bot that works without Telegram auth on Railway"""
    
    def __init__(self):
        self.config = Config()
        self.positions = {}
        self.trade_count = 0
        self.start_time = time.time()
        self.telegram_ready = False
        
    async def initialize(self):
        """Initialize bot systems"""
        logger.info("""
        🚀 SOLANA TRADING BOT - VALIDATION MODE
        ======================================
        Position Size: 0.05 SOL
        Daily Loss Limit: 0.30 SOL
        
        Initializing systems...
        """)
        
        # Try Telegram if session provided
        if self.config.tg_session:
            await self.init_telegram_from_session()
        else:
            logger.info("No Telegram session provided - running in simulation mode")
            logger.info("To use ToxiBot:")
            logger.info("1. Run locally first to generate session")
            logger.info("2. Add TG_SESSION to Railway environment variables")
    
    async def init_telegram_from_session(self):
        """Initialize Telegram from session string"""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            self.client = TelegramClient(
                StringSession(self.config.tg_session),
                int(self.config.tg_api_id),
                self.config.tg_api_hash
            )
            
            await self.client.connect()
            
            if await self.client.is_user_authorized():
                self.telegram_ready = True
                logger.info("✅ Telegram connected via session!")
                
                # Test ToxiBot
                try:
                    await self.client.send_message('@toxi_solana_bot', '/start')
                    logger.info("✅ ToxiBot connection verified")
                except:
                    logger.warning("Could not verify ToxiBot")
            else:
                logger.warning("Telegram session invalid - running in simulation")
                
        except Exception as e:
            logger.warning(f"Telegram init failed: {e}")
            logger.info("Running in simulation mode")
    
    async def scan_tokens(self) -> List[Dict]:
        """Scan for new tokens with error handling"""
        try:
            # Try frontend API first (more reliable)
            url = "https://frontend-api.pump.fun/coins?offset=0&limit=20&sort=created&order=DESC"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        tokens = []
                        
                        for token in data:
                            # Basic filtering
                            market_cap = token.get('usd_market_cap', 0)
                            if market_cap > 5000 and market_cap < 500000:
                                tokens.append({
                                    'address': token.get('mint', ''),
                                    'symbol': token.get('symbol', 'UNKNOWN'),
                                    'name': token.get('name', ''),
                                    'market_cap': market_cap,
                                    'created': token.get('created_timestamp', 0)
                                })
                        
                        if tokens:
                            logger.info(f"Found {len(tokens)} potential tokens")
                        return tokens
                    else:
                        logger.warning(f"API returned status {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Token scan error: {e}")
            return []
    
    async def simulate_trade(self, token: Dict):
        """Simulate a trade (or execute via ToxiBot if connected)"""
        logger.info(f"💎 Found potential gem: {token['symbol']}")
        
        if self.telegram_ready:
            try:
                # Real ToxiBot execution
                command = f"/buy {token['address']} 0.05 0.15"
                await self.client.send_message('@toxi_solana_bot', command)
                logger.info(f"📤 Sent to ToxiBot: {command}")
                
                # Wait for confirmation
                await asyncio.sleep(5)
                
                # Check for response
                messages = await self.client.get_messages('@toxi_solana_bot', limit=5)
                for msg in messages:
                    if msg.text and token['address'][:8] in msg.text:
                        if 'success' in msg.text.lower() or 'bought' in msg.text.lower():
                            logger.info(f"✅ Trade confirmed!")
                            self.trade_count += 1
                            return True
                            
            except Exception as e:
                logger.error(f"ToxiBot execution error: {e}")
        else:
            # Simulation mode
            logger.info(f"📝 SIMULATION: Would buy 0.05 SOL of {token['symbol']}")
            self.trade_count += 1
            
        return True
    
    async def monitor_social(self):
        """Monitor social signals with better error handling"""
        if not os.getenv('TWITTER_BEARER_TOKEN'):
            logger.info("No Twitter API configured - skipping social monitoring")
            return
            
        while True:
            try:
                # Simplified Twitter monitoring
                headers = {'Authorization': f"Bearer {os.getenv('TWITTER_BEARER_TOKEN')}"}
                
                # Just check if API works
                async with aiohttp.ClientSession() as session:
                    url = "https://api.twitter.com/2/users/by/username/elonmusk"
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            logger.info("✅ Twitter API working")
                        else:
                            logger.warning(f"Twitter API status: {resp.status}")
                            
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Social monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def run(self):
        """Main bot loop"""
        await self.initialize()
        
        # Run simplified tasks
        tasks = [
            self.token_scanner_loop(),
            self.monitor_social(),
            self.health_check()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def token_scanner_loop(self):
        """Main token scanning loop"""
        while True:
            try:
                tokens = await self.scan_tokens()
                
                # Process top tokens
                for token in tokens[:3]:
                    # Simple filtering
                    if 'rug' not in token['name'].lower():
                        await self.simulate_trade(token)
                        break  # One trade at a time
                        
                await asyncio.sleep(120)  # Scan every 2 minutes
                
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(300)
    
    async def health_check(self):
        """Regular health updates"""
        while True:
            try:
                uptime = (time.time() - self.start_time) / 3600
                
                logger.info(f"""
📊 BOT STATS
===========
Uptime: {uptime:.1f} hours
Trades: {self.trade_count}
Positions: {len(self.positions)}
Mode: {'LIVE' if self.telegram_ready else 'SIMULATION'}
                """)
                
                await asyncio.sleep(3600)  # Every hour
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(3600)

# === HELPER SCRIPT ===
def generate_session_locally():
    """Run this locally to generate session string"""
    print("""
    ===================================
    GENERATE TELEGRAM SESSION LOCALLY
    ===================================
    
    1. Run this script on your computer (not Railway)
    2. Enter your phone when prompted
    3. Enter the code from Telegram
    4. Copy the session string
    5. Add to Railway as TG_SESSION environment variable
    
    """)
    
    import asyncio
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    
    api_id = input("Enter TG_API_ID: ")
    api_hash = input("Enter TG_API_HASH: ")
    
    async def create_session():
        client = TelegramClient(StringSession(), int(api_id), api_hash)
        await client.start()
        session_string = client.session.save()
        print("\n✅ SUCCESS! Your session string:")
        print("=" * 50)
        print(session_string)
        print("=" * 50)
        print("\nAdd this to Railway as: TG_SESSION")
        
    asyncio.run(create_session())

# === MAIN ===
async def main():
    """Entry point"""
    bot = SimplifiedBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    import sys
    
    # Check if generating session
    if len(sys.argv) > 1 and sys.argv[1] == '--generate-session':
        generate_session_locally()
    else:
        # Normal bot run
        print("""
        💎 SOLANA TRADING BOT 💎
        ======================
        Starting up...
        """)
        
        asyncio.run(main())
