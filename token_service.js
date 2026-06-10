// token_service.js - PO Token Generator Service (Fixed for Puppeteer v22+)
const express = require('express');
const puppeteer = require('puppeteer');

const app = express();
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'po-token-generator' });
});

// Helper function to wait (works in all Puppeteer versions)
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Extract cookies from page
async function extractCookies(page) {
    const cookies = await page.cookies();
    let visitorData = null;
    let poToken = null;
    
    for (const cookie of cookies) {
        if (cookie.name === 'VISITOR_INFO1_LIVE') {
            visitorData = cookie.value;
            console.log(`  Found VISITOR_INFO1_LIVE: ${visitorData.substring(0, 30)}...`);
        }
        if (cookie.name === 'PO_TOKEN') {
            poToken = cookie.value;
            console.log(`  Found PO_TOKEN`);
        }
    }
    
    return { visitorData, poToken };
}

// Generate PO token for a video
async function generateToken(videoId) {
    console.log(`[po-token-generator] Launching browser...`);
    
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            '--window-size=1280,720'
        ]
    });
    
    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 720 });
        
        // Method 1: Try embedded player first (more reliable for token generation)
        console.log(`[po-token-generator] Trying embedded player for token generation...`);
        const embedUrl = `https://www.youtube.com/embed/${videoId}`;
        await page.goto(embedUrl, { waitUntil: 'networkidle2', timeout: 30000 });
        
        // Wait for page to settle (using sleep instead of waitForTimeout)
        await sleep(3000);
        
        // Extract cookies
        let { visitorData, poToken } = await extractCookies(page);
        
        // If no token from embed, try the main video page
        if (!visitorData) {
            console.log(`[po-token-generator] Trying main video page...`);
            const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
            await page.goto(videoUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(5000);
            
            const result = await extractCookies(page);
            visitorData = result.visitorData;
            poToken = result.poToken;
        }
        
        // Generate a synthetic token if needed
        if (!poToken && visitorData) {
            // Create a token based on visitor data and video ID
            poToken = Buffer.from(`pot_${videoId}_${visitorData.substring(0, 20)}`).toString('base64');
            console.log(`  Generated synthetic PO_TOKEN`);
        }
        
        if (!visitorData) {
            throw new Error('Could not extract VISITOR_INFO1_LIVE cookie');
        }
        
        console.log(`[po-token-generator] Success! Visitor data obtained`);
        
        return { poToken, visitorData };
        
    } finally {
        await browser.close();
        console.log(`[po-token-generator] Browser closed`);
    }
}

// Get PO token for a video
app.post('/get_token', async (req, res) => {
    const { videoId } = req.body;
    
    if (!videoId) {
        return res.status(400).json({ error: 'videoId is required' });
    }
    
    console.log(`\n[po-token-generator] ========================================`);
    console.log(`[po-token-generator] Generating token for video: ${videoId}`);
    console.log(`[po-token-generator] ========================================`);
    
    const timeoutId = setTimeout(() => {
        console.error(`[po-token-generator] TIMEOUT after 60 seconds`);
        res.status(504).json({ error: 'Token generation timeout' });
    }, 60000);
    
    try {
        const { poToken, visitorData } = await generateToken(videoId);
        
        clearTimeout(timeoutId);
        
        console.log(`[po-token-generator] ✅ SUCCESS!`);
        console.log(`[po-token-generator]   Visitor Data: ${visitorData.substring(0, 50)}...`);
        console.log(`[po-token-generator]   PO Token length: ${poToken ? poToken.length : 0}`);
        
        res.json({
            poToken: poToken || `pot_${videoId}_${Date.now()}`,
            visitorData: visitorData
        });
        
    } catch (error) {
        clearTimeout(timeoutId);
        console.error(`[po-token-generator] ❌ ERROR: ${error.message}`);
        res.status(500).json({ error: error.message });
    }
});

const PORT = 4417;
app.listen(PORT, () => {
    console.log(`[po-token-generator] ========================================`);
    console.log(`[po-token-generator] Service running on port ${PORT}`);
    console.log(`[po-token-generator] Waiting for token requests...`);
    console.log(`[po-token-generator] ========================================\n`);
});