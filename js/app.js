/* ============================================================
   ПУЛЬСАР — приложение: hash-роутер и представления.
   ============================================================ */
(function(){
  var P = window.PULSAR;
  var app = document.getElementById('app');
  var img = P.imgTag, getImg = P.getImage;

  /* ---------------- утилиты ---------------- */
  function fmt(n){ return (Math.round(n)||0).toLocaleString('ru-RU').replace(/,/g,' ')+' ₽'; }
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function el(id){ return document.getElementById(id); }
  function qsAll(s,root){ return Array.prototype.slice.call((root||document).querySelectorAll(s)); }
  function unitLabel(r){ return '/ '+r.priceUnit; }

  var ICON = {
    building:'<path d="M4 21V5l8-3 8 3v16"/><path d="M4 21h16M9 9h.01M15 9h.01M9 13h.01M15 13h.01M9 17h.01M15 17h.01"/>',
    device:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6M9 15h3"/>',
    user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    doc:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    dna:'<path d="M8 4c0 6 8 6 8 12M16 4c0 6-8 6-8 12M8 5h8M8 19h8M10 8h4M10 15h4"/>',
    cpu:'<rect x="7" y="7" width="10" height="10" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    flask:'<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/><path d="M7.5 15h9"/>',
    rocket:'<path d="M12 2c3 2 5 6 5 11l-3 3h-4l-3-3c0-5 2-9 5-11z"/><circle cx="12" cy="9" r="1.5"/><path d="M9 17l-3 4M15 17l3 4"/>',
    atom:'<circle cx="12" cy="12" r="2"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>',
    leaf:'<path d="M4 20c0-8 6-14 16-14 0 10-6 16-16 14z"/><path d="M4 20c4-6 8-8 12-9"/>',
    pill:'<rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(-45 12 12)"/><path d="M9 9l6 6"/>',
    check:'<path d="M20 6L9 17l-5-5"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    pin:'<path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    phone:'<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2 4.2 2 2 0 0 1 4 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>'
  };
  function icon(name,size){ return '<svg width="'+(size||22)+'" height="'+(size||22)+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+(ICON[name]||ICON.device)+'</svg>'; }

  function toast(msg){
    var t=el('toast'); t.innerHTML='<span class="ok-dot">'+icon('check',16)+'</span>'+esc(msg);
    t.classList.add('show'); clearTimeout(t._t); t._t=setTimeout(function(){ t.classList.remove('show'); },2600);
  }

  function render(html, mount){
    app.innerHTML=html; window.scrollTo(0,0);
    if(mount) mount();
    applyReveal();
    syncNav(); syncCart();
  }
  function applyReveal(){
    var els=qsAll('.res-card,.tile,.step,.dir-clean .d,.card-flat,.figure,.promo');
    if(!els.length) return;
    els.forEach(function(e){ e.classList.add('reveal'); });
    if(!('IntersectionObserver' in window)){ els.forEach(function(e){e.classList.add('in');}); return; }
    var io=new IntersectionObserver(function(ents){
      ents.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } });
    },{rootMargin:'0px 0px -6% 0px'});
    els.forEach(function(e){ io.observe(e); });
    setTimeout(function(){ els.forEach(function(e){ e.classList.add('in'); }); },1600); // страховка
  }
  function syncCart(){
    var c=P.cart.count(), b=el('cartcount');
    if(b){ b.textContent=c; b.setAttribute('data-empty', c?'0':'1'); }
  }
  function syncNav(){
    var path=(location.hash.replace('#','')||'/').split('?')[0];
    qsAll('[data-nav]').forEach(function(a){
      a.classList.toggle('active', a.getAttribute('data-nav')===path);
    });
  }
  window.addEventListener('pulsar:cart', syncCart);

  /* ---------------- переиспользуемые куски ---------------- */
  function availBadge(id){
    var s=P.availabilityLabel(id);
    return s==='ok'
      ? '<span class="res-avail ok">Свободно сегодня</span>'
      : '<span class="res-avail busy">Занято сегодня</span>';
  }
  function resCard(r){
    var op = r.requiresOperator ? '<span class="op-flag">'+icon('user',13)+' с оператором</span>' : '';
    return ''+
    '<a class="res-card" href="#/resource/'+r.id+'">'+
      '<div class="res-media">'+img(r,'',r.title)+
        '<span class="res-badge">'+(r.cleanClass||P.typeMeta[r.type].single)+'</span>'+
      '</div>'+
      '<div class="res-body">'+
        '<div class="res-lab">'+esc(r.lab)+'</div>'+
        '<div class="res-title">'+esc(r.title)+'</div>'+
        op+
        '<ul class="res-specs">'+r.specs.slice(0,3).map(function(s){return '<li>'+esc(s)+'</li>';}).join('')+'</ul>'+
        '<div class="res-foot">'+
          '<div class="res-price">'+fmt(r.priceValue)+'<small>'+unitLabel(r)+'</small></div>'+
          '<span class="btn btn-outline btn-sm">Подробнее</span>'+
        '</div>'+
      '</div>'+
    '</a>';
  }

  /* ==========================================================
     ГЛАВНАЯ
     ========================================================== */
  function viewHome(){
    var arrow='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M8 7h9v9"/></svg>';
    var tiles=[
      ['room','Лаборатории','Чистые комнаты ISO 5–7, GMP-зоны, испытательные комплексы','room-cleanroom-v'],
      ['equipment','Оборудование','Микроскопы, спектрометры, испытательные и климатические камеры','eq-vk1000'],
      ['specialist','Специалисты','Операторы приборов и инженеры под конкретную задачу','sp-bioinf'],
      ['service','Услуги под ключ','Аналитика по образцу: сдал образец — получил протокол','srv-xrd']
    ];
    var featured = P.getResources().filter(function(r){
      return ['eq-massspec','eq-sem','eq-vk1000','eq-nmr','room-cleanroom-a','srv-sem'].indexOf(r.id)>=0;
    });
    var typeChip=function(t,label){ return '<a class="chip-link" href="#/catalog?type='+t+'">'+label+' <span class="n">'+P.getByType(t).length+'</span></a>'; };

    return render(''+
    /* ---- ПОИСКОВЫЙ HERO ---- */
    '<section class="hero2"><div class="wrap"><div class="hero2-grid">'+
      '<div class="hero2-copy">'+
        '<div class="hero2-cobrand">'+
          '<svg class="mgu-mark" viewBox="0 0 64 58" aria-hidden="true"><g fill="currentColor">'+
          '<rect x="5" y="42" width="12" height="15"/><rect x="47" y="42" width="12" height="15"/>'+
          '<rect x="17" y="36" width="8" height="21"/><rect x="39" y="36" width="8" height="21"/>'+
          '<rect x="26" y="21" width="12" height="36"/><rect x="29.5" y="13" width="5" height="9"/>'+
          '<polygon points="32,3 29.5,13 34.5,13"/><circle cx="32" cy="4" r="1.7"/></g></svg>'+
          '<span>МГУ им. М.В. Ломоносова · ИНТЦ «Воробьёвы&nbsp;горы»</span></div>'+
        '<div class="eyebrow">Платформа лабораторной инфраструктуры</div>'+
        '<h1>Найдите и забронируйте <em>научную инфраструктуру</em> МГУ</h1>'+
        '<p class="lead">Приборы, чистые комнаты, специалисты и аналитические услуги ИНТЦ «Воробьёвы горы» — в аренду по заявке.</p>'+
        '<form class="searchbar" id="hsearch" onsubmit="return false">'+
          '<select id="hsel" aria-label="Раздел">'+
            '<option value="equipment">Оборудование</option>'+
            '<option value="room">Лаборатории</option>'+
            '<option value="specialist">Специалисты</option>'+
            '<option value="service">Услуги</option>'+
          '</select>'+
          '<input id="hq" placeholder="Масс-спектрометр, чистая комната, ICP-MS…">'+
          '<button id="hgo" type="submit"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>Найти</button>'+
        '</form>'+
        '<div class="chips">'+
          typeChip('room','Лаборатории')+typeChip('equipment','Оборудование')+
          typeChip('specialist','Специалисты')+typeChip('service','Услуги под ключ')+
        '</div>'+
      '</div>'+
      '<div class="hero2-media">'+
        '<span class="hero2-frame"></span>'+
        img({img:'hero-media',title:'Лаборатория ИНТЦ МГУ'},'','Лаборатория ИНТЦ МГУ «Воробьёвы горы»')+
        '<div class="hero2-card">'+
          '<svg class="hero2-card-ic" viewBox="0 0 40 40" aria-hidden="true"><g transform="rotate(-28 20 20)"><ellipse cx="20" cy="20" rx="11.5" ry="4.6" fill="none" stroke="#CBA968" stroke-width="1.7" opacity="0.5"/><path d="M20 16.4 L17.6 3 L22.4 3 Z" fill="#CBA968"/><path d="M20 23.6 L17.6 37 L22.4 37 Z" fill="#CBA968"/><circle cx="20" cy="20" r="3.6" fill="#fff"/></g></svg>'+
          '<div><b>Единый оператор</b><span>научной инфраструктуры МГУ</span></div>'+
        '</div>'+
      '</div>'+
    '</div></div></section>'+

    /* ---- ПЛИТКИ КАТЕГОРИЙ ---- */
    '<section class="section"><div class="wrap">'+
      '<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:26px;flex-wrap:wrap">'+
        '<div><div class="eyebrow">Каталог</div><h2 class="h-lg">Что можно забронировать</h2></div>'+
        '<a class="btn btn-outline btn-sm" href="#/catalog">Весь каталог →</a>'+
      '</div>'+
      '<div class="tiles">'+tiles.map(function(t){
        return '<a class="tile" href="#/catalog?type='+t[0]+'">'+img(P.getById(t[3]),'',t[1])+
          '<span class="tile-arrow">'+arrow+'</span>'+
          '<div class="tile-body"><div class="tile-count">'+P.getByType(t[0]).length+' позиций</div>'+
          '<div class="tile-name">'+t[1]+'</div><div class="tile-desc">'+t[2]+'</div></div></a>';
      }).join('')+'</div>'+
    '</div></section>'+

    /* ---- КЛАСТЕР «ЛОМОНОСОВ» ---- */
    '<section class="section" style="background:var(--paper-2);border-top:1px solid var(--line);border-bottom:1px solid var(--line)"><div class="wrap"><div class="grid-2">'+
      '<div>'+
        '<div class="eyebrow">Где мы находимся</div>'+
        '<h2 class="h-lg" style="margin-bottom:16px">Кластер «Ломоносов»</h2>'+
        '<p class="prose"><p>Инфраструктура ПУЛЬСАР расположена в ИНТЦ МГУ «Воробьёвы горы» — научно-технологической долине МГУ им. М.В. Ломоносова. Кластер «Ломоносов» объединяет лаборатории, чистые комнаты и опытные производства ведущего университета страны.</p></p>'+
        '<a class="btn btn-primary" href="#/catalog" style="margin-top:6px">Открыть каталог</a>'+
      '</div>'+
      '<div class="figure">'+img({img:'hero',title:'Кластер «Ломоносов»'},'','Кластер «Ломоносов» · ИНТЦ МГУ «Воробьёвы горы»')+
        '<div class="figure-cap">Кластер «Ломоносов» · ИНТЦ МГУ «Воробьёвы горы»</div></div>'+
    '</div></div></section>'+

    /* ---- КАК РАБОТАЕМ (компактно) ---- */
    '<section class="section section-invert"><div class="wrap">'+
      '<div class="eyebrow">Как работаем</div><h2 class="h-lg" style="margin-bottom:34px">Четыре шага до доступа</h2>'+
      '<div class="steps">'+[
        ['Найдите ресурс','Поиск по каталогу приборов, помещений и услуг'],
        ['Соберите заявку','Выберите дату и слот — оператор добавится автоматически'],
        ['Подтверждение','Оператор согласует бронирование и договор'],
        ['Работа на объекте','Инструктаж, доступ и поддержка дежурного инженера']
      ].map(function(s){ return '<div class="step"><h4>'+s[0]+'</h4><p>'+s[1]+'</p></div>'; }).join('')+'</div>'+
    '</div></section>'+

    /* ---- РЕЗИДЕНТАМ (лёгкая полоса) ---- */
    '<section class="section" style="padding:44px 0 72px"><div class="wrap"><div class="promo">'+
      '<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">'+
        '<div class="promo-badge">−25%</div>'+
        '<div><h3>Резидентам ИНТЦ МГУ</h3><p>Скидка 25% на бронирование лабораторий, оборудования и услуг, а также доступ к научным школам и партнёрам МГУ.</p></div>'+
      '</div>'+
      '<a class="btn btn-primary" href="#/about">Условия резидентства</a>'+
    '</div></div></section>'
    , mountHome);
  }
  function mountHome(){
    var go=function(){
      var t=el('hsel').value, q=el('hq').value.trim();
      catState.type=t; catState.q=q; catState.cat=''; catState.onlyFree=false; catState.sort='default';
      location.hash='#/catalog';
    };
    if(el('hgo')) el('hgo').onclick=go;
    if(el('hq')) el('hq').addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); go(); } });
  }

  /* ==========================================================
     КАТАЛОГ
     ========================================================== */
  var catState={ type:'room', q:'', cat:'', onlyFree:false, sort:'default' };
  function viewCatalog(query){
    if(query && query.type && P.typeMeta[query.type]) catState.type=query.type;
    renderCatalog();
  }
  function renderCatalog(){
    var meta=P.typeMeta;
    var tabs=['room','equipment','specialist','service'].map(function(t){
      var n=P.getByType(t).length;
      return '<button class="tab '+(catState.type===t?'on':'')+'" data-tab="'+t+'">'+meta[t].label+
             ' <span class="cnt">'+n+'</span></button>';
    }).join('');

    // категории, встречающиеся в этом типе
    var cats={};
    P.getByType(catState.type).forEach(function(r){ if(r.category) cats[r.category]=P.categories[r.category]||r.category; });
    var catOpts='<option value="">Все направления</option>'+Object.keys(cats).map(function(k){
      return '<option value="'+k+'"'+(catState.cat===k?' selected':'')+'>'+esc(cats[k])+'</option>';
    }).join('');

    render(''+
    '<section class="page-head"><div class="wrap">'+
      '<div class="eyebrow">Каталог инфраструктуры</div>'+
      '<h1 class="h-lg">Аренда и бронирование</h1>'+
      '<p>Лаборатории, оборудование, специалисты и услуги «под ключ». Приборы с пометкой «с оператором» бронируются вместе со специалистом автоматически.</p>'+
    '</div></section>'+
    '<section class="section-sm"><div class="wrap">'+
      '<div class="tabs" id="tabs">'+tabs+'</div>'+
      '<div class="catalog-layout">'+
        '<aside class="filters">'+
          '<div class="fgroup"><h4>Поиск</h4><input class="search-box" id="fsearch" placeholder="Название, прибор…" value="'+esc(catState.q)+'"></div>'+
          '<div class="fgroup"><h4>Направление</h4><select id="fcat">'+catOpts+'</select></div>'+
          '<div class="fgroup"><h4>Сортировка</h4><select id="fsort">'+
            '<option value="default"'+(catState.sort==='default'?' selected':'')+'>По умолчанию</option>'+
            '<option value="price-asc"'+(catState.sort==='price-asc'?' selected':'')+'>Цена ↑</option>'+
            '<option value="price-desc"'+(catState.sort==='price-desc'?' selected':'')+'>Цена ↓</option>'+
          '</select></div>'+
          '<button class="clearf" id="fclear">Сбросить фильтры</button>'+
        '</aside>'+
        '<div>'+
          '<div class="result-bar" id="rbar"></div>'+
          '<div class="res-grid" id="rgrid"></div>'+
        '</div>'+
      '</div>'+
    '</div></section>'
    , bindCatalog);
  }
  function bindCatalog(){
    qsAll('#tabs .tab').forEach(function(b){ b.onclick=function(){ catState.type=b.getAttribute('data-tab'); catState.cat=''; catState.q=''; renderCatalog(); }; });
    el('fsearch').oninput=function(){ catState.q=this.value; drawList(); };
    el('fcat').onchange=function(){ catState.cat=this.value; drawList(); };
    el('fsort').onchange=function(){ catState.sort=this.value; drawList(); };
    el('fclear').onclick=function(){ catState.q='';catState.cat='';catState.onlyFree=false;catState.sort='default'; renderCatalog(); };
    drawList();
  }
  function drawList(){
    var list=P.getByType(catState.type);
    if(catState.q){ var q=catState.q.toLowerCase();
      list=list.filter(function(r){ return (r.title+' '+r.lab+' '+r.specs.join(' ')+' '+r.description).toLowerCase().indexOf(q)>=0; }); }
    if(catState.cat) list=list.filter(function(r){ return r.category===catState.cat; });
    if(catState.sort==='price-asc') list.sort(function(a,b){ return a.priceValue-b.priceValue; });
    if(catState.sort==='price-desc') list.sort(function(a,b){ return b.priceValue-a.priceValue; });
    var grid=el('rgrid'), bar=el('rbar'); if(!grid) return;
    bar.innerHTML='Найдено: <strong style="color:var(--navy)">'+list.length+'</strong>';
    grid.innerHTML = list.length ? list.map(resCard).join('')
      : '<div class="empty" style="grid-column:1/-1"><h3>Ничего не найдено</h3><p>Измените параметры фильтра.</p></div>';
  }

  /* ==========================================================
     КАРТОЧКА РЕСУРСА + панель бронирования
     ========================================================== */
  var book={};
  function viewResource(id){
    var r=P.getById(id);
    if(!r) return render('<section class="section"><div class="wrap empty"><h3>Ресурс не найден</h3><a class="btn btn-primary" href="#/catalog">В каталог</a></div></section>');
    // разумный дефолт интервала = «1 тарифная единица» от 10:00
    var d1=P.dates.plusISO(1), endD=d1, endT='18:00';
    if(r.priceUnit==='час'){ endT=('0'+(10+(r.minUnits||2))).slice(-2)+':00'; }
    else if(r.priceUnit==='сутки'){ endD=P.dates.plusISO(2); endT='10:00'; }
    book={ res:r, date:d1, start:null, hours:r.minUnits||2, qty:1, shift:'day',
           startDate:d1, endDate:endD, startTime:'10:00', endTime:endT, err:'' };
    var bundled=P.cart.bundledFor(r);
    render(''+
    '<section class="detail"><div class="wrap">'+
      '<div class="crumbs"><a href="#/catalog?type='+r.type+'">'+P.typeMeta[r.type].label+'</a> › '+esc(r.title)+'</div>'+
      '<div class="detail-grid">'+
        '<div>'+
          '<div class="detail-media">'+img(r,'',r.title)+'</div>'+
          '<div class="detail-lab" style="margin-top:16px">'+esc(r.lab)+'</div>'+
          '<h1>'+esc(r.title)+'</h1>'+
          (r.cleanClass?'<div style="margin-bottom:14px"><span class="tag">'+esc(r.cleanClass)+'</span></div>':'')+
          '<p class="detail-desc">'+esc(r.description)+'</p>'+
          '<h3 class="h-md" style="margin-bottom:14px">Характеристики</h3>'+
          '<table class="spec-table"><tbody>'+
            r.specs.map(function(s){ var parts=s.split(':'); return parts.length>1
              ? '<tr><th>'+esc(parts[0])+'</th><td>'+esc(parts.slice(1).join(':').trim())+'</td></tr>'
              : '<tr><td colspan="2">'+esc(s)+'</td></tr>'; }).join('')+
          '</tbody></table>'+
          (bundled.length? '<div class="bundle-note">В стоимость включено: '+bundled.map(function(b){return esc(b.title);}).join(' · ')+'</div>':'')+
        '</div>'+
        '<div><div class="booking" id="booking"></div></div>'+
      '</div>'+
    '</div></section>'
    , renderBooking);
  }

  function timeStarts(){ // 09..16 (чтобы влезло ≥2ч)
    var a=[]; for(var h=9;h<=16;h++) a.push((h<10?'0':'')+h+':00'); return a;
  }
  function computeEnd(start,hours){ var h=parseInt(start,10)+hours; return (h<10?'0':'')+h+':00'; }
  function rangeInvalid(){ return (book.startDate+'T'+book.startTime) >= (book.endDate+'T'+book.endTime); }
  function rangeNoteHtml(){
    var r=book.res;
    if(rangeInvalid()) return '<span class="rn-err">Окончание должно быть позже начала.</span>';
    var o=currentOpts(), hrs=P.cart.rangeHours(o), units=P.cart.rangeUnits(r,o);
    var uw=P.unitShort[r.priceUnit]||r.priceUnit;
    var span = book.startDate===book.endDate
      ? P.dates.human(book.startDate)+', '+book.startTime+'–'+book.endTime
      : P.dates.human(book.startDate)+' '+book.startTime+' → '+P.dates.human(book.endDate)+' '+book.endTime;
    var dur = (hrs%1===0? hrs : hrs.toFixed(1))+' ч';
    return span+' · <strong>'+units+' '+esc(uw)+'</strong> ('+dur+')';
  }
  function refreshRange(){ var n=el('rnote'); if(n) n.innerHTML=rangeNoteHtml(); updateEstimate(); }

  function renderBooking(){
    var r=book.res, b=el('booking'); if(!b) return;
    var priceHead=fmt(r.priceValue)+' <small>'+unitLabel(r)+'</small>';
    var html='<div class="price-lead">'+priceHead+'</div><hr>';

    if(r.type==='service'){
      html+='<div class="field"><label>Количество образцов</label>'+
        '<input type="number" id="bqty" min="'+(r.minUnits||1)+'" value="'+book.qty+'"></div>'+
        '<div class="op-note">'+icon('clock',16)+'<div>Услуга «под ключ»: время прибора и работа специалиста включены. Срок — по регламенту услуги.</div></div>';
    } else if(r.bookMode==='range'){
      html+='<div class="field"><label>Начало</label><div class="field-row">'+
          '<input type="date" id="bstartd" min="'+P.dates.todayISO()+'" value="'+book.startDate+'">'+
          '<input type="time" id="bstartt" step="1800" value="'+book.startTime+'">'+
        '</div></div>'+
        '<div class="field"><label>Окончание</label><div class="field-row">'+
          '<input type="date" id="bendd" min="'+book.startDate+'" value="'+book.endDate+'">'+
          '<input type="time" id="bendt" step="1800" value="'+book.endTime+'">'+
        '</div></div>'+
        '<div class="range-note" id="rnote">'+rangeNoteHtml()+'</div>';
    } else {
      html+='<div class="field"><label>Дата</label><input type="date" id="bdate" min="'+P.dates.todayISO()+'" value="'+book.date+'"></div>';
      if(r.bookMode==='shift'){
        html+='<div class="field"><label>Смена</label><select id="bshift"><option value="day">Дневная смена (09:00–17:00)</option><option value="eve">Вечерняя смена (18:00–02:00)</option></select></div>';
      } else if(r.bookMode==='day'){
        html+='<div class="field"><label>Количество суток</label><input type="number" id="bqty" min="1" max="14" value="'+book.qty+'"></div>';
      } else { // hour
        html+='<div class="field"><label>Время начала</label><div class="slots" id="bslots">'+
          timeStarts().map(function(t){
            var busy=isStartBusy(r.id,book.date,t,book.hours);
            return '<button class="slot'+(book.start===t?' sel':'')+'" data-t="'+t+'"'+(busy?' disabled':'')+'>'+t+'</button>';
          }).join('')+'</div></div>'+
          '<div class="field"><label>Длительность</label><select id="bhours">'+
            [2,3,4,5,6].filter(function(h){return h>=(r.minUnits||1);}).map(function(h){
              return '<option value="'+h+'"'+(book.hours===h?' selected':'')+'>'+h+' ч</option>'; }).join('')+
          '</select></div>';
      }
    }

    if(r.requiresOperator){
      var op=P.getById(r.requiresOperator);
      html+='<div class="op-note">'+icon('user',16)+'<div><strong>Работа с оператором.</strong> В бронирование автоматически добавится «'+esc(op?op.title:'специалист')+'» на тот же слот.</div></div>';
    }

    html+='<hr><div id="best"></div>'+
      '<button class="btn btn-brass btn-block" id="badd" style="margin-top:6px">Добавить в бронирование</button>'+
      '<div id="bmsg"></div>'+
      '<a href="#/cart" class="btn btn-ghost btn-block btn-sm" style="margin-top:8px">Перейти в бронирование →</a>';
    b.innerHTML=html;
    bindBooking();
    updateEstimate();
  }

  function isStartBusy(id,date,start,hours){
    return !!P.cart.conflict(id,date,start,computeEnd(start,hours));
  }
  function bindBooking(){
    var r=book.res;
    if(el('bdate')) el('bdate').onchange=function(){ book.date=this.value; book.start=null; renderBooking(); };
    if(el('bstartd')) el('bstartd').onchange=function(){ book.startDate=this.value; if(book.endDate<book.startDate) book.endDate=book.startDate; renderBooking(); };
    if(el('bstartt')) el('bstartt').onchange=function(){ book.startTime=this.value; refreshRange(); };
    if(el('bendd')) el('bendd').onchange=function(){ book.endDate=this.value; if(book.endDate<book.startDate) book.endDate=book.startDate; renderBooking(); };
    if(el('bendt')) el('bendt').onchange=function(){ book.endTime=this.value; refreshRange(); };
    if(el('bshift')) el('bshift').onchange=function(){ book.shift=this.value; };
    if(el('bqty')) el('bqty').oninput=function(){ book.qty=Math.max(parseInt(this.value||1,10),(r.minUnits||1)); updateEstimate(); };
    if(el('bhours')) el('bhours').onchange=function(){ book.hours=parseInt(this.value,10); renderBooking(); };
    qsAll('#bslots .slot').forEach(function(s){ if(s.disabled) return;
      s.onclick=function(){ book.start=s.getAttribute('data-t'); qsAll('#bslots .slot').forEach(function(x){x.classList.remove('sel');}); s.classList.add('sel'); updateEstimate(); };
    });
    el('badd').onclick=addToCart;
  }
  function currentOpts(){
    var r=book.res, o={};
    if(r.type==='service'){ o.qty=book.qty; return o; }
    if(r.bookMode==='range'){
      o.startDate=book.startDate; o.endDate=book.endDate;
      o.slotStart=book.startTime; o.slotEnd=book.endTime; o.date=book.startDate;
      return o;
    }
    o.date=book.date;
    if(r.bookMode==='shift'){ o.qty=1; o.slotStart=book.shift==='day'?'09:00':'18:00'; o.slotEnd=book.shift==='day'?'17:00':'26:00'; }
    else if(r.bookMode==='day'){ o.qty=book.qty; }
    else { o.hours=book.hours; if(book.start){ o.slotStart=book.start; o.slotEnd=computeEnd(book.start,book.hours); } }
    return o;
  }
  function estimatePrice(){
    var r=book.res, o=currentOpts();
    if(r.bookMode==='range') return r.priceValue*P.cart.rangeUnits(r,o);
    if(r.bookMode==='hour') return r.priceValue*(o.hours||r.minUnits||1);
    if(r.bookMode==='sample'||r.bookMode==='day') return r.priceValue*(o.qty||1);
    return r.priceValue*(o.qty||1);
  }
  function updateEstimate(){
    var r=book.res, box=el('best'); if(!box) return;
    var base=estimatePrice(), opLine='';
    if(r.requiresOperator){
      var op=P.getById(r.requiresOperator);
      var h = r.bookMode==='hour'?book.hours : r.bookMode==='day'?8*book.qty : r.bookMode==='range'?Math.max(Math.ceil(P.cart.rangeHours(currentOpts())),1) : 8;
      if(op){ opLine='<div class="est-line"><span>Оператор ('+h+' ч)</span><span>'+fmt(op.priceValue*h)+'</span></div>'; base+=op.priceValue*h; }
    }
    box.innerHTML='<div class="est-line"><span>'+esc(P.typeMeta[r.type].single)+'</span><span>'+fmt(estimatePrice())+'</span></div>'+
      opLine+'<div class="est-line" style="margin-top:6px"><span>Итого за позицию</span><strong>'+fmt(base)+'</strong></div>';
  }
  function addToCart(){
    var r=book.res, o=currentOpts(), msg=el('bmsg');
    if(r.bookMode==='hour' && !book.start){ msg.innerHTML='<div class="form-msg err">Выберите время начала.</div>'; return; }
    if(r.bookMode==='range' && rangeInvalid()){ msg.innerHTML='<div class="form-msg err">Окончание должно быть позже начала.</div>'; return; }
    var res=P.cart.add(r.id,o);
    if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
    msg.innerHTML='<div class="form-msg ok">Добавлено в бронирование'+(r.requiresOperator?' вместе с оператором':'')+'.</div>';
    toast('Добавлено в бронирование');
    if(r.bookMode==='hour'||r.bookMode==='range') renderBooking(); // обновить занятость
  }

  /* ==========================================================
     КОРЗИНА / БРОНИРОВАНИЕ
     ========================================================== */
  function slotText(l){
    if(l.bookMode==='sample') return l.qty+' образец(ов)';
    if(l.bookMode==='range'){
      var sd=l.startDate||l.date, ed=l.endDate||sd;
      var uw=P.unitShort[l.unit]||l.unit||'';
      var units=l.units? ' · '+l.units+' '+uw : '';
      return sd===ed
        ? P.dates.human(sd)+', '+(l.slotStart||'')+'–'+(l.slotEnd||'')+units
        : P.dates.human(sd)+' '+(l.slotStart||'')+' → '+P.dates.human(ed)+' '+(l.slotEnd||'')+units;
    }
    var d=P.dates.human(l.date);
    if(l.bookMode==='shift') return d+' · '+(l.slotStart==='09:00'?'дневная смена':'вечерняя смена');
    if(l.bookMode==='day') return d+' · '+l.qty+' сут.';
    // час без конкретного времени (напр. оператор при суточной/промежуточной брони)
    if(!l.slotStart){
      var span=(l.startDate&&l.endDate&&l.startDate!==l.endDate)
        ? P.dates.human(l.startDate)+' — '+P.dates.human(l.endDate) : d;
      return span+' · '+(l.hours||'')+' ч';
    }
    return d+' · '+(l.slotStart||'')+'–'+(l.slotEnd||'')+' ('+(l.hours||'')+' ч)';
  }
  function viewCart(){
    var lines=P.cart.get();
    if(!lines.length){
      return render('<section class="cart-wrap"><div class="wrap"><div class="empty">'+
        '<h3>В бронировании пока пусто</h3><p>Добавьте помещения, оборудование, специалистов или услуги из каталога.</p>'+
        '<a class="btn btn-primary" href="#/catalog">Открыть каталог</a></div></div></section>');
    }
    var t=P.cart.totals();
    render(''+
    '<section class="page-head"><div class="wrap"><div class="eyebrow">Бронирование</div><h1 class="h-lg">Ваша заявка</h1>'+
      '<p>Проверьте позиции и оформите заявку. Оператор свяжется для подтверждения бронирования.</p></div></section>'+
    '<section class="cart-wrap"><div class="wrap"><div class="cart-grid">'+
      '<div id="clines">'+lines.map(cartLine).join('')+'</div>'+
      '<aside class="summary" id="summary"></aside>'+
    '</div>'+
      '<div id="checkoutbox"></div>'+
    '</div></section>'
    , function(){ bindCart(); });
  }
  function cartLine(l){
    var r=P.getById(l.resourceId)||{img:l.img,title:l.title};
    return '<div class="cart-line'+(l.linkedTo?' linked':'')+'" style="position:relative">'+
      '<div class="cline-media">'+img(r,'',l.title)+'</div>'+
      '<div>'+
        (l.isOperator?'<div class="cline-link-tag">↳ оператор к оборудованию</div>':'')+
        '<div class="cline-title">'+esc(l.title)+'</div>'+
        '<div class="cline-meta">'+esc(l.lab)+'<br>'+slotText(l)+'</div>'+
      '</div>'+
      '<div class="cline-right">'+
        '<div class="cline-price">'+fmt(l.linePrice)+'</div>'+
        (l.linkedTo?'<span class="cline-meta" style="font-size:12px">удаляется вместе с прибором</span>'
          :'<button class="cline-remove" data-rm="'+l.lineId+'">Убрать</button>')+
      '</div>'+
    '</div>';
  }
  function bindCart(){
    qsAll('[data-rm]').forEach(function(b){ b.onclick=function(){ P.cart.remove(b.getAttribute('data-rm')); viewCart(); }; });
    drawSummary();
  }
  function drawSummary(){
    var t=P.cart.totals(), s=el('summary'); if(!s) return;
    s.innerHTML='<h3>Смета</h3>'+
      '<div class="sum-line"><span>Позиций</span><span>'+t.count+'</span></div>'+
      '<div class="sum-line"><span>Стоимость</span><span>'+fmt(t.subtotal)+'</span></div>'+
      '<label class="resident-toggle"><input type="checkbox" id="resident" '+(t.resident?'checked':'')+'>'+
        '<span><strong>Резидент ИНТЦ МГУ</strong> — скидка 25% на всё бронирование</span></label>'+
      (t.discount?'<div class="sum-line"><span>Скидка резидента</span><span>−'+fmt(t.discount)+'</span></div>':'')+
      '<div class="sum-total"><span>Итого</span><span class="val">'+fmt(t.total)+'</span></div>'+
      '<button class="btn btn-brass btn-block" id="tocheckout" style="margin-top:18px">Оформить заявку</button>'+
      '<button class="btn btn-ghost btn-block btn-sm" id="clearcart" style="margin-top:8px">Очистить</button>';
    el('resident').onchange=function(){ P.cart.setResident(this.checked); drawSummary(); };
    el('clearcart').onclick=function(){ P.cart.clear(); viewCart(); };
    el('tocheckout').onclick=function(){ drawCheckout(); el('checkoutbox').scrollIntoView({behavior:'smooth'}); };
  }
  function drawCheckout(){
    var box=el('checkoutbox');
    box.innerHTML='<div class="checkout-form"><h3>Контактные данные</h3>'+
      '<p class="sub">Гостевая заявка — регистрация не требуется. Мы свяжемся с вами для подтверждения.</p>'+
      '<div class="form-grid">'+
        '<div class="field"><label>Организация *</label><input id="c_org" placeholder="ООО «Название»"></div>'+
        '<div class="field"><label>Контактное лицо *</label><input id="c_name" placeholder="Иванов Иван Иванович"></div>'+
        '<div class="field"><label>Email *</label><input id="c_email" type="email" placeholder="ivan@company.ru"></div>'+
        '<div class="field"><label>Телефон *</label><input id="c_phone" placeholder="+7 (___) ___-__-__"></div>'+
        '<div class="field full"><label>Комментарий</label><input id="c_note" placeholder="Опишите задачу или пожелания"></div>'+
      '</div>'+
      '<div id="c_msg"></div>'+
      '<button class="btn btn-brass" id="submitorder" style="margin-top:8px">Отправить заявку</button>'+
    '</div>';
    el('submitorder').onclick=submitOrder;
  }
  function submitOrder(){
    var org=el('c_org').value.trim(), name=el('c_name').value.trim(),
        email=el('c_email').value.trim(), phone=el('c_phone').value.trim();
    var msg=el('c_msg');
    if(!org||!name||!email||!phone){ msg.innerHTML='<div class="form-msg err">Заполните обязательные поля (*).</div>'; return; }
    if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ msg.innerHTML='<div class="form-msg err">Проверьте email.</div>'; return; }
    var res=P.cart.checkout({org:org,name:name,email:email,phone:phone,note:el('c_note').value.trim()});
    if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
    location.hash='#/order/'+res.order.id;
  }

  /* ==========================================================
     ПОДТВЕРЖДЕНИЕ ЗАЯВКИ
     ========================================================== */
  function viewOrder(id){
    var o=P.getOrders().find(function(x){return x.id===id;});
    if(!o) return render('<section class="section"><div class="wrap empty"><h3>Заявка не найдена</h3><a class="btn btn-primary" href="#/catalog">В каталог</a></div></section>');
    render('<section class="confirm"><div class="wrap">'+
      '<div class="check-ic">'+icon('check',34)+'</div>'+
      '<h1>Заявка принята</h1>'+
      '<div class="onum">№ '+esc(o.id)+'</div>'+
      '<p class="muted">Спасибо, '+esc(o.contact.name.split(' ')[0]||o.contact.name)+'. Оператор ПУЛЬСАР свяжется с вами для подтверждения бронирования и оформления договора.</p>'+
      '<div class="confirm-card">'+
        o.lines.map(function(l){ return '<div class="cl"><span>'+esc(l.title)+(l.isOperator?' <em style="color:var(--brass)">(оператор)</em>':'')+'</span><span>'+fmt(l.linePrice)+'</span></div>'; }).join('')+
        (o.discount?'<div class="cl"><span>Скидка резидента ИНТЦ</span><span>−'+fmt(o.discount)+'</span></div>':'')+
        '<div class="cl" style="font-weight:700;color:var(--navy)"><span>Итого</span><span>'+fmt(o.total)+'</span></div>'+
      '</div>'+
      '<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">'+
        '<a class="btn btn-primary" href="#/catalog">Продолжить в каталоге</a>'+
        '<a class="btn btn-outline" href="#/admin">Открыть кабинет оператора</a>'+
      '</div>'+
    '</div></section>');
  }

  /* ==========================================================
     ДЕМО-КАБИНЕТ ОПЕРАТОРА
     ========================================================== */
  var adminTab='orders';
  function viewAdmin(){
    render('<section class="admin-head"><div class="wrap">'+
      '<div class="eyebrow">Демо-кабинет</div>'+
      '<h1 class="h-lg">Кабинет оператора</h1>'+
      '<p>Заявки, загрузка ресурсов и управление каталогом. Данные демо хранятся локально в браузере.</p>'+
    '</div></section>'+
    '<section class="section-sm"><div class="wrap">'+
      '<div class="admin-tabs" id="atabs"></div>'+
      '<div id="adminbody"></div>'+
    '</div></section>', bindAdmin);
  }
  function bindAdmin(){
    var tabs=[['orders','Заявки'],['load','Загрузка'],['catalog','Каталог']];
    el('atabs').innerHTML=tabs.map(function(t){ return '<button class="tab '+(adminTab===t[0]?'on':'')+'" data-at="'+t[0]+'">'+t[1]+'</button>'; }).join('');
    qsAll('#atabs .tab').forEach(function(b){ b.onclick=function(){ adminTab=b.getAttribute('data-at'); bindAdmin(); }; });
    if(adminTab==='orders') adminOrders();
    else if(adminTab==='load') adminLoad();
    else adminCatalog();
  }
  function statusBadge(s){ return s==='confirmed'?'<span class="badge ok">Подтверждена</span>':s==='rejected'?'<span class="badge rej">Отклонена</span>':'<span class="badge new">Новая</span>'; }
  function adminOrders(){
    var orders=P.getOrders(), body=el('adminbody');
    if(!orders.length){ body.innerHTML='<div class="empty"><h3>Заявок пока нет</h3><p>Оформите заявку в каталоге — она появится здесь.</p><a class="btn btn-primary" href="#/catalog">В каталог</a></div>'; return; }
    body.innerHTML=orders.map(function(o){
      return '<div class="order-card">'+
        '<div class="order-top">'+
          '<div><span class="order-id">№ '+esc(o.id)+'</span> &nbsp;'+statusBadge(o.status)+'<div class="cline-meta" style="margin-top:4px">'+esc(o.contact.org)+' · '+esc(o.contact.name)+' · '+esc(o.contact.email)+' · '+esc(o.contact.phone)+'</div></div>'+
          '<div style="text-align:right"><div class="order-id">'+fmt(o.total)+'</div><div class="cline-meta">'+esc(o.createdHuman||'')+'</div></div>'+
        '</div>'+
        '<div class="order-lines">'+o.lines.map(function(l){ return '<div>• '+esc(l.title)+' — <span class="muted">'+slotText(l)+'</span> — '+fmt(l.linePrice)+'</div>'; }).join('')+
          (o.contact.note?'<div style="margin-top:6px">💬 '+esc(o.contact.note)+'</div>':'')+'</div>'+
        '<div class="order-actions">'+
          '<button class="btn btn-primary btn-sm" data-ok="'+o.id+'">Подтвердить</button>'+
          '<button class="btn btn-outline btn-sm" data-rej="'+o.id+'">Отклонить</button>'+
          '<button class="btn btn-ghost btn-sm" data-new="'+o.id+'">Вернуть в новые</button>'+
        '</div>'+
      '</div>';
    }).join('');
    qsAll('[data-ok]').forEach(function(b){ b.onclick=function(){ P.setOrderStatus(b.getAttribute('data-ok'),'confirmed'); toast('Заявка подтверждена'); adminOrders(); }; });
    qsAll('[data-rej]').forEach(function(b){ b.onclick=function(){ P.setOrderStatus(b.getAttribute('data-rej'),'rejected'); adminOrders(); }; });
    qsAll('[data-new]').forEach(function(b){ b.onclick=function(){ P.setOrderStatus(b.getAttribute('data-new'),'new'); adminOrders(); }; });
  }
  function adminLoad(){
    var body=el('adminbody');
    // ближайшие 7 дней
    var days=[]; for(var i=0;i<7;i++){ days.push(P.dates.plusISO(i)); }
    var evByDay={}; days.forEach(function(d){ evByDay[d]=[]; });
    P.getResources().forEach(function(r){
      P.getBusy(r.id).forEach(function(b){
        if(evByDay[b.date]!=null) evByDay[b.date].push({t:r.title,s:b.slotStart});
      });
    });
    body.innerHTML='<p class="muted" style="margin-bottom:16px">Занятость ресурсов на ближайшую неделю: демо-расписание и подтверждённые заявки.</p>'+
      '<div class="load-cal">'+days.map(function(d){
        var ev=evByDay[d].slice(0,4).map(function(e){ return '<div class="ev">'+(e.s?e.s+' ':'')+esc(e.t.split(' ').slice(0,3).join(' '))+'</div>'; }).join('');
        var more=evByDay[d].length>4?'<div class="cline-meta" style="font-size:11px">+'+(evByDay[d].length-4)+' ещё</div>':'';
        return '<div class="load-day"><div class="d">'+P.dates.human(d)+'</div>'+(ev||'<div class="cline-meta" style="font-size:11px">свободно</div>')+more+'</div>';
      }).join('')+'</div>';
  }
  function adminCatalog(){
    var body=el('adminbody'), all=P.getResources();
    body.innerHTML='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px">'+
        '<p class="muted">Всего позиций: '+all.length+'. Демо-CRUD: изменения сохраняются локально.</p>'+
        '<div style="display:flex;gap:8px"><button class="btn btn-outline btn-sm" id="addres">+ Добавить позицию</button>'+
        '<button class="btn btn-ghost btn-sm" id="resetcat">Сбросить каталог</button></div>'+
      '</div>'+
      '<div id="editbox"></div>'+
      '<table class="admin-table"><thead><tr><th>Наименование</th><th>Тип</th><th>Цена</th><th></th></tr></thead><tbody>'+
      all.map(function(r){ return '<tr><td>'+esc(r.title)+'</td><td>'+P.typeMeta[r.type].single+'</td><td>'+fmt(r.priceValue)+' '+unitLabel(r)+'</td>'+
        '<td style="text-align:right;white-space:nowrap"><button class="btn btn-ghost btn-sm" data-edit="'+r.id+'">Ред.</button> '+
        '<button class="cline-remove" data-del="'+r.id+'">Удалить</button></td></tr>'; }).join('')+
      '</tbody></table>';
    el('addres').onclick=function(){ editForm(null); };
    el('resetcat').onclick=function(){ if(confirm('Сбросить каталог к исходному?')){ P.resetCatalog(); toast('Каталог сброшен'); adminCatalog(); } };
    qsAll('[data-edit]').forEach(function(b){ b.onclick=function(){ editForm(P.getById(b.getAttribute('data-edit'))); }; });
    qsAll('[data-del]').forEach(function(b){ b.onclick=function(){ if(confirm('Удалить позицию?')){ P.deleteResource(b.getAttribute('data-del')); adminCatalog(); } }; });
  }
  function editForm(r){
    var isNew=!r; r=r||{id:'', type:'equipment', bookMode:'hour', title:'', lab:'', category:'analytics', priceValue:1000, priceUnit:'час', minUnits:2, specs:[], description:'', requiresOperator:null, bundledWith:[], img:'eq-meter'};
    el('editbox').innerHTML='<div class="checkout-form" style="margin-bottom:18px"><h3>'+(isNew?'Новая позиция':'Редактирование')+'</h3>'+
      '<div class="form-grid">'+
        '<div class="field full"><label>Наименование</label><input id="e_title" value="'+esc(r.title)+'"></div>'+
        '<div class="field"><label>Подразделение</label><input id="e_lab" value="'+esc(r.lab)+'"></div>'+
        '<div class="field"><label>Тип</label><select id="e_type">'+['room','equipment','specialist','service'].map(function(t){return '<option value="'+t+'"'+(r.type===t?' selected':'')+'>'+P.typeMeta[t].single+'</option>';}).join('')+'</select></div>'+
        '<div class="field"><label>Цена, ₽</label><input id="e_price" type="number" value="'+r.priceValue+'"></div>'+
        '<div class="field"><label>Единица</label><input id="e_unit" value="'+esc(r.priceUnit)+'"></div>'+
        '<div class="field full"><label>Описание</label><input id="e_desc" value="'+esc(r.description)+'"></div>'+
      '</div>'+
      '<div id="e_msg"></div>'+
      '<button class="btn btn-brass" id="e_save" style="margin-top:8px">Сохранить</button> '+
      '<button class="btn btn-ghost" id="e_cancel" style="margin-top:8px">Отмена</button>'+
    '</div>';
    el('e_cancel').onclick=function(){ el('editbox').innerHTML=''; };
    el('e_save').onclick=function(){
      var title=el('e_title').value.trim(); if(!title){ el('e_msg').innerHTML='<div class="form-msg err">Введите наименование.</div>'; return; }
      var type=el('e_type').value;
      var modeMap={room:'range',equipment:'range',specialist:'range',service:'sample'};
      var out={ id:r.id||('x-'+Math.random().toString(36).slice(2,8)), type:type, bookMode:r.id?r.bookMode:modeMap[type],
        title:title, lab:el('e_lab').value.trim()||'ПУЛЬСАР', category:r.category||'analytics',
        priceValue:parseInt(el('e_price').value,10)||0, priceUnit:el('e_unit').value.trim()||'час',
        minUnits:r.minUnits||2, specs:r.specs&&r.specs.length?r.specs:['Демонстрационная позиция'],
        description:el('e_desc').value.trim()||title, requiresOperator:r.requiresOperator||null,
        bundledWith:r.bundledWith||[], img:r.img||'eq-meter', cleanClass:r.cleanClass };
      P.saveResource(out); toast('Сохранено'); el('editbox').innerHTML=''; adminCatalog();
    };
  }

  /* ==========================================================
     СТАТИЧЕСКИЕ СТРАНИЦЫ
     ========================================================== */
  function pageHead(eyebrow,title,sub){
    return '<section class="page-head"><div class="wrap"><div class="eyebrow">'+eyebrow+'</div><h1 class="h-lg">'+title+'</h1>'+(sub?'<p>'+sub+'</p>':'')+'</div></section>';
  }
  function viewAbout(){
    render(pageHead('О платформе','Точка сборки науки и бизнеса','Единый оператор доступа к научной инфраструктуре МГУ и ИНТЦ «Воробьёвы горы».')+
    '<section class="section"><div class="wrap"><div class="grid-2">'+
      '<div class="prose">'+
        '<p><strong>ПУЛЬСАР</strong> создан как механизм коммерциализации уникальной научной инфраструктуры кластера «Ломоносов». Мы соединяем компании глубоких технологий с ресурсами ведущего университета страны — аттестованными лабораториями, оборудованием и научными кадрами МГУ.</p>'+
        '<p>Резиденты ИНТЦ получают налоговые преференции, ускоренную регистрацию интеллектуальной собственности и льготы на аренду научной инфраструктуры.</p>'+
        '<p>Наша задача — соединить фундаментальную науку МГУ с индустрией: помочь отобрать перспективные разработки, провести их прикладную валидацию, довести до прототипов и вывести на рынок.</p>'+
        '<div class="tags">'+['Биотехнологии','Фармацевтика','Микроэлектроника','Вакуумные технологии','Молекулярная генетика','Новые материалы','Функциональное питание'].map(function(t){return '<span class="tag">'+t+'</span>';}).join('')+'</div>'+
      '</div>'+
      '<div class="figure">'+img({img:'about',title:'ИНТЦ МГУ'},'','ИНТЦ МГУ')+'<div class="figure-cap">ИНТЦ МГУ «Воробьёвы горы» · кластер «Ломоносов»</div></div>'+
    '</div></div></section>'+
    '<section class="section" style="background:#fff;border-top:1px solid var(--line)"><div class="wrap">'+
      '<div class="eyebrow">Резидентам ИНТЦ</div><h2 class="h-lg" style="margin-bottom:32px">Что входит в резидентство</h2>'+
      '<div class="cards-3">'+[
        ['Льготы резидента ИНТЦ','Налоговые преференции, ускоренная регистрация ИС, упрощённый таможенный режим'],
        ['Доступ к науке МГУ','Совместные НИР, научный персонал, оборудование факультетов и ЦКП'],
        ['Скидка 25%','Резиденты получают скидку на бронирование оборудования и специалистов'],
        ['Грантовая поддержка','Сопровождение заявок в ФСИ, РНФ, Сколково — от стратегии до защиты'],
        ['Сеть партнёрств','Связи с промышленными предприятиями и государственными заказчиками'],
        ['Правовое сопровождение','Договоры по 217-ФЗ, структурирование сделок, NDA, ТЗ на НИР']
      ].map(function(c,i){ return '<div class="card-flat"><div class="card-num">0'+(i+1)+'</div><h3>'+c[0]+'</h3><p>'+c[1]+'</p></div>'; }).join('')+'</div>'+
    '</div></section>');
  }
  function viewHow(){
    render(pageHead('Как работаем','Четыре шага до доступа','Прозрачный процесс единого оператора — от заявки до работы на объекте.')+
    '<section class="section"><div class="wrap">'+
      '<div class="steps">'+[
        ['Оставьте заявку','Соберите ресурсы в каталоге и отправьте бронирование — или опишите задачу, мы подберём ресурс'],
        ['Подпишем договор','Типовой договор аренды или технологического хостинга — подготовим и согласуем'],
        ['Пройдите инструктаж','Вводный инструктаж по объекту, безопасности и регламентам чистых зон'],
        ['Работайте','Полный доступ к инфраструктуре, поддержка дежурного инженера, отчёты по использованию']
      ].map(function(s){ return '<div class="step"><h4>'+s[0]+'</h4><p>'+s[1]+'</p></div>'; }).join('')+'</div>'+
      '<div style="margin-top:44px;text-align:center"><a class="btn btn-brass" href="#/catalog">Перейти в каталог</a></div>'+
    '</div></section>'+
    '<section class="section" style="background:var(--navy-deep)"><div class="wrap text-center">'+
      '<h2 class="h-lg" style="color:#fff;margin-bottom:12px">Бронирование по модели «с оператором»</h2>'+
      '<p style="color:rgba(255,255,255,.72);max-width:640px;margin:0 auto">Сложные приборы бронируются вместе со специалистом автоматически — вам не нужно отдельно искать оператора. Услуги «под ключ» избавляют от работы с прибором совсем: вы передаёте образец и получаете протокол.</p>'+
    '</div></section>');
  }
  function viewContacts(){
    var items=[
      ['pin','Адрес','Москва, Воробьёвское шоссе, 2',''],
      ['mail','Email','info@pulsar-mgu.ru','mailto:info@pulsar-mgu.ru'],
      ['phone','Телефон','+7 (495) 123-45-67','tel:+74951234567'],
      ['clock','Часы работы','Пн–Пт, 9:00–18:00','']
    ];
    var mapSrc='https://yandex.ru/map-widget/v1/?mode=search&text='+encodeURIComponent('ИНТЦ МГУ Воробьёвы горы')+'&z=15';
    render(pageHead('Контакты','Свяжитесь с нами','ИНТЦ МГУ «Воробьёвы горы» · кластер «Ломоносов». Бронирование оформляется через каталог — оператор свяжется для подтверждения.')+
    '<section class="section"><div class="wrap"><div class="contact-grid">'+
      '<div>'+
        '<div class="contact-card">'+items.map(function(c){
          var val=c[3]?'<a class="val" href="'+c[3]+'">'+esc(c[2])+'</a>':'<span class="val">'+esc(c[2])+'</span>';
          return '<div class="contact-item"><span class="contact-ic">'+icon(c[0],22)+'</span>'+
            '<div><div class="lbl">'+c[1]+'</div>'+val+'</div></div>';
        }).join('')+'</div>'+
        '<div class="contact-actions">'+
          '<a class="btn btn-primary" href="#/catalog">Открыть каталог</a>'+
          '<a class="btn btn-outline" href="mailto:info@pulsar-mgu.ru?subject=Экскурсия%20по%20объекту">Записаться на экскурсию</a>'+
        '</div>'+
      '</div>'+
      '<div class="contact-map">'+
        '<iframe title="Карта — ИНТЦ МГУ «Воробьёвы горы»" src="'+mapSrc+'" loading="lazy" allowfullscreen referrerpolicy="no-referrer-when-downgrade"></iframe>'+
      '</div>'+
    '</div></div></section>');
  }

  /* ==========================================================
     РОУТЕР
     ========================================================== */
  function parseQuery(qs){ var o={}; (qs||'').split('&').forEach(function(p){ if(!p) return; var kv=p.split('='); o[decodeURIComponent(kv[0])]=decodeURIComponent(kv[1]||''); }); return o; }
  function route(){
    var raw=location.hash.replace('#','')||'/';
    var parts=raw.split('?'); var path=parts[0]; var query=parseQuery(parts[1]);
    var seg=path.split('/').filter(Boolean); // ['resource','id']
    if(!seg.length) return viewHome();
    switch(seg[0]){
      case 'catalog': return viewCatalog(query);
      case 'resource': return viewResource(seg[1]);
      case 'cart': return viewCart();
      case 'order': return viewOrder(seg[1]);
      case 'admin': return viewAdmin();
      case 'about': return viewAbout();
      case 'how': return viewHow();
      case 'contacts': return viewContacts();
      default: return viewHome();
    }
  }
  window.addEventListener('hashchange', route);

  // мобильное меню
  el('navtoggle').onclick=function(){ el('navlinks').classList.toggle('open'); };
  qsAll('#navlinks a').forEach(function(a){ a.addEventListener('click',function(){ el('navlinks').classList.remove('open'); }); });

  // старт
  route(); syncCart();
})();
