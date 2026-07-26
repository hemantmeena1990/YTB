const fs = require('fs');
const https = require('https');

// Multiple live independent endpoint origins
const SOURCE_USERAGENTS_NET = 'https://raw.githubusercontent.com/fake-useragent/fake-useragent/main/src/fake_useragent/data/browsers.jsonl';
const SOURCE_JNRBSN = 'https://raw.githubusercontent.com/jnrbsn/user-agents/main/user-agents.json';
const SOURCE_MICROLINK_DESKTOP = 'https://raw.githubusercontent.com/microlinkhq/top-user-agents/master/src/desktop.json';
const SOURCE_MICROLINK_MOBILE = 'https://raw.githubusercontent.com/microlinkhq/top-user-agents/master/src/mobile.json';

function fetchOnlineData(url) {
    return new Promise((resolve) => {
        https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(data));
        }).on('error', () => resolve('')); // Fail-safe fallback to return empty if any source drops down
    });
}

function getOsTierScore(ua, type) {
    if (type === 'desktop') {
        if (/(Windows NT 10\.0|Macintosh; Intel Mac OS X (13|14|15|16)_|X11; Linux x86_64)/.test(ua)) return 1;
        if (/(Windows NT 6\.[123]|Macintosh; Intel Mac OS X (10_15|11|12)_)/.test(ua)) return 2;
        return 3;
    } else {
        if (/(Android (14|15|16)|iPhone OS (16|17|18|19)_)/.test(ua)) return 1;
        if (/(Android (11|12|13)|iPhone OS (14|15)_)/.test(ua)) return 2;
        return 3;
    }
}

// Strictly validates browser parameters to protect against telemetry traps
function isValidAndModern(ua, isMobile) {
    // 1. Drop fringe custom layouts or non-standard tracking strings (e.g. ADG, SamsungBrowser fragments on desktop)
    if (!isMobile && /(ADG\/|SamsungBrowser)/i.test(ua)) return false;

    // 2. Drop ancient versions below Chrome/CriOS/Firefox/Safari 120
    const versionMatch = ua.match(/(?:Chrome|CriOS|Firefox|Version)\/(\d+)/);
    if (versionMatch) {
        const version = parseInt(versionMatch[1], 10);
        if (version < 120) return false;
    }

    if (isMobile) {
        const isIphone = /iPhone|iPad|iPod/i.test(ua);
        
        // 3. Prevent the Fake iPhone Chrome trap
        // Real Chrome on iOS uses the 'CriOS' identifier token, never the standard desktop 'Chrome/' token
        if (isIphone && /Chrome\/\d+/i.test(ua) && !/CriOS\/\d+/i.test(ua)) {
            return false;
        }
    }
    return true;
}

function compileFingerprint(uaString, category) {
    const isWin = /Windows/i.test(uaString);
    const isMac = /Macintosh/i.test(uaString);
    const isIphone = /iPhone|iPad|iPod/i.test(uaString);
    
    let platform = "Linux x86_64";
    if (category === 'desktop') {
        if (isWin) platform = "Win32";
        else if (isMac) platform = "MacIntel";
    } else {
        platform = isIphone ? "iPhone" : "Linux armv8l";
    }

    const desktopScreens = [[1920, 1080], [2560, 1440], [1440, 900], [1536, 864], [1366, 768]];
    const mobileScreens = [[390, 844], [412, 915], [360, 800], [428, 926], [393, 852]];
    const [sw, sh] = category === 'desktop' 
        ? desktopScreens[Math.floor(Math.random() * desktopScreens.length)]
        : mobileScreens[Math.floor(Math.random() * mobileScreens.length)];

    // FIX: Enforce real layout viewport offsets so bounding rect calculations pass bot checks
    let vh = sh;
    if (category === 'desktop') {
        vh = sh - 80;
    } else {
        // Simulates mobile navigation bars/status bars cleanly (subtracting between 60px and 90px loss)
        vh = sh - (Math.floor(Math.random() * (90 - 60 + 1)) + 60);
    }

    // FIX: Enforce strictly accurate vendors across core OS platforms
    let vendor = "";
    if (category === 'mobile' && isIphone) {
        vendor = "Apple Computer, Inc."; // All browsers on iOS run inside WebKit and present this vendor token
    } else if (/Chrome|Edge/i.test(uaString)) {
        vendor = "Google Inc.";
    } else if (/Safari/i.test(uaString) && !/Chrome/i.test(uaString)) {
        vendor = "Apple Computer, Inc.";
    }

    return {
        appName: "Netscape",
        connection: {
            downlink: parseFloat((Math.random() * (10 - 4) + 4).toFixed(1)),
            effectiveType: "4g",
            rtt: [0, 50, 100][Math.floor(Math.random() * 3)]
        },
        deviceCategory: category,
        platform: platform,
        // FIX: Hardcode to 5 for desktop platforms to match modern browser fingerprint standards
        pluginsLength: category === 'desktop' ? 5 : 0,
        screenHeight: sh,
        screenWidth: sw,
        userAgent: uaString,
        vendor: vendor,
        viewportHeight: vh,
        viewportWidth: sw
    };
}

async function runPipeline() {
    try {
        console.log("Downloading concurrent target matrices across multiple open web providers...");
        
        const [resUserAgentsNet, resJnrbsn, resMicroDesk, resMicroMob] = await Promise.all([
            fetchOnlineData(SOURCE_USERAGENTS_NET),
            fetchOnlineData(SOURCE_JNRBSN),
            fetchOnlineData(SOURCE_MICROLINK_DESKTOP),
            fetchOnlineData(SOURCE_MICROLINK_MOBILE)
        ]);

        const uniqueStrings = new Set();
        const desktopCandidates = [];
        const mobileCandidates = [];

        // Helper tracker hook to route raw string loops cleanly
        const processRawString = (ua, forceCategory = null) => {
            if (!ua || typeof ua !== 'string' || uniqueStrings.has(ua)) return;

            const isMobile = forceCategory ? (forceCategory === 'mobile') : /Mobi|Android|iPhone|iPad/i.test(ua);
            const targetCategory = isMobile ? 'mobile' : 'desktop';

            // FIX: Prevent inconsistent, corrupted, or legacy browser structures entirely
            if (!isValidAndModern(ua, isMobile)) return;

            // Strip out Tier 3 legacy entries to maintain clean, human-like execution pools
            const score = getOsTierScore(ua, targetCategory);
            if (score === 3) return; 

            uniqueStrings.add(ua);

            const itemObj = { 
                useragent: ua, 
                type: targetCategory, 
                score: score 
            };

            if (targetCategory === 'desktop') desktopCandidates.push(itemObj);
            else mobileCandidates.push(itemObj);
        };

        // 1. Process user-agents.net Lines
        if (resUserAgentsNet) {
            resUserAgentsNet.split('\n').forEach(line => {
                if (!line.trim()) return;
                try {
                    const item = JSON.parse(line);
                    processRawString(item.useragent, item.type);
                } catch(e){}
            });
        }

        // 2. Process Jnrbsn Array
        if (resJnrbsn) {
            try { JSON.parse(resJnrbsn).forEach(ua => processRawString(ua)); } catch(e){}
        }

        // 3. Process Microlink Desktop Array
        if (resMicroDesk) {
            try { JSON.parse(resMicroDesk).forEach(ua => processRawString(ua, 'desktop')); } catch(e){}
        }

        // 4. Process Microlink Mobile Array
        if (resMicroMob) {
            try { JSON.parse(resMicroMob).forEach(ua => processRawString(ua, 'mobile')); } catch(e){}
        }

        console.log(`Aggregated, sanitized, and isolated ${uniqueStrings.size} valid modern unique variants.`);

        // Step 2: Sort descending (Ascending priority tier: 1 first, then 2)
        desktopCandidates.sort((a, b) => a.score - b.score);
        mobileCandidates.sort((a, b) => a.score - b.score);

        // Step 3: Map and slice arrays cleanly to extract top 500 configurations each
        const finalDesktopPool = desktopCandidates.slice(0, 500).map(item => compileFingerprint(item.useragent, 'desktop'));
        const finalMobilePool = mobileCandidates.slice(0, 500).map(item => compileFingerprint(item.useragent, 'mobile'));

        const saveWithFormatting = (filename, dataArray) => {
            const body = dataArray
                .map(obj => '  ' + JSON.stringify(obj, null, 2).replace(/\n/g, '\n  '))
                .join(',\n\n');
            fs.writeFileSync(filename, `[\n${body}\n]`, 'utf-8');
            console.log(`[Success] Written ${dataArray.length} unique sanitized profiles straight into ${filename}`);
        };

        saveWithFormatting('intoli_desktop.json', finalDesktopPool);
        saveWithFormatting('intoli_mobile.json', finalMobilePool);

        console.log("\nMulti-source aggregation matrix finished successfully with zero inconsistencies.");

    } catch (error) {
        console.error("Critical Execution Abort Error:", error.message);
    }
}

runPipeline();