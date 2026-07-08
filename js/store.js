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

  /* ---- расчёт цены строки ---- */
  function priceLine(res, opts){
    var v=res.priceValue;
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
    if(parentRes.bookMode==='shift') return 8;
    return 8;
  }

  /* ---- добавить ресурс в корзину ---- */
  // opts: { date, slotStart, slotEnd, qty, hours }
  Cart.add = function(resId, opts){
    opts=opts||{};
    var res=P.getById(resId); if(!res) return {ok:false,msg:'Ресурс не найден'};

    // конфликт по времени
    var c=Cart.conflict(resId, opts.date, opts.slotStart||null, opts.slotEnd||null);
    if(c) return {ok:false,msg:'Этот слот '+c+'. Выберите другое время.'};

    var lines=read();
    var pr=priceLine(res,opts);
    var parentId=uid();
    lines.push({
      lineId:parentId, resourceId:res.id, type:res.type, bookMode:res.bookMode,
      title:res.title, lab:res.lab, img:res.img, unit:res.priceUnit,
      date:opts.date||null, slotStart:opts.slotStart||null, slotEnd:opts.slotEnd||null,
      qty:opts.qty||1, hours:opts.hours||null,
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
          date:opts.date||null, slotStart:opts.slotStart||null, slotEnd:opts.slotEnd||null,
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
