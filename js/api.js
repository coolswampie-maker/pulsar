/* ============================================================
   ПУЛЬСАР — слой данных (api).
   ЕДИНСТВЕННАЯ граница между UI и хранилищем: сейчас читает
   window.PULSAR.baseResources + localStorage; при переходе на
   backend здесь появляются fetch() к REST, остальной код не меняется.
   ============================================================ */
(function(){
  var P = window.PULSAR = window.PULSAR || {};
  // база REST-API Django. По умолчанию тот же домен (/api). Если бэкенд на другом
  // хосте — задайте window.PULSAR_API_BASE в index.html.
  var API_BASE = (window.PULSAR_API_BASE || '/api').replace(/\/+$/,'');
  P.API_BASE = API_BASE;
  P.apiFetch = function(path, opts){ return fetch(API_BASE+path, opts); };
  // подчищаем данные демо-версии, если остались в браузере с прошлых визитов
  try{ localStorage.removeItem('pulsar_catalog_v1'); localStorage.removeItem('pulsar_orders_v1'); }catch(e){}

  /* ---------- даты ---------- */
  function pad(n){ return (n<10?'0':'')+n; }
  function iso(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()); }
  function today(){ var d=new Date(); d.setHours(0,0,0,0); return d; }
  function addDays(base, n){ var d=new Date(base); d.setDate(d.getDate()+n); return d; }
  P.dates = {
    iso:iso, today:today, addDays:addDays,
    todayISO:function(){ return iso(today()); },
    plusISO:function(n){ return iso(addDays(today(),n)); },
    human:function(s){
      if(!s) return '';
      var p=s.split('-'); var m=['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
      return parseInt(p[2],10)+' '+m[parseInt(p[1],10)-1]+' '+p[0];
    },
    // список ISO-дат в промежутке [startISO..endISO] включительно
    range:function(startISO,endISO){
      if(!startISO) return [];
      if(!endISO || endISO<startISO) return [startISO];
      var out=[], cur=new Date(startISO+'T12:00:00'), end=new Date(endISO+'T12:00:00'), guard=0;
      while(cur<=end && guard<400){ out.push(iso(cur)); cur=addDays(cur,1); guard++; }
      return out;
    },
    // число суток в промежутке (включительно), минимум 1
    days:function(startISO,endISO){ return this.range(startISO,endISO).length||1; }
  };

  /* ---------- каталог ----------
     Источник истины — бэкенд: GET /api/resources/ (то, что оператор ведёт
     в кабинете). data/resources.js остаётся страховкой: если бэкенд не
     ответил, сайт продолжает работать на встроенном каталоге. */
  function clone(o){ return JSON.parse(JSON.stringify(o)); }

  P._catalog = null;          // каталог, полученный с бэкенда
  P.catalogLoaded = false;
  // Приводим ответ API к формату фронта:
  //  · поле фото в API называется image, во фронте — img;
  //  · суточный режим в базе называется 'day', во фронте — 'range'
  //    (иначе бронь суток считалась бы по количеству, а не по диапазону дат).
  function fromApi(r){
    var o = clone(r);
    o.img = r.img || r.image || '';
    delete o.image;
    if(o.bookMode==='day') o.bookMode='range';
    o.specs = r.specs || [];
    o.bundledWith = r.bundledWith || [];
    return o;
  }
  P.loadCatalog = function(cb){
    P.apiFetch('/resources/').then(function(r){ return r.json(); })
      .then(function(data){
        if(Array.isArray(data) && data.length) P._catalog = data.map(fromApi);
      })
      .catch(function(){ P._catalog = null; })
      .then(function(){ P.catalogLoaded = true; if(cb) cb(); });
  };

  P.getResources = function(){ return P._catalog ? clone(P._catalog) : clone(P.baseResources); };
  P.getById = function(id){
    var all=P.getResources(); for(var i=0;i<all.length;i++) if(all[i].id===id) return all[i];
    return null;
  };
  P.getByType = function(type){ return P.getResources().filter(function(r){ return r.type===type; }); };
  P.typeMeta = {
    room:{label:'Лаборатории', single:'Лаборатория', icon:'building'},
    equipment:{label:'Оборудование', single:'Оборудование', icon:'device'},
    specialist:{label:'Специалисты', single:'Специалист', icon:'user'},
    service:{label:'Услуги под ключ', single:'Услуга', icon:'doc'}
  };
  P.unitShort = { 'смена':'смена','сутки':'сут','час':'ч','образец':'образец','партия':'партия' };

  // Каталог правится оператором в кабинете (Django /admin) — локального
  // редактирования во фронте больше нет.

  /* ---------- занятость (из бэкенда: подтверждённые оператором брони) ---------- */
  P._busy = {};           // кэш: slug -> [{date, slotStart, slotEnd}]
  P.busyLoaded = false;
  // грузим всю занятость одним запросом при старте; при сбое — работаем без блокировок
  P.loadBusy = function(cb){
    P.apiFetch('/busy/').then(function(r){ return r.json(); })
      .then(function(data){ P._busy = data || {}; })
      .catch(function(){ P._busy = {}; })
      .then(function(){ P.busyLoaded = true; if(cb) cb(); });
  };
  P.getBusy = function(id){ return (P._busy[id] || []).slice(); };
  // статус на СЕГОДНЯ: занят ли ресурс сегодня (бронь — на конкретный день, не навсегда)
  P.availabilityLabel = function(id){
    var t=P.dates.todayISO();
    var busyToday=P.getBusy(id).some(function(b){ return b.date===t; });
    return busyToday ? 'busy' : 'ok';
  };
  // дата ближайшей брони (для подписи «свободно, ближайшая бронь …»)
  P.nextBusyDate = function(id){
    var t=P.dates.todayISO();
    var future=P.getBusy(id).map(function(b){return b.date;}).filter(function(d){return d>t;}).sort();
    return future.length ? future[0] : null;
  };

  /* ---------- заявки (orders) ----------
     Заявки хранятся в базе на бэкенде: создаются через POST /api/orders/
     (см. store.js → Cart.checkout), а оператор ведёт их в Django /admin.
     Локального хранилища заявок больше нет. */
})();
