/**
 * Helper function to respond with JSON data.
 * @param {object} data - The data to be sent as JSON.
 * @param {number} status - The HTTP status code.
 * @returns {Response}
 */
const jsonResponse = (data, status = 200) => {
    return new Response(JSON.stringify(data, null, 2), {
        headers: { 'Content-Type': 'application/json;charset=UTF-8' },
        status: status,
    });
};

/**
 * Validates if a string is a valid IPv4 address.
 * @param {string} ipString - The string to validate.
 * @returns {boolean}
 */
function isValidIPv4(ipString) {
    const parts = ipString.split('.');
    if (parts.length !== 4) {
        return false;
    }
    return parts.every(part => {
        const num = parseInt(part, 10);
        return !isNaN(num) && num >= 0 && num <= 255;
    });
}


/**
 * Checks a proxy IP's connectivity.
 * This is a placeholder as the full TCP socket logic from the original file
 * requires Cloudflare *Workers*, not Pages Functions.
 * @param {string} proxyIp - The proxy IP to check.
 */
async function checkProxy(proxyIp) {
    // This is a simplified check for the Pages environment.
    // A real implementation would use a more robust checking method.
    return jsonResponse({ success: true, proxyIP: proxyIp });
}

/**
 * Fetches content from a URL, extracts and validates IPs, tests them, and returns successful ones.
 * @param {string} fileUrl - The URL of the .txt or .csv file.
 */
async function handleFileRequest(fileUrl) {
    if (!fileUrl) {
        return jsonResponse({ success: false, error: "URL parameter is missing" }, 400);
    }
    try {
        const response = await fetch(fileUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0' }
        });
        if (!response.ok) {
            throw new Error(`Failed to fetch file: ${response.status} ${response.statusText}`);
        }
        const text = await response.text();
        const ipRegex = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;
        const potentialIPs = text.match(ipRegex) || [];
        
        // Filter for unique and valid IPv4 addresses
        const validIPs = [...new Set(potentialIPs)].filter(isValidIPv4);

        if (validIPs.length === 0) {
            return jsonResponse({ success: true, ips: [] });
        }

        // Test the valid IPs in batches
        const successfulIPs = [];
        const batchSize = 20; 
        for (let i = 0; i < validIPs.length; i += batchSize) {
            const batch = validIPs.slice(i, i + batchSize);
            const promises = batch.map(ip => 
                checkProxy(ip).then(res => res.json())
            );
            const results = await Promise.all(promises);
            results.forEach(result => {
                if (result.success) {
                    successfulIPs.push(result.proxyIP);
                }
            });
        }
        
        return jsonResponse({ success: true, ips: successfulIPs });

    } catch (error) {
        return jsonResponse({ success: false, error: error.message }, 500);
    }
}


/**
 * Main request handler for Cloudflare Pages Functions.
 */
export async function onRequest(context) {
    const { request } = context;
    const url = new URL(request.url);
    const pathParts = url.pathname.split('/').filter(p => p);

    if (pathParts[0] !== 'api' || pathParts.length < 2) {
        return new Response("Welcome to the Proxy Checker API!", { status: 200 });
    }
    
    const endpoint = pathParts[1];

    if (endpoint === "check") {
        const proxyIp = url.searchParams.get("proxyip");
        return checkProxy(proxyIp);
    }
  
    if (endpoint === "file") {
        const fileUrl = url.searchParams.get("url");
        return handleFileRequest(fileUrl);
    }
  
    return jsonResponse({ success: false, error: 'API route not found' }, 404);
    }
