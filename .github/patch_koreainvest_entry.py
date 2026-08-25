from pathlib import Path


path = Path('.github/workflows/rate_update.yml')
text = path.read_text(encoding='utf-8')

replacements = {
    'python crawler/pension_rates.py': 'python crawler/pension_entry.py',
    'python crawler/pension_retry_failed.py': 'python crawler/pension_retry_entry.py',
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one occurrence of {old!r}, found {count}')
    text = text.replace(old, new, 1)

path.write_text(text.rstrip() + '\n', encoding='utf-8')
print('rate_update.yml Korea Investment entry wiring patched')
