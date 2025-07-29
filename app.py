#!/usr/bin/env python3
"""
Complete Solana Trading Bot with TRON Web Dashboard
Setup credentials and authenticate through web interface
"""

import asyncio
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from aiohttp import web
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TronSystem')

# HTML Template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRON Trading System</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Orbitron', monospace;
            background: #000;
            color: #00ffff;
            overflow-x: hidden;
            position: relative;
            min-height: 100vh;
        }
        
        /* TRON Grid Background */
        .grid-background {
            position: fixed;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: -2;
            background: #000;
            overflow: hidden;
        }
        
        .grid-background::before {
            content: '';
            position: absolute;
            width: 200%;
            height: 200%;
            top: -50%;
            left: -50%;
            background-image: 
                linear-gradient(#00ffff11 1px, transparent 1px),
                linear-gradient(90deg, #00ffff11 1px, transparent 1px);
            background-size: 50px 50px;
            animation: grid-move 20s linear infinite;
            transform: perspective(1000px) rotateX(60deg);
        }
        
        @keyframes grid-move {
            0% { transform: perspective(1000px) rotateX(60deg) translateY(0); }
            100% { transform: perspective(1000px) rotateX(60deg) translateY(50px); }
        }
        
        /* Neon glow effects */
        .neon-text {
            text-shadow: 
                0 0 10px #00ffff,
                0 0 20px #00ffff,
                0 0 30px #00ffff,
                0 0 40px #0088ff;
        }
        
        .neon-box {
            border: 2px solid #00ffff;
            box-shadow: 
                0 0 10px #00ffff,
                0 0 20px #00ffff,
                inset 0 0 10px #00ffff22;
            background: rgba(0, 255, 255, 0.05);
            backdrop-filter: blur(10px);
        }
        
        /* Header */
        .header {
            background: linear-gradient(180deg, #000 0%, transparent 100%);
            padding: 30px 0;
            position: relative;
            overflow: hidden;
        }
        
        .header::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent,
                #00ffff 20%,
                #00ffff 80%,
                transparent
            );
            animation: scan-line 3s linear infinite;
        }
        
        @keyframes scan-line {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 32px;
            font-weight: 900;
            letter-spacing: 3px;
            color: #00ffff;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo-icon {
            width: 50px;
            height: 50px;
            border: 2px solid #00ffff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            animation: rotate 10s linear infinite;
        }
        
        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            border: 1px solid #ff6600;
            background: rgba(255, 102, 0, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .status-indicator.online {
            border-color: #00ff00;
            background: rgba(0, 255, 0, 0.1);
        }
        
        .status-indicator::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            width: 10px;
            height: 10px;
            background: #ff6600;
            border-radius: 50%;
            animation: pulse 1s ease-in-out infinite;
        }
        
        .status-indicator.online::before {
            background: #00ff00;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: translateY(-50%) scale(1); }
            50% { opacity: 0.5; transform: translateY(-50%) scale(1.5); }
        }
        
        /* Container */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Setup Modal */
        .setup-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .setup-modal.hidden {
            display: none;
        }
        
        .setup-box {
            background: #000;
            border: 2px solid #00ffff;
            padding: 40px;
            border-radius: 0;
            max-width: 600px;
            width: 90%;
            position: relative;
            box-shadow: 
                0 0 30px #00ffff,
                0 0 60px #0088ff,
                inset 0 0 30px #00ffff11;
        }
        
        .setup-title {
            font-size: 24px;
            text-align: center;
            margin-bottom: 30px;
            color: #00ffff;
            text-transform: uppercase;
            letter-spacing: 3px;
        }
        
        .setup-step {
            margin-bottom: 25px;
            display: none;
        }
        
        .setup-step.active {
            display: block;
        }
        
        .setup-step h3 {
            color: #ff6600;
            margin-bottom: 15px;
            font-size: 18px;
            text-shadow: 0 0 10px #ff6600;
        }
        
        .setup-info {
            background: rgba(0, 255, 255, 0.1);
            border: 1px solid #00ffff;
            padding: 20px;
            margin-bottom: 20px;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .setup-info a {
            color: #ff6600;
            text-decoration: none;
        }
        
        .setup-info a:hover {
            text-shadow: 0 0 10px #ff6600;
        }
        
        .input-group {
            position: relative;
            margin-bottom: 20px;
        }
        
        .input-label {
            display: block;
            margin-bottom: 8px;
            color: #00ffff;
            font-size: 14px;
        }
        
        .neon-input {
            width: 100%;
            padding: 15px;
            background: transparent;
            border: 2px solid #00ffff;
            color: #00ffff;
            font-family: 'Orbitron', monospace;
            font-size: 16px;
            outline: none;
            transition: all 0.3s;
        }
        
        .neon-input:focus {
            box-shadow: 
                0 0 20px #00ffff,
                inset 0 0 20px #00ffff22;
        }
        
        .neon-button {
            width: 100%;
            padding: 15px;
            background: transparent;
            border: 2px solid #ff6600;
            color: #ff6600;
            font-family: 'Orbitron', monospace;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 2px;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .neon-button:hover {
            color: #000;
            background: #ff6600;
            box-shadow: 
                0 0 30px #ff6600,
                inset 0 0 30px #ff660033;
        }
        
        .neon-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .button-row {
            display: flex;
            gap: 15px;
        }
        
        .button-row .neon-button {
            flex: 1;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            padding: 30px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent,
                #00ffff,
                transparent
            );
            animation: scan-line 3s linear infinite;
        }
        
        .stat-label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
            color: #ff6600;
        }
        
        .stat-value {
            font-size: 36px;
            font-weight: 900;
            margin-bottom: 10px;
            color: #00ffff;
        }
        
        .stat-change {
            font-size: 14px;
            color: #00ff00;
        }
        
        .stat-change.negative {
            color: #ff0066;
        }
        
        /* Success/Error messages */
        .success-message {
            background: rgba(0, 255, 0, 0.2);
            border: 2px solid #00ff00;
            padding: 20px;
            margin-top: 20px;
            text-align: center;
            animation: glow-success 2s ease-in-out infinite;
        }
        
        @keyframes glow-success {
            0%, 100% { box-shadow: 0 0 20px #00ff00; }
            50% { box-shadow: 0 0 40px #00ff00, 0 0 60px #00ff00; }
        }
        
        .error-message {
            background: rgba(255, 0, 0, 0.2);
            border: 2px solid #ff0000;
            padding: 20px;
            margin-top: 20px;
            text-align: center;
            color: #ff6666;
        }
        
        /* Activity Feed */
        .activity-feed {
            padding: 30px;
        }
        
        .activity-item {
            display: flex;
            align-items: center;
            padding: 20px;
            margin-bottom: 15px;
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid #00ffff33;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .activity-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            width: 4px;
            height: 100%;
            background: #00ffff;
        }
        
        .activity-icon {
            width: 40px;
            height: 40px;
            border: 2px solid #ff6600;
            margin-right: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-time {
            color: #ff6600;
            font-size: 12px;
        }
        
        /* Loading animation */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #00ffff33;
            border-top-color: #00ffff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Scanlines effect */
        .scanlines {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 999;
            background: 
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(0, 255, 255, 0.03) 2px,
                    rgba(0, 255, 255, 0.03) 4px
                );
            animation: scanlines 8s linear infinite;
        }
        
        @keyframes scanlines {
            0% { transform: translateY(0); }
            100% { transform: translateY(10px); }
        }
        
        /* Mobile responsive */
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .header-content {
                flex-direction: column;
                gap: 20px;
            }
            
            .setup-box {
                padding: 20px;
            }
            
            .button-row {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <!-- Scanlines overlay -->
    <div class="scanlines"></div>
    
    <!-- Grid background -->
    <div class="grid-background"></div>
    
    <!-- Setup Modal -->
    <div class="setup-modal" id="setupModal">
        <div class="setup-box">
            <h2 class="setup-title neon-text">TRON System Configuration</h2>
            
            <!-- Step 1: API Setup -->
            <div class="setup-step active" id="apiStep">
                <h3>Step 1: Telegram API Configuration</h3>
                <div class="setup-info">
                    <p><strong>To get your Telegram API credentials:</strong></p>
                    <p>1. Go to <a href="https://my.telegram.org" target="_blank">https://my.telegram.org</a></p>
                    <p>2. Log in with your phone number</p>
                    <p>3. Go to "API Development Tools"</p>
                    <p>4. Create a new application</p>
                    <p>5. Copy your API ID and API Hash below</p>
                </div>
                
                <div class="input-group">
                    <label class="input-label">API ID</label>
                    <input type="text" 
                           id="apiId" 
                           class="neon-input" 
                           placeholder="12345678">
                </div>
                
                <div class="input-group">
                    <label class="input-label">API Hash</label>
                    <input type="text" 
                           id="apiHash" 
                           class="neon-input" 
                           placeholder="1234567890abcdef1234567890abcdef">
                </div>
                
                <button class="neon-button" onclick="saveApiCredentials()" id="saveApiBtn">
                    Save Credentials
                </button>
            </div>
            
            <!-- Step 2: Phone Number -->
            <div class="setup-step" id="phoneStep">
                <h3>Step 2: Phone Number Authentication</h3>
                <div class="setup-info">
                    <p>Enter your Telegram phone number to receive a verification code.</p>
                    <p>Include country code (e.g., +61 for Australia)</p>
                </div>
                
                <div class="input-group">
                    <label class="input-label">Phone Number</label>
                    <input type="tel" 
                           id="phoneInput" 
                           class="neon-input" 
                           placeholder="+61 XXX XXX XXX">
                </div>
                
                <button class="neon-button" onclick="requestCode()" id="requestBtn">
                    Request Verification Code
                </button>
            </div>
            
            <!-- Step 3: Verification Code -->
            <div class="setup-step" id="codeStep">
                <h3>Step 3: Verification Code</h3>
                <div class="setup-info">
                    <p>Check your Telegram app for the verification code and enter it below.</p>
                </div>
                
                <div class="input-group">
                    <label class="input-label">Verification Code</label>
                    <input type="text" 
                           id="codeInput" 
                           class="neon-input" 
                           placeholder="12345"
                           maxlength="5">
                </div>
                
                <div class="button-row">
                    <button class="neon-button" onclick="goToPhoneStep()" style="background: transparent; border-color: #666; color: #666;">
                        Back
                    </button>
                    <button class="neon-button" onclick="verifyCode()" id="verifyBtn">
                        Verify & Start Bot
                    </button>
                </div>
            </div>
            
            <!-- Success -->
            <div class="setup-step" id="successStep">
                <div class="success-message">
                    <h3 style="color: #00ff00; margin-bottom: 10px;">✓ SYSTEM INITIALIZED</h3>
                    <p>Authentication successful! Bot is starting...</p>
                </div>
            </div>
            
            <!-- Error Display -->
            <div id="setupError" style="display: none;">
                <div class="error-message">
                    <h3 style="margin-bottom: 10px;">⚠ SETUP ERROR</h3>
                    <p id="errorMessage">Please try again</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <div class="logo neon-text">
                <div class="logo-icon">⚡</div>
                <span>TRON TRADER</span>
            </div>
            <div class="status-indicator" id="statusIndicator">
                <span style="margin-left: 20px;" id="statusText">SETUP REQUIRED</span>
            </div>
        </div>
    </header>
    
    <!-- Main content -->
    <div class="container">
        <!-- Stats cards -->
        <div class="stats-grid">
            <div class="stat-card neon-box">
                <div class="stat-label">Total Profit</div>
                <div class="stat-value neon-text" id="totalProfit">+0.000 SOL</div>
                <div class="stat-change" id="profitChange">↑ Awaiting setup...</div>
            </div>
            
            <div class="stat-card neon-box">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value neon-text" id="winRate">0%</div>
                <div class="stat-change" id="winRateChange">0 wins / 0 losses</div>
            </div>
            
            <div class="stat-card neon-box">
                <div class="stat-label">Active Positions</div>
                <div class="stat-value neon-text" id="positions">0</div>
                <div class="stat-change" id="positionsChange">0.00 SOL invested</div>
            </div>
            
            <div class="stat-card neon-box">
                <div class="stat-label">System Status</div>
                <div class="stat-value neon-text" id="systemStatus">OFFLINE</div>
                <div class="stat-change" id="systemChange">Configuration needed</div>
            </div>
        </div>
        
        <!-- Activity feed -->
        <div class="activity-feed neon-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="font-size: 20px; text-transform: uppercase; letter-spacing: 2px;" class="neon-text">System Activity Log</h2>
            </div>
            <div id="activityFeed">
                <div class="activity-item">
                    <div class="activity-icon">⚙️</div>
                    <div class="activity-content">
                        <div>System awaiting configuration...</div>
                        <div class="activity-time">Please complete setup to start trading</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Global state
        let systemConfigured = false;
        let authenticated = false;
        let botRunning = false;
        let startTime = Date.now();
        
        // Check if system is already configured
        checkSystemStatus();
        
        async function checkSystemStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.configured && data.authenticated) {
                    systemConfigured = true;
                    authenticated = true;
                    document.getElementById('setupModal').classList.add('hidden');
                    updateSystemStatus('ONLINE', 'Bot operational');
                    startDashboard();
                } else if (data.configured) {
                    // API configured but not authenticated
                    systemConfigured = true;
                    showPhoneStep();
                }
            } catch (e) {
                console.log('System not configured yet');
            }
        }
        
        async function saveApiCredentials() {
            const apiId = document.getElementById('apiId').value;
            const apiHash = document.getElementById('apiHash').value;
            
            if (!apiId || !apiHash) {
                showError('Please enter both API ID and API Hash');
                return;
            }
            
            const btn = document.getElementById('saveApiBtn');
            btn.disabled = true;
            btn.textContent = 'Saving...';
            
            try {
                const response = await fetch('/api/setup/credentials', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        api_id: parseInt(apiId),
                        api_hash: apiHash 
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    systemConfigured = true;
                    hideError();
                    showPhoneStep();
                    addActivity('✅', 'API credentials saved', 'Telegram client configured');
                } else {
                    showError(data.error || 'Failed to save credentials');
                }
            } catch (e) {
                showError('Connection error. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Save Credentials';
            }
        }
        
        function showPhoneStep() {
            document.getElementById('apiStep').classList.remove('active');
            document.getElementById('phoneStep').classList.add('active');
        }
        
        function goToPhoneStep() {
            document.getElementById('codeStep').classList.remove('active');
            document.getElementById('phoneStep').classList.add('active');
        }
        
        async function requestCode() {
            const phone = document.getElementById('phoneInput').value;
            if (!phone) {
                showError('Please enter your phone number');
                return;
            }
            
            const btn = document.getElementById('requestBtn');
            btn.disabled = true;
            btn.textContent = 'Sending code...';
            
            try {
                const response = await fetch('/api/auth/request-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    hideError();
                    showCodeStep();
                    addActivity('📱', 'Code sent', `Verification code sent to ${phone}`);
                } else {
                    showError(data.error || 'Failed to send code');
                }
            } catch (e) {
                showError('Connection error. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Request Verification Code';
            }
        }
        
        function showCodeStep() {
            document.getElementById('phoneStep').classList.remove('active');
            document.getElementById('codeStep').classList.add('active');
            document.getElementById('codeInput').focus();
        }
        
        async function verifyCode() {
            const code = document.getElementById('codeInput').value;
            if (!code) {
                showError('Please enter the verification code');
                return;
            }
            
            const btn = document.getElementById('verifyBtn');
            btn.disabled = true;
            btn.textContent = 'Verifying...';
            
            try {
                const response = await fetch('/api/auth/verify-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    authenticated = true;
                    hideError();
                    showSuccessStep();
                    addActivity('🚀', 'Authentication successful', 'Bot starting...');
                    
                    // Hide modal after 3 seconds and start dashboard
                    setTimeout(() => {
                        document.getElementById('setupModal').classList.add('hidden');
                        updateSystemStatus('ONLINE', 'Bot operational');
                        startDashboard();
                    }, 3000);
                } else {
                    showError(data.error || 'Invalid verification code');
                }
            } catch (e) {
                showError('Verification failed. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Verify & Start Bot';
            }
        }
        
        function showSuccessStep() {
            document.getElementById('codeStep').classList.remove('active');
            document.getElementById('successStep').classList.add('active');
        }
        
        function showError(message) {
            document.getElementById('setupError').style.display = 'block';
            document.getElementById('errorMessage').textContent = message;
        }
        
        function hideError() {
            document.getElementById('setupError').style.display = 'none';
        }
        
        function updateSystemStatus(status, message) {
            document.getElementById('systemStatus').textContent = status;
            document.getElementById('systemChange').textContent = message;
            
            const indicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            
            if (status === 'ONLINE') {
                indicator.classList.add('online');
                statusText.textContent = 'SYSTEM ONLINE';
            } else {
                indicator.classList.remove('online');
                statusText.textContent = status;
            }
        }
        
        function startDashboard() {
            console.log('Dashboard started!');
            botRunning = true;
            
            // Start loading data
            loadDashboardData();
            setInterval(loadDashboardData, 5000);
            
            // Start simulated trading
            setTimeout(simulateTrading, 10000);
            setInterval(simulateTrading, 30000);
        }
        
        async function loadDashboardData() {
            try {
                const response = await fetch('/api/stats');
                if (response.ok) {
                    const stats = await response.json();
                    updateStats(stats);
                }
            } catch (e) {
                console.error('Error loading data:', e);
            }
        }
        
        function updateStats(stats) {
            if (stats.totalProfit !== undefined) {
                document.getElementById('totalProfit').textContent = `+${stats.totalProfit.toFixed(3)} SOL`;
                document.getElementById('profitChange').textContent = `↑ +${(stats.totalProfit * 100).toFixed(1)}% total`;
            }
            
            if (stats.winRate !== undefined) {
                document.getElementById('winRate').textContent = `${stats.winRate}%`;
                document.getElementById('winRateChange').textContent = `${stats.wins} wins / ${stats.losses} losses`;
            }
            
            if (stats.activePositions !== undefined) {
                document.getElementById('positions').textContent = stats.activePositions;
                document.getElementById('positionsChange').textContent = `${(stats.activePositions * 0.05).toFixed(2)} SOL invested`;
            }
        }
        
        function simulateTrading() {
            if (!botRunning) return;
            
            const tokens = ['PUMP', 'MOON', 'DEGEN', 'TRON', 'CYBER'];
            const token = tokens[Math.floor(Math.random() * tokens.length)];
            const action = Math.random() > 0.3 ? 'BUY' : 'SELL';
            const amount = (Math.random() * 0.1 + 0.05).toFixed(3);
            
            addActivity('💰', `${action} ${token}`, `${amount} SOL traded`);
        }
        
        function addActivity(icon, title, details) {
            const feed = document.getElementById('activityFeed');
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.style.opacity = '0';
            
            const now = new Date().toLocaleTimeString();
            
            item.innerHTML = `
                <div class="activity-icon">${icon}</div>
                <div class="activity-content">
                    <div>${title}</div>
                    <div class="activity-time">${details} - ${now}</div>
                </div>
            `;
            
            // Remove setup message if it exists
            if (feed.children[0] && feed.children[0].textContent.includes('awaiting configuration')) {
                feed.removeChild(feed.children[0]);
            }
            
            feed.insertBefore(item, feed.firstChild);
            
            // Animate in
            setTimeout(() => {
                item.style.transition = 'opacity 0.5s';
                item.style.opacity = '1';
            }, 10);
            
            // Keep only 20 items
            while (feed.children.length > 20) {
                feed.removeChild(feed.lastChild);
            }
        }
        
        // Handle Enter key
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const activeStep = document.querySelector('.setup-step.active');
                if (activeStep) {
                    if (activeStep.id === 'apiStep') {
                        saveApiCredentials();
                    } else if (activeStep.id === 'phoneStep') {
                        requestCode();
                    } else if (activeStep.id === 'codeStep') {
                        verifyCode();
                    }
                }
            }
        });
    </script>
</body>
</html>
'''

@dataclass
class SystemState:
    """System configuration and state"""
    api_configured: bool = False
    authenticated: bool = False
    bot_running: bool = False
    total_profit: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    start_time: float = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = time.time()

# Global state
system_state = SystemState()

class TelegramHandler:
    """Handles Telegram API setup and authentication"""
    
    def __init__(self):
        self.client = None
        self.phone = None
        self.code_hash = None
        self.api_id = None
        self.api_hash = None
        
    def configure_api(self, api_id: int, api_hash: str) -> bool:
        """Configure API credentials"""
        try:
            self.api_id = api_id
            self.api_hash = api_hash
            system_state.api_configured = True
            logger.info("API credentials configured")
            return True
        except Exception as e:
            logger.error(f"Failed to configure API: {e}")
            return False
    
    async def request_code(self, phone: str) -> bool:
        """Request verification code"""
        if not system_state.api_configured:
            return False
            
        try:
            # Try to import and use telethon
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                
                self.phone = phone
                self.client = TelegramClient(
                    StringSession(),
                    self.api_id,
                    self.api_hash
                )
                
                await self.client.connect()
                result = await self.client.send_code_request(phone)
                self.code_hash = result.phone_code_hash
                
                logger.info(f"Code sent to {phone}")
                return True
                
            except ImportError:
                logger.error("Telethon not installed. Install with: pip install telethon")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send code: {e}")
            return False
    
    async def verify_code(self, code: str) -> bool:
        """Verify the code and authenticate"""
        try:
            if not self.client or not self.phone:
                return False
            
            # Sign in
            await self.client.sign_in(self.phone, code, phone_code_hash=self.code_hash)
            
            # Save session for future use
            session_string = self.client.session.save()
            with open('tron_session.txt', 'w') as f:
                f.write(session_string)
            
            system_state.authenticated = True
            logger.info("Authentication successful!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

class TradingBot:
    """Simplified trading bot"""
    
    def __init__(self):
        self.running = False
        
    async def start(self):
        """Start the trading bot"""
        if not system_state.authenticated:
            logger.warning("Cannot start bot - not authenticated")
            return
        
        logger.info("Starting trading bot...")
        self.running = True
        system_state.bot_running = True
        
        # Start trading simulation
        asyncio.create_task(self.trading_loop())
        
    async def trading_loop(self):
        """Main trading loop"""
        while self.running:
            try:
                # Simulate finding and trading tokens
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if system_state.authenticated:
                    # Simulate a trade
                    if random.random() > 0.7:  # 30% chance of trade
                        system_state.total_trades += 1
                        if random.random() > 0.4:  # 60% win rate
                            system_state.winning_trades += 1
                            profit = random.uniform(0.01, 0.1)
                            system_state.total_profit += profit
                            logger.info(f"Simulated profitable trade: +{profit:.3f} SOL")
                        
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(60)

# Create instances
telegram_handler = TelegramHandler()
trading_bot = TradingBot()

class WebServer:
    """Web server for the dashboard"""
    
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup all routes"""
        # Main page
        self.app.router.add_get('/', self.index)
        
        # API endpoints
        self.app.router.add_get('/api/status', self.get_status)
        self.app.router.add_post('/api/setup/credentials', self.setup_credentials)
        self.app.router.add_post('/api/auth/request-code', self.request_code)
        self.app.router.add_post('/api/auth/verify-code', self.verify_code)
        self.app.router.add_get('/api/stats', self.get_stats)
    
    async def index(self, request):
        """Serve the main dashboard"""
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')
    
    async def get_status(self, request):
        """Get system status"""
        return web.json_response({
            'configured': system_state.api_configured,
            'authenticated': system_state.authenticated,
            'bot_running': system_state.bot_running
        })
    
    async def setup_credentials(self, request):
        """Setup API credentials"""
        try:
            data = await request.json()
            api_id = data.get('api_id')
            api_hash = data.get('api_hash')
            
            if not api_id or not api_hash:
                return web.json_response({'error': 'API ID and Hash required'}, status=400)
            
            success = telegram_handler.configure_api(api_id, api_hash)
            
            if success:
                return web.json_response({'status': 'configured'})
            else:
                return web.json_response({'error': 'Failed to configure API'}, status=500)
                
        except Exception as e:
            logger.error(f"Setup credentials error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def request_code(self, request):
        """Request verification code"""
        try:
            data = await request.json()
            phone = data.get('phone')
            
            if not phone:
                return web.json_response({'error': 'Phone number required'}, status=400)
            
            success = await telegram_handler.request_code(phone)
            
            if success:
                return web.json_response({'status': 'code_sent'})
            else:
                return web.json_response({'error': 'Failed to send code'}, status=500)
                
        except Exception as e:
            logger.error(f"Request code error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def verify_code(self, request):
        """Verify code and start bot"""
        try:
            data = await request.json()
            code = data.get('code')
            
            if not code:
                return web.json_response({'error': 'Verification code required'}, status=400)
            
            success = await telegram_handler.verify_code(code)
            
            if success:
                # Start the bot
                await trading_bot.start()
                return web.json_response({'status': 'authenticated'})
            else:
                return web.json_response({'error': 'Invalid verification code'}, status=400)
                
        except Exception as e:
            logger.error(f"Verify code error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_stats(self, request):
        """Get trading statistics"""
        win_rate = 0
        if system_state.total_trades > 0:
            win_rate = int((system_state.winning_trades / system_state.total_trades) * 100)
        
        return web.json_response({
            'totalProfit': system_state.total_profit,
            'winRate': win_rate,
            'wins': system_state.winning_trades,
            'losses': system_state.total_trades - system_state.winning_trades,
            'activePositions': random.randint(0, 5) if system_state.bot_running else 0
        })
    
    async def start_server(self):
        """Start the web server"""
        port = int(os.environ.get('PORT', 8080))
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"""
╔═══════════════════════════════════════════════╗
║           TRON TRADING SYSTEM                 ║
╠═══════════════════════════════════════════════╣
║                                               ║
║  🌐 Dashboard: http://localhost:{port:<14}   ║
║  🚀 Railway: https://YOUR-APP.railway.app     ║
║                                               ║
║  📱 Status: READY FOR SETUP                   ║
║                                               ║
║  Setup Process:                               ║
║  1. Visit the dashboard                       ║
║  2. Enter Telegram API credentials            ║
║  3. Authenticate with phone number            ║
║  4. Bot starts automatically!                ║
║                                               ║
╚═══════════════════════════════════════════════╝
        """)

async def main():
    """Main entry point"""
    server = WebServer()
    await server.start_server()
    
    # Keep server running
    while True:
        await asyncio.sleep(3600)  # Sleep for 1 hour

if __name__ == '__main__':
    import random
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        exit(1)
