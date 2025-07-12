# Proxy IP Tester Bot

A powerful and feature-rich Telegram bot designed to test the connectivity and gather information about proxy IPs. This bot works in tandem with a lightweight web service deployed on Cloudflare Pages/Workers for handling network requests asynchronously.

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

## Requirements

1.  A Telegram Bot Token from [@BotFather](https://t.me/BotFather).
2.  A free [Cloudflare](https://www.cloudflare.com/) account.
3.  A server or machine with Python 3.8+ and `screen` installed (standard on most Linux distros).
4.  The Python libraries listed in `requirements.txt`.

## Deployment (Step-by-Step)

Deployment is a two-part process: first, you deploy the web service, and second, you run the Python bot.

### Part 1: Deploying the Web Service (Cloudflare Worker)

This service is the backend engine that the Python bot calls to check proxies.

1.  **Log in to Cloudflare:** Go to your Cloudflare dashboard.
2.  **Navigate to Workers & Pages:** In the left sidebar, find and click on "Workers & Pages".
3.  **Create a Pages Project:** Click on the "Create application" button, then go to the "Pages" tab and click "Create a new project".
4.  **Choose Direct Upload:** Select the "Direct Upload" option.
5.  **Upload File:**
    **Download Worker:** Download [Worker.js](https://github.com/mehdi-hexing/CF-Workers-CheckProxyIP/edit/main/_worker.js) and Upload it.
7.  **Deploy:** Click the `Save and Deploy` button.
8.  **Get Your URL:** After deployment is complete, you will get a unique URL like `https://<your-project>.pages.dev`. **Copy this URL.** This is your `WORKER_URL`.

### Part 2: Running the Telegram Bot

1.  **Download the Bot Code:** Place the `bot.py` file and a `requirements.txt` file in a directory on your server.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set Environment Variables:** You must set **two** environment variables now.

    * **On Linux/macOS:**
        ```bash
        export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
        export WORKER_URL="https://<your-project>.pages.dev"
        ```

    * **On Windows (Command Prompt):**
        ```cmd
        set TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
        set WORKER_URL="https://<your-project>.pages.dev"
        ```
    Replace `"YOUR_BOT_TOKEN_HERE"` with your token and `"https://<your-project>.pages.dev"` with the URL you got from Cloudflare.

4.  **Run the Bot Persistently:** To ensure the bot keeps running even after you close your terminal, use the `screen` utility.

    a.  **Start a new screen session:**
        ```bash
        screen -S proxybot
        ```
    b.  **Run the Python script inside the screen session:**
        ```bash
        python bot.py
        ```
    c.  **Detach from the screen:** The bot is now running. To exit the screen session without stopping the bot, press `Ctrl+A` and then press `D`.

    d.  You can now safely close your terminal.

* To **re-attach** to the session later to see the logs, use: `screen -r proxybot`
* To **stop** the bot, re-attach to the screen and press `Ctrl+C`.
* Made with ❤️‍🔥 by [mehdi-hexing](t.me/mehdiasmart)
