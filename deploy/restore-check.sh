#!/usr/bin/env bash
# Проверка, что резервная копия действительно разворачивается.
#
# Зачем отдельный скрипт. Копия, которую ни разу не восстанавливали, копией
# не является: она может годами создаваться пустой, битой или без нужных
# таблиц, и никто об этом не узнает — до того дня, когда она понадобится.
# Единственный способ убедиться — развернуть её и посмотреть, что внутри.
#
# Что делает: берёт свежий дамп, поднимает из него ВРЕМЕННУЮ базу, считает
# записи в главных таблицах и базу удаляет. Рабочую базу не трогает вообще —
# она даже не открывается.

set -euo pipefail

DEST="${PULSAR_BACKUP_DIR:-/var/backups/pulsar}"
TMPDB="pulsar_restore_check"

log() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf 'ОШИБКА: %s\n' "$*" >&2; exit 1; }

DUMP="$(ls -t "$DEST"/db_*.sql.gz 2>/dev/null | head -1 || true)"
[ -n "$DUMP" ] || die "в $DEST нет ни одного дампа Postgres. Сначала deploy/backup.sh"

AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$DUMP") ) / 3600 ))
log "Проверяю: $(basename "$DUMP") (создан $AGE_H ч. назад)"
[ "$AGE_H" -lt 48 ] || printf 'ВНИМАНИЕ: свежей копии нет уже %s ч. — расписание не работает?\n' "$AGE_H" >&2

# Временная база. Имя нарочно не похоже на боевое, и в конце она удаляется
# при любом исходе — чтобы неудачная проверка не оставляла мусор.
cleanup() { sudo -u postgres psql -q -c "DROP DATABASE IF EXISTS $TMPDB;" >/dev/null 2>&1 || true; }
trap cleanup EXIT

cleanup
sudo -u postgres psql -q -c "CREATE DATABASE $TMPDB;" >/dev/null

log "Разворачиваю…"
if ! gunzip -c "$DUMP" | sudo -u postgres psql -q -d "$TMPDB" >/dev/null 2>/tmp/restore-check.err; then
    printf '%s\n' "$(tail -20 /tmp/restore-check.err)" >&2
    die "дамп не развернулся — копия непригодна"
fi

# Считаем записи. Пустая база разворачивается без ошибок — значит, «ошибок
# не было» ещё ничего не доказывает, надо посмотреть, что внутри.
ROWS=$(sudo -u postgres psql -tAd "$TMPDB" <<'SQL'
SELECT string_agg(t || ': ' || c, E'\n') FROM (
  SELECT 'компаний' t, count(*) c FROM booking_company
  UNION ALL SELECT 'заявок',      count(*) FROM booking_order
  UNION ALL SELECT 'позиций',     count(*) FROM booking_bookingline
  UNION ALL SELECT 'каталог',     count(*) FROM booking_resource
  UNION ALL SELECT 'профилей',    count(*) FROM booking_projectprofile
  UNION ALL SELECT 'показателей', count(*) FROM booking_kpi
) q;
SQL
)
printf '%s\n' "$ROWS" | sed 's/^/    /'

CATALOG=$(printf '%s' "$ROWS" | grep -oP 'каталог: \K\d+' || echo 0)
[ "$CATALOG" -gt 0 ] || die "в копии пустой каталог — так быть не может, копия негодна"

log "Копия разворачивается и содержит данные."
