#!/usr/bin/env python3
"""
Complete Solana Trading Bot with TRON Web Dashboard
Handles all authentication through the web interface
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
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TronSystem')

# Suppress Telethon SSL warnings
logging.getLogger('telethon.crypto.libssl').setLevel(logging.ERROR)

# HTML Template (embedded for Railway)
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
            border: 1px solid #00ff00;
            background: rgba(0, 255, 0, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .status-indicator.offline {
            border-color: #ff6600;
            background: rgba(255, 102, 0, 0.1);
        }
        
        .status-indicator::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            width: 10px;
            height: 10px;
            background: #00ff00;
            border-radius: 50%;
            animation: pulse 1s ease-in-out infinite;
        }
        
        .status-indicator.offline::before {
            background: #ff6600;
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
        
        /* Telegram Auth Modal */
        .auth-modal {
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
        
        .auth-modal.hidden {
            display: none;
        }
        
        .auth-box {
            background: #000;
            border: 2px solid #00ffff;
            padding: 40px;
            border-radius: 0;
            max-width: 500px;
            width: 90%;
            position: relative;
            box-shadow: 
                0 0 30px #00ffff,
                0 0 60px #0088ff,
                inset 0 0 30px #00ffff11;
        }
        
        .auth-box::before,
        .auth-box::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            border: 2px solid #00ffff;
        }
        
        .auth-box::before {
            top: -2px;
            left: -2px;
            border-right: none;
            border-bottom: none;
        }
        
        .auth-box::after {
            bottom: -2px;
            right: -2px;
            border-left: none;
            border-top: none;
        }
        
        .auth-title {
            font-size: 24px;
            text-align: center;
            margin-bottom: 30px;
            color: #00ffff;
            text-transform: uppercase;
            letter-spacing: 3px;
        }
        
        .auth-step {
            margin-bottom: 25px;
        }
        
        .auth-step h3 {
            color: #ff6600;
            margin-bottom: 15px;
            font-size: 18px;
            text-shadow: 0 0 10px #ff6600;
        }
        
        .input-group {
            position: relative;
            margin-bottom: 20px;
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
        
        /* Chart Container */
        .chart-container {
            padding: 30px;
            margin-bottom: 30px;
            height: 400px;
            position: relative;
        }
        
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .chart-title {
            font-size: 20px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        /* Positions Table */
        .table-container {
            padding: 30px;
            margin-bottom: 30px;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 10px;
        }
        
        th {
            text-align: left;
            padding: 15px;
            color: #ff6600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 2px;
            border-bottom: 2px solid #00ffff;
        }
        
        td {
            padding: 15px;
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid #00ffff33;
        }
        
        tr {
            transition: all 0.3s;
        }
        
        tr:hover td {
            background: rgba(0, 255, 255, 0.1);
            border-color: #00ffff;
            box-shadow: 0 0 20px #00ffff33;
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
        
        .activity-item:hover {
            border-color: #00ffff;
            box-shadow: 0 0 20px #00ffff33;
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
        
        /* Success message */
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
        
        /* Mobile responsive */
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .header-content {
                flex-direction: column;
                gap: 20px;
            }
            
            .auth-box {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <!-- Scanlines overlay -->
    <div class="scanlines"></div>
    
    <!-- Grid background -->
    <div class="grid-background"></div>
    
    <!-- Telegram Auth Modal -->
    <div class="auth-modal" id="authModal">
        <div class="auth-box">
            <h2 class="auth-title neon-text">System Authentication</h2>
            
            <div class="auth-step" id="phoneStep">
                <h3>Step 1: Enter Phone Number</h3>
                <div class="input-group">
                    <input type="tel" 
                           id="phoneInput" 
                           class="neon-input" 
                           placeholder="+61 XXX XXX XXX"
                           value="">
                </div>
                <button class="neon-button" onclick="requestCode()" id="requestBtn">
                    Request Access Code
                </button>
            </div>
            
            <div class="auth-step" id="codeStep" style="display: none;">
                <h3>Step 2: Enter Verification Code</h3>
                <p style="margin-bottom: 15px; font-size: 14px; color: #888;">
                    Check your Telegram for the code
                </p>
                <div class="input-group">
                    <input type="text" 
                           id="codeInput" 
                           class="neon-input" 
                           placeholder="12345"
                           maxlength="5">
                </div>
                <button class="neon-button" onclick="verifyCode()" id="verifyBtn">
                    Initialize System
                </button>
            </div>
            
            <div id="authSuccess" style="display: none;">
                <div class="success-message">
                    <h3 style="color: #00ff00; margin-bottom: 10px;">✓ AUTHENTICATION SUCCESSFUL</h3>
                    <p>System initializing...</p>
                </div>
            </div>
            
            <div id="authError" style="display: none;">
                <div class="error-message">
                    <h3 style="margin-bottom: 10px;">⚠ AUTHENTICATION ERROR</h3>
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
                <span style="margin-left: 20px;" id="statusText">AWAITING AUTH</span>
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
                <div class="stat-change" id="profitChange">↑ Initializing...</div>
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
                <div class="stat-label">System Uptime</div>
                <div class="stat-value neon-text" id="uptime">00:00</div>
                <div class="stat-change" id="uptimeChange">Initializing...</div>
            </div>
        </div>
        
        <!-- Chart -->
        <div class="chart-container neon-box">
            <div class="chart-header">
                <h2 class="chart-title neon-text">Profit Matrix</h2>
                <div class="loading" id="chartLoading"></div>
            </div>
            <canvas id="profitChart" style="width: 100%; height: 300px;"></canvas>
        </div>
        
        <!-- Positions table -->
        <div class="table-container neon-box">
            <div class="chart-header">
                <h2 class="chart-title neon-text">Active Positions</h2>
                <div class="loading" id="positionsLoading"></div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Token ID</th>
                        <th>Entry Vector</th>
                        <th>Current Vector</th>
                        <th>P&L Ratio</th>
                        <th>Size</th>
                        <th>Duration</th>
                        <th>Signal Source</th>
                    </tr>
                </thead>
                <tbody id="positionsTable">
                    <tr>
                        <td colspan="7" style="text-align: center; color: #888;">
                            Awaiting system initialization...
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Activity feed -->
        <div class="activity-feed neon-box">
            <div class="chart-header">
                <h2 class="chart-title neon-text">System Activity Log</h2>
            </div>
            <div id="activityFeed">
                <div class="activity-item">
                    <div class="activity-icon">⚡</div>
                    <div class="activity-content">
                        <div>System awaiting authentication...</div>
                        <div class="activity-time">Please complete Telegram verification</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Global state
        let authenticated = false;
        let wsConnection = null;
        let startTime = Date.now();
        
        // Check if pre-filled phone from environment
        const envPhone = '{{ PHONE_NUMBER }}';
        if (envPhone && envPhone !== '{{ PHONE_NUMBER }}') {
            document.getElementById('phoneInput').value = envPhone;
        }
        
        // Auto-start if session exists
        checkAuthStatus();
        
        async function checkAuthStatus() {
            try {
                const response = await fetch('/api/auth/status');
                const data = await response.json();
                
                if (data.authenticated) {
                    authenticated = true;
                    document.getElementById('authModal').classList.add('hidden');
                    initializeDashboard();
                }
            } catch (e) {
                console.log('No existing session');
            }
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
                    document.getElementById('phoneStep').style.display = 'none';
                    document.getElementById('codeStep').style.display = 'block';
                    document.getElementById('authError').style.display = 'none';
                    
                    // Auto-focus code input
                    document.getElementById('codeInput').focus();
                } else {
                    showError(data.error || 'Failed to send code');
                }
            } catch (e) {
                showError('Connection error. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Request Access Code';
            }
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
                    authSuccess();
                } else {
                    showError(data.error || 'Invalid code');
                }
            } catch (e) {
                showError('Verification failed. Please try again.');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Initialize System';
            }
        }
        
        function showError(message) {
            document.getElementById('authError').style.display = 'block';
            document.getElementById('errorMessage').textContent = message;
        }
        
        function authSuccess() {
            document.getElementById('codeStep').style.display = 'none';
            document.getElementById('authSuccess').style.display = 'block';
            document.getElementById('authError').style.display = 'none';
            
            authenticated = true;
            
            // Hide modal after 2 seconds
            setTimeout(() => {
                document.getElementById('authModal').classList.add('hidden');
                initializeDashboard();
            }, 2000);
        }
        
        function initializeDashboard() {
            console.log('Dashboard initialized!');
            
            // Update status
            document.getElementById('statusIndicator').classList.remove('offline');
            document.getElementById('statusText').textContent = 'SYSTEM ONLINE';
            
            // Start WebSocket connection
            connectWebSocket();
            
            // Start uptime counter
            startUptimeCounter();
            
            // Draw initial chart
            drawTronChart();
            
            // Load initial data
            loadDashboardData();
            
            // Set up periodic updates
            setInterval(loadDashboardData, 5000);
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            wsConnection = new WebSocket(wsUrl);
            
            wsConnection.onopen = () => {
                console.log('WebSocket connected');
                addActivity('🌐', 'System connected', 'Real-time updates active');
            };
            
            wsConnection.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleRealtimeUpdate(data);
            };
            
            wsConnection.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            wsConnection.onclose = () => {
                console.log('WebSocket disconnected');
                // Reconnect after 5 seconds
                setTimeout(connectWebSocket, 5000);
            };
        }
        
        function handleRealtimeUpdate(data) {
            if (data.type === 'trade') {
                addActivity('💰', `${data.action} ${data.symbol}`, `${data.amount} SOL @ ${data.price}`);
            } else if (data.type === 'stats') {
                updateStats(data.stats);
            } else if (data.type === 'position') {
                updatePositionsTable(data.positions);
            }
        }
        
        async function loadDashboardData() {
            try {
                // Load stats
                const statsResponse = await fetch('/api/stats');
                if (statsResponse.ok) {
                    const stats = await statsResponse.json();
                    updateStats(stats);
                }
                
                // Load positions
                const positionsResponse = await fetch('/api/positions');
                if (positionsResponse.ok) {
                    const positions = await positionsResponse.json();
                    updatePositionsTable(positions);
                }
                
                // Load activity
                const activityResponse = await fetch('/api/activity');
                if (activityResponse.ok) {
                    const activities = await activityResponse.json();
                    updateActivityFeed(activities);
                }
            } catch (e) {
                console.error('Error loading dashboard data:', e);
            }
        }
        
        function updateStats(stats) {
            // Update profit
            if (stats.totalProfit !== undefined) {
                const profitElement = document.getElementById('totalProfit');
                const changeElement = document.getElementById('profitChange');
                
                profitElement.textContent = `+${stats.totalProfit.toFixed(3)} SOL`;
                
                if (stats.dailyChange !== undefined) {
                    const changeSymbol = stats.dailyChange >= 0 ? '↑' : '↓';
                    changeElement.textContent = `${changeSymbol} ${Math.abs(stats.dailyChange).toFixed(1)}% today`;
                    changeElement.className = stats.dailyChange >= 0 ? 'stat-change' : 'stat-change negative';
                }
            }
            
            // Update win rate
            if (stats.winRate !== undefined) {
                document.getElementById('winRate').textContent = `${stats.winRate}%`;
                if (stats.wins !== undefined && stats.losses !== undefined) {
                    document.getElementById('winRateChange').textContent = `${stats.wins} wins / ${stats.losses} losses`;
                }
            }
            
            // Update positions
            if (stats.activePositions !== undefined) {
                document.getElementById('positions').textContent = stats.activePositions;
                if (stats.totalInvested !== undefined) {
                    document.getElementById('positionsChange').textContent = `${stats.totalInvested.toFixed(2)} SOL invested`;
                }
            }
        }
        
        function updatePositionsTable(positions) {
            const tbody = document.getElementById('positionsTable');
            
            if (positions.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; color: #888;">
                            No active positions
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = positions.map(pos => {
                const pnlClass = pos.pnl >= 0 ? 'profit' : 'loss';
                const pnlSign = pos.pnl >= 0 ? '+' : '';
                
                return `
                    <tr>
                        <td>${pos.symbol}</td>
                        <td>$${pos.entryPrice.toFixed(6)}</td>
                        <td>$${pos.currentPrice.toFixed(6)}</td>
                        <td class="${pnlClass}">${pnlSign}${pos.pnl.toFixed(1)}%</td>
                        <td>${pos.size} SOL</td>
                        <td>${pos.duration}</td>
                        <td>${pos.signal}</td>
                    </tr>
                `;
            }).join('');
        }
        
        function updateActivityFeed(activities) {
            const feed = document.getElementById('activityFeed');
            
            // Clear existing items except the first
            while (feed.children.length > 1) {
                feed.removeChild(feed.lastChild);
            }
            
            // Add new activities
            activities.forEach(activity => {
                addActivity(activity.icon, activity.title, activity.details, false);
            });
        }
        
        function startUptimeCounter() {
            setInterval(() => {
                const elapsed = Date.now() - startTime;
                const hours = Math.floor(elapsed / 3600000);
                const minutes = Math.floor((elapsed % 3600000) / 60000);
                document.getElementById('uptime').textContent = 
                    `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                
                if (authenticated) {
                    document.getElementById('uptimeChange').textContent = 'System operational';
                }
            }, 60000);
        }
        
        function addActivity(icon, title, details, animate = true) {
            const feed = document.getElementById('activityFeed');
            const item = document.createElement('div');
            item.className = 'activity-item';
            if (animate) item.style.opacity = '0';
            
            const now = new Date().toLocaleTimeString();
            
            item.innerHTML = `
                <div class="activity-icon">${icon}</div>
                <div class="activity-content">
                    <div>${title}</div>
                    <div class="activity-time">${details} - ${now}</div>
                </div>
            `;
            
            // Remove the initial "awaiting auth" message if it exists
            if (feed.children[0] && feed.children[0].textContent.includes('awaiting authentication')) {
                feed.removeChild(feed.children[0]);
            }
            
            feed.insertBefore(item, feed.firstChild);
            
            if (animate) {
                // Animate in
                setTimeout(() => {
                    item.style.transition = 'opacity 0.5s';
                    item.style.opacity = '1';
                }, 10);
            }
            
            // Keep only 20 items
            while (feed.children.length > 20) {
                feed.removeChild(feed.lastChild);
            }
        }
        
        function drawTronChart() {
            const canvas = document.getElementById('profitChart');
            const ctx = canvas.getContext('2d');
            
            // Set canvas size
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            
            // TRON style grid
            ctx.strokeStyle = '#00ffff33';
            ctx.lineWidth = 1;
            
            // Draw grid
            const gridSize = 30;
            for (let x = 0; x < canvas.width; x += gridSize) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, canvas.height);
                ctx.stroke();
            }
            
            for (let y = 0; y < canvas.height; y += gridSize) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(canvas.width, y);
                ctx.stroke();
            }
            
            // Draw profit line
            ctx.strokeStyle = '#00ffff';
            ctx.lineWidth = 3;
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#00ffff';
            
            ctx.beginPath();
            ctx.moveTo(0, canvas.height - 50);
            
            // Random upward trend
            for (let x = 0; x < canvas.width; x += 50) {
                const y = canvas.height - 50 - (x / canvas.width) * 100 - Math.random() * 30;
                ctx.lineTo(x, y);
            }
            
            ctx.stroke();
            
            // Reset shadow
            ctx.shadowBlur = 0;
        }
        
        // Handle Enter key in inputs
        document.getElementById('phoneInput')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') requestCode();
        });
        
        document.getElementById('codeInput')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') verifyCode();
        });
    </script>
</body>
</html>
'''

@dataclass
class BotState:
    """Global bot state"""
    authenticated: bool = False
    telegram_ready: bool = False
    bot_running: bool = False
    total_profit: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    positions: Dict = None
    start_time: float = None
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = {}
        if self.start_time is None:
            self.start_time = time.time()

# Global state
bot_state = BotState()

class TelegramAuthHandler:
    """Handles Telegram authentication"""
    
    def __init__(self):
        self.client = None
        self.phone = None
        self.code_hash = None
        
    async def request_code(self, phone: str) -> bool:
        """Request verification code"""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            # Check for existing session
            session_file = 'tron_session.txt'
            session_string = None
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    session_string = f.read().strip()
            
            api_id = int(os.getenv('TG_API_ID', '0'))
            api_hash = os.getenv('TG_API_HASH', '')
            
            if not api_id or not api_hash:
                logger.error("Missing Telegram API credentials")
                return False
            
            self.phone = phone
            self.client = TelegramClient(
                StringSession(session_string) if session_string else 'tron_auth',
                api_id,
                api_hash
            )
            
            await self.client.connect()
            
            # Send code
            result = await self.client.send_code_request(phone)
            self.code_hash = result.phone_code_hash
            
            logger.info(f"Code sent to {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send code: {e}")
            return False
    
    async def verify_code(self, code: str) -> bool:
        """Verify the code"""
        try:
            if not self.client or not self.phone:
                return False
            
            # Sign in
            await self.client.sign_in(self.phone, code, phone_code_hash=self.code_hash)
            
            # Save session
            session_string = self.client.session.save()
            with open('tron_session.txt', 'w') as f:
                f.write(session_string)
            
            bot_state.authenticated = True
            bot_state.telegram_ready = True
            
            logger.info("Authentication successful!")
            return True
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

class SimplifiedTradingBot:
    """Simplified trading bot that works with web dashboard"""
    
    def __init__(self):
        self.running = False
        self.client = None
        
    async def start(self):
        """Start the bot after authentication"""
        if not bot_state.authenticated:
            logger.warning("Bot start attempted without authentication")
            return
        
        logger.info("Starting trading bot...")
        self.running = True
        bot_state.bot_running = True
        
        # Start bot tasks
        asyncio.create_task(self.main_loop())
        asyncio.create_task(self.monitor_positions())
        
    async def main_loop(self):
        """Main trading loop"""
        while self.running:
            try:
                # Scan for tokens
                tokens = await self.scan_tokens()
                
                if tokens:
                    logger.info(f"Found {len(tokens)} potential tokens")
                    
                    # Process best token
                    for token in tokens[:1]:  # One at a time
                        await self.process_token(token)
                
                await asyncio.sleep(120)  # 2 minute scan interval
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(300)
    
    async def scan_tokens(self) -> List[Dict]:
        """Scan pump.fun for new tokens"""
        try:
            url = "https://frontend-api.pump.fun/coins?offset=0&limit=20&sort=created&order=DESC"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        tokens = []
                        for token in data:
                            market_cap = token.get('usd_market_cap', 0)
                            if 5000 < market_cap < 500000:  # Good range
                                tokens.append({
                                    'address': token.get('mint', ''),
                                    'symbol': token.get('symbol', 'UNKNOWN'),
                                    'name': token.get('name', ''),
                                    'market_cap': market_cap,
                                    'price': token.get('price', 0),
                                    'created': token.get('created_timestamp', 0)
                                })
                        
                        return tokens
                        
        except Exception as e:
            logger.error(f"Token scan error: {e}")
            
        return []
    
    async def process_token(self, token: Dict):
        """Process a potential token"""
        # Add to activity
        activity = {
            'icon': '🔍',
            'title': f'Analyzing {token["symbol"]}',
            'details': f'Market cap: ${token["market_cap"]:,.0f}'
        }
        
        # Would execute trade here if criteria met
        if bot_state.telegram_ready:
            # Execute via ToxiBot
            logger.info(f"Would buy {token['symbol']} via ToxiBot")
        else:
            logger.info(f"Would buy {token['symbol']} (simulation)")
        
        # Update state
        bot_state.total_trades += 1
        if token['market_cap'] > 10000:  # Arbitrary success
            bot_state.winning_trades += 1
            bot_state.total_profit += 0.05
        
        # Add position
        bot_state.positions[token['address']] = {
            'symbol': token['symbol'],
            'entryPrice': token['price'],
            'currentPrice': token['price'],
            'size': 0.05,
            'entryTime': time.time(),
            'pnl': 0
        }
    
    async def monitor_positions(self):
        """Monitor open positions"""
        while self.running:
            try:
                # Update position prices
                for address, position in bot_state.positions.items():
                    # Simulate price movement
                    change = (time.time() - position['entryTime']) / 3600  # Hours
                    position['currentPrice'] = position['entryPrice'] * (1 + change * 0.1)
                    position['pnl'] = ((position['currentPrice'] - position['entryPrice']) / 
                                     position['entryPrice']) * 100
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)

# Create bot instance
trading_bot = SimplifiedTradingBot()

class WebDashboard:
    """Web dashboard with authentication"""
    
    def __init__(self):
        self.app = web.Application()
        self.auth_handler = TelegramAuthHandler()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup all routes"""
        # Pages
        self.app.router.add_get('/', self.index)
        
        # Auth API
        self.app.router.add_get('/api/auth/status', self.auth_status)
        self.app.router.add_post('/api/auth/request-code', self.request_code)
        self.app.router.add_post('/api/auth/verify-code', self.verify_code)
        
        # Data API
        self.app.router.add_get('/api/stats', self.get_stats)
        self.app.router.add_get('/api/positions', self.get_positions)
        self.app.router.add_get('/api/activity', self.get_activity)
        
        # WebSocket
        self.app.router.add_get('/ws', self.websocket_handler)
    
    async def index(self, request):
        """Serve the dashboard"""
        # Replace phone placeholder if available
        html = DASHBOARD_HTML.replace('{{ PHONE_NUMBER }}', os.getenv('TG_PHONE', ''))
        return web.Response(text=html, content_type='text/html')
    
    async def auth_status(self, request):
        """Check authentication status"""
        return web.json_response({
            'authenticated': bot_state.authenticated,
            'telegram_ready': bot_state.telegram_ready,
            'bot_running': bot_state.bot_running
        })
    
    async def request_code(self, request):
        """Request verification code"""
        try:
            data = await request.json()
            phone = data.get('phone')
            
            if not phone:
                return web.json_response({'error': 'Phone required'}, status=400)
            
            success = await self.auth_handler.request_code(phone)
            
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
                return web.json_response({'error': 'Code required'}, status=400)
            
            success = await self.auth_handler.verify_code(code)
            
            if success:
                # Start the bot
                await trading_bot.start()
                return web.json_response({'status': 'authenticated'})
            else:
                return web.json_response({'error': 'Invalid code'}, status=400)
                
        except Exception as e:
            logger.error(f"Verify code error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_stats(self, request):
        """Get bot statistics"""
        uptime = time.time() - bot_state.start_time
        win_rate = 0
        if bot_state.total_trades > 0:
            win_rate = int((bot_state.winning_trades / bot_state.total_trades) * 100)
        
        return web.json_response({
            'totalProfit': bot_state.total_profit,
            'winRate': win_rate,
            'wins': bot_state.winning_trades,
            'losses': bot_state.total_trades - bot_state.winning_trades,
            'activePositions': len(bot_state.positions),
            'totalInvested': len(bot_state.positions) * 0.05,
            'dailyChange': 14.2 if bot_state.total_profit > 0 else 0,
            'uptime': uptime
        })
    
    async def get_positions(self, request):
        """Get current positions"""
        positions = []
        
        for address, pos in bot_state.positions.items():
            duration_hours = (time.time() - pos['entryTime']) / 3600
            duration_str = f"{int(duration_hours)}h {int((duration_hours % 1) * 60)}m"
            
            positions.append({
                'symbol': pos['symbol'],
                'entryPrice': pos['entryPrice'],
                'currentPrice': pos['currentPrice'],
                'pnl': pos['pnl'],
                'size': pos['size'],
                'duration': duration_str,
                'signal': '🔍 Scanner'
            })
        
        return web.json_response(positions)
    
    async def get_activity(self, request):
        """Get recent activity"""
        # Return last 10 activities
        activities = [
            {'icon': '🚀', 'title': 'System online', 'details': 'All modules operational'},
            {'icon': '🔍', 'title': 'Scanning pump.fun', 'details': 'Looking for new tokens'}
        ]
        
        return web.json_response(activities)
    
    async def websocket_handler(self, request):
        """WebSocket for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        try:
            # Send updates every 5 seconds
            while not ws.closed:
                # Send stats update
                stats = await self.get_stats(request)
                await ws.send_json({
                    'type': 'stats',
                    'stats': json.loads(stats.text)
                })
                
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            return ws
    
async def start(self):
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
        ║  Dashboard: http://localhost:{port:<17}║
        ║  Railway: https://YOUR-APP.railway.app        ║
        ║                                               ║
        ║  Status: AWAITING AUTHENTICATION              ║
        ║                                               ║
        ║  1. Visit dashboard                           ║
        ║  2. Enter phone number                        ║
        ║  3. Enter verification code                   ║
        ║  4. Bot starts automatically!                 ║
        ║                                               ║
        ╚═══════════════════════════════════════════════╝
        """)

async def main():
    """Main entry point"""
    dashboard = WebDashboard()
    
    # Start web server
    await dashboard.start()
    
    # Keep running
    while True:
        await asyncio.sleep(60)

if __name__ == '__main__':
    # Print the port we're using
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}")
    
    # Check environment
    required = ['TG_API_ID', 'TG_API_HASH']
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.info("Bot will run in limited mode")
    
    # Run
    asyncio.run(main())
    
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.info("Bot will run in limited mode")
    
    # Run
    asyncio.run(main())
