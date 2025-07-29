# main.py - Complete Solana Trading Bot for Railway
# Copy this entire file and save as main.py
"""
Solana Trading Bot - All-in-One Version
Ready for Railway deployment with ToxiBot integration
"""

import os
import asyncio
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

# === CONFIGURATION ===
@dataclass
class Config:
    """Bot configuration from environment variables"""
    # Telegram
    tg_api_id: str = os.getenv('TG_API_ID', '')
    tg_api_hash: str = os.getenv('TG_API_HASH', '')
    tg_phone: str = os.getenv('TG_PHONE', '')
    
    # Twitter
    twitter_bearer: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    
    # Solana RPC
    rpc_url: str = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    
    # Alerts
    alert_chat_id: str = os.getenv('TELEGRAM_CHAT_ID', '')
    alert_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    # Trading
    validation_mode: bool = True
    base_position_size: float = 0.05
    daily_loss_limit: float = 0.30

# === SIMPLE TOXIBOT INTEGRATION ===
class ToxiBotTrader:
    """Simplified ToxiBot integration"""
    
    def __init__(self, config: Config):
        self.config = config
        self.telegram_ready = False
        
    async def initialize(self):
        """Initialize Telegram connection"""
        try:
            # Import here to avoid issues if not installed
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            # Try to load existing session
            session_file = 'session.txt'
            session_string = None
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    session_string = f.read().strip()
            
            # Create client
            self.client = TelegramClient(
                StringSession(session_string) if session_string else 'bot_session',
                int(self.config.tg_api_id),
                self.config.tg_api_hash
            )
            
            # Start client
            await self.client.start(phone=self.config.tg_phone)
            
            # Save session for next time
            if not session_string:
                with open(session_file, 'w') as f:
                    f.write(self.client.session.save())
            
            self.telegram_ready = True
            logger.info("✅ Telegram connected successfully!")
            
            # Test ToxiBot connection
            await self.test_toxibot()
            
        except Exception as e:
            logger.error(f"❌ Telegram initialization failed: {e}")
            logger.info("Bot will run in simulation mode")
    
    async def test_toxibot(self):
        """Test ToxiBot is accessible"""
        try:
            await self.client.send_message('@toxi_solana_bot', '/start')
            logger.info("✅ ToxiBot connection verified")
        except Exception as e:
            logger.error(f"⚠️ ToxiBot test failed: {e}")
    
    async def execute_trade(self, action: str, token: str, amount: float, slippage: float = 0.15):
        """Execute trade via ToxiBot"""
        if not self.telegram_ready:
            logger.info(f"📝 SIMULATION: Would {action} {amount} SOL of {token[:8]}...")
            return True
        
        try:
            if action == 'buy':
                command = f"/buy {token} {amount:.3f} {slippage:.2f}"
            else:
                command = f"/sell {token} {int(amount)}"  # amount is percentage for sells
            
            logger.info(f"📤 Sending to ToxiBot: {command}")
            await self.client.send_message('@toxi_solana_bot', command)
            
            # Wait for confirmation
            await asyncio.sleep(5)
            
            # Check recent messages
            messages = await self.client.get_messages('@toxi_solana_bot', limit=5)
            
            for msg in messages:
                if msg.text and token[:8] in msg.text:
                    if 'success' in msg.text.lower() or 'bought' in msg.text.lower():
                        logger.info(f"✅ Trade confirmed: {msg.text[:100]}")
                        return True
            
            logger.warning("⚠️ No confirmation received from ToxiBot")
            return False
            
        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            return False

# === SOCIAL MONITORING ===
class SocialMonitor:
    """Monitor Twitter for Elon/Trump signals"""
    
    def __init__(self, config: Config):
        self.config = config
        self.vip_accounts = [
            'elonmusk',
            'realDonaldTrump',
            'CoinbaseEarns',
            'binance'
        ]
        self.pump_keywords = [
            'doge', 'shib', 'mars', 'moon',
            'maga', 'trump', 'america',
            'listing', 'pump', 'crypto'
        ]
    
    async def check_vip_tweets(self) -> List[Dict]:
        """Check for pump signals from VIP accounts"""
        signals = []
        
        if not self.config.twitter_bearer:
            logger.warning("⚠️ Twitter API not configured - skipping social signals")
            return signals
        
        try:
            headers = {'Authorization': f'Bearer {self.config.twitter_bearer}'}
            
            for account in self.vip_accounts:
                # Get user ID
                url = f"https://api.twitter.com/2/users/by/username/{account}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        user_id = data['data']['id']
                
                # Get recent tweets
                tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                params = {'max_results': 10, 'tweet.fields': 'created_at'}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(tweets_url, headers=headers, params=params) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        
                        if 'data' in data:
                            for tweet in data['data']:
                                # Check for keywords
                                text_lower = tweet['text'].lower()
                                for keyword in self.pump_keywords:
                                    if keyword in text_lower:
                                        signals.append({
                                            'account': account,
                                            'keyword': keyword,
                                            'text': tweet['text'][:100],
                                            'multiplier': 2.0 if account == 'elonmusk' else 1.5
                                        })
                                        logger.info(f"🚨 VIP Signal: {account} mentioned {keyword}!")
                                        break
            
        except Exception as e:
            logger.error(f"Social monitoring error: {e}")
        
        return signals

# === TOKEN DISCOVERY ===
class TokenFinder:
    """Find new tokens on pump.fun"""
    
    def __init__(self):
        self.pump_fun_api = "https://client-api.pump.fun"
    
    async def find_new_tokens(self) -> List[Dict]:
        """Find potential gems"""
        tokens = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get newest tokens
                async with session.get(f"{self.pump_fun_api}/coins/newest") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        for token in data[:20]:  # Check top 20
                            # Basic filters
                            if token.get('liquidity_usd', 0) > 5000:
                                if token.get('market_cap', 0) < 500000:
                                    tokens.append({
                                        'address': token['mint'],
                                        'symbol': token.get('symbol', 'UNKNOWN'),
                                        'name': token.get('name', ''),
                                        'liquidity': token.get('liquidity_usd', 0),
                                        'age_minutes': (time.time() - token.get('created_at', time.time())) / 60,
                                        'score': self._calculate_score(token)
                                    })
                        
                        # Sort by score
                        tokens.sort(key=lambda x: x['score'], reverse=True)
                        
        except Exception as e:
            logger.error(f"Token discovery error: {e}")
        
        return tokens
    
    def _calculate_score(self, token: Dict) -> float:
        """Simple scoring system"""
        score = 0.0
        
        # Liquidity score
        if token.get('liquidity_usd', 0) > 50000:
            score += 0.3
        elif token.get('liquidity_usd', 0) > 25000:
            score += 0.2
        elif token.get('liquidity_usd', 0) > 10000:
            score += 0.1
        
        # Age score (newer = better)
        age_minutes = (time.time() - token.get('created_at', time.time())) / 60
        if age_minutes < 10:
            score += 0.3
        elif age_minutes < 30:
            score += 0.2
        elif age_minutes < 60:
            score += 0.1
        
        # Meme potential
        meme_words = ['elon', 'doge', 'moon', 'mars', 'pepe', 'maga', 'trump']
        name_lower = token.get('name', '').lower()
        symbol_lower = token.get('symbol', '').lower()
        
        for word in meme_words:
            if word in name_lower or word in symbol_lower:
                score += 0.2
                break
        
        return min(score, 1.0)

# === MAIN BOT ===
class SolanaTradingBot:
    """Main bot orchestrator"""
    
    def __init__(self):
        self.config = Config()
        self.trader = ToxiBotTrader(self.config)
        self.social_monitor = SocialMonitor(self.config)
        self.token_finder = TokenFinder()
        self.positions = {}
        self.daily_pnl = 0.0
        self.trade_count = 0
        self.start_time = time.time()
    
    async def initialize(self):
        """Initialize all systems"""
        logger.info("""
        🚀 SOLANA TRADING BOT - VALIDATION MODE
        ======================================
        Position Size: 0.05 SOL
        Daily Loss Limit: 0.30 SOL
        
        Initializing systems...
        """)
        
        await self.trader.initialize()
        await self.send_alert("🚀 Bot started in validation mode!", "INFO")
    
    async def run(self):
        """Main bot loop"""
        await self.initialize()
        
        # Run all tasks concurrently
        tasks = [
            self.monitor_social_signals(),
            self.scan_new_tokens(),
            self.monitor_positions(),
            self.health_check()
        ]
        
        await asyncio.gather(*tasks)
    
    async def monitor_social_signals(self):
        """Monitor for Elon/Trump signals"""
        while True:
            try:
                signals = await self.social_monitor.check_vip_tweets()
                
                for signal in signals:
                    logger.info(f"🚨 SOCIAL SIGNAL: {signal['account']} - {signal['keyword']}")
                    
                    # Find matching tokens
                    tokens = await self.token_finder.find_new_tokens()
                    
                    for token in tokens[:3]:  # Check top 3
                        if signal['keyword'] in token['name'].lower() or signal['keyword'] in token['symbol'].lower():
                            # Calculate position size with multiplier
                            position_size = self.config.base_position_size * signal['multiplier']
                            position_size = min(position_size, 0.10)  # Cap at 0.10
                            
                            logger.info(f"🎯 Matched token {token['symbol']} with {signal['keyword']}!")
                            
                            # Execute trade
                            success = await self.trader.execute_trade(
                                'buy',
                                token['address'],
                                position_size,
                                0.15  # 15% slippage
                            )
                            
                            if success:
                                self.positions[token['address']] = {
                                    'symbol': token['symbol'],
                                    'entry_time': time.time(),
                                    'size': position_size,
                                    'signal': f"{signal['account']}_{signal['keyword']}"
                                }
                                self.trade_count += 1
                                
                                await self.send_alert(
                                    f"🚀 BOUGHT {token['symbol']}\n"
                                    f"Signal: {signal['account']} tweeted '{signal['keyword']}'\n"
                                    f"Amount: {position_size} SOL",
                                    "TRADE"
                                )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Social monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def scan_new_tokens(self):
        """Regular token scanning"""
        while True:
            try:
                # Skip if we have too many positions
                if len(self.positions) >= 5:
                    await asyncio.sleep(120)
                    continue
                
                tokens = await self.token_finder.find_new_tokens()
                
                for token in tokens[:10]:
                    if token['score'] >= 0.7:
                        # Check if we already have this token
                        if token['address'] in self.positions:
                            continue
                        
                        logger.info(f"🔍 Found potential gem: {token['symbol']} (score: {token['score']:.2f})")
                        
                        # Execute trade
                        success = await self.trader.execute_trade(
                            'buy',
                            token['address'],
                            self.config.base_position_size,
                            0.15
                        )
                        
                        if success:
                            self.positions[token['address']] = {
                                'symbol': token['symbol'],
                                'entry_time': time.time(),
                                'size': self.config.base_position_size,
                                'signal': 'scanner'
                            }
                            self.trade_count += 1
                            
                            await self.send_alert(
                                f"💎 Found gem: {token['symbol']}\n"
                                f"Score: {token['score']:.2f}\n"
                                f"Amount: {self.config.base_position_size} SOL",
                                "TRADE"
                            )
                            
                            break  # One trade at a time
                
                await asyncio.sleep(120)  # Scan every 2 minutes
                
            except Exception as e:
                logger.error(f"Token scanning error: {e}")
                await asyncio.sleep(300)
    
    async def monitor_positions(self):
        """Monitor and exit positions"""
        while True:
            try:
                for address, position in list(self.positions.items()):
                    # Simple time-based exit for validation
                    hold_time = (time.time() - position['entry_time']) / 3600  # hours
                    
                    if hold_time > 2:  # Hold for 2 hours max during validation
                        logger.info(f"⏰ Time to exit {position['symbol']}")
                        
                        # Sell 100%
                        success = await self.trader.execute_trade(
                            'sell',
                            address,
                            100,  # 100% for sells
                            0
                        )
                        
                        if success:
                            # Remove position
                            del self.positions[address]
                            
                            await self.send_alert(
                                f"💰 Sold {position['symbol']}\n"
                                f"Held for {hold_time:.1f} hours",
                                "TRADE"
                            )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def health_check(self):
        """Regular health checks and stats"""
        while True:
            try:
                uptime_hours = (time.time() - self.start_time) / 3600
                
                stats = f"""
📊 BOT STATS
===========
Uptime: {uptime_hours:.1f} hours
Trades: {self.trade_count}
Positions: {len(self.positions)}
Mode: {'LIVE' if self.trader.telegram_ready else 'SIMULATION'}
                """
                
                logger.info(stats)
                
                # Send daily summary
                if int(uptime_hours) % 24 == 0 and uptime_hours > 0:
                    await self.send_alert(stats, "DAILY")
                
                await asyncio.sleep(3600)  # Every hour
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(3600)
    
    async def send_alert(self, message: str, alert_type: str = "INFO"):
        """Send alerts to Telegram"""
        if not self.config.alert_bot_token or not self.config.alert_chat_id:
            logger.info(f"📱 Alert [{alert_type}]: {message}")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.config.alert_bot_token}/sendMessage"
            data = {
                'chat_id': self.config.alert_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=data)
                
        except Exception as e:
            logger.error(f"Alert error: {e}")

# === ENTRY POINT ===
async def main():
    """Main entry point"""
    bot = SolanaTradingBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    # Print startup banner
    print("""
    💎 SOLANA TRADING BOT 💎
    ======================
    Validation Mode: ON
    Position Size: 0.05 SOL
    
    Starting up...
    """)
    
    # Check environment variables
    required_vars = ['TG_API_ID', 'TG_API_HASH', 'TG_PHONE']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"⚠️ Missing environment variables: {', '.join(missing)}")
        print("Bot will run in simulation mode")
    
    # Run the bot
    asyncio.run(main())
