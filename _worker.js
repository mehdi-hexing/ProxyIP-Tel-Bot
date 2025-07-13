import { connect } from 'cloudflare:sockets';

// --- Server-Side Helper Functions ---

async function doubleHash(text) {
  const encoder = new TextEncoder();
  const firstHashBuffer = await crypto.subtle.digest('MD5', encoder.encode(text));
  const firstHashArray = Array.from(new Uint8Array(firstHashBuffer));
  const firstHex = firstHashArray.map(byte => byte.toString(16).padStart(2, '0')).join('');
  const secondHashBuffer = await crypto.subtle.digest('MD5', encoder.encode(firstHex.slice(7, 27)));
  const secondHashArray = Array.from(new Uint8Array(secondHashBuffer));
  const secondHex = secondHashArray.map(byte => byte.toString(16).padStart(2, '0')).join('');
  return secondHex.toLowerCase();
}

function simpleHash(str) {
    let hash = 0;
    if (str.length === 0) return hash.toString();
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = (hash << 5) - hash + char;
        hash |= 0;
    }
    return hash.toString();
}

async function resolveDomain(domain) {
  domain = domain.includes(':') ? domain.split(':')[0] : domain;
  try {
    const [ipv4Response, ipv6Response] = await Promise.all([
      fetch(`https://1.1.1.1/dns-query?name=${domain}&type=A`, { headers: { 'Accept': 'application/dns-json' } }),
      fetch(`https://1.1.1.1/dns-query?name=${domain}&type=AAAA`, { headers: { 'Accept': 'application/dns-json' } })
    ]);
    if (!ipv4Response.ok && !ipv6Response.ok) throw new Error('DNS query failed for both IPv4 and IPv6.');
    
    const ipv4Data = ipv4Response.ok ? await ipv4Response.json() : {};
    const ipv6Data = ipv6Response.ok ? await ipv6Response.json() : {};

    const ips = [];
    if (ipv4Data.Answer) ips.push(...ipv4Data.Answer.filter(r => r.type === 1).map(r => r.data));
    if (ipv6Data.Answer) ips.push(...ipv6Data.Answer.filter(r => r.type === 28).map(r => `[${r.data}]`));
    if (ips.length === 0) throw new Error('No A or AAAA records found for this domain.');
    return ips;
  } catch (error) {
    throw new Error(`DNS resolution failed: ${error.message}`);
  }
}

async function checkProxyIP(proxyIP) {
  let portRemote = 443;
  let hostToCheck = proxyIP;

  if (proxyIP.includes('.tp')) {
    const portMatch = proxyIP.match(/\.tp(\d+)\./);
    if (portMatch) portRemote = parseInt(portMatch[1], 10);
    hostToCheck = proxyIP.split('.tp')[0];
  } else if (proxyIP.includes('[') && proxyIP.includes(']:')) {
    portRemote = parseInt(proxyIP.split(']:')[1], 10);
    hostToCheck = proxyIP.split(']:')[0] + ']';
  } else if (proxyIP.includes(':') && !proxyIP.startsWith('[')) {
    const parts = proxyIP.split(':');
    if (parts.length === 2 && parts[0].includes('.')) {
      hostToCheck = parts[0];
      portRemote = parseInt(parts[1], 10) || 443;
    }
  }

  let tcpSocket;
  try {
    tcpSocket = connect({ hostname: hostToCheck.replace(/\[|\]/g, ''), port: portRemote });
    const writer = tcpSocket.writable.getWriter();
    const httpRequest = 'GET /cdn-cgi/trace HTTP/1.1\r\nHost: speed.cloudflare.com\r\nUser-Agent: checkip/mehdi/\r\nConnection: close\r\n\r\n';
    await writer.write(new TextEncoder().encode(httpRequest));

    const reader = tcpSocket.readable.getReader();
    let responseData = new Uint8Array(0);
    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), 5000));

    while (responseData.length < 4096) {
      const { value, done } = await Promise.race([reader.read(), timeout]);
      if (done) break;
      if (value) {
        const newData = new Uint8Array(responseData.length + value.length);
        newData.set(responseData);
        newData.set(value, responseData.length);
        responseData = newData;
        if (new TextDecoder().decode(responseData).includes('\r\n\r\n')) break;
      }
    }

    const responseText = new TextDecoder().decode(responseData);
    const statusMatch = responseText.match(/^HTTP\/\d\.\d\s+(\d+)/i);
    const statusCode = statusMatch ? parseInt(statusMatch[1], 10) : null;
    const isSuccessful = statusCode !== null && responseText.includes('cloudflare') && (responseText.includes('plain HTTP request') || responseText.includes('400 Bad Request')) && responseData.length > 100;

    return { success: isSuccessful, proxyIP: hostToCheck, portRemote, statusCode, responseSize: responseData.length, timestamp: new Date().toISOString() };
  } catch (error) {
    return { success: false, proxyIP: hostToCheck, portRemote, timestamp: new Date().toISOString(), error: error.message };
  } finally {
    if (tcpSocket) {
      try { await tcpSocket.close(); } catch (e) {}
    }
  }
}

async function getIpInfo(ip) {
    try {
        const response = await fetch(`http://ip-api.com/json/${ip}?fields=status,message,country,countryCode,as&lang=en`);
        if (!response.ok) return { country: 'N/A', countryCode: 'N/A', as: 'N/A' };
        const data = await response.json();
        if (data.status === 'fail') return { country: 'N/A', countryCode: 'N/A', as: 'N/A' };
        return data;
    } catch (e) {
        return { country: 'N/A', countryCode: 'N/A', as: 'N/A' };
    }
}

// --- Main Handler for Cloudflare Pages ---
export async function onRequest(context) {
    const { request, env } = context;
    const url = new URL(request.url);
    const path = url.pathname;
    const UA = request.headers.get('User-Agent') || 'null';
    const hostname = url.hostname;

    // --- API Route Handling ---
    if (path.toLowerCase().startsWith('/api/')) {
        const endpoint = path.substring(5).split('/')[0]; // Gets 'check', 'resolve', 'ip-info'

        const timestampForToken = Math.ceil(new Date().getTime() / (1000 * 60 * 31));
        const temporaryTOKEN = await doubleHash(hostname + timestampForToken + UA);
        const permanentTOKEN = env.TOKEN || temporaryTOKEN;
        
        const isTokenValid = () => {
            if (!env.TOKEN) return true;
            const providedToken = url.searchParams.get('token');
            return providedToken === permanentTOKEN || providedToken === temporaryTOKEN;
        };
        
        if (endpoint === 'get-token') {
            return new Response(JSON.stringify({ token: temporaryTOKEN }), { headers: { "Content-Type": "application/json" } });
        }

        if (!isTokenValid()) {
            return new Response(JSON.stringify({ success: false, error: "Invalid TOKEN" }), {
                status: 403, headers: { "Content-Type": "application/json" }
            });
        }

        if (endpoint === 'check') {
            const proxyIPInput = url.searchParams.get('proxyip');
            if (!proxyIPInput) return new Response(JSON.stringify({success: false, error: 'Missing proxyip parameter'}), { status: 400, headers: { "Content-Type": "application/json" }});
            const result = await checkProxyIP(proxyIPInput);
            return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
        }
        
        if (endpoint === 'resolve') {
            const domain = url.searchParams.get('domain');
            if (!domain) return new Response(JSON.stringify({success: false, error: 'Missing domain parameter'}), { status: 400, headers: { "Content-Type": "application/json" }});
            try {
                const ips = await resolveDomain(domain);
                return new Response(JSON.stringify({ success: true, domain, ips }), { headers: { "Content-Type": "application/json" } });
            } catch (error) {
                return new Response(JSON.stringify({ success: false, error: error.message }), { status: 500, headers: { "Content-Type": "application/json" } });
            }
        }

        if (endpoint === 'ip-info') {
            let ip = url.searchParams.get('ip') || request.headers.get('CF-Connecting-IP');
            if (!ip) return new Response(JSON.stringify({success: false, error: 'IP parameter not provided'}), { status: 400, headers: { "Content-Type": "application/json" }});
            if (ip.includes('[')) ip = ip.replace(/\[|\]/g, '');
            const data = await getIpInfo(ip);
            return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
        }
        
        return new Response(JSON.stringify({success: false, error: 'API route not found'}), { status: 404, headers: { "Content-Type": "application/json" } });
    }

    // --- Static Asset and HTML Page Handling (Unchanged) ---
    // The rest of your original file logic for serving HTML and JS should go here.
    // For example:
    if (path === '/') {
        // Your generateMainHTML() function would be called here
        return new Response("This is the main page.", { headers: { "content-type": "text/html;charset=UTF-8" } });
    }

    if (path === '/client.js') {
        // Your CLIENT_SCRIPT variable would be returned here
        return new Response("/* client.js content */", { headers: { "Content-Type": "application/javascript;charset=UTF-8" } });
    }
    
    return new Response('Not Found', { status: 404 });
}
