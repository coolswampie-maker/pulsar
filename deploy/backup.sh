#!/usr/bin/env bash
# Резервная копия базы ПУЛЬСАРа и загруженных документов.
#
# Запускается по расписанию (см. DEPLOY.md, раздел «Резервные копии»).
# Читает DATABASE_URL из backend/.env — отдельно пароль нигде не хранится.
#
# ВАЖНО ПРО МЕСТО ХРАНЕНИЯ. Копия рядом с базой, на том же диске, спасает
# только от ошибки человека («удалил не ту компанию»). От смерти диска и от
# потери сервера она не спасает ни от чего: пропадёт вместе с оригиналом.
# Поэтому в конце скрипта есть шаг выгрузки наружу, и если он не настроен,
# скрипт об этом говорит вслух при каждом запуске. Молчаливая копия на том
# же диске — худший вариант: она создаёт уверенность, которой нет оснований.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
DEST="${PULSAR_BACKUP_DIR:-/var/backups/pulsar}"
KEEP_DAYS="${PULSAR_BACKUP_KEEP:-14}"
STAMP="$(date +%Y-%m-%d_%H%M)"

log() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ОШИБКА: %s\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "нет $ENV_FILE — скрипт запускают на сервере, где стоит сайт"

# DATABASE_URL достаём без source: в .env есть значения со спецсимволами,
# и выполнять этот файл как код не нужно.
DB_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"

mkdir -p "$DEST"
chmod 700 "$DEST"   # в дампе персональные данные — чужим читать нечего

# ---------- база ----------
if [ -n "$DB_URL" ]; then
    OUT="$DEST/db_$STAMP.sql.gz"
    log "Снимаю дамп Postgres…"
    # -Fp + gzip, а не -Fc: обычный текстовый дамп восстанавливается psql'ом,
    # без совпадения версий pg_restore. Для базы такого размера разницы нет,
    # а восстанавливать проще — в аварийной ситуации это важнее.
    pg_dump "$DB_URL" --no-owner --no-privileges | gzip -9 > "$OUT"
    SIZE=$(stat -c %s "$OUT")
    [ "$SIZE" -gt 1000 ] || die "дамп подозрительно мал ($SIZE Б) — проверьте DATABASE_URL"
    log "База: $OUT ($((SIZE / 1024)) КБ)"
else
    # SQLite — режим разработки; на сервере так быть не должно
    SQLITE="$ROOT/backend/db.sqlite3"
    [ -f "$SQLITE" ] || die "в .env нет DATABASE_URL и файла db.sqlite3 тоже нет"
    OUT="$DEST/db_$STAMP.sqlite.gz"
    log "DATABASE_URL пуст — копирую SQLite (так бывает только в разработке)"
    # Через python3, а не утилиту sqlite3: питон на сервере с Django есть
    # всегда, а отдельной консольной утилиты может не быть — скрипт падал
    # бы с «sqlite3: command not found», и по этой строке не догадаешься,
    # что копия не сделана. Метод .backup(), а не cp: файл, скопированный
    # во время записи, бьётся.
    python3 - "$SQLITE" "$DEST/tmp.sqlite" <<'PYBACKUP'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
src.close(); dst.close()
PYBACKUP
    gzip -9 < "$DEST/tmp.sqlite" > "$OUT" && rm -f "$DEST/tmp.sqlite"
    log "База: $OUT"
fi

# ---------- загруженные документы ----------
# Подтверждающие документы по показателям лежат файлами, в дампе базы их нет —
# там только пути. Без этого архива восстановленная база будет ссылаться
# в пустоту.
MEDIA="$ROOT/backend/media"
if [ -d "$MEDIA" ] && [ -n "$(ls -A "$MEDIA" 2>/dev/null)" ]; then
    MOUT="$DEST/media_$STAMP.tar.gz"
    tar -czf "$MOUT" -C "$ROOT/backend" media
    log "Документы: $MOUT ($(( $(stat -c %s "$MOUT") / 1024 )) КБ)"
fi

# ---------- чистка старых ----------
find "$DEST" -name 'db_*.gz' -mtime "+$KEEP_DAYS" -delete
find "$DEST" -name 'media_*.tar.gz' -mtime "+$KEEP_DAYS" -delete
log "Копий на диске: $(find "$DEST" -name 'db_*.gz' | wc -l), храним $KEEP_DAYS дн."

# ---------- выгрузка наружу ----------
# PULSAR_BACKUP_UPLOAD — команда, которой отдают файл. Примеры в DEPLOY.md.
# Файл подставляется вместо {}.
if [ -n "${PULSAR_BACKUP_UPLOAD:-}" ]; then
    log "Выгружаю наружу…"
    for f in "$OUT" ${MOUT:-}; do
        [ -f "$f" ] || continue
        eval "${PULSAR_BACKUP_UPLOAD//\{\}/$f}" || die "выгрузка не удалась: $f"
    done
    log "Выгружено."
else
    cat >&2 <<'WARN'

  ВНИМАНИЕ: копия лежит только на этом сервере.
  Умрёт диск — пропадёт вместе с базой. Настройте PULSAR_BACKUP_UPLOAD,
  раздел «Резервные копии» в DEPLOY.md.

WARN
fi

log "Готово."
