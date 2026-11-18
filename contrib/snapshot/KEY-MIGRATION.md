# BTGS Old Wallet to New Chain: Key Migration Guide (DRAFT)

Nov 18, 2026 · GreenMiner

## What this guide does

Your old BTGS coins follow your private key: the same key controls the same balance on the new chain, at a new address that starts with **B**. Two small free tools convert each old key into its new key and new address: a web page, `btgs-key-migration.html` (works on Windows, Mac and Linux, nothing to install), and a Python script, `btgs_migrate_keys.py`. Both give the same result. Both run on your own computer, offline, and never send anything anywhere.

|  | Old chain | New chain |
| --- | --- | --- |
| Address | starts with `G`, or `bcg1q...` (SegWit) | starts with `B` |
| Private key (WIF) | old format | starts with `P` |

The new chain starts from a snapshot of the old chain, and the balances are paid out in block 1. You do not need to do anything until the snapshot list is published. You can prepare now with the steps below.

## Safety rules (read first)

Your private keys are your coins: anyone who sees them can take them. Follow these rules every time.

1. **Work offline.** Run the tool on your own computer. Disconnect from the internet while your keys are on screen or in a file if you can.
2. **Never share keys.** No one from the BTGS team will ever ask for your private keys, your wallet file, your seed words or your output file. Anyone who asks is trying to steal from you.
3. **Never post the output.** Do not post the key files, or screenshots of them, in Discord, forums, e-mail or cloud notes.
4. **Delete the files when you are done.** That means the exported old keys, `btgs-import.json` and `btgs-new-keys.txt`. The tool creates the last two so that only you can read them.
5. **Download the tool only from the official repository:** `github.com/BTGS-Community/btgs-core`, folder `contrib/snapshot/`. Do not use copies from anyone else.
6. **Test first.** Try the steps with a small wallet or a single address before you do your main wallet.

## Step 1: Export your old keys

Use your OLD BTGS wallet, the one that holds your coins today. Open it, then go to **Window > Console**. If the wallet is encrypted, unlock it first for a short time:

```
walletpassphrase "your passphrase" 120
```

Then run the command that matches your wallet. If you are not sure which one, try the first. A newer wallet will accept it, and an older one will say the command is not available.

```
listdescriptors true
```

Copy the whole output into a plain text file on your own computer, for example `descriptors.json`. For an older wallet file, run this instead (it writes a file to the folder you name):

```
dumpwallet "C:/keys/old-wallet-keys.txt"
```

If you only have single private keys, you can also put them in a text file, one per line. The tool accepts all three forms. When you are done, lock the wallet again with `walletlock`.

## Step 2: Convert the keys with the tool

**Option A: the web page (easiest).** Download `btgs-key-migration.html` and the snapshot list `btgs-snapshot-<height>.csv` from the official repository (`github.com/BTGS-Community/btgs-core`, folder `contrib/snapshot/`). Compare the file's SHA-256 checksum with the one the team publishes (draft version: 2e289362a15684a1241ee0f2dbbaf70d04d3faae62e2a03cf8e0b8659121957a). Switch off your internet, then double-click the file to open it in your browser. Two boxes at the top must say that you are offline and that the self-test passed. Choose your old keys file from Step 1 (or paste the text), choose the snapshot list, and press **Convert my keys**. Check the table and the total, then press **Download import line** to save `btgs-import.json`, and go on to Step 3. Press **Clear everything** when you are done.

**Option B: the Python tool** (below) gives exactly the same result. Use it if you prefer the command line.

Option B: Python. You need Python 3 (no extra packages) and two files in one folder: `btgs_migrate_keys.py` from the official repository, and the published snapshot list `btgs-snapshot-<height>.csv`. First check that the tool works on your computer. It must print `selftest OK`:

```
python3 btgs_migrate_keys.py --selftest
```

Then run it on the file from Step 1. Use `--descriptors` for the `listdescriptors` output, or `--wif` for a `dumpwallet` file or a list of single keys. On Windows, use `python` if `python3` is not found.

```
python3 btgs_migrate_keys.py --descriptors descriptors.json --snapshot btgs-snapshot-<height>.csv
```

The tool prints a table with each old address, its new `B...` address and the balance it gets on the new chain, and a total at the bottom. Check that the total matches what you expect. Only keys that appear in the snapshot list are kept. Your new private keys are saved in two files: `btgs-import.json` (one line, used in Step 3) and `btgs-new-keys.txt` (a list, which most people never need). Use `--json` and `--out` to pick other file names.

If the tool prints `WARNING: list address differs`, stop and ask for help in the BTGS Discord before you import anything. Do not paste the table or the file there, only the warning line.

## Step 3: Import the new keys into the new BTGS Core wallet

Install the new BTGS Core wallet and let it sync. Open **Window > Console**. If your wallet is encrypted, unlock it first with `walletpassphrase "your passphrase" 120`. Then open `btgs-import.json` in a plain text editor such as Notepad, select everything and copy it. It is one long line that holds all your keys. In the console, type `importdescriptors`, a space and a single quote `'`, paste the line, type another single quote `'`, and press Enter. The single quotes are required: the console removes double quotes, so without them it fails with "Error parsing JSON". Your line is longer, with one entry per address:

```
importdescriptors '[{"desc":"pkh(P...)#xxxxxxxx","timestamp":0,"label":"BTGS-old"}]'
```

The answer shows `"success": true` for every key. The wallet scans the chain by itself, so there is nothing else to run. If an entry shows `"success": false`, copy the error message (never the key) and ask for help.

When the scan has finished and block 1 has matured, your balance shows in the wallet. Check it against the total the tool printed in Step 2. The file `btgs-new-keys.txt` is only for wallets created with "Descriptor Wallet" switched off. Most people never need it.

An imported key is not part of your wallet's recovery words (mnemonic). Right after importing, make a fresh backup of the wallet file with **File > Backup Wallet** and keep it somewhere safe. Then delete `btgs-import.json`, `btgs-new-keys.txt`, the exported old keys and `descriptors.json`, and lock the wallet again.

## What does not carry over automatically

Only coins on normal single-key addresses carry over: legacy addresses that start with `G`, and SegWit addresses that start with `bcg1q` (42 characters). Coins on any other address type are not paid out on the new chain, because the tool cannot derive a single key for them.

| Address type | Carries over? | What to do |
| --- | --- | --- |
| Legacy `G...` | Yes | Nothing |
| SegWit `bcg1q...` (42 characters) | Yes | Nothing |
| P2SH, including wrapped SegWit (`sh(wpkh)`) | No | Move the coins on the old chain to a `G...` or `bcg1q...` address before the snapshot |
| Multisig (P2SH or P2WSH) | No | Move the coins on the old chain first; all required signers must sign |
| Taproot | No | Move the coins on the old chain first |

The snapshot height will be announced by the team. Coins you move after that height will not be included, so move them early. Coins held on an exchange are handled by the exchange, and the team is working with exchanges separately. Follow the exchange's own announcement.

## Troubleshooting

| What you see | Likely cause | What to do |
| --- | --- | --- |
| `not an extended PRIVATE key (use: listdescriptors true)` | The export was made without `true` | Run `listdescriptors true` again and save the new output |
| `skipped: sh(...) is not a single-key address type` | Your coins are on a P2SH, multisig or Taproot address | See the table above; move them on the old chain first |
| `No keys that are in the snapshot list were found` | Wrong wallet or file, an address type that does not carry over, or a snapshot list from the wrong network (the testnet list is for testing only) | Check that you used the right wallet and the official list for the real snapshot |
| `WARNING: list address differs` | The list and your key do not agree | Stop. Do not import. Ask for help with the warning line only |
| `importdescriptors` asks for the wallet passphrase | The new wallet is encrypted | Unlock it with `walletpassphrase "your passphrase" 120`, then repeat |
| An entry shows `"success": false` | The line was copied only in part, or it is from the wrong network | Copy the whole line again from `btgs-import.json` and repeat. Real keys start with `P` |
| Balance is 0 after the import | The wallet is still scanning, or block 1 has not matured | Wait until the wallet is synced and the scan has finished, and for the team's announcement about block 1 |

For help, ask in the BTGS Discord. Show only the error message. Never post private keys, the output file, the descriptors, wallet files or recovery words, and ignore anyone who asks for them.
