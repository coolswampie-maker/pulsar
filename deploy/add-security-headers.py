#!/usr/bin/env python3
"""Подключить заголовки безопасности к установленному конфигу Nginx.

Запуск на сервере:
    sudo python3 /srv/pulsar/deploy/add-security-headers.py

Скрипт сам находит блок `listen 443`, вставляет include в двух нужных местах,
проверяет конфиг и перезагружает Nginx. Если проверка не прошла — возвращает
файл как был и ничего не перезагружает.

Почему скриптом, а не руками в nano: правка нужна в двух местах, и промах
роняет сайт целиком. Здесь же всегда остаётся резервная копия рядом с файлом.

Почему include В ДВУХ местах: в Nginx add_header не складывается по уровням.
Если в location есть хоть один свой add_header (у нас там Cache-Control), все
заголовки, унаследованные от server, отбрасываются. Поэтому набор нужен и в
блоке server, и внутри location /.
"""
import os
import re
import shutil
import subprocess
import sys
import time

CONF = '/etc/nginx/sites-available/pulsar'
SNIPPET_SRC = '/srv/pulsar/deploy/security-headers.conf'
SNIPPET_DST = '/etc/nginx/snippets/pulsar-security.conf'
INCLUDE = 'include /etc/nginx/snippets/pulsar-security.conf;'


def fail(msg):
    print(f'\n✗ {msg}')
    sys.exit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def add_includes(lines):
    """Вставить include в блок с listen 443 и в его location /.

    Возвращает (новые строки, что было сделано).
    """
    out, done = [], []
    depth = 0            # глубина вложенности { } внутри текущего server
    in_443 = False
    server_start = None
    pending_server = False   # видели `server {`, ждём подтверждения listen 443
    buffered = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not in_443 and re.match(r'^server\s*\{', stripped):
            # запоминаем блок целиком, чтобы понять, 443 он или 80
            block, j, d = [], i, 0
            while j < len(lines):
                block.append(lines[j])
                d += lines[j].count('{') - lines[j].count('}')
                j += 1
                if d == 0:
                    break
            is443 = any(re.search(r'listen\s+.*443', b) for b in block)
            if is443:
                block = patch_block(block, done)
            out.extend(block)
            i = j
            continue

        out.append(line)
        i += 1
    return out, done


def patch_block(block, done):
    """Вставить include в начало server-блока и внутрь location /."""
    res = []
    have_server_include = any(INCLUDE in b for b in block)

    k = 0
    while k < len(block):
        line = block[k]
        res.append(line)
        stripped = line.strip()

        # 1) сразу после `server {`
        if re.match(r'^server\s*\{', stripped) and not have_server_include:
            res.append('\n    # заголовки безопасности (см. deploy/security-headers.conf)\n')
            res.append(f'    {INCLUDE}\n\n')
            done.append('в блок server')

        # 2) внутри `location / {`
        if re.match(r'^location\s+/\s*\{', stripped):
            # смотрим, нет ли include уже внутри этого location
            d, m, inner = 1, k + 1, []
            while m < len(block) and d > 0:
                d += block[m].count('{') - block[m].count('}')
                if d > 0:
                    inner.append(block[m])
                m += 1
            if not any(INCLUDE in x for x in inner):
                pad = indent_of(line) + '    '
                res.append(f'{pad}{INCLUDE}\n')
                done.append('в location /')
        k += 1
    return res


def main():
    if os.geteuid() != 0:
        fail('Запускать нужно через sudo: sudo python3 ' + __file__)
    if not os.path.exists(CONF):
        fail(f'Не найден конфиг {CONF}. Проверьте путь: ls /etc/nginx/sites-available/')
    if not os.path.exists(SNIPPET_SRC):
        fail(f'Не найден {SNIPPET_SRC}. Сделайте сначала: cd /srv/pulsar && git pull')

    os.makedirs(os.path.dirname(SNIPPET_DST), exist_ok=True)
    shutil.copyfile(SNIPPET_SRC, SNIPPET_DST)
    print(f'✓ Набор заголовков скопирован в {SNIPPET_DST}')

    with open(CONF, encoding='utf-8') as f:
        lines = f.readlines()

    if not any(re.search(r'listen\s+.*443', ln) for ln in lines):
        fail('В конфиге нет блока listen 443 — значит HTTPS ещё не настроен.\n'
             '  Сначала: sudo certbot --nginx -d pulsar.jaglionrus.ru')

    new, done = add_includes(lines)
    if not done:
        print('✓ Заголовки уже подключены, менять нечего.')
        return

    backup = f'{CONF}.bak-{time.strftime("%Y%m%d-%H%M%S")}'
    shutil.copyfile(CONF, backup)
    print(f'✓ Резервная копия: {backup}')

    with open(CONF, 'w', encoding='utf-8') as f:
        f.writelines(new)
    print('✓ Добавлено: ' + ', '.join(done))

    check = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if check.returncode != 0:
        shutil.copyfile(backup, CONF)
        print(check.stderr.strip())
        fail('Проверка конфига не прошла — файл возвращён как был, сайт не тронут.')
    print('✓ Проверка конфига пройдена')

    reload_ = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
    if reload_.returncode != 0:
        shutil.copyfile(backup, CONF)
        subprocess.run(['systemctl', 'reload', 'nginx'])
        print(reload_.stderr.strip())
        fail('Перезагрузка не удалась — файл возвращён как был.')

    print('✓ Nginx перезагружен\n')
    print('Проверьте, что заголовки появились:')
    print("  curl -sI https://pulsar.jaglionrus.ru | grep -i -E "
          "'strict|frame|content-type-opt|referrer|policy'")
    print('\nИ откройте сайт: если что-то перестало отображаться, откатиться можно так:')
    print(f'  sudo cp {backup} {CONF} && sudo systemctl reload nginx')


if __name__ == '__main__':
    main()
