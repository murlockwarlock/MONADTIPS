import time
import random
import json
from web3 import Web3
from colorama import Fore, Style, init
from decimal import Decimal

# Инициализация colorama
init(autoreset=True)

# Подключение к Monad testnet RPC
w3 = Web3(Web3.HTTPProvider('https://testnet-rpc.monad.xyz'))
if not w3.is_connected():
    print(f"{Fore.RED}Не удалось подключиться к сети Monad.{Style.RESET_ALL}")
    exit()

print(f"{Fore.GREEN}Успешно подключились к Monad testnet.{Style.RESET_ALL}")

# Адрес контракта для Tips
TIP_ADDRESS = "0xd3E51bfEE95E31760B671AfEF9763fB2CF4A375a"

# Параметры транзакции
GAS_LIMIT = 48294  # Базовый лимит газа из транзакции
TIP_AMOUNT = w3.to_wei(1.0001, 'ether')  # Сумма Tips из примера

# Чтение ABI из файла
try:
    with open('tip_abi.json', 'r') as file:
        TIP_ABI = json.load(file)
except FileNotFoundError:
    print(f"{Fore.RED}Файл tip_abi.json не найден.{Style.RESET_ALL}")
    exit()
except json.JSONDecodeError:
    print(f"{Fore.RED}Ошибка при разборе tip_abi.json. Проверьте формат JSON.{Style.RESET_ALL}")
    exit()

# Создание контракта
contract = w3.eth.contract(address=TIP_ADDRESS, abi=TIP_ABI)


# Загрузка аккаунтов (приватные ключи) из файла
def load_accounts(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]


# Загрузка получателей (адреса) из файла
def load_recipients(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines()]


accounts = load_accounts('accounts.txt')  # Берем все доступные аккаунты
recipients = load_recipients('recipients.txt')  # Все адреса получателей Tips

# Проверка, есть ли аккаунты и получатели
if not accounts:
    print(f"{Fore.RED}Файл accounts.txt пуст или не содержит аккаунтов.{Style.RESET_ALL}")
    exit()
if not recipients:
    print(f"{Fore.RED}Файл recipients.txt пуст или не содержит адресов.{Style.RESET_ALL}")
    exit()


# Получение текущей цены газа с добавлением 10%
def get_current_gas_price():
    base_gas_price = w3.eth.gas_price  # В wei, типа decimal.Decimal
    base_gwei = w3.from_wei(base_gas_price, 'gwei')  # Преобразуем в gwei, тоже decimal.Decimal
    increase_percent = Decimal('0.10')  # Преобразуем 0.10 в Decimal, чтобы избежать ошибки
    increase_gwei = int(base_gwei * increase_percent)  # Умножаем с правильным типом
    adjusted_gas_price = int(base_gas_price) + w3.to_wei(increase_gwei, 'gwei')  # Преобразуем в wei
    print(
        f"{Fore.YELLOW}Debug: base_gwei={base_gwei}, increase_gwei={increase_gwei}, adjusted_gas_price={adjusted_gas_price}{Style.RESET_ALL}")
    return adjusted_gas_price


# Функция отправки Tips
def send_tip(account_private_key, recipient_address):
    try:
        account = w3.eth.account.from_key(account_private_key)
        print(f"{Fore.CYAN}Отправка Tip от {account.address} на {recipient_address}{Style.RESET_ALL}")

        # Получение баланса кошелька
        balance = w3.eth.get_balance(account.address)
        balance_mon = w3.from_wei(balance, 'ether')
        print(f"{Fore.YELLOW}Баланс кошелька: {balance_mon} MON{Style.RESET_ALL}")

        # Получение последнего nonce
        nonce = w3.eth.get_transaction_count(account.address, 'latest')

        # Получение текущей цены газа
        gas_price = get_current_gas_price()
        gas_cost = int(gas_price) * GAS_LIMIT  # Преобразуем gas_price в int перед умножением
        gas_cost_mon = w3.from_wei(gas_cost, 'ether')
        print(
            f"{Fore.YELLOW}Стоимость газа: {gas_cost_mon} MON (Gas Price: {w3.from_wei(gas_price, 'gwei')} Gwei){Style.RESET_ALL}")

        # Проверка достаточности баланса
        if balance < TIP_AMOUNT + gas_cost:
            print(
                f"{Fore.RED}Недостаточно средств: требуется {w3.from_wei(TIP_AMOUNT + gas_cost, 'ether')} MON{Style.RESET_ALL}")
            return False

        # Построение транзакции для tip
        tx = contract.functions.tip(
            recipient_address  # Адрес получателя
        ).build_transaction({
            'from': account.address,
            'value': TIP_AMOUNT,
            'gas': GAS_LIMIT,
            'maxFeePerGas': gas_price,
            'maxPriorityFeePerGas': gas_price,
            'nonce': nonce,
            'chainId': 10143,  # Monad testnet ChainID
        })

        # Подпись и отправка
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=account_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        print(f"{Fore.GREEN}Транзакция отправлена: {tx_hash_hex}{Style.RESET_ALL}")

        # Ожидание подтверждения
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            tx_url = f"https://testnet.monadexplorer.com/tx/{tx_hash_hex}"
            sender_url = f"https://testnet.monadexplorer.com/address/{account.address}"
            recipient_url = f"https://testnet.monadexplorer.com/address/{recipient_address}"
            print(
                f"{Fore.GREEN}Успешная отправка Tip {w3.from_wei(TIP_AMOUNT, 'ether')} MON от {account.address} на {recipient_address}! Хэш: {tx_hash_hex}")
            print(f"Ссылка на транзакцию: {tx_url}")
            print(f"Ссылка на кошелек отправителя: {sender_url}")
            print(f"Ссылка на кошелек получателя: {recipient_url}{Style.RESET_ALL}")
            return True
        else:
            tx_url = f"https://testnet.monadexplorer.com/tx/{tx_hash_hex}"
            sender_url = f"https://testnet.monadexplorer.com/address/{account.address}"
            recipient_url = f"https://testnet.monadexplorer.com/address/{recipient_address}"
            print(
                f"{Fore.RED}Неудачная отправка Tip {w3.from_wei(TIP_AMOUNT, 'ether')} MON от {account.address} на {recipient_address}! Хэш: {tx_hash_hex}")
            print(f"Ссылка на транзакцию: {tx_url}")
            print(f"Ссылка на кошелек отправителя: {sender_url}")
            print(f"Ссылка на кошелек получателя: {recipient_url}")
            print(f"{Fore.RED}Причина: execution reverted{Style.RESET_ALL}")
            return False

    except Exception as e:
        print(f"{Fore.RED}Ошибка при отправке Tip: {e}{Style.RESET_ALL}")
        return False


# Функция для распределения адресов между аккаунтами
def distribute_recipients(accounts, recipients):
    num_accounts = len(accounts)
    num_recipients = len(recipients)

    # Если только один аккаунт, он берет всех получателей
    if num_accounts == 1:
        return {0: recipients}

    # Делим адреса между аккаунтами максимально равномерно
    recipients_per_account = max(1, num_recipients // num_accounts)
    distribution = {}

    for i in range(num_accounts):
        start_idx = i * recipients_per_account
        # Для последнего аккаунта добавляем остаток
        if i == num_accounts - 1:
            end_idx = num_recipients
        else:
            end_idx = min(start_idx + recipients_per_account, num_recipients)
        distribution[i] = recipients[start_idx:end_idx]

    return distribution


# Функция для получения и вывода баланса
def print_balances(accounts, recipients):
    for account_idx, private_key in enumerate(accounts):
        account = w3.eth.account.from_key(private_key)
        balance = w3.eth.get_balance(account.address)
        balance_mon = w3.from_wei(balance, 'ether')
        print(
            f"{Fore.YELLOW}Баланс отправителя {account.address} после всех транзакций: {balance_mon} MON{Style.RESET_ALL}")

    for recipient in recipients:
        balance = w3.eth.get_balance(recipient)
        balance_mon = w3.from_wei(balance, 'ether')
        print(f"{Fore.YELLOW}Баланс получателя {recipient} после всех транзакций: {balance_mon} MON{Style.RESET_ALL}")


# Основной цикл
def main():
    successful_tips = 0
    total_tips = 0

    # Распределяем адреса между аккаунтами
    distribution = distribute_recipients(accounts, recipients)

    # Проходим по каждому аккаунту
    for account_idx, private_key in enumerate(accounts):
        recipient_list = distribution.get(account_idx, [])
        if not recipient_list:
            print(f"{Fore.YELLOW}Для аккаунта {account_idx + 1} нет адресов для отправки Tips.{Style.RESET_ALL}")
            continue

        print(
            f"{Fore.CYAN}Аккаунт {account_idx + 1} отправляет Tips на {len(recipient_list)} адресов.{Style.RESET_ALL}")

        # Для каждого адреса из списка отправляем 3 транзакции
        for recipient in recipient_list:
            for _ in range(3):  # 3 транзакции на каждый адрес
                if send_tip(private_key, recipient):
                    successful_tips += 1
                total_tips += 1
                sleep_time = random.uniform(15, 20)  # Пауза 15-20 секунд между транзакциями
                print(f"{Fore.YELLOW}Ожидание {sleep_time:.2f} секунд перед следующей транзакцией...{Style.RESET_ALL}")
                time.sleep(sleep_time)

        # Добавляем паузу 1 минута между аккаунтами, кроме последнего
        if account_idx < len(accounts) - 1:
            sleep_time = 60  # Фиксированная пауза 1 минута
            print(f"{Fore.YELLOW}Ожидание {sleep_time} секунд перед следующим аккаунтом...{Style.RESET_ALL}")
            time.sleep(sleep_time)

    # Вывод балансов после завершения всех транзакций
    print_balances(accounts, recipients)
    print(f"{Fore.GREEN}Завершено! Успешно отправлено Tips: {successful_tips}/{total_tips}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()