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

function parseIPRangeServer(rangeInput) {
    const ips = [];
    const cidrMatch = rangeInput.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/24$/);
    const rangeMatch = rangeInput.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.)(\d{1,3})-(\d{1,3})$/);

    if (cidrMatch) {
        const prefix = cidrMatch[1].substring(0, cidrMatch[1].lastIndexOf('.'));
        for (let i = 0; i <= 255; i++) ips.push(`${prefix}.${i}`);
    } else if (rangeMatch) {
        const prefix = rangeMatch[1];
        const start = parseInt(rangeMatch[2], 10);
        const end = parseInt(rangeMatch[3], 10);
        if (!isNaN(start) && !isNaN(end) && start >=0 && end <= 255) {
            for (let i = start; i <= end; i++) ips.push(`${prefix}${i}`);
        }
    }
    return ips;
}

const forgivingIPv4Regex = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;
const ipv6Regex = /(?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4}|\[(?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4}\]/gi;

function generateClientSideCheckPageHTML({ title, subtitleLabel, subtitleContent, ipsToCheck, temporaryTOKEN, pageType, contentHash }) {
    const ipsJson = JSON.stringify(ipsToCheck);
    let subtitleHTML = '';
    if (subtitleLabel && subtitleContent) {
        if (pageType === 'file') {
             subtitleHTML = `<div class="ranges-list"><strong>${subtitleLabel}</strong> <a href="${subtitleContent}" class="range-tag" target="_blank" rel="noopener noreferrer">${subtitleContent}</a></div>`;
        } else if (pageType === 'iprange') {
             const ranges = subtitleContent.split(',').map(r => `<span class="range-tag" onclick="copyToClipboard('${r.trim()}', this)">${r.trim()}</span>`).join('<br>');
             subtitleHTML = `<div class="ranges-list"><strong>${subtitleLabel}</strong><br>${ranges}</div>`;
        } else {
             subtitleHTML = `<div class="ranges-list"><strong>${subtitleLabel}</strong> <span class="range-tag">${subtitleContent}</span></div>`;
        }
    }

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checking IPs...</title>
    <style>
        :root{--bg-color:#f4f7f9;--card-bg-color:#fff;--text-color:#2c3e50;--border-color:#e1e8ed;--hover-bg-color:#f8f9fa;--primary-color:#3498db;--primary-text-color:#fff;--subtle-text-color:#7f8c8d;--tag-bg-color:#e8eaed;--secondary-color:#95a5a6}body.dark-mode{--bg-color:#2c3e50;--card-bg-color:#34495e;--text-color:#ecf0f1;--border-color:#465b71;--hover-bg-color:#4a6075;--subtle-text-color:#bdc3c7;--tag-bg-color:#2b2b2b;--secondary-color:#7f8c8d}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background-color:var(--bg-color);color:var(--text-color);margin:0;padding:20px;transition:background-color .3s,color .3s}.container{max-width:700px;margin:0 auto}.header{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:15px;margin-bottom:25px;border-bottom:1px solid var(--border-color)}.title-section h1{font-size:1.8em;margin:0 0 10px}.ranges-list{font-size:.9em;color:var(--subtle-text-color)}.range-tag{display:inline-block;background-color:var(--tag-bg-color);padding:4px 8px;border-radius:6px;font-family:'Courier New',Courier,monospace;cursor:pointer;margin:2px 0;transition:background-color .2s;text-decoration:none;color:var(--text-color);word-break:break-all;}.range-tag:hover{background-color:var(--primary-color);color:var(--primary-text-color)}.button-group{display:flex;gap:10px;flex-shrink:0;margin-left:20px}.btn{padding:8px 16px;border:none;border-radius:8px;cursor:pointer;font-weight:500;font-size:.9em;transition:transform .2s;text-decoration:none;display:inline-flex;align-items:center}.btn-primary{background:linear-gradient(135deg,var(--primary-color),#2980b9);color:var(--primary-text-color)}.btn-secondary{background-color:var(--secondary-color);color:var(--primary-text-color)}.btn:hover{transform:translateY(-2px)}.theme-toggle{background-color:var(--card-bg-color);border:1px solid var(--border-color);width:38px;height:38px;justify-content:center;padding:0;border-radius:50%}.results-card{background-color:var(--card-bg-color);border:1px solid var(--border-color);border-radius:10px;padding:10px;min-height:50px;}.ip-item{display:flex;justify-content:space-between;align-items:center;padding:12px 15px;border-radius:6px;}.ip-item:not(:last-child){border-bottom:1px solid var(--border-color)}.ip-tag{background-color:var(--tag-bg-color);padding:3px 7px;border-radius:5px;font-family:'Courier New',Courier,monospace;cursor:pointer;transition:background-color .2s}.ip-tag:hover{background-color:var(--primary-color);color:var(--primary-text-color)}.ip-details{font-size:.9em;color:var(--subtle-text-color);padding-left:15px}.action-buttons{margin-top:20px;display:flex;justify-content:center;gap:10px}.footer{text-align:center;padding:20px;margin-top:30px;color:var(--subtle-text-color);font-size:.9em;border-top:1px solid var(--border-color)}.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:12px 20px;border-radius:8px;z-index:1001;opacity:0;transition:opacity .3s,transform .3s;pointer-events:none}.toast.show{opacity:1}
        .theme-toggle svg { width: 18px; height: 18px; stroke: var(--text-color); transition: all 0.3s ease; }
        body:not(.dark-mode) .theme-toggle .sun-icon { display: block; fill: none;}
        body:not(.dark-mode) .theme-toggle .moon-icon { display: none; }
        body.dark-mode .theme-toggle .sun-icon { display: none; }
        body.dark-mode .theme-toggle .moon-icon { display: block; fill: var(--text-color); stroke: var(--text-color); }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="title-section">
                <h1 id="main-title">${title}</h1>
                ${subtitleHTML}
            </div>
            <div class="button-group">
                <button class="btn theme-toggle" onclick="toggleTheme()">
                    <svg class="sun-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                    <svg class="moon-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                </button>
            </div>
        </header>
        <p id="summary">Total IPs to check: ${ipsToCheck.length}. Starting tests...</p>
        <main id="results-container" class="results-card">
            <p style="text-align:center; padding: 20px;">Processing...</p>
        </main>
        <div id="action-buttons-container"></div>
        <footer class="footer">
            <p>© ${new Date().getFullYear()} Proxy IP Checker - By <strong>mehdi-hexing</strong></p>
        </footer>
    </div>
    <div id="toast" class="toast"></div>
    <script>
        const ipsToCheck = ${ipsJson};
        const TEMP_TOKEN = "${temporaryTOKEN}";
        const pageType = "${pageType}";
        const contentHash = "${contentHash || ''}";
        const storageKey = 'proxy_results_' + window.location.pathname;
        let successfulIPs = [];
        let checkedCount = 0;
        let allResults = {};

        function showToast(message) { const toast = document.getElementById('toast'); toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3000); }
        function copyToClipboard(text, element) { navigator.clipboard.writeText(text).then(() => { const o = element ? element.textContent : ''; if(element) {element.textContent = 'Copied!'; setTimeout(()=>element.textContent=o, 2000);} else { showToast('Copied!')} }).catch(err => { showToast('Copy failed!'); }); }
        function toggleTheme() {
            const body = document.body; body.classList.toggle('dark-mode');
            localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
        }

        async function fetchAPI(path, params) {
            params.append('token', TEMP_TOKEN);
            const response = await fetch('/api' + path + '?' + params.toString());
            const data = await response.json();
            if (!response.ok && typeof data.success === 'undefined') {
                throw new Error('API Error: ' + (data.message || response.statusText));
            }
            return data;
        }

        function renderResult(item) {
            const container = document.getElementById('results-container');
            if (successfulIPs.length === 1 && container.querySelector('p')) {
                 container.innerHTML = '';
            }
            const detailsParts = [];
            if (item.info && item.info.country) detailsParts.push(item.info.country);
            if (item.info && item.info.as) detailsParts.push(item.info.as);
            const detailsText = detailsParts.length > 0 ? \`(\${detailsParts.join(' - ')})\` : '';
            const itemHTML = \`<div class="ip-item"><span class="ip-tag" onclick="copyToClipboard('\${item.ip}', this)">\${item.ip}</span><span class="ip-details">\${detailsText}</span></div>\`;
            container.insertAdjacentHTML('beforeend', itemHTML);
        }

        function updateSummary() {
            document.getElementById('summary').textContent = \`Checked: \${checkedCount} / \${ipsToCheck.length} | Successful: \${successfulIPs.length}\`;
        }
        
        function loadSavedResults() {
            try {
                const savedJSON = localStorage.getItem(storageKey);
                if (!savedJSON) return;
                const cachedData = JSON.parse(savedJSON);

                if (pageType === 'file' && contentHash && cachedData.hash !== contentHash) {
                    localStorage.removeItem(storageKey);
                    showToast('File content has changed. Starting fresh check.');
                    return;
                }

                allResults = cachedData.results || {};
                for(const ip in allResults) {
                    if(allResults[ip].success) {
                        const resultItem = { ip: allResults[ip].ip, info: allResults[ip].info };
                        successfulIPs.push(resultItem);
                        renderResult(resultItem);
                    }
                }
                checkedCount = Object.keys(allResults).length;
                updateSummary();
            } catch(e) { console.error("Error loading from cache", e); allResults = {}; }
        }

        async function startChecking() {
            document.title = \`Checking \${ipsToCheck.length} IPs...\`;
            
            loadSavedResults();

            const ipsToActuallyTest = ipsToCheck.filter(ip => !allResults[ip]);
            if (ipsToActuallyTest.length === 0 && ipsToCheck.length > 0) {
                 document.getElementById('summary').textContent += ' (All IPs loaded from cache)';
                 if(successfulIPs.length === 0) document.getElementById('results-container').innerHTML = '<p style="text-align:center;">No successful proxies found.</p>';
            }

            const batchSize = 20;
            for (let i = 0; i < ipsToActuallyTest.length; i += batchSize) {
                const batch = ipsToActuallyTest.slice(i, i + batchSize);
                const promises = batch.map(async (ip) => {
                    try {
                        const checkData = await fetchAPI('/check', new URLSearchParams({ proxyip: ip }));
                        const ipInfo = checkData.success ? await fetchAPI('/ip-info', new URLSearchParams({ ip: checkData.proxyIP })) : null;
                        
                        const resultItem = { ip: checkData.proxyIP, success: checkData.success, info: ipInfo };
                        allResults[ip] = resultItem; 

                        if (checkData.success) {
                            successfulIPs.push(resultItem);
                            renderResult(resultItem);
                        }
                    } catch (e) {
                        console.error('Failed to check ip:', ip, e);
                        allResults[ip] = { success: false, error: e.message };
                    } finally {
                        checkedCount++;
                    }
                });
                await Promise.allSettled(promises);
                const dataToSave = { hash: contentHash, results: allResults };
                localStorage.setItem(storageKey, JSON.stringify(dataToSave));
                updateSummary();
            }

            document.title = \`\${successfulIPs.length} Successful IPs Found\`;
            const actionContainer = document.getElementById('action-buttons-container');
            if (successfulIPs.length === 0) {
                 if (Object.keys(allResults).length >= ipsToCheck.length) {
                    document.getElementById('results-container').innerHTML = '<p style="text-align:center;">No successful proxies found.</p>';
                 }
            } else {
                 let downloadButton = '';
                 const successfulIPsText = successfulIPs.map(i=>i.ip).join('\\n');
                 if (pageType === 'file') {
                    const dataUrl = \`data:text/plain;charset=utf-8;base64,\${btoa(unescape(encodeURIComponent(successfulIPsText)))}\`;
                    downloadButton = \`<a href="\${dataUrl}" download="successful_ips.txt" class="btn btn-secondary">📥 Download Results</a>\`;
                 }
                 actionContainer.innerHTML = \`<div class="action-buttons">\${downloadButton}<button class="btn btn-primary" onclick="copyToClipboard('\${successfulIPsText}')">📋 Copy All</button></div>\`;
            }
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                 document.body.classList.add('dark-mode');
            }
            startChecking();
        });
    </script>
</body>
</html>`;
}

const CLIENT_SCRIPT = `
    let isChecking = false;
    let TEMP_TOKEN = '';
    let currentSuccessfulRangeIPs = [];

    document.addEventListener('DOMContentLoaded', () => {
        fetch('/api/get-token').then(res => res.json()).then(data => { TEMP_TOKEN = data.token; });
        document.getElementById('checkBtn').addEventListener('click', checkInputs);
        
        document.getElementById('copyRangeBtn').addEventListener('click', () => {
            if (currentSuccessfulRangeIPs.length > 0) {
                const textToCopy = currentSuccessfulRangeIPs.map(item => item.ip).join('\\n');
                copyToClipboard(textToCopy, document.getElementById('copyRangeBtn'), "All successful IPs copied!");
            }
        });

        document.body.addEventListener('click', event => {
            const target = event.target;
            if (target.classList.contains('copy-btn') || target.classList.contains('ip-tag') || target.classList.contains('range-tag')) {
                const text = target.getAttribute('data-copy') || target.textContent;
                if (text) copyToClipboard(text, target);
            }
        });
        
        const drawerToggle = document.getElementById('drawer-toggle');
        const drawerContent = document.getElementById('drawer-content');
        if (drawerToggle && drawerContent) {
            drawerToggle.addEventListener('click', () => {
                drawerContent.classList.toggle('visible');
                drawerToggle.classList.toggle('active');
            });
        }

        const themeToggleBtn = document.getElementById('theme-toggle');
        const body = document.body;
        
        const applyTheme = (theme) => {
            if (theme === 'dark') body.classList.add('dark-mode');
            else body.classList.remove('dark-mode');
        };

        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) applyTheme(savedTheme);
        else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) applyTheme('dark');

        themeToggleBtn.addEventListener('click', () => {
            body.classList.toggle('dark-mode');
            localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
        });
    });

    function showToast(message, duration = 3000) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), duration);
    }

    function copyToClipboard(text, element, successMessage = "Copied!") {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = element ? element.textContent : '';
            if (element) {
                element.textContent = 'Copied ✓';
                setTimeout(() => { if(element) element.textContent = originalText; }, 2000);
            } else {
                 showToast(successMessage);
            }
        }).catch(err => showToast('Copy failed.'));
    }

    function toggleCheckButton(checking) {
        isChecking = checking;
        const checkBtn = document.getElementById('checkBtn');
        checkBtn.disabled = checking;
        const btnText = checkBtn.querySelector('.btn-text');
        const spinner = checkBtn.querySelector('.loading-spinner');
        if(btnText) btnText.style.display = checking ? 'none' : 'inline-block';
        if(spinner) spinner.style.display = checking ? 'inline-block' : 'none';
    }

    async function fetchAPI(path, params) {
        if (!TEMP_TOKEN) {
             await new Promise(resolve => setTimeout(resolve, 500));
             if (!TEMP_TOKEN) await fetch('/api/get-token').then(res => res.json()).then(data => { TEMP_TOKEN = data.token; });
             if (!TEMP_TOKEN) throw new Error("Could not retrieve session token.");
        }
        params.append('token', TEMP_TOKEN);
        const fullPathWithParams = '/api' + path + '?' + params.toString();
        
        const response = await fetch(fullPathWithParams);
        if (!response.ok) {
            const errorText = await response.text();
            let errorJson;
            try {
                errorJson = JSON.parse(errorText);
            } catch (e) {
                 throw new Error(errorText || 'API request failed');
            }
            throw new Error(errorJson.error || errorJson.message || 'API request failed');
        }
        return response.json();
    }

    const isIPAddress = (input) => /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(input.split(':')[0].replace(/[\\[\\]]/g, ''));
    const isDomain = (input) => /^(?!-)[a-zA-Z0-9-]+([\\-\\.]{1}[a-zA-Z0-9]+)*\\.[a-zA-Z]{2,}$/.test(input.split(':')[0]);
    const isIPRange = (input) => /^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\/24$/.test(input) || /^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.)(\\d{1,3})-(\\d{1,3})$/.test(input);

    function parseIPRange(rangeInput) {
        const ips = [];
        const cidrMatch = rangeInput.match(/^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\/24$/);
        const rangeMatch = rangeInput.match(/^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.)(\\d{1,3})-(\\d{1,3})$/);

        if (cidrMatch) {
            const prefix = cidrMatch[1].substring(0, cidrMatch[1].lastIndexOf('.'));
            for (let i = 0; i <= 255; i++) ips.push(\`\${prefix}.\${i}\`);
        } else if (rangeMatch) {
            const prefix = rangeMatch[1];
            const start = parseInt(rangeMatch[2], 10);
            const end = parseInt(rangeMatch[3], 10);
            if (!isNaN(start) && !isNaN(end) && start <= end) {
                for (let i = start; i <= end; i++) ips.push(\`\${prefix}\${i}\`);
            }
        }
        return ips;
    }
    
    async function checkInputs() {
        if (isChecking) return;
        
        const mainInputEl = document.getElementById('proxyip');
        const rangeIpTextareaEl = document.getElementById('proxyipRangeRows');
        const mainInputs = mainInputEl.value.split(/[\\n,;\\s]+/).map(s => s.trim()).filter(Boolean);
        const rangeInputs = rangeIpTextareaEl.value.split('\\n').map(s => s.trim()).filter(Boolean);

        if (mainInputs.length === 0 && rangeInputs.length === 0) {
            showToast('Please enter something to check.');
            return;
        }
        
        toggleCheckButton(true);
        document.getElementById('result').innerHTML = '';
        document.getElementById('rangeResultCard').style.display = 'none';

        try {
            if (mainInputs.length === 1 && rangeInputs.length === 0) {
                const singleInput = mainInputs[0];
                if (isDomain(singleInput)) await checkAndDisplayDomain_graphical(singleInput);
                else if (isIPAddress(singleInput)) await checkAndDisplaySingleIP_graphical(singleInput);
                else document.getElementById('result').innerHTML = '<div class="result-card result-error"><h3>❌ Unrecognized Format</h3></div>';
            } else if (mainInputs.length > 1) {
                await processMultipleInputs(mainInputs);
            }
            
            if (rangeInputs.length > 0) {
                 await processRangeInputs(rangeInputs);
            }
        } catch (e) {
            console.error(e);
            showToast("An unexpected error occurred.");
        } finally {
            toggleCheckButton(false);
        }
    }
    
    async function checkAndDisplaySingleIP_graphical(proxyip) {
        const resultDiv = document.getElementById('result');
        resultDiv.innerHTML = '<div class="result-card"><p style="text-align:center;">Checking...</p></div>';
        try {
            const data = await fetchAPI('/check', new URLSearchParams({ proxyip }));
            const resultCard = resultDiv.firstChild;
            if (data.success) {
                const ipInfo = await fetchAPI('/ip-info', new URLSearchParams({ ip: data.proxyIP }));
                resultCard.className = 'result-card result-success';
                resultCard.innerHTML = \`
                    <h3>✅ Valid Proxy IP</h3>
                    <p><strong>📍 IP Address:</strong> <span class="ip-tag" data-copy="\${data.proxyIP}">\${data.proxyIP}</span></p>
                    <p><strong>🌍 Country:</strong> \${ipInfo.country || 'N/A'}</p>
                    <p><strong>🌐 AS:</strong> \${ipInfo.as || 'N/A'}</p>
                    <p><strong>🔌 Port:</strong> \${data.portRemote}</p>
                    <p><strong>🕒 Check Time:</strong> \${new Date(data.timestamp).toLocaleString()}</p>
                \`;
            } else {
                resultCard.className = 'result-card result-error';
                resultCard.innerHTML = \`
                    <h3>❌ Invalid Proxy IP</h3>
                    <p><strong>📍 IP Address:</strong> <span class="ip-tag" data-copy="\${proxyip}">\${proxyip}</span></p>
                    <p><strong>Error:</strong> \${data.error || 'Check failed.'}</p>
                    <p><strong>🕒 Check Time:</strong> \${new Date(data.timestamp).toLocaleString()}</p>
                \`;
            }
        } catch (error) {
            resultDiv.innerHTML = \`<div class="result-card result-error"><h3>❌ Error</h3><p>\${error.message}</p></div>\`;
        }
    }
    
    async function checkAndDisplayDomain_graphical(domain) {
        const resultDiv = document.getElementById('result');
        resultDiv.innerHTML = '<div class="result-card"><p style="text-align:center;">Resolving & Checking...</p></div>';
        const resultCard = resultDiv.firstChild;

        try {
            resultCard.className = 'result-card';
            const resolveData = await fetchAPI('/resolve', new URLSearchParams({ domain }));
            if (!resolveData.success || !resolveData.ips || resolveData.ips.length === 0) {
                throw new Error(resolveData.error || 'Could not resolve domain.');
            }
            const ips = resolveData.ips;
            resultCard.innerHTML = \`
                <h3>Checking \${ips.length} IPs for \${domain}</h3>
                <div class="domain-ip-list"></div>
            \`;
            const ipListDiv = resultCard.querySelector('.domain-ip-list');

            let successCount = 0;
            const checkPromises = ips.map(async (ip, index) => {
                const ipItem = document.createElement('div');
                ipItem.className = 'ip-item-multi';
                ipItem.innerHTML = \`<span class="ip-tag" data-copy="\${ip}">\${ip}</span><span class="ip-details" id="status-\${index}">🔄</span>\`;
                ipListDiv.appendChild(ipItem);
                
                try {
                    const checkData = await fetchAPI('/check', new URLSearchParams({ proxyip: ip }));
                    const statusSpan = document.getElementById(\`status-\${index}\`);
                    if (checkData.success) {
                        successCount++;
                        const ipInfo = await fetchAPI('/ip-info', new URLSearchParams({ ip: ip }));
                        statusSpan.innerHTML = \`✅ (\${ipInfo.country || 'N/A'} - \${ipInfo.as || 'N/A'})\`;
                    } else {
                        statusSpan.textContent = '❌';
                    }
                } catch(e) {
                     document.getElementById(\`status-\${index}\`).textContent = '⚠️';
                }
            });

            await Promise.all(checkPromises);

            resultCard.classList.add(successCount > 0 ? 'result-success' : 'result-error');
            resultCard.querySelector('h3').innerHTML = \`\${successCount > 0 ? '✅' : '❌'} \${successCount} of \${ips.length} IPs are valid for \${domain}\`;

        } catch (error) {
            resultCard.className = 'result-card result-error';
            resultCard.innerHTML = \`<h3>❌ Error</h3><p>\${error.message}</p>\`;
        }
    }
    
    async function processMultipleInputs(mainInputs) {
        const resultDiv = document.getElementById('result');
        resultDiv.innerHTML = '<div class="result-card"><p style="text-align:center; padding: 20px;">Processing...</p></div>';
        
        const mainCard = resultDiv.querySelector('.result-card');
        
        const domains = mainInputs.filter(isDomain);
        const directIPs = mainInputs.filter(isIPAddress);
        const numberEmojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣'];
        const formatNumber = (n) => (n).toString().split('').map(digit => numberEmojis[parseInt(digit)]).join('');
        
        let allIPsToTest = directIPs.map(ip => ({ ip, domainIndex: -1 })); 
        
        let domainListHTML = '';
        if (domains.length > 0) {
            domainListHTML = '<h2>Domains to Check</h2>';
            domains.forEach((d, i) => {
                domainListHTML += \`<p style="margin: 0; margin-bottom: 5px;">\${formatNumber(i + 1)} <span class="copy-btn" data-copy="\${d}">\${d}</span></p>\`;
            });
        }
        mainCard.innerHTML = domainListHTML + (domains.length > 0 ? '<hr style="margin: 15px 0;">' : '') + '<div id="multi-ip-list" class="domain-ip-list"><p style="text-align:center;">Resolving and preparing IP list...</p></div>';
        
        const resolvePromises = domains.map(async (domain, index) => {
            try {
                const resolveData = await fetchAPI('/resolve', new URLSearchParams({ domain }));
                if (resolveData.success) {
                    resolveData.ips.forEach(ip => allIPsToTest.push({ ip, domainIndex: index }));
                }
            } catch (e) { console.error("Failed to resolve", domain, e); }
        });
        await Promise.allSettled(resolvePromises);
        
        allIPsToTest = [...new Map(allIPsToTest.map(item => [item.ip, item])).values()];
        
        const ipListContainer = document.getElementById('multi-ip-list');
        ipListContainer.innerHTML = '<p style="text-align:center;">Checking all IPs...</p>';
        
        const checkPromises = allIPsToTest.map(async (ipObject) => {
            try {
                const checkData = await fetchAPI('/check', new URLSearchParams({ proxyip: ipObject.ip }));
                if (checkData.success) {
                    const ipInfo = await fetchAPI('/ip-info', new URLSearchParams({ ip: checkData.proxyIP }));
                    return { ip: checkData.proxyIP, info: ipInfo, domainIndex: ipObject.domainIndex };
                }
            } catch (e) {}
            return null;
        });

        const successfulIPs = (await Promise.all(checkPromises)).filter(Boolean);

        if (successfulIPs.length > 0) {
            ipListContainer.innerHTML = '<h2>Successful IPs</h2>' + successfulIPs.map(item => {
                const details = \`(\${item.info.country || 'N/A'} - \${item.info.as || 'N/A'})\`;
                const prefix = item.domainIndex > -1 ? \`\${formatNumber(item.domainIndex + 1)} \` : '';
                return \`<div class="ip-item-multi"><div>\${prefix}<span class="ip-tag" data-copy="\${item.ip}">\${item.ip}</span></div><span class="ip-details">\${details}</span></div>\`;
            }).join('');
        } else {
            ipListContainer.innerHTML = '<p>No valid proxies found.</p>';
        }

        if (successfulIPs.length > 0) {
            const actionButtonHTML = \`<div class="action-buttons"><button class="btn btn-primary" onclick="copyToClipboard('\${successfulIPs.map(i=>i.ip).join('\\n')}')">📋 Copy All Successful IPs</button></div>\`;
            mainCard.insertAdjacentHTML('beforeend', actionButtonHTML);
        }
    }
    
    async function processRangeInputs(rangeInputs) {
        const rangeResultCard = document.getElementById('rangeResultCard');
        const summaryDiv = document.getElementById('rangeResultSummary');
        const listDiv = document.getElementById('successfulRangeIPsList');
        const copyBtn = document.getElementById('copyRangeBtn');
        
        rangeResultCard.style.display = 'block';
        rangeResultCard.className = 'result-card result-section';
        listDiv.innerHTML = '<p style="text-align:center;">Processing...</p>';
        summaryDiv.innerHTML = 'Total Tested: 0 | Total Successful: 0';
        copyBtn.style.display = 'none';
        currentSuccessfulRangeIPs = [];
        
        const allIPsToTest = [...new Set(rangeInputs.flatMap(parseIPRange))];
        if (allIPsToTest.length === 0) {
            summaryDiv.innerHTML = 'Invalid range format provided.';
            listDiv.innerHTML = '';
            return;
        }

        let successCount = 0;
        let checkedCount = 0;
        const batchSize = 20;

        for (let i = 0; i < allIPsToTest.length; i += batchSize) {
            const batch = allIPsToTest.slice(i, i + batchSize);
            const batchPromises = batch.map(ip => 
                fetchAPI('/check', new URLSearchParams({ proxyip: ip }))
                    .then(async (data) => {
                        checkedCount++;
                        if (data.success) {
                            successCount++;
                            const ipInfo = await fetchAPI('/ip-info', new URLSearchParams({ ip: data.proxyIP }));
                            currentSuccessfulRangeIPs.push({ ip: data.proxyIP, countryCode: ipInfo.countryCode || 'N/A' });
                        }
                    })
                    .catch(err => { checkedCount++; })
            );
            await Promise.all(batchPromises);
            summaryDiv.innerHTML = \`Tested: \${checkedCount}/\${allIPsToTest.length} | Successful: \${successCount}\`;
            updateSuccessfulRangeIPsDisplay();
        }
        
        if (currentSuccessfulRangeIPs.length > 0) copyBtn.style.display = 'inline-block';
    }

    function updateSuccessfulRangeIPsDisplay() {
        const listDiv = document.getElementById('successfulRangeIPsList');
        if (currentSuccessfulRangeIPs.length === 0) {
            listDiv.innerHTML = '<p style="text-align:center; color: var(--text-light);">No successful IPs found in range(s).</p>';
            return;
        }
        listDiv.innerHTML = currentSuccessfulRangeIPs.map(item => 
            \`<div class="ip-item-multi">
                <span class="ip-tag" data-copy="\${item.ip}">\${item.ip}</span>
                <span class="ip-details">\${item.countryCode}</span>
            </div>\`
        ).join('');
    }
`;

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const path = url.pathname;
        const UA = request.headers.get('User-Agent') || 'null';
        const hostname = url.hostname;
        
        if (path.toLowerCase().startsWith('/api/')) {
            const endpoint = path.substring(5);
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
                return new Response(JSON.stringify({ status: "error", message: "Invalid TOKEN" }), {
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
                return resolveDomain(domain);
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
        
        const faviconURL = env.ICO || 'https://github.com/user-attachments/assets/31a6ced0-62b8-429f-a98e-082ea5ac1990';

        if (path.toLowerCase() === '/favicon.ico') {
            return Response.redirect(faviconURL, 302);
        }
        
        if (path === '/') {
            return new Response(generateMainHTML(faviconURL), {
                headers: { "content-type": "text/html;charset=UTF-8" }
            });
        }
        
        if (path === '/client.js') {
            return new Response(CLIENT_SCRIPT, { headers: { "Content-Type": "application/javascript;charset=UTF-8" } });
        }

        if (path.toLowerCase().startsWith('/file/') || path.toLowerCase().startsWith('/iprange/') || path.toLowerCase().startsWith('/proxyip/')) {
            const timestamp = Math.ceil(new Date().getTime() / (1000 * 60 * 31));
            const temporaryTOKEN = await doubleHash(hostname + timestamp + UA);
            let ipsToCheck = [];
            let options = {};
            let pageType = '';
            let contentHash = '';

            if (path.toLowerCase().startsWith('/proxyip/')) {
                pageType = 'proxyip';
                const ips_string = decodeURIComponent(path.substring('/proxyip/'.length));
                ipsToCheck = ips_string.split(',').map(s => s.trim()).filter(Boolean);
                contentHash = simpleHash(ipsToCheck.join(''));
                options = {
                    title: "Proxy IP's Results:",
                    subtitleLabel: "IPs:",
                    subtitleContent: ips_string,
                };
            } else if (path.toLowerCase().startsWith('/iprange/')) {
                pageType = 'iprange';
                const ranges_string = decodeURIComponent(path.substring('/iprange/'.length));
                ipsToCheck = ranges_string.split(',').flatMap(range => parseIPRangeServer(range.trim()));
                contentHash = simpleHash(ipsToCheck.join(''));
                options = {
                    title: "IP Range's Results:",
                    subtitleLabel: "Range's:",
                    subtitleContent: ranges_string,
                };
            } else { // /file/ path
                pageType = 'file';
                const targetUrl = decodeURIComponent(request.url.substring(request.url.indexOf('/file/') + 6));
                if (!targetUrl || !targetUrl.startsWith('http')) return new Response('Invalid URL', {status: 400});
                 try {
                    const response = await fetch(targetUrl, { headers: {'User-Agent': 'ProxyChecker/1.0'} });
                    if (!response.ok) throw new Error(`Fetch failed: ${response.statusText}`);
                    const text = await response.text();
                    contentHash = simpleHash(text);
                    const foundIPs = [...new Set([...(text.match(forgivingIPv4Regex) || []), ...(text.match(ipv6Regex) || [])])];
                    ipsToCheck = foundIPs.filter(ip => {
                        const parts = ip.split(':');
                        return parts.length === 1 || !isNaN(parseInt(parts[parts.length - 1]));
                    });
                     options = {
                        title: 'File Test Results:',
                        subtitleLabel: 'File Link Address:',
                        subtitleContent: targetUrl,
                    };
                } catch(e) {
                    return new Response(`Error processing file: ${e.message}`, { status: 500 });
                }
            }
            return new Response(generateClientSideCheckPageHTML({ ...options, ipsToCheck, temporaryTOKEN, pageType, contentHash }), { headers: { 'Content-Type': 'text/html;charset=UTF-8' } });
        }
        
        return new Response('Not Found', { status: 404 });
    }
};
