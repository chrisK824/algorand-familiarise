import sys
import json
import base64
from datetime import datetime, timezone, timedelta
from random import randint

import matplotlib.pyplot as plt
from time import sleep
import pandas as pd
import algosdk.constants
from algosdk import account, mnemonic
from algosdk.v2client import algod, indexer
from algosdk.transaction import PaymentTxn, AssetConfigTxn, AssetOptInTxn, AssetTransferTxn, ApplicationCallTxn
from tinyman.v2.client import TinymanV2TestnetClient
from algosdk import error
from tinyman.assets import AssetAmount

ALGOD_ADDRESS = "https://testnet-api.algonode.network"
ALGOD_TOKEN = ""
HEADERS = {
    algosdk.constants.ALGOD_AUTH_HEADER: ALGOD_TOKEN
}
ALGOD_CLIENT = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS, HEADERS)

INDEXER_API_URL = "https://testnet-idx.algonode.network"
INDEXER_HEADERS = {
    algosdk.constants.INDEXER_AUTH_HEADER : ALGOD_TOKEN
}
INDEXER_CLIENT = indexer.IndexerClient(indexer_address=INDEXER_API_URL,
                                       indexer_token=ALGOD_TOKEN,
                                       headers=INDEXER_HEADERS)
AVG_BLOCK_TIME = 4.5
USDC_INDEX = 10458941
ALGO_INDEX = 0
TINYMAN_APP_ID = 148607000

def create_account():
    private_key, address = account.generate_account()
    mnemonic_phrase = mnemonic.from_private_key(private_key)
    print(f"Created account with address: {address} and mnemonic phrase {mnemonic_phrase} storing it in file")
    with open("accounts.txt", 'a') as f:
        f.write(f"{address},{private_key},{mnemonic_phrase}\n")


def get_accounts():
    accounts = []
    with open("accounts.txt", 'r') as f:
        lines = f.readlines()
        for line in lines:
            data = line.split(',')
            if len(data) == 3:
                accounts.append(data[0])
    return accounts

def get_receivers():
    receivers = []
    with open("receiver_addr.txt", 'r') as f:
        lines = f.readlines()
        for line in lines:
            receivers.append(line.split('\n')[0])
    return receivers

def get_unique_venue_mnemonic():
    mnemonic = None
    with open("unique_venue_one_mnemonic.txt", 'r') as f:
        mnemonic = f.readline()
    return mnemonic

def get_address_private_key(addr):
    private_key = None
    with open("accounts.txt", 'r') as f:
        lines = f.readlines()
        for line in lines:
            data = line.split(',')
            if len(data) == 3 and data[0] == addr:
                private_key = data[1]
                return private_key
    return private_key


def wait_for_confirmation(client, txid):
    last_round = client.status().get('last-round')
    txinfo = client.pending_transaction_info(txid)
    while not (txinfo.get('confirmed-round') and txinfo.get('confirmed-round') > 0):
        print('Waiting for confirmation')
        last_round += 1
        client.status_after_block(last_round)
        txinfo = client.pending_transaction_info(txid)
    print('Transaction confirmed in round', txinfo.get('confirmed-round'))
    return txinfo


def perform_payment_transaction():
    params = ALGOD_CLIENT.suggested_params()
    sender = str(input("Enter your account address:\n"))
    receiver = str(input("Enter the account's address to which you want to send algos:\n"))
    amount = int(input("Enter the amount of microalgos you want to send:\n"))
    use_flat_fee = str(input("Use minimum fee for transaction? y/n\n"))
    if use_flat_fee == "n":
        params.flat_fee = True
        fee_input = int(input("Using flat fee, enter integer in microalgos for the fee to be used:\n"))
        params.fee = max(params.min_fee, fee_input)
    print(f"Fee to be used for transaction: {params.fee}")
    note = str(input("Leave an encoded note for the transaction:\n"))
    json_note = {
        "key": note
    }
    string_json_note = json.dumps(json_note)

    unsigned_txn = PaymentTxn(sender, params, receiver, amount, None, string_json_note.encode())
    private_key = get_address_private_key(addr=sender)
    signed_txn = unsigned_txn.sign(private_key)
    try:
        signed_txn_id = ALGOD_CLIENT.send_transaction(signed_txn)
        print(f"The transaction has been sent and has the ID: {signed_txn_id}")
        txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_txn_id)
    except Exception as err:
        print("Transaction confirmation error!")
        print(err)
        return

    print(f'Transaction information: {json.dumps(txn_cfm, indent=4)}')
    decoded_note = base64.b64decode(txn_cfm['txn']['txn']['note']).decode()
    print(f"Decoded note: {decoded_note}")
    decoded_note = json.loads(decoded_note)
    print(f'My decoded json value from field "key" : {decoded_note["key"]}')


def create_asset_transaction():
    params = ALGOD_CLIENT.suggested_params()
    sender = str(input("Enter your account address:\n"))
    asset_name = str(input("Name the asset:\n"))
    unit_name = str(input("Name the unit for the asset:\n"))
    total = int(input(f"Enter the total amount of {unit_name} for asset {asset_name}:\n"))
    manager = sender
    reserve = sender
    freeze = sender
    clawback = str(input(f"Does the asset {asset_name} have clawback? y/n\n"))
    if clawback == 'y':
        clawback = sender
    else:
        clawback = ""
    url = ""
    decimals = int(input(f"Enter the decimals for unit {unit_name} of asset {asset_name}:\n"))
    asset_cfg_txn = AssetConfigTxn(sender=sender, sp=params, total=total, default_frozen=False, unit_name=unit_name,
                                   asset_name=asset_name, manager=manager, reserve=reserve, freeze=freeze,
                                   clawback=clawback, url=url, decimals=decimals, strict_empty_address_check=False)
    private_key = get_address_private_key(addr=sender)
    signed_asset_cfg_txn= asset_cfg_txn.sign(private_key)
    try:
        signed_txn_id = ALGOD_CLIENT.send_transaction(signed_asset_cfg_txn)
        print(f"The transaction has been sent and has the ID: {signed_txn_id}")
        txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_txn_id)
    except Exception as err:
        print("Transaction confirmation error!")
        print(err)
        return

    # print(f'Transaction information: {json.dumps(txn_cfm, indent=4)}')
    print(f"Asset {asset_name} has been created with total amount of {unit_name} {total} and has id {txn_cfm['asset-index']}")


def get_account_info(addr=None):
    if not addr:
        addr = str(input("Enter an account address:\n"))
    acc_info = ALGOD_CLIENT.account_info(address=addr)
    return acc_info


def get_transactions_for_account(addr=None):
    if not addr:
        addr = str(input("Enter account's address to search transactions for:\n"))
    fetched_transactions = []
    next_token = ""
    num_tx = 1
    while num_tx > 0:
        response = INDEXER_CLIENT.search_transactions(address=addr, next_page=next_token)
        transactions = response['transactions']
        fetched_transactions += transactions
        num_tx = len(transactions)
        if num_tx > 0:
            print(f"Transactions fetched {num_tx}")
            next_token = response['next-token']
    
    for transaction in fetched_transactions:
        print(json.dumps(transaction, indent=2))

    return fetched_transactions

def search_account_transactions_by_note():
    addr = str(input("Enter account's address to search transactions for:\n"))
    note_prefix = str(input("Enter transaction note prefix to look for:\n"))
    note_prefix_encoded = note_prefix.encode()
    fetched_transactions = INDEXER_CLIENT.search_transactions(address=addr, note_prefix=note_prefix_encoded)
    return fetched_transactions


def search_account_transactions_per_timespan(addr=None):
    if not addr:
        addr = str(input("Enter account's address to search transactions for:\n"))
    start_date = str(input("Enter start date:\n"))
    end_date = str(input("Enter end date:\n"))
    start_date = datetime.strptime(start_date, "%d-%m-%Y")
    start_date = start_date.date()
    end_date = datetime.strptime(end_date, "%d-%m-%Y")
    end_date = end_date.date()
    fetched_transactions = INDEXER_CLIENT.search_transactions(address=addr, start_time=start_date, end_time=end_date)
    return fetched_transactions


def analyze_account_transactions_per_timespan():
    addr = str(input("Enter account address:\n"))
    start_date = str(input("Enter start date:\n"))
    end_date = str(input("Enter end date:\n"))
    start_date = datetime.strptime(start_date, "%d-%m-%Y")
    end_date = datetime.strptime(end_date, "%d-%m-%Y")

    fetched_transactions = []

    print(f"Fetching transactions for timespan {start_date}-{end_date}")
    next_token = ""
    num_tx = 1
    while num_tx > 0:
        response = INDEXER_CLIENT.search_transactions_by_address(
            address=addr,
            start_time=start_date.astimezone(timezone.utc).isoformat('T'),
            end_time=end_date.astimezone(timezone.utc).isoformat('T'),
            next_page=next_token,
            limit=10000
        )
        transactions = response['transactions']
        fetched_transactions += transactions
        num_tx = len(transactions)
        if num_tx > 0:
            print(f"Transactions fetched {num_tx}")
            next_token = response['next-token']

    df = pd.DataFrame(fetched_transactions)
    if 'asset-transfer-transaction' in df.index:
        df = pd.concat([df.drop(['asset-transfer-transaction'], axis=1),
                        df['asset-transfer-transaction'].apply(
                            pd.Series).add_suffix('-asset-txn').drop(
                            ['0-asset-txn'], axis=1, errors='ignore')], axis=1)

    df = pd.concat([df.drop(['payment-transaction'], axis=1),
                    df['payment-transaction'].apply(
                        pd.Series).add_suffix('-pay-txn').drop(['0-pay-txn'], axis=1, errors='ignore')], axis=1)
    if 'asset-config-transaction' in df.index:
        df = pd.concat([df.drop(['asset-config-transaction'], axis=1),
                        df['asset-config-transaction'].apply(pd.Series).add_suffix(
                            '-asst-cnfg-txn').drop(
                            ['0-asst-cnfg-txn'], axis=1, errors='ignore')], axis=1)

    if 'signature' in df.index:
        df = pd.concat([df.drop(['signature'], axis=1),
                        df['signature'].apply(pd.Series).add_suffix('-sig').drop(
                            ['0-sig'], axis=1, errors='ignore')], axis=1)

    # format the unix seconds to human readble date format
    df['date'] = pd.to_datetime(df['round-time'], unit='s').dt.date
    print(f"Number of transactions: {len(df)}")
    print("Count of transactions grouped per kind:")
    print(df['tx-type'].value_counts())
    print(f"Total amount of algos transferred {df['amount-pay-txn'].sum()}")
    df['day'] = pd.to_datetime(df['date']).dt.day_name()
    df['day'].value_counts().plot()
    # print(f"Unique number of assets transferred {df['asset-id-asset-txn'].nunique()}")
    plt.show()


def analyze_assets():
    assets_num = int(input("How many asset to fetch?\n"))
    fetched_assets = []
    next_token = ""
    num_tx = 1
    while num_tx > 0 and len(fetched_assets) < assets_num:
        response = INDEXER_CLIENT.search_assets(
            next_page=next_token,
            limit=min(assets_num, 100000)
        )
        assets = response['assets']
        fetched_assets += assets
        num_tx = len(assets)
        if num_tx > 0:
            next_token = response['next-token']

    print(f"Fetched {len(fetched_assets)} assets")

    assets = pd.DataFrame(fetched_assets)
    assets = pd.concat([assets.drop(['params'], axis=1),
                        assets['params'].apply(pd.Series)], axis=1)

    fetched_transactions = []
    for _, row in assets.iterrows():
        next_token = ""
        num_tx = 1
        while num_tx > 0:
            response = INDEXER_CLIENT.search_transactions(
                asset_id=row['index'],
                next_page=next_token,
                limit=1000
            )
            transactions = response['transactions']
            fetched_transactions += transactions
            num_tx = len(transactions)
            if num_tx > 0:
                print(f"Fetched {num_tx} transactions for asset {row['index']}")
                next_token = response['next-token']

    df = pd.DataFrame(fetched_transactions)
    df = pd.concat([df.drop(['asset-transfer-transaction'], axis=1),
                    df['asset-transfer-transaction'].apply(
                        pd.Series).add_suffix('-asset-txn').drop(
                        ['0-asset-txn'], axis=1, errors='ignore')], axis=1)

    assets_counts = pd.DataFrame(df['asset-id-asset-txn'].value_counts()).join(
        assets[['index', 'name', 'unit-name']].set_index('index'))
    assets_counts.sort_values(by='asset-id-asset-txn', inplace=True, ascending=False)
    pd.DataFrame(assets_counts.groupby(
        'unit-name')['asset-id-asset-txn'].sum()).nlargest(10, 'asset-id-asset-txn').plot()
    plt.show()


def opt_in_asa():
    my_addr = str(input("Enter your account's address:\n"))
    target_addr = str(input("Enter account address that hold the asset you want to opt in:\n"))
    holder_account_info = get_account_info(target_addr)
    account_assets = holder_account_info["created-assets"]
    print(f"Account {target_addr} has created the assets:")
    for asset in account_assets:
        print(f"Total {asset['params']['total']} {asset['params']['unit-name']}"
              f"of asset {asset['params']['name']} with ID {asset['index']}")
    asa_index = int(input(f"Enter ID of asset you want to opt in:\n"))
    params = ALGOD_CLIENT.suggested_params()
    try:
        unsigned_asa_opt_in_txn = AssetOptInTxn(sender=my_addr, sp=params, index=asa_index)
        private_key = get_address_private_key(addr=my_addr)
        signed_asa_opt_in_txn = unsigned_asa_opt_in_txn.sign(private_key)
        signed_asa_opt_in_txn_id = ALGOD_CLIENT.send_transaction(signed_asa_opt_in_txn)
        print(f"The transaction has been sent and has the ID: {signed_asa_opt_in_txn_id}")
        signed_asa_opt_in_txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_asa_opt_in_txn_id)
    except Exception as err:
        print("Transaction confirmation error!")
        print(err)
        return
    # print(f'Transaction information: {json.dumps(signed_asa_opt_in_txn_cfm, indent=4)}')


def transfer_asa_units(snd=None, rcv=None, asa_index=None, amount=None, note=None):
    params = ALGOD_CLIENT.suggested_params()
    if not snd:
        snd = str(input("Enter your account address:\n"))
    if not rcv:
        rcv = str(input("Enter the account's address to which you want to transfer ASA units:\n"))
    if not asa_index:
        asa_index = int(input("Enter the index of ASA you want to send:\n"))
    if not amount:
        amount = int(input("Enter the amount of ASA you want to send:\n"))
    params.flat_fee = True
    params.fee = params.min_fee
    if not note:
        note = str(input("Leave an encoded note for the transaction:\n"))

    unsigned_asset_txn = AssetTransferTxn(sender=snd, sp=params, receiver=rcv, index=asa_index, amt=amount, note=note)
    private_key = get_address_private_key(addr=snd)
    signed_asset_txn = unsigned_asset_txn.sign(private_key)
    try:
        signed_asset_txn_id = ALGOD_CLIENT.send_transaction(signed_asset_txn)
        print(f"The transaction has been sent and has the ID: {signed_asset_txn_id}")
        asset_txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_asset_txn_id)
    except Exception as err:
        print("Transaction confirmation error!")
        print(err)
        return

    # print(f'Transaction information: {json.dumps(asset_txn_cfm, indent=4)}')
    decoded_note = base64.b64decode(asset_txn_cfm['txn']['txn']['note']).decode()
    print(f"Decoded note: {decoded_note}")


def reward_investors_in_asa():
    addr = input("Enter your account address:\n")
    transactions = get_transactions_for_account(addr)
    blacklist_addresses = [
        "HZ57J3K46JIJXILONBBZOHX6BKPXEM2VVXNRFSUED6DKFD5ZD24PMJ3MVA",
        "ARVGBBBRNURYHWRXQDHUOZFN6PYXIE4CWRD77PJIBAR5NRL3YGVA",
        "GD64YIY3TWGDMCNPP553DZPPR6LDUSFQOIJVFDPPXWEG3FVOJCCDBBHU5A"
    ]
    payment_transactions_received = [
        curr_transaction for curr_transaction in transactions
        if curr_transaction['tx-type'] == "pay"
        and curr_transaction['payment-transaction']['receiver'] == addr
        and curr_transaction['sender'] not in blacklist_addresses
    ]
    total_investment = sum([curr_transaction['payment-transaction']['amount']
                            for curr_transaction in payment_transactions_received])
    investors_contribution = [
        {
            "address": curr_transaction['sender'],
            "percentage": curr_transaction['payment-transaction']['amount']/total_investment
        }
        for curr_transaction in payment_transactions_received
    ]
    my_account_info = get_account_info(addr)
    print(f"Your account assets:")
    account_assets = my_account_info["assets"]
    for asset in account_assets:
        print(f"{asset['amount']} of asset with ID {asset['asset-id']}")

    asa_total_to_distribute = 0

    asa_index = int(input(f"Enter ID of asset you want to reward investors for:\n"))
    for asset in account_assets:
        if asset['asset-id'] == asa_index:
            asa_total_to_distribute = int(input(f"Enter amount of asset with ID "
                                                f"{asset['asset-id']} to reward to investors:\n"))
            break

    for investor_contributor in investors_contribution:
        amount_to_distribute = int(investor_contributor['percentage']*asa_total_to_distribute)
        transfer_asa_units(
            snd=addr,
            rcv=investor_contributor['address'],
            asa_index=asa_index,
            amount=amount_to_distribute,
            note= f"Rewarding you with {amount_to_distribute} units of asset with ID {asa_index}"
        )


def future_payment_transaction(sender, params, receiver, amount, note):
    status = ALGOD_CLIENT.status()
    current_round = status.get('last-round')
    while params.first > current_round:
        # print(f"First valid round for scheduled transaction: {params.first}")
        # print(f"Current round: {current_round}, going to sleep for {AVG_BLOCK_TIME}")
        sleep(AVG_BLOCK_TIME)
        status = ALGOD_CLIENT.status()
        current_round = status.get('last-round')

    print("Performing scheduled transaction!")
    unsigned_txn = PaymentTxn(sender, params, receiver, amount, None, note.encode())
    private_key = get_address_private_key(addr=sender)
    signed_txn = unsigned_txn.sign(private_key)
    try:
        signed_txn_id = ALGOD_CLIENT.send_transaction(signed_txn)
        print(f"The transaction has been sent and has the ID: {signed_txn_id}")
        txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_txn_id)
    except Exception as err:
        print(err)
        return
    decoded_note = base64.b64decode(txn_cfm['txn']['txn']['note']).decode()
    print(f"Decoded note: {decoded_note}")
    return


def schedule_payment_transaction():
    sender = str(input("Enter your account address:\n"))
    receiver = str(input("Enter the account's address to which you want to send algos:\n"))
    amount = int(input("Enter the amount of microalgos you want to send:\n"))
    seconds_delay = int(input("Enter the offset window start in future for the transaction in seconds:\n"))
    note = str(input("Leave an encoded note for the transaction:\n"))
    params = ALGOD_CLIENT.suggested_params()
    params.flat_fee = True
    params.fee = params.min_fee
    params.first = params.first + int(seconds_delay/AVG_BLOCK_TIME)
    params.last = params.first + 1000
    from threading import Thread
    scheduled_transaction_thread = Thread(target=future_payment_transaction,
                                          args=(sender, params, receiver, amount, note,))
    scheduled_transaction_thread.start()
    return

def get_unique_note_prefix():
    unique_mnemonic = get_unique_venue_mnemonic()
    venue_private_key = mnemonic.to_private_key(unique_mnemonic)
    return venue_private_key

def opt_in_usdc(address):
    params = ALGOD_CLIENT.suggested_params()
    try:
        print(f"Account {address} is opting in USDC asset")
        unsigned_asa_opt_in_txn = AssetOptInTxn(sender=address, sp=params, index=USDC_INDEX)
        private_key = get_address_private_key(addr=address)
        signed_asa_opt_in_txn = unsigned_asa_opt_in_txn.sign(private_key)
        signed_asa_opt_in_txn_id = ALGOD_CLIENT.send_transaction(signed_asa_opt_in_txn)
        signed_asa_opt_in_txn_cfm = wait_for_confirmation(ALGOD_CLIENT, signed_asa_opt_in_txn_id)
        print(f"Account {address} has opted in USDC successfully in round {signed_asa_opt_in_txn_cfm.get('confirmed-round')}")
    except Exception as err:
        print("Transaction confirmation error!")
        print(err)
        return
    
def convert_algo_to_usdc_tinyman_unote(account_addr, unit_amount, reversed):
    note_prefix = get_unique_note_prefix()
    note_prefix = note_prefix + account_addr
    client = TinymanV2TestnetClient(algod_client=ALGOD_CLIENT, user_address=account_addr, client_name=note_prefix)
    USDC = client.fetch_asset(USDC_INDEX)
    ALGO = client.fetch_asset(ALGO_INDEX)
    pool = client.fetch_pool(USDC, ALGO)

    if reversed:
        amount_in = AssetAmount(pool.asset_1, unit_amount)
        print(f"Account {account_addr} is converting {unit_amount} micro USDCs to Algos")
    else:
        amount_in = AssetAmount(pool.asset_2, unit_amount)
        print(f"Account {account_addr} is converting {unit_amount} micro Algos to USDC")

    quote = pool.fetch_fixed_input_swap_quote(
        amount_in=amount_in,
    )
    txn_group = pool.prepare_swap_transactions_from_quote(quote=quote)
    sender_private_key = get_address_private_key(addr=account_addr)
    txn_group.sign_with_private_key(account_addr, sender_private_key)

    try:
        txn_info = client.submit(txn_group, wait=True)
        print(f"Conversion confirmed in round {txn_info.get('confirmed-round')}")
    except Exception as e:
        print("Group transaction failed")
        print(e)
        convert_algo_to_usdc_tinyman_unote(account_addr, unit_amount, reversed=not reversed)


def convert_algos_to_usdc_via_tinyman(reversed=False):
    transactions_num = int(input("Enter a transactions number to perform with pool of sender accounts:\n"))
    accounts = get_accounts()

    for i in range(0, transactions_num):
        micro_units = randint(4,9)*10**2
        account_index = randint(0, len(accounts)-1)
        account_addr = accounts[account_index]
        account_assets = get_account_info(account_addr)['assets']
        try:
            if all([USDC_INDEX != asset['asset-id'] for asset in account_assets]):
                print(f"Account {account_addr} hasn't opted in USDC")
                opt_in_usdc(account_addr)
            print(i)
            convert_algo_to_usdc_tinyman_unote(account_addr, micro_units, reversed)
        except Exception:
            pass
        

def fetch_unique_note_transactions():
    start_time = datetime.now()
    note_prefix = get_unique_note_prefix()
    note_prefix = 'tinyman/v2:j{"origin":"' + note_prefix
    fetched_transactions = []
    next_token = ""
    num_tx = 1
    while num_tx > 0:
        response = INDEXER_CLIENT.search_transactions(application_id=TINYMAN_APP_ID, note_prefix=note_prefix.encode(), next_page=next_token, txn_type="appl", limit=1000)
        transactions = response['transactions']
        fetched_transactions += transactions
        num_tx = len(transactions)
        if num_tx > 0:
            next_token = response['next-token']
    end_time = datetime.now()
    print(f"Fetched {len(fetched_transactions)} transactions in {end_time-start_time}")

    confirmed_sender_transactions = []
    for transaction in fetched_transactions:
        decoded_note = base64.b64decode(transaction['note']).decode()
        sender_addr = decoded_note.split(note_prefix)[1].split('"')[0]
        if sender_addr == transaction['sender']:
            confirmed_sender_transactions.append(transaction)
    print(f"{len(confirmed_sender_transactions)} transactions confirmed with sender address in note field")
    return confirmed_sender_transactions

def calculate_total_converted(index, name):
    transactions = fetch_unique_note_transactions()
    micro_units_converted = 0
    for transaction in transactions:
        if 'inner-txns' in transaction:
            for inner_transaction in  transaction['inner-txns']:
                if inner_transaction['tx-type'] == "axfer":
                    key = 'asset-transfer-transaction'
                elif inner_transaction['tx-type'] == "pay":
                    key = 'payment-transaction'
                    if key in inner_transaction:
                        if key == 'payment-transaction':
                            amount = inner_transaction[key]['amount']
                        elif inner_transaction[key]['asset-id'] == index:
                            amount = inner_transaction[key]['amount']
                        micro_units_converted = micro_units_converted + amount
    print(f"Total converted {name}s: {micro_units_converted/1000000}")

def get_transactions_in_same_group(txid=None):
    if not txid:
        txid = str(input("Enter a transaction ID:\n"))
    
    txn = INDEXER_CLIENT.search_transactions(txid=txid)['transactions'][0]
    block_info = INDEXER_CLIENT.block_info(block=txn['confirmed-round'])
    # print(json.dumps(block_info))
    grp_id = txn['group']
    block_transactions = INDEXER_CLIENT.search_transactions(block=txn['confirmed-round'])
    group_txns = [txn for txn in block_transactions['transactions'] if txn['group'] == grp_id]
    for txn in group_txns:
        print(json.dumps(txn, indent=2))

def get_accounts_assets(addr=None, asset_id=None):
    if not addr:
        addr = str(input("Enter your algorand address:\n"))
    assets = INDEXER_CLIENT.lookup_account_assets(address=addr)
    print(assets)

def print_menu():
    print(
        """
Menu selection
    1. Create account
    2. Payment transaction
    3. Print my account info
    4. Create an asset
    5. Get account's transactions
    6. Search transactions of account by note
    7. Search transactions of account by timespan
    8. Opt in account's asset
    9. Reward investors that have opted in your ASA
    10. Transfer ASA units
    11. Analyze account transactions per timespan
    12. Analyze assets
    13. Schedule payment transaction
    14. Convert Algos to USDCs via tinyman with note prefix
    15. Convert USDCs to Algos via tinyman with note prefix
    16. Fetch transactions with unique note prefix from tinyman application
    17. Calculated total USDCs converted in tinyman via python
    18. Calculated total Algos converted in tinyman via python
    19. Get transactions in same group
    20. Get account's assets
    21. Exit
"""
    )


print_menu()

selection = int(input())

while True:
    if selection == 1:
        create_account()
        print_menu()
    elif selection == 2:
        perform_payment_transaction()
        print_menu()
    elif selection == 3:
        account_info = get_account_info()
        print("Your account information: \n")
        print(json.dumps(account_info, indent=2))
        print_menu()
    elif selection == 4:
        create_asset_transaction()
        print_menu()
    elif selection == 5:
        txns_fetched = get_transactions_for_account()
        print(json.dumps(txns_fetched, indent=2))
        print_menu()
    elif selection == 6:
        fetched_txns = search_account_transactions_by_note()
        print(json.dumps(fetched_txns, indent=2))
        print_menu()
    elif selection == 7:
        fetched_txns = search_account_transactions_per_timespan()
        print(json.dumps(fetched_txns, indent=2))
        print_menu()
    elif selection == 8:
        opt_in_asa()
        print_menu()
    elif selection == 9:
        reward_investors_in_asa()
        print_menu()
    elif selection == 10:
        transfer_asa_units()
        print_menu()
    elif selection == 11:
        analyze_account_transactions_per_timespan()
        print_menu()
    elif selection == 12:
        analyze_assets()
        print_menu()
    elif selection == 13:
        schedule_payment_transaction()
        print_menu()
    elif selection == 14:
        convert_algos_to_usdc_via_tinyman()
        print_menu()
    elif selection == 15:
        convert_algos_to_usdc_via_tinyman(reversed=True)
        print_menu()
    elif selection == 16:
        fetch_unique_note_transactions()
        print_menu()
    elif selection == 17:
        calculate_total_converted(index=USDC_INDEX, name="USDC")
        print_menu()
    elif selection == 18:
        calculate_total_converted(index=ALGO_INDEX, name="Algo")
        print_menu()
    elif selection == 19:
        get_transactions_in_same_group()
        print_menu()
    elif selection == 20:
        get_accounts_assets()
        print_menu()
    elif selection == 21:
        print("Exiting")
        sys.exit(0)
    else:
        print("Not supported option")
        print_menu()
    selection = int(input())
