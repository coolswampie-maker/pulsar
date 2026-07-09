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

  /* ---- проверка конфликта: занятость + уже добавленное ---- */
  Cart.conflict = function(resId, date, slotStart, slotEnd){
    var clash=null;
    P.getBusy(resId).forEach(function(b){
      if(b.date===date && overlap(slotStart,slotEnd,b.slotStart,b.slotEnd)) clash='занято в расписании';
    });
    read().forEach(function(l){
      if(l.resourceId===resId && l.date===date && overlap(slotStart,slotEnd,l.slotStart,l.slotEnd))
        clash='уже в вашей корзине';
    });
    return clash;
  };

  /* ---- проверка конфликта для datetime-промежутка (помещения) ---- */
  // интервал брони: [дата+время начала .. дата+время конца]; даты могут различаться.
  // конфликт — реальное пересечение интервалов (учитывает переход через сутки).
  Cart.conflictInterval = function(resId, startDate, startTime, endDate, endTime){
    if(!startDate) return null;
    var iv = slotAbs(startDate, startTime, endDate, endTime), clash=null;
    function hit(a){ return iv[0] < a[1] && a[0] < iv[1]; }
    P.getBusy(resId).forEach(function(b){
      if(hit(slotAbs(b.date, b.slotStart, b.date, b.slotEnd))) clash='занято в расписании';
    });
    read().forEach(function(l){
      if(l.resourceId!==resId) return;
      var a = l.bookMode==='range'
        ? slotAbs(l.startDate||l.date, l.slotStart, l.endDate||l.date, l.slotEnd)
        : slotAbs(l.date, l.slotStart, l.date, l.slotEnd);
      if(hit(a)) clash='уже занято в вашей брони';
    });
    return clash;
  };

  /* ---- datetime-интервал → часы и единицы тарифа ---- */
  // длина интервала брони в часах
  var UNIT_HOURS = { 'час':1, 'смена':8, 'сутки':24 };
  Cart.rangeHours = function(o){
    var iv=slotAbs(o.startDate, o.slotStart, o.endDate||o.startDate, o.slotEnd);
    return Math.max(0, (iv[1]-iv[0])/60);
  };
  // сколько тарифных единиц (час/смена/сутки) укладывается в интервал, с учётом минимума
  Cart.rangeUnits = function(res, o){
    var uh = UNIT_HOURS[res.priceUnit] || 1;
    return Math.max(Math.ceil(Cart.rangeHours(o)/uh), res.minUnits||1);
  };

  /* ---- расчёт цены строки ---- */
  function priceLine(res, opts){
    var v=res.priceValue;
    if(res.bookMode==='range') return { line:v*Cart.rangeUnits(res,opts), unit:v };
    if(res.bookMode==='shift') return { line:v*(opts.qty||1), unit:v };
    if(res.bookMode==='day')   return { line:v*(opts.qty||1), unit:v };
    if(res.bookMode==='hour')  return { line:v*(opts.hours||res.minUnits||1), unit:v };
    if(res.bookMode==='sample')return { line:v*(opts.qty||1), unit:v };
    return { line:v, unit:v };
  }

  // сколько часов работы оператора нужно на родительскую строку
  function operatorHours(parentRes, opts){
    if(parentRes.bookMode==='hour')  return opts.hours||parentRes.minUnits||2;
    if(parentRes.bookMode==='day')   return 8*(opts.qty||1);
    if(parentRes.bookMode==='range') return Math.max(Math.ceil(Cart.rangeHours(opts)),1);
    if(parentRes.bookMode==='shift') return 8;
    return 8;
  }

  /* ---- добавить ресурс в корзину ---- */
  // opts: { date, slotStart, slotEnd, qty, hours }
  Cart.add = function(resId, opts){
    opts=opts||{};
    var res=P.getById(resId); if(!res) return {ok:false,msg:'Ресурс не найден'};

    // конфликт: помещения — по datetime-интервалу, остальное — по времени в дне
    var c = res.bookMode==='range'
      ? Cart.conflictInterval(resId, opts.startDate, opts.slotStart||null, opts.endDate, opts.slotEnd||null)
      : Cart.conflict(resId, opts.date, opts.slotStart||null, opts.slotEnd||null);
    if(c){
      return res.bookMode==='range'
        ? {ok:false,msg:'Выбранное время '+c+'. Укажите другой промежуток.'}
        : {ok:false,msg:'Этот слот '+c+'. Выберите другое время.'};
    }

    var lines=read();
    var isRange=res.bookMode==='range';
    var pr=priceLine(res,opts);
    var parentId=uid();
    lines.push({
      lineId:parentId, resourceId:res.id, type:res.type, bookMode:res.bookMode,
      title:res.title, lab:res.lab, img:res.img, unit:res.priceUnit,
      date:opts.date||null, slotStart:opts.slotStart||null, slotEnd:opts.slotEnd||null,
      startDate:opts.startDate||null, endDate:opts.endDate||null,
      days: isRange ? P.dates.days(opts.startDate, opts.endDate) : (opts.days||null),
      units: isRange ? Cart.rangeUnits(res,opts) : null,
      qty:opts.qty||1, hours: isRange ? Cart.rangeHours(opts) : (opts.hours||null),
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
          // при интервальной брони оператор идёт на весь промежуток (показываем длительность, а не слот)
          slotStart: isRange ? null : (opts.slotStart||null),
          slotEnd:   isRange ? null : (opts.slotEnd||null),
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
  Cart.totals = function(){
    var lines=read();
    var subtotal=lines.reduce(function(s,l){ return s+l.linePrice; },0);
    var resident=Cart.isResident();
    var discount= resident ? Math.round(subtotal*RESIDENT_DISCOUNT) : 0;
    return { subtotal:subtotal, resident:resident, discount:discount, total:subtotal-discount, count:lines.length };
  };

  /* ---- оформить заявку ---- */
  Cart.checkout = function(contact){
    var lines=read(); if(!lines.length) return {ok:false,msg:'Корзина пуста'};
    var t=Cart.totals();
    var orders=P.getOrders();
    var num = 'PLS-' + String(1000+orders.length+1);
    var order={
      id:num,
      createdAt:new Date().toISOString(),
      createdHuman: new Date().toLocaleString('ru-RU',{day:'numeric',month:'long',hour:'2-digit',minute:'2-digit'}),
      lines:lines, contact:contact, resident:t.resident,
      subtotal:t.subtotal, discount:t.discount, total:t.total, status:'new'
    };
    orders.unshift(order);
    P.saveOrders(orders);
    Cart.clear();
    return {ok:true, order:order};
  };
})();
