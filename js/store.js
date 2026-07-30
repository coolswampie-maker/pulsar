/* ============================================================
   ПУЛЬСАР — корзина бронирования и оформление заявок.
   Логика: единицы брони, авто-подтягивание оператора,
   проверка конфликтов, смета, льгота резидента ИНТЦ (−25%).
   ============================================================ */
(function(){
  var P = window.PULSAR = window.PULSAR || {};
  var CART_KEY='pulsar_cart_v1', RESIDENT_KEY='pulsar_resident_v1';
  var RESIDENT_DISCOUNT=0.25;

  function read(){ try{ return JSON.parse(localStorage.getItem(CART_KEY)||'[]'); }catch(e){ return []; } }
  function write(l){ localStorage.setItem(CART_KEY, JSON.stringify(l)); dispatch(); }
  function uid(){ return 'l'+Math.random().toString(36).slice(2,9); }
  function dispatch(){ window.dispatchEvent(new CustomEvent('pulsar:cart')); }

  var Cart = P.cart = {};

  Cart.get = read;
  Cart.count = function(){ return read().length; };
  Cart.isResident = function(){ return localStorage.getItem(RESIDENT_KEY)==='1'; };
  Cart.setResident = function(v){ localStorage.setItem(RESIDENT_KEY, v?'1':'0'); dispatch(); };

  /* ---- пересечение временных интервалов ---- */
  function toMin(t){ if(!t) return null; var p=t.split(':'); return (+p[0])*60+(+p[1]); }
  function overlap(aS,aE,bS,bE){
    // без времени (shift/day) — конфликт по совпадению даты
    if(aS==null||bS==null) return true;
    return toMin(aS) < toMin(bE) && toMin(bS) < toMin(aE);
  }
  // абсолютная минута = индекс дня * 1440 + время суток (для интервалов, переходящих через сутки)
  function dayIndex(dateISO){ return Math.round(new Date(dateISO+'T12:00:00').getTime()/86400000); }
  function absMin(dateISO, hhmm, fallbackMin){
    var m = hhmm!=null ? toMin(hhmm) : fallbackMin;
    return dayIndex(dateISO)*1440 + m;
  }
  // datetime-интервал строки/слота как [начало, конец] в абсолютных минутах
  function slotAbs(dateStart, timeStart, dateEnd, timeEnd){
    if(timeStart==null){ // весь день (сменная/дневная бронь без времени)
      return [ dayIndex(dateStart)*1440, dayIndex(dateEnd||dateStart)*1440 + 1440 ];
    }
    return [ absMin(dateStart, timeStart, 0), absMin(dateEnd||dateStart, timeEnd, 1440) ];
  }

  /* ---- проверка конфликта по времени (только расписание, не корзина) ---- */
  // свою корзину не блокируем — можно бронировать несколько пересекающихся позиций.
  Cart.conflict = function(resId, date, slotStart, slotEnd){
    var clash=null;
    P.getBusy(resId).forEach(function(b){
      if(b.date===date && overlap(slotStart,slotEnd,b.slotStart,b.slotEnd)) clash='занято в расписании';
    });
    return clash;
  };

  /* ---- проверка конфликта диапазона дат (только расписание, не корзина) ---- */
  // занятые дни в календаре и так недоступны для выбора; свою корзину не блокируем —
  // можно бронировать несколько пересекающихся позиций.
  Cart.conflictRange = function(resId, startDate, endDate){
    if(!startDate) return null;
    var busy=P.getBusy(resId), clash=null;
    P.dates.range(startDate, endDate).forEach(function(d){
      if(busy.some(function(b){ return b.date===d; })) clash='занято в расписании ('+P.dates.human(d)+')';
    });
    return clash;
  };

  /* ---- дни → тарифные единицы (смена/сутки = 1/день, час = 8/день) ---- */
  var UNIT_PER_DAY = { 'час':8, 'смена':1, 'сутки':1, 'образец':1, 'партия':1 };
  Cart.rangeUnits = function(res, o){
    var days = o.days || P.dates.days(o.startDate, o.endDate);
    return Math.max(days,1) * (UNIT_PER_DAY[res.priceUnit] || 1);
  };

  /* ---- расчёт цены строки ---- */
  function priceLine(res, opts){
    var v=res.priceValue;
    if(res.bookMode==='range') return { line:v*Cart.rangeUnits(res,opts), unit:v };
    if(res.bookMode==='shift') return { line:v*(opts.shifts||1), unit:v };
    if(res.bookMode==='day')   return { line:v*(opts.qty||1), unit:v };
    if(res.bookMode==='hour')  return { line:v*(opts.hours||res.minUnits||1)*(opts.days||1), unit:v };
    if(res.bookMode==='sample')return { line:v*(opts.qty||1), unit:v };
    return { line:v, unit:v };
  }

  // сколько часов работы оператора нужно на родительскую строку
  function operatorHours(parentRes, opts){
    if(parentRes.bookMode==='hour')  return (opts.hours||parentRes.minUnits||2)*(opts.days||1);
    if(parentRes.bookMode==='day')   return 8*(opts.qty||1);
    if(parentRes.bookMode==='range') return 8*(opts.days||P.dates.days(opts.startDate,opts.endDate)||1);
    if(parentRes.bookMode==='shift') return 8*(opts.shifts||1);
    return 8;
  }

  /* ---- добавить ресурс в корзину ---- */
  // opts: { date, slotStart, slotEnd, qty, hours }
  Cart.add = function(resId, opts){
    opts=opts||{};
    var res=P.getById(resId); if(!res) return {ok:false,msg:'Ресурс не найден'};

    // конфликт по расписанию (свою корзину не блокируем)
    var byDays = res.bookMode==='range' || res.bookMode==='shift';
    var c=null;
    if(byDays){
      c=Cart.conflictRange(resId, opts.startDate, opts.endDate);
    } else if(res.bookMode==='hour'){
      // почасово, возможно на несколько дней — проверяем слот в каждый день
      P.dates.range(opts.startDate||opts.date, opts.endDate||opts.date).forEach(function(d){
        if(!c){ var x=Cart.conflict(resId, d, opts.slotStart||null, opts.slotEnd||null); if(x) c=x; }
      });
    } else {
      c=Cart.conflict(resId, opts.date, opts.slotStart||null, opts.slotEnd||null);
    }
    if(c){
      return byDays
        ? {ok:false,msg:'Часть дат '+c+'. Выберите другие даты.'}
        : {ok:false,msg:'Этот слот '+c+'. Выберите другое время.'};
    }

    var lines=read();
    var isRange=res.bookMode==='range', isShift=res.bookMode==='shift';
    var pr=priceLine(res,opts);
    var parentId=uid();
    lines.push({
      lineId:parentId, resourceId:res.id, type:res.type, bookMode:res.bookMode,
      title:res.title, lab:res.lab, img:res.img, unit:res.priceUnit,
      date:opts.date||null, slotStart:opts.slotStart||null, slotEnd:opts.slotEnd||null,
      startDate:opts.startDate||null, endDate:opts.endDate||null,
      shiftType:opts.shiftType||null, shifts:opts.shifts||null,
      days: isRange ? P.dates.days(opts.startDate, opts.endDate) : (opts.days||null),
      units: isRange ? Cart.rangeUnits(res,opts) : null,
      qty:opts.qty||1, hours: (isRange||isShift) ? null : (opts.hours||null),
      unitPrice:pr.unit, linePrice:pr.line,
      linkedTo:null, isOperator:false
    });

    // авто-подтягивание оператора
    if(res.requiresOperator){
      var op=P.getById(res.requiresOperator);
      if(op){
        var h=operatorHours(res,opts);
        lines.push({
          lineId:uid(), resourceId:op.id, type:'specialist', bookMode:'hour',
          title:op.title, lab:op.lab, img:op.img, unit:'час',
          date:opts.date||null,
          // оператор показывается общей длительностью (а не слотом)
          slotStart:null, slotEnd:null,
          startDate:opts.startDate||null, endDate:opts.endDate||null,
          qty:1, hours:h, unitPrice:op.priceValue, linePrice:op.priceValue*h,
          linkedTo:parentId, isOperator:true
        });
      }
    }
    write(lines);
    return {ok:true};
  };

  /* ---- удалить строку (и связанного оператора) ---- */
  Cart.remove = function(lineId){
    var lines=read().filter(function(l){ return l.lineId!==lineId && l.linkedTo!==lineId; });
    write(lines);
  };
  Cart.clear = function(){ write([]); };

  /* ---- включённое в помещение оборудование (bundled) ---- */
  Cart.bundledFor = function(res){
    return (res.bundledWith||[]).map(function(id){ return P.getById(id); }).filter(Boolean);
  };

  /* ---- смета ---- */
  // Скидку 25% даёт только компания, которую оператор подтвердил как резидента
  // ИНТЦ (P.isResident). Галочка в корзине — лишь заявление о статусе: она уходит
  // оператору на проверку и сама по себе цену не снижает. Так итог в корзине
  // всегда совпадает с суммой заявки, которую посчитает сервер.
  Cart.totals = function(){
    var lines=read();
    var subtotal=lines.reduce(function(s,l){ return s+l.linePrice; },0);
    var claim=Cart.isResident();
    var confirmed=!!(P.isResident && P.isResident());
    var discount= confirmed ? Math.round(subtotal*RESIDENT_DISCOUNT) : 0;
    return { subtotal:subtotal, resident:confirmed, claim:claim, confirmed:confirmed,
             discount:discount, total:subtotal-discount, count:lines.length };
  };

  /* ---- разворот брони в строки-по-дню под модель бэкенда ---- */
  // Бэкенд хранит одну дату на строку и считает цену = цена×(часы для почасовых)×кол-во.
  // Поэтому многодневную/сменную бронь разворачиваем в отдельные строки на каждый день,
  // где каждая строка = ровно одна единица (1 смена / 1 сутки / N часов).
  var SHIFT_WIN = { day:{s:'09:00', e:'17:00'}, eve:{s:'18:00', e:'02:00'} };
  function daysOf(l){ return P.dates.range(l.startDate||l.date, l.endDate||l.startDate||l.date); }
  function expandLine(l, parent){
    var base={ resourceId:l.resourceId, unitPrice:l.unitPrice||0, isOperator:!!l.isOperator };
    var out=[];
    if(l.isOperator){
      // Оператор занят ровно тогда же, когда и его прибор: те же дни и то же окно
      // времени. Одной строкой без слота нельзя — иначе специалист блокируется на
      // весь день при 2-часовой брони и, наоборот, остаётся «свободен» во 2-й и
      // последующие дни многодневной брони.
      var p = parent || l;
      var opDays = daysOf(p);
      if(p.bookMode==='sample'){ // услуга под ключ — без даты
        out.push(Object.assign({date:null, slotStart:null, slotEnd:null,
          qty:1, hours:l.hours||8, linePrice:(l.unitPrice||0)*(l.hours||8)}, base));
        return out;
      }
      if(p.bookMode==='shift'){  // смена лаборатории = 8 ч работы оператора
        var opShifts = p.shiftType==='full' ? ['day','eve'] : [p.shiftType||'day'];
        opDays.forEach(function(d){ opShifts.forEach(function(s){
          out.push(Object.assign({date:d, slotStart:SHIFT_WIN[s].s, slotEnd:SHIFT_WIN[s].e,
            qty:1, hours:8, linePrice:(l.unitPrice||0)*8}, base));
        }); });
        return out;
      }
      // почасовое оборудование — окно прибора; суточное — весь день (8 ч)
      var hPerDay = p.bookMode==='hour' ? (p.hours||2) : 8;
      var byHour  = p.bookMode==='hour';
      opDays.forEach(function(d){
        out.push(Object.assign({date:d,
          slotStart: byHour ? (p.slotStart||null) : null,
          slotEnd:   byHour ? (p.slotEnd||null)   : null,
          qty:1, hours:hPerDay, linePrice:(l.unitPrice||0)*hPerDay}, base));
      });
      return out;
    }
    if(l.bookMode==='sample'){
      out.push(Object.assign({date:null, slotStart:null, slotEnd:null, qty:l.qty||1, hours:null,
        linePrice:l.linePrice}, base));
      return out;
    }
    if(l.bookMode==='shift'){
      var shifts = l.shiftType==='full' ? ['day','eve'] : [l.shiftType||'day'];
      daysOf(l).forEach(function(d){ shifts.forEach(function(s){
        out.push(Object.assign({date:d, slotStart:SHIFT_WIN[s].s, slotEnd:SHIFT_WIN[s].e,
          qty:1, hours:null, linePrice:l.unitPrice||0}, base));
      }); });
      return out;
    }
    if(l.bookMode==='hour'){
      daysOf(l).forEach(function(d){
        out.push(Object.assign({date:d, slotStart:l.slotStart||null, slotEnd:l.slotEnd||null,
          qty:1, hours:l.hours||null, linePrice:(l.unitPrice||0)*(l.hours||1)}, base));
      });
      return out;
    }
    // range/day (суточное оборудование) — по одной строке на день
    daysOf(l).forEach(function(d){
      out.push(Object.assign({date:d, slotStart:null, slotEnd:null, qty:1, hours:null,
        linePrice:l.unitPrice||0}, base));
    });
    return out;
  }

  /* ---- оформить заявку (POST в бэкенд) ---- */
  Cart.checkout = function(contact){
    var lines=read(); if(!lines.length) return Promise.resolve({ok:false,msg:'Корзина пуста'});
    var t=Cart.totals();
    // сводка для страницы подтверждения (данные корзины ещё есть до очистки)
    var summary={ lines:lines.slice(), contact:contact, subtotal:t.subtotal,
                  discount:t.discount, total:t.total };
    var apiLines=[];
    var byId={}; lines.forEach(function(l){ byId[l.lineId]=l; });
    lines.forEach(function(l){ apiLines=apiLines.concat(expandLine(l, l.linkedTo?byId[l.linkedTo]:null)); });
    // resident — заявление о статусе: подтверждённый резидент или галочка в корзине.
    // Итоговое решение о скидке принимает сервер по профилю компании.
    var payload={ contact:contact, resident:!!(t.claim || t.confirmed), lines:apiLines };
    return P.apiFetch('/orders/', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    }).then(function(r){ return r.json().then(function(j){ return {status:r.status, body:j}; }); })
      .then(function(res){
        if(res.status>=200 && res.status<300 && res.body && res.body.ok){
          summary.id=res.body.id;
          // суммы берём из ответа сервера: скидку резидента считает он
          if(typeof res.body.subtotal==='number') summary.subtotal=res.body.subtotal;
          if(typeof res.body.discount==='number') summary.discount=res.body.discount;
          if(typeof res.body.total==='number')    summary.total=res.body.total;
          summary.residentClaimed = !!t.claim && !res.body.resident;
          P.lastOrder=summary; Cart.clear();
          return {ok:true, order:summary};
        }
        var msg=(res.body && (res.body.detail || res.body.lines)) || 'Не удалось оформить заявку. Попробуйте ещё раз.';
        return {ok:false, msg:(typeof msg==='string'?msg:'Проверьте данные и попробуйте снова.')};
      })
      .catch(function(){ return {ok:false, msg:'Нет связи с сервером. Проверьте подключение и попробуйте снова.'}; });
  };
})();
