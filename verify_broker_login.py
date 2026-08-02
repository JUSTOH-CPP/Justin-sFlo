"""
verify_broker_login.py
Fallback diagnostic for the -6 'Authorization failed' error when a bare
mt5.initialize() doesn't work even with Algo Trading enabled. Prompts
for your login/password/server interactively so nothing gets typed into
a file or committed to git.

You'll need, from your MT5 terminal (File > Login to Trade Account, or
visible in the top-right of the terminal window):
  - Login: your account number
  - Server: your broker's server name (e.g. "ICMarkets-Demo")
"""

import getpass
from modules import broker

login = input("MT5 login (account number): ").strip()
password = getpass.getpass("MT5 password (won't be shown): ")
server = input("MT5 server (e.g. Broker-Demo): ").strip()

print("\nConnecting with explicit credentials...")
try:
    broker.connect(login=login, password=password, server=server)
    print("Connected OK.")
    import MetaTrader5 as mt5
    print("Account info:", mt5.account_info())
    broker.disconnect()
except Exception as e:
    print(f"Still failed: {e}")
    print("\nIf this also fails with the same -6 error, the next things to check are:")
    print("  1. Is the account number/server exactly right (case-sensitive, no typos)?")
    print("  2. Does this account require a separate 'investor password' vs "
          "'trader password' - Python needs the trader (full access) one")
    print("  3. Is there more than one MT5 terminal installed? broker.connect(path=...) "
          "may need to point at the specific terminal64.exe")
