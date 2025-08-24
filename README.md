# Proxy IP Checker Bot

A powerful and feature-rich Telegram bot designed to test the connectivity and gather information about proxy IPs. This bot works in tandem with a powerful web service deployed on Cloudflare Pages/Workers for handling network requests asynchronously.

## Features

* **Multiple Test Modes**: `/proxyip`, `/iprange`, `/domain`, `/file`.
* **Free Proxies**: `/freeproxyip` command with a 3-column, sorted country menu.
* **Interactive Live Testing**: Live-updating messages with Pause/Resume/Cancel controls for tests run in private chat.
* **Comprehensive Results**: Final output includes a copyable code block and both `.txt` and `.csv` files.
* **Channel & Group Posting**:
    * `/addchat`: A user-friendly, multi-step process to register a target channel or group.
    * `/deletechat`: An interactive menu to remove a registered chat.
    * `/post`: A command to run any test in the background and post the final, clean results to a registered destination.
* **Advanced Conversational Logic**:
    * Hybrid mode (direct args & conversational) in private chat.
    * Conversational-only (reply-based) mode in group chats to ensure stability.
* **User-Friendly UX**:
    * Emoji numbering for multi-domain tests.
    * Auto-deletion of temporary messages.
    * Helpful replies for incorrect command usage.

## Architecture Overview

1.  **Backend API (Python):** A simple but essential service that performs the raw TCP connection test. You will deploy this on either Vercel (serverless) or your own server.
2.  **Cloudflare Worker:** This is the core of the system. It acts as the main API endpoint for your Telegram bot. It receives requests, calls your Backend API for TCP checks, and also connects directly to the **Scamalytics API** to fetch fraud risk scores.
3.  **Telegram Bot (Python):** This is the user-facing component. It runs on your server and communicates with your Cloudflare Worker to process all user commands.

**Workflow:**
`User` -> `Telegram Bot (Your Server)` -> `Cloudflare Worker (Your Cloudflare Account)` -> ( `Backend API (Your Vercel/Server)` + `Scamalytics API` )

## Requirements

1.  A Telegram Bot Token from [@BotFather](https://t.me/BotFather).
2.  A free [Cloudflare](https://www.cloudflare.com/) account.
3.  A server or machine with Python 3.8+ and `screen` installed (standard on most Linux distros).
4.  The Python libraries listed in `requirements.txt`.
5.  A GitHub Account.
6.  A Vercel Account (if you choose the Vercel deployment option).

---

## 🚀 Deployment: Full Step-by-Step Guide

Follow these four parts carefully to get your bot fully operational.

### Part 1: Deploy the Backend API

The Cloudflare Worker needs this helper service to perform TCP checks. **Choose only ONE of the following two options.**

#### Option A: Deploy to Vercel (Recommended)

This is the simplest method, ideal for users who do not want to manage a server.

1.  **Go to the Vercel API Repository:** Navigate to [**mehdi-hexing/ProxyIP-Checker-Vercel-API**](https://github.com/mehdi-hexing/ProxyIP-Checker-Vercel-API).
2.  **Deploy to Vercel:** Click the **"Deploy"** button on the repository's README page. You will be prompted to create a copy of the project and deploy it to your Vercel account.
3.  **Get Your URL:** Once deployment is complete, Vercel will provide a production URL (e.g., `https://my-proxy-checker.vercel.app`). This is your full API base URL. **Save this URL** for Part 3.

#### Option B: Self-Host on a Server (Advanced)

Use this option if you have your own Linux server (VPS).

1.  **Go to the Server API Repository:** Navigate to [**mehdi-hexing/ProxyIP-Checker-API**](https://github.com/mehdi-hexing/ProxyIP-Checker-API).
2.  **Connect to Your Server & Clone:**
    ```bash
    git clone [https://github.com/mehdi-hexing/ProxyIP-Checker-API.git](https://github.com/mehdi-hexing/ProxyIP-Checker-API.git)
    cd ProxyIP-Checker-API
    ```
3.  **Install Prerequisites:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the API Persistently:**
    * Start a new `screen` session: `screen -S tcp-api`
    * Run the script, specifying a port (e.g., `8080`): `python main.py --port 8080`
    * Detach from the session by pressing `Ctrl+A`, then `D`.
5.  **Get Your URL:** Your API base URL will be `http://YOUR_SERVER_IP:8080`. Make sure the port is open in your server's firewall. **Save this URL** for Part 3.

### Part 2: Set Up Scamalytics API

This step is mandatory for the Cloudflare Worker to analyze risk scores.

1.  **Register:** Go to [Scamalytics.com](https://scamalytics.com/) and sign up for a **Free** account.
2.  **Confirm & Wait:** Confirm your email address and wait for your API access to be manually approved (this can take up to 24 hours).
3.  **Get Credentials:** Once approved, log in to your Scamalytics dashboard and find your **Username** and **API Key**. **Save these credentials.**

### Part 3: Configure and Deploy the Cloudflare Worker

This is the central part of the system that connects everything.

1.  **Fork this Repository:** Create your own copy of this (`ProxyIP-Tel-Bot`) repository by clicking the **"Fork"** button on its GitHub page.
2.  **Configure the Worker Script:**
    * In your forked repository, open the `_worker.js` file for editing.
    * Find the `apiUrls` array and replace the placeholder URLs with the URL of your Backend API from **Part 1**.
        ```javascript
        // In _worker.js
        const apiUrls = [
            `https://<YOUR_VERCEL_OR_SERVER_URL>/api/v1/check?proxyip=${encodeURIComponent(proxyIPInput)}`,
            `https://<YOUR_VERCEL_OR_SERVER_URL>/api/v1/check?proxyip=${encodeURIComponent(proxyIPInput)}`
        ];
        ```
    * Commit the changes.
3.  **Deploy to Cloudflare Pages:**
    * In your Cloudflare dashboard, go to **Workers & Pages**.
    * Click "Create application" -> "Pages" -> "Connect to Git".
    * Select your forked `ProxyIP-Tel-Bot` repository.
    * In the build settings, select "None" for the framework preset and click `Save and Deploy`.
4.  **Set Environment Variables:**
    * In your new Cloudflare project, go to **Settings > Environment variables**.
    * Add the following required variables from **Part 2**:

|       Variable Name.       |            Value            | Required |
| :------------------------: |  :-----------------------:  | :------: |
| `SCAMALYTICS_USERNAME`     | Your Scamalytics username   | **Yes**  |
| `SCAMALYTICS_API_KEY`      | Your Scamalytics API key    | **Yes**  |
| `SCAMALYTICS_API_BASE_URL` | Your Scamalytics Base URL   | **Yes**  |

5.  **Get Your Worker URL:** After deployment, Cloudflare will provide a URL (e.g., `https://your-bot-worker.pages.dev`). **Copy this URL.** This is your main `WORKER_URL`.

### Part 4: Run the Telegram Bot

Finally, run the Python bot on your server.

1.  **Connect to Your Server** and clone your forked repository:
    ```bash
    git clone [https://github.com/YOUR_USERNAME/ProxyIP-Tel-Bot.git](https://github.com/YOUR_USERNAME/ProxyIP-Tel-Bot.git)
    cd ProxyIP-Tel-Bot
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set Environment Variables:**

    #### For Linux (e.g., Ubuntu, CentOS) or macOS
    * **Temporary (current session only):**
        ```bash
        export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
        export WORKER_URL="[https://your-bot-worker.pages.dev](https://your-bot-worker.pages.dev)"
        ```
    * **Permanent (recommended):** Add the `export` lines to your `~/.bashrc` or `~/.profile` file, then run `source ~/.bashrc`.

    #### For Windows
    * **Command Prompt (Temporary):**
        ```cmd
        set BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
        set WORKER_URL="[https://your-bot-worker.pages.dev](https://your-bot-worker.pages.dev)"
        ```
    * **PowerShell (Temporary):**
        ```powershell
        $env:BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
        $env:WORKER_URL="[https://your-bot-worker.pages.dev](https://your-bot-worker.pages.dev)"
        ```

4.  **Run the Bot Persistently:**
    * Start a new `screen` session: `screen -S proxybot`
    * Run the script: `python proxy-ip-bot.py`
    * Detach from the session: Press `Ctrl+A`, then `D`.

Your bot is now fully deployed and operational.

* To **re-attach** to the session later, use: `screen -r proxybot`
* To **stop** the bot, re-attach and press `Ctrl+C`.
* Made with ❤️‍🔥 by [mehdi-hexing](t.me/mehdiasmart)
