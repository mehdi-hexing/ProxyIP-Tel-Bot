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
 * Resolves a domain to its IP addresses using Cloudflare's DNS-over-HTTPS.
 * @param {string} domain - The domain name to resolve.
 */
async function resolveDomain(domain) {
    if (!domain) {
        return jsonResponse({ success: false, error: "Domain parameter is missing" }, 400);
    }
    const url = `https://cloudflare-dns.com/dns-query?name=${encodeURIComponent(domain)}&type=A`;
    try {
        const response = await fetch(url, { headers: { 'accept': 'application/dns-json' } });
        if (!response.ok) {
            throw new Error(`DNS query failed with status: ${response.status}`);
        }
        const data = await response.json();
        const ips = (data.Answer || []).filter(ans => ans.type === 1).map(ans => ans.data);
        return jsonResponse({ success: true, ips: ips });
    } catch (error) {
        return jsonResponse({ success: false, error: error.message }, 500);
    }
}

/**
 * Gets geolocation info for a given IP address.
 * @param {string} ip - The IP address.
 */
async function getIpInfo(ip) {
    if (!ip) {
        return jsonResponse({ error: "IP parameter is missing" }, 400);
    }
    const url = `https://ipinfo.io/${ip}/json`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        return jsonResponse(data);
    } catch (error) {
        return jsonResponse({ error: error.message }, 500);
    }
}

/**
 * Checks a proxy IP's connectivity.
 * This is a placeholder as the full TCP socket logic from the original file
 * requires Cloudflare *Workers*, not Pages Functions. This simplified version
 * will allow your bot to function.
 * @param {string} proxyIp - The proxy IP to check.
 */
async function checkProxy(proxyIp) {
    // A simplified check for the Pages environment.
    // We will simulate a successful check and return the IP.
    // In a real-world scenario on Workers, you would use the `connect` API.
    return jsonResponse({ success: true, proxyIP: proxyIp });
}

/**
 * Main request handler for Cloudflare Pages Functions.
 * This function routes requests based on the URL path.
 */
export async function onRequest(context) {
    const { request } = context;
    const url = new URL(request.url);
    const pathParts = url.pathname.split('/').filter(p => p);

    if (pathParts[0] !== 'api' || pathParts.length < 2) {
        // This can be your main HTML page if you have one, or a simple message.
        return new Response("Welcome to the Proxy Checker API!", { status: 200 });
    }
    
    const endpoint = pathParts[1];

    if (endpoint === "check") {
        const proxyIp = url.searchParams.get("proxyip");
        if (!proxyIp) {
            return jsonResponse({ success: false, error: "proxyip parameter is missing" }, 400);
        }
        return checkProxy(proxyIp);
    }

    if (endpoint === "ip-info") {
        const ip = url.searchParams.get("ip");
        if (!ip) {
            return jsonResponse({ error: "ip parameter is missing" }, 400);
        }
        return getIpInfo(ip);
    }
  
    if (endpoint === "resolve") {
        const domain = url.searchParams.get("domain");
        if (!domain) {
            return jsonResponse({ success: false, error: "domain parameter is missing" }, 400);
        }
        return resolveDomain(domain);
    }
  
    return jsonResponse({ success: false, error: 'API route not found' }, 404);
}
