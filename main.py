#!/usr/bin/env python3
import threading
import time
import secrets
import hashlib
import requests
import base58
import logging

from ecdsa import SigningKey, SECP256k1
from Crypto.Hash import RIPEMD160
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler

# ── CONFIG ─────────────────────────────────
TOKEN       = "7422645915:AAHuS6uYjZDnv_BvEK54GbozRTOmxwykbT8"
CHECK_EVERY = 1000
ALPHABET    = "abcdef0123456789"
API_URL     = "https://blockstream.info/api/address/{}"
LOG_FILE    = "bot.log"
# ──────────────────────────────────────────

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Track each user’s scan count
user_scan_status = {}

# Message templates
START_MESSAGE = (
    "✨ Awesome! Starting a scan on BTC... 🌍\n"
    "🌱 Private key : .......\n"
    "🏦 Address: .......\n"
    "🎯 Balance: .......\n"
    "🔄 Scanned wallets: 0"
)

PROGRESS_TEMPLATE = (
    "```\n"
    "✨ Scanning BTC...\n"
    "🌱 Private key : {privatekey}\n"
    "🏦 Address: {address}\n"
    "🎯 Balance: {balance} sats\n"
    "🔄 Wallets scanned: {scanned}\n"
    "⏳ Working hard to find balances! 🌟\n"
    "```"
)

FOUND_TEMPLATE = (
    "🎉 **Found a wallet with balance!**\n\n"
    "🌱 **Private key:** `{privatekey}`\n"
    "🏦 **Address:** `{address}`\n"
    "💰 **Balance:** {balance} sats\n\n"
    "🔗 *Use this wallet responsibly!*"
)


def privkey_to_address(priv_hex: str) -> str:
    priv = bytes.fromhex(priv_hex)
    sk   = SigningKey.from_string(priv, curve=SECP256k1)
    vk   = sk.verifying_key
    x    = vk.to_string()[:32]
    prefix = b'\x02' if vk.to_string()[-1] % 2 == 0 else b'\x03'
    pub_compr = prefix + x

    # SHA-256
    h1 = hashlib.sha256(pub_compr).digest()
    # RIPEMD-160 via pycryptodome
    h2 = RIPEMD160.new(h1).digest()
    versioned = b'\x00' + h2
    checksum  = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
    addr_bytes = versioned + checksum
    return base58.b58encode(addr_bytes).decode()


def get_balance_sats(address: str) -> int:
    r = requests.get(API_URL.format(address), timeout=10)
    r.raise_for_status()
    stats = r.json().get("chain_stats", {})
    return stats.get("funded_txo_sum", 0) - stats.get("spent_txo_sum", 0)


def scan_loop(bot, chat_id, message_id, user_id):
    count = 0
    while True:
        # 1) Generate a new private key
        priv_hex = "".join(secrets.choice(ALPHABET) for _ in range(64))
        # 2) Derive its BTC address
        addr = privkey_to_address(priv_hex)
        # 3) Check balance
        try:
            bal = get_balance_sats(addr)
        except Exception as e:
            logger.error(f"Error fetching balance for {addr}: {e}")
            time.sleep(1)
            continue

        count += 1
        user_scan_status[user_id]['wallets_scanned'] = count

        # Log each check
        logger.info(f"Checked {addr}: {bal} sats (count={count})")

        # If funds found, send alert
        if bal > 0:
            logger.info(f"Found balance {bal} sats at {addr}")
            bot.send_message(
                chat_id=chat_id,
                text=FOUND_TEMPLATE.format(
                    privatekey=priv_hex,
                    address=addr,
                    balance=bal
                ),
                parse_mode=ParseMode.MARKDOWN
            )

        # Update progress every CHECK_EVERY
        if count % CHECK_EVERY == 0:
            try:
                bot.edit_message_text(
                    text=PROGRESS_TEMPLATE.format(
                        privatekey=priv_hex,
                        address=addr,
                        balance=bal,
                        scanned=count
                    ),
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning(f"Progress message update failed: {e}")
                msg = bot.send_message(
                    chat_id=chat_id,
                    text=PROGRESS_TEMPLATE.format(
                        privatekey=priv_hex,
                        address=addr,
                        balance=bal,
                        scanned=count
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
                message_id = msg.message_id


def start(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    # Initialize scan count
    user_scan_status[user_id] = {'wallets_scanned': 0}
    # Send initial message
    msg = context.bot.send_message(chat_id, START_MESSAGE)
    # Launch scanning thread
    threading.Thread(
        target=scan_loop,
        args=(context.bot, chat_id, msg.message_id, user_id),
        daemon=True
    ).start()


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

