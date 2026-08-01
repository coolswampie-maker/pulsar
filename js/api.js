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
  // подчищаем данные демо-версии, если остались в браузере с прошлых визитов
  try{ localStorage.removeItem('pulsar_catalog_v1'); localStorage.removeItem('pulsar_orders_v1'); }catch(e){}

  /* ---------- авторизация компании (личный кабинет) ---------- */
  var AUTH_KEY='pulsar_auth_v1';
  function readAuth(){
    try{ var o=JSON.parse(localStorage.getItem(AUTH_KEY)); return (o&&o.token)?o:null; }catch(e){ return null; }
  }
  P.auth = readAuth();            // {token, company} либо null
  function setAuth(o){
    P.auth = o;
    if(o) localStorage.setItem(AUTH_KEY, JSON.stringify(o));
    else localStorage.removeItem(AUTH_KEY);
  }
  P.isLogged = function(){ return !!(P.auth && P.auth.token); };
  P.company = function(){ return P.auth ? P.auth.company : null; };
  // резидентская скидка действует, только когда оператор подтвердил статус
  P.isResident = function(){ var c=P.company(); return !!(c && c.resident && c.confirmed); };

  // Все запросы к API идут через apiFetch: он сам подставляет токен компании.
  P.apiFetch = function(path, opts){
    opts = opts || {};
    var h = {};
    for(var k in (opts.headers||{})) h[k]=opts.headers[k];
    if(P.auth && P.auth.token && !h.Authorization) h.Authorization='Token '+P.auth.token;
    opts.headers = h;
    return fetch(API_BASE+path, opts);
  };
  // разбор ответа: {ok, data, msg} — сообщение об ошибке уже человекочитаемое
  function parse(r){
    return r.text().then(function(t){
      var j=null; try{ j=t?JSON.parse(t):null; }catch(e){}
      if(r.ok) return {ok:true, data:j};
      return {ok:false, status:r.status, data:j, msg:errText(j) || ('Ошибка сервера ('+r.status+')')};
    });
  }
  // DRF отдаёт ошибки как {поле:[текст]} или {detail:текст} — сводим к строке
  /* Внутренние формулировки DRF по-английски и человеку ничего не говорят:
     «CSRF Failed: CSRF token missing.» на форме заявки выглядит как поломка
     сайта, а не как то, что можно исправить. Подменяем понятным текстом;
     всё остальное, что сервер шлёт по-русски (проверки полей), пропускаем
     как есть — оно писалось для людей. */
  /* Ограничение частоты. Правило /throttled/ не срабатывало на боевом
     ответе: русская локализация DRF отдаёт «Запрос был проигнорирован.
     Expected available in 1971 seconds.» — слова throttled там нет, зато
     есть половина фразы по-английски и сырые секунды. Человек видел это
     на форме регистрации и не понимал ни что случилось, ни сколько ждать.
     Ловим все три написания и переводим секунды в минуты и часы. */
  function throttleText(t){
    var m = /(\d+)\s*second/i.exec(t) || /(\d+)\s*секунд/i.exec(t);
    var sec = m ? parseInt(m[1], 10) : 0;
    // без точки внутри: её ставит сама фраза, иначе выходило «через 33 мин..»
    var when = sec > 3600 ? 'через ' + Math.ceil(sec / 3600) + ' ч'
             : sec > 90   ? 'через ' + Math.ceil(sec / 60) + ' мин'
             : 'через минуту';
    return 'Слишком много попыток подряд. Попробуйте ' + when + '.';
  }

  var TECH_ERRORS = [
    [/csrf/i, 'Не удалось отправить: сессия устарела. Обновите страницу (Ctrl+F5) и попробуйте ещё раз.'],
    [/authentication credentials were not provided/i, 'Требуется вход.'],
    [/invalid token/i, 'Сессия истекла — войдите заново.'],
    [/throttl|проигнорирован|expected available/i, throttleText],
    [/server error|internal/i, 'На сервере произошла ошибка. Попробуйте позже или напишите оператору.']
  ];
  function humanize(t){
    for(var i=0;i<TECH_ERRORS.length;i++)
      if(TECH_ERRORS[i][0].test(t)){
        var r=TECH_ERRORS[i][1];
        return typeof r==='function' ? r(t) : r;
      }
    // латиница без кириллицы — почти наверняка внутреннее сообщение фреймворка
    if(t && !/[а-яё]/i.test(t) && /[a-z]{4}/i.test(t))
      return 'Не удалось выполнить запрос. Попробуйте ещё раз или напишите оператору.';
    return t;
  }
  function errText(j){
    if(!j) return '';
    if(typeof j==='string') return humanize(j);
    if(j.detail) return humanize(String(j.detail));
    var out=[];
    for(var k in j){
      var v=j[k];
      out.push(Array.isArray(v)?v.join(' '):String(v));
    }
    return out.join(' ');
  }
  P.apiErrText = errText;

  function sendJson(method, path, body){
    return P.apiFetch(path, {method:method, headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body||{})}).then(parse);
  }
  function postJson(path, body){ return sendJson('POST', path, body); }

  P.authApi = {
    register:function(d){
      return postJson('/auth/register/', d).then(function(res){
        if(res.ok) setAuth({token:res.data.token, company:res.data.company});
        return res;
      });
    },
    login:function(email,password){
      return postJson('/auth/login/', {email:email, password:password}).then(function(res){
        if(res.ok) setAuth({token:res.data.token, company:res.data.company});
        return res;
      });
    },
    logout:function(){ setAuth(null); },
    // перечитать профиль (например, оператор подтвердил статус резидента)
    refresh:function(){
      if(!P.isLogged()) return Promise.resolve({ok:false});
      return P.apiFetch('/auth/me/').then(parse).then(function(res){
        if(res.ok) setAuth({token:P.auth.token, company:res.data});
        else if(res.status===401) setAuth(null);   // токен отозван
        return res;
      });
    },
    save:function(d){
      return sendJson('PATCH', '/auth/me/', d).then(function(res){
        if(res.ok) setAuth({token:P.auth.token, company:res.data});
        return res;
      });
    }
  };

  /* ---------- подбор позиций по описанию задачи (ИИ на бэкенде) ---------- */
  P.assistApi = {
    ask:function(query){
      return postJson('/assist/', {query:query}).catch(function(){
        return {ok:false, msg:'Подбор недоступен'};
      });
    }
  };

  /* ---------- индивидуальная заявка на подбор ---------- */
  P.customRequestApi = {
    send:function(d){ return postJson('/custom-request/', d); }
  };

  /* ---------- заявки компании ---------- */
  P.ordersApi = {
    list:function(){ return P.apiFetch('/orders/').then(parse); },
    cancel:function(id){ return postJson('/orders/'+id+'/cancel/', {}); },
    requestChange:function(id,message){ return postJson('/orders/'+id+'/request-change/', {message:message}); }
  };

  /* ---------- помощник резидента: профиль проекта ---------- */
  P.profileApi = {
    get:function(){ return P.apiFetch('/profile/').then(parse); },
    save:function(d){ return sendJson('PATCH', '/profile/', d); },
    next:function(){ return P.apiFetch('/profile/next/').then(parse); },
    formats:function(){ return P.apiFetch('/profile/formats/').then(parse); },
    compose:function(fmt){ return postJson('/profile/compose/', {format:fmt}); },
    composeJob:function(id){ return P.apiFetch('/profile/compose/'+id+'/').then(parse); },
    // Смета: каждый ответ возвращает смету целиком, а не одну строку —
    // итог считает сервер, и клиенту нечего досчитывать самому.
    budget:function(){ return P.apiFetch('/profile/budget/').then(parse); },
    budgetAdd:function(d){ return postJson('/profile/budget/', d); },
    budgetSet:function(id,d){ return sendJson('PATCH', '/profile/budget/'+id+'/', d); },
    budgetDel:function(id){
      return P.apiFetch('/profile/budget/'+id+'/', {method:'DELETE'}).then(parse);
    },
    budgetReview:function(){ return postJson('/profile/budget/review/', {}); }
  };

  /* ---------- программы поддержки и проверка на формальные отказы ---------- */
  P.programsApi = {
    list:function(){ return P.apiFetch('/programs/').then(parse); }
  };

  /* ---------- показатели (KPI по методологии ИНТЦ) ---------- */
  P.kpiApi = {
    get:function(year){ return P.apiFetch('/kpi/'+(year?'?year='+year:'')).then(parse); },
    addEntry:function(key,d,year){
      return postJson('/kpi/'+key+'/entries/'+(year?'?year='+year:''), d);
    },
    deleteEntry:function(key,id){
      return P.apiFetch('/kpi/'+key+'/entries/'+id+'/', {method:'DELETE'}).then(parse);
    },
    // загрузка документа: система сама заводит позицию по файлу
    upload:function(key,file,year){
      var fd=new FormData(); fd.append('document', file);
      return P.apiFetch('/kpi/'+key+'/extract/'+(year?'?year='+year:''), {method:'POST', body:fd}).then(parse);
    }
  };

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
    // «10 авг», и только для другого года — «10 авг 2027». Год в подписи
    // почти всегда текущий, а места на карточке мало.
    humanShort:function(s){
      if(!s) return '';
      var full=this.human(s);
      return s.slice(0,4)===this.todayISO().slice(0,4) ? full.replace(/\s\d{4}$/,'') : full;
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
  /* Ближайший день, когда ресурс можно взять. Нужен в двух местах: в каталоге
     («занято сегодня, свободно с 6 авг» вместо глухого «занято») и при
     повторе прошлой заявки — там даты из старого заказа давно в прошлом.

     Правило занятости то же, что в календаре на карточке: смены и сутки
     закрывает любая запись на дату, почасовой ресурс — только запись без
     времени (закрыт весь день); частичную занятость снимает выбор
     другого часа. Иначе календарь и подпись под ним противоречили бы. */
  P.nextFreeDate = function(id, fromISO, maxDays){
    var res = P.getById(id); if(!res) return null;
    var byDay = {};
    P.getBusy(id).forEach(function(b){ (byDay[b.date] = byDay[b.date] || []).push(b); });
    var start = fromISO || P.dates.plusISO(1);
    var base = new Date(start + 'T12:00:00');
    maxDays = maxDays || 120;          // дальше искать бессмысленно
    for (var i = 0; i < maxDays; i++) {
      var d = P.dates.iso(P.dates.addDays(base, i));
      if (d < P.dates.todayISO()) continue;
      var list = byDay[d];
      if (!list || !list.length) return d;
      if (res.bookMode === 'hour' && !list.some(function(x){ return x.slotStart == null; }))
        return d;
    }
    return null;
  };

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
