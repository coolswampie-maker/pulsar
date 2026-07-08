/* ============================================================
   ПУЛЬСАР — слой данных (api).
   ЕДИНСТВЕННАЯ граница между UI и хранилищем: сейчас читает
   window.PULSAR.baseResources + localStorage; при переходе на
   backend здесь появляются fetch() к REST, остальной код не меняется.
   ============================================================ */
(function(){
  var P = window.PULSAR = window.PULSAR || {};
  var CATALOG_KEY = 'pulsar_catalog_v1';

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
    }
  };

  /* ---------- каталог (base + overlay) ---------- */
  function clone(o){ return JSON.parse(JSON.stringify(o)); }

  P.getResources = function(){
    var stored = localStorage.getItem(CATALOG_KEY);
    if(stored){ try{ return JSON.parse(stored); }catch(e){} }
    return clone(P.baseResources);
  };
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

  // admin CRUD (пишет полную копию каталога в localStorage)
  P.saveResource = function(res){
    var all=P.getResources(); var i=all.findIndex(function(r){return r.id===res.id;});
    if(i>=0) all[i]=res; else all.push(res);
    localStorage.setItem(CATALOG_KEY, JSON.stringify(all));
  };
  P.deleteResource = function(id){
    var all=P.getResources().filter(function(r){return r.id!==id;});
    localStorage.setItem(CATALOG_KEY, JSON.stringify(all));
  };
  P.resetCatalog = function(){ localStorage.removeItem(CATALOG_KEY); };

  /* ---------- занятость (демо busy + подтверждённые заявки) ---------- */
  // сид: id -> [{off:деньОтСегодня, s:'HH:MM', e:'HH:MM'}] ; для shift/day s/e опускаем
  var SEED = {
    'eq-massspec':[{off:0,s:'09:00',e:'13:00'},{off:1,s:'10:00',e:'14:00'},{off:2,s:'09:00',e:'12:00'}],
    'eq-sem':[{off:1,s:'12:00',e:'16:00'}],
    'eq-nmr':[{off:3,s:'10:00',e:'13:00'}],
    'room-cleanroom-a':[{off:2}],
    'room-vacuum':[{off:0},{off:4}],
    'eq-vk1000':[{off:2},{off:3}],
    'eq-mim':[{off:5}]
  };
  function seedBusy(id){
    return (SEED[id]||[]).map(function(b){
      return { date:P.dates.plusISO(b.off), slotStart:b.s||null, slotEnd:b.e||null };
    });
  }
  P.getBusy = function(id){
    var out = seedBusy(id);
    // добавляем слоты из подтверждённых заявок
    P.getOrders().forEach(function(o){
      if(o.status!=='confirmed') return;
      o.lines.forEach(function(l){
        if(l.resourceId===id) out.push({date:l.date, slotStart:l.slotStart||null, slotEnd:l.slotEnd||null});
      });
    });
    return out;
  };
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

  /* ---------- заявки (orders) ---------- */
  var ORDERS_KEY='pulsar_orders_v1';
  P.getOrders = function(){
    try{ return JSON.parse(localStorage.getItem(ORDERS_KEY)||'[]'); }catch(e){ return []; }
  };
  P.saveOrders = function(list){ localStorage.setItem(ORDERS_KEY, JSON.stringify(list)); };
  P.setOrderStatus = function(id,status){
    var l=P.getOrders(); var o=l.find(function(x){return x.id===id;});
    if(o){ o.status=status; P.saveOrders(l); }
  };
})();
