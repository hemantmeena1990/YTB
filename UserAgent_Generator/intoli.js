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

function compileFingerprint(uaString, category) {
    const isWin = /Windows/i.test(uaString);
    const isMac = /Macintosh/i.test(uaString);
    
    let platform = "Linux x86_64";
    if (category === 'desktop') {
        if (isWin) platform = "Win32";
        else if (isMac) platform = "MacIntel";
    } else {
        platform = /iPhone|iPad|iPod/i.test(uaString) ? "iPhone" : "Linux armv8l";
    }

    const desktopScreens = [[1920, 1080], [2560, 1440], [1440, 900], [1536, 864], [1366, 768]];
    const mobileScreens = [[390, 844], [412, 915], [360, 800], [428, 926], [393, 852]];
    const [sw, sh] = category === 'desktop' 
        ? desktopScreens[Math.floor(Math.random() * desktopScreens.length)]
        : mobileScreens[Math.floor(Math.random() * mobileScreens.length)];

    return {
        appName: "Netscape",
        connection: {
            downlink: parseFloat((Math.random() * (10 - 4) + 4).toFixed(1)),
            effectiveType: "4g",
            rtt: [0, 50, 100][Math.floor(Math.random() * 3)]
        },
        deviceCategory: category,
        platform: platform,
        pluginsLength: category === 'desktop' ? Math.floor(Math.random() * 4) + 1 : 0,
        screenHeight: sh,
        screenWidth: sw,
        userAgent: uaString,
        vendor: /Chrome|Edge/i.test(uaString) ? "Google Inc." : (/Safari/i.test(uaString) && !/Chrome/i.test(uaString) ? "Apple Computer, Inc." : ""),
        viewportHeight: sh - (category === 'desktop' ? 80 : 0),
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
            uniqueStrings.add(ua);

            const isMobile = forceCategory ? (forceCategory === 'mobile') : /Mobi|Android|iPhone|iPad/i.test(ua);
            const targetCategory = isMobile ? 'mobile' : 'desktop';
            const itemObj = { 
                useragent: ua, 
                type: targetCategory, 
                score: getOsTierScore(ua, targetCategory) 
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

        console.log(`Aggregated and isolated ${uniqueStrings.size} total individual unique variants across pools.`);

        // Step 2: Sort descending (Ascending priority tier: 1 first, then 2, then 3)
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
            console.log(`[Success] Written ${dataArray.length} unique tier-sorted profiles straight into ${filename}`);
        };

        saveWithFormatting('intoli_desktop.json', finalDesktopPool);
        saveWithFormatting('intoli_mobile.json', finalMobilePool);

        console.log("\nMulti-source aggregation matrix finished successfully.");

    } catch (error) {
        console.error("Critical Execution Abort Error:", error.message);
    }
}

runPipeline();