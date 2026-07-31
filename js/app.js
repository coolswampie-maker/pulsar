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
  // склонение единиц по числу: 1 смена / 2 смены / 5 смен
  var UNIT_FORMS = {
    'смена':  ['смена','смены','смен'],
    'час':    ['час','часа','часов'],
    'сутки':  ['сутки','суток','суток'],
    'день':   ['день','дня','дней'],
    'образец':['образец','образца','образцов'],
    'партия': ['партия','партии','партий']
  };
  function plural(n, f){ n=Math.abs(n)%100; var d=n%10;
    if(n>10 && n<20) return f[2]; if(d>1 && d<5) return f[1]; if(d===1) return f[0]; return f[2]; }
  function unitWord(n, unit){ var f=UNIT_FORMS[unit]; return f ? plural(n,f) : (unit||''); }

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
     ИИ-ПОИСК — общий движок для главной и каталога
     ==========================================================
     Одно поле на оба сценария: и «масс-спектрометр» (поиск по каталогу),
     и «нужно определить примеси в субстанции» (подбор под задачу). Различать
     их пользователь не обязан — разбирается сервер.

     Если бэкенд недоступен (статическая сборка, сеть), поле не должно
     умирать: молча переходим на поиск по каталогу прямо в браузере. Но
     подписываем результат честно — выдавать его за работу ИИ нельзя. */
  function aiBadge(cls){
    return '<span class="ai-badge'+(cls?' '+cls:'')+'" aria-label="Работает на искусственном интеллекте">'+
      '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">'+
        '<path d="M12 2.6l1.9 5.1 5.1 1.9-5.1 1.9-1.9 5.1-1.9-5.1-5.1-1.9 5.1-1.9z"/>'+
        '<path d="M18.6 14.4l.85 2.25 2.25.85-2.25.85-.85 2.25-.85-2.25-2.25-.85 2.25-.85z"/>'+
      '</svg>AI</span>';
  }
  function aiHitsHtml(items){
    return '<div class="assist-hits">'+items.map(function(i){
      return '<a class="assist-hit" href="#/resource/'+esc(i.id)+'">'+
        '<div class="assist-hit-t">'+esc(i.title)+'</div>'+
        (i.why?'<div class="assist-hit-w">'+esc(i.why)+'</div>':'')+
        '<div class="assist-hit-p">'+fmt(i.priceValue)+' / '+esc(i.priceUnit)+'</div>'+
      '</a>';
    }).join('')+'</div>';
  }
  // запасной поиск в браузере — тем же алгоритмом, что и в каталоге
  function localSearch(q){
    return P.getResources().map(function(r){ return { r:r, s:scoreQuery(r, q.toLowerCase()) }; })
      .filter(function(x){ return x.s>0; })
      .sort(function(a,b){ return b.s-a.s; })
      .slice(0,4)
      .map(function(x){ return { id:x.r.id, title:x.r.title, why:'',
                                 priceValue:x.r.priceValue, priceUnit:x.r.priceUnit }; });
  }
  /* Ответ показываем диалогом: слева реплика человека, ниже ответ ассистента
     с подобранным. Список карточек под формой читался как выдача поисковика —
     а тут именно разговор, и продолжение разговора («уточнить», «заявка»)
     должно быть видно сразу, а не угадываться. */
  /* Запасная реплика — на случай, когда сервер не ответил и позиции искал
     сам браузер. Обязана зависеть от результата: бодрое «вот что нашлось»
     над пустым списком человек читает как поломку, и правильно делает. */
  function fallbackReply(items){
    return items.length
      ? 'Вот что нашлось под вашу задачу:'
      : 'По такому описанию ничего не нашлось. Опишите задачу иначе или '+
        'оставьте индивидуальную заявку — оператор подберёт под задачу.';
  }
  function aiDialogHtml(q, reply, items, mode, catalogLink){
    // честная подпись: ИИ ставим только там, где отвечала модель
    var src = mode==='ai' ? 'Подобрал ИИ-ассистент'
            : mode==='licensed' ? ''
            : 'Подобрано поиском по каталогу';
    var acts=['<button class="pick-link" id="airefine">Уточнить запрос</button>'];
    if(items.length && catalogLink)
      acts.push('<button class="pick-link" id="aiall">Показать всё в каталоге</button>');
    acts.push('<button class="pick-link" id="pickopen">Оставить заявку на подбор</button>');

    return '<div class="ai-dialog">'+
      '<button class="ai-close" id="aiclose" type="button" aria-label="Закрыть подбор">'+
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">'+
        '<path d="M6 6l12 12M18 6L6 18"/></svg></button>'+
      '<div class="ai-msg you"><div class="ai-bubble">'+esc(q)+'</div></div>'+
      '<div class="ai-msg bot">'+
        '<span class="ai-ava" aria-hidden="true">'+
          '<svg viewBox="0 0 24 24" fill="currentColor">'+
          '<path d="M12 2.6l1.9 5.1 5.1 1.9-5.1 1.9-1.9 5.1-1.9-5.1-5.1-1.9 5.1-1.9z"/>'+
          '<path d="M18.6 14.4l.85 2.25 2.25.85-2.25.85-.85 2.25-.85-2.25-2.25-.85 2.25-.85z"/>'+
          '</svg></span>'+
        '<div class="ai-bubble">'+
          '<p class="ai-say">'+esc(reply||fallbackReply(items))+'</p>'+
          (items.length?aiHitsHtml(items):'')+
          // подпись «чем подобрано» без единой позиции бессмысленна
          (items.length&&src?'<div class="ai-src">'+esc(src)+'</div>':'')+
          '<div class="ai-foot"><span>Нужно что-то другое?</span> '+acts.join(' · ')+'</div>'+
          '<div id="pickbox"></div>'+
        '</div>'+
      '</div>'+
    '</div>';
  }

  /* o = { out, input, catalogLink, onOpen, onClose, done } */
  function runAssist(q, o){
    o=o||{};
    var out=o.out, done=o.done||function(){};
    if(!out) return done();
    q=(q||'').trim();
    if(!q){ out.innerHTML=''; out.dataset.q=''; return done(); }
    // Тот же запрос при уже открытом ответе не переспрашиваем: ответ на
    // экране, а вызов модели платный. Поймать это легко — «Уточнить запрос»
    // ставит курсор в поле и выделяет текст, так что Enter нажимается
    // рефлекторно, ничего не изменив.
    if(q===out.dataset.q && out.querySelector('.ai-dialog')){
      // не молчим: показываем, что ответ уже есть, иначе Enter выглядит
      // как будто ничего не сработало
      out.scrollIntoView({ behavior:'smooth', block:'nearest' });
      if(o.input) o.input.focus();
      return done();
    }
    out.dataset.q=q;
    out.innerHTML='<div class="ai-dialog"><div class="ai-msg you"><div class="ai-bubble">'+
      esc(q)+'</div></div><div class="ai-wait">'+aiBadge()+'Подбираем…</div></div>';
    if(o.onOpen) o.onOpen();
    // окно открывается ниже формы и на невысоком экране остаётся за кадром:
    // человек нажал «Найти» и решил бы, что ничего не произошло
    if(out.getBoundingClientRect().bottom > window.innerHeight)
      out.scrollIntoView({ behavior:'smooth', block:'nearest' });
    P.assistApi.ask(q).then(function(res){
      var d=(res && res.ok) ? (res.data||{}) : null;
      // бэкенд не ответил — ищем в браузере, человек не должен остаться ни с чем
      var items = d ? (d.items||[]) : localSearch(q);
      var reply = d ? (d.reply||'') : '';
      // 429 — упёрлись в ограничение частоты. Молча подменять ответ поиском
      // нельзя: человек решит, что подбор поглупел, и будет прав по-своему.
      if(!d && res && res.status===429)
        reply='Слишком много запросов подряд — подбор временно ограничен. '+
              'Подождите минуту и попробуйте снова.'+
              (items.length?' Пока — что нашлось по словам:':'');
      out.innerHTML=aiDialogHtml(q, reply, items,
                                 d?(d.mode||''):'offline', o.catalogLink);
      bindPick(q);
      var close=el('aiclose');
      if(close) close.onclick=function(){
        out.innerHTML='';
        out.dataset.q='';       // окно закрыли — тот же запрос снова уместен
        if(o.onClose) o.onClose();
        if(o.input) o.input.focus();
      };
      var refine=el('airefine');
      if(refine) refine.onclick=function(){
        if(o.input){ o.input.focus(); o.input.select(); }
      };
      var all=el('aiall');
      if(all) all.onclick=function(){
        catState.q=q; catState.cat=''; catState.onlyFree=false; catState.sort='default';
        location.hash='#/catalog';
      };
      done();
    });
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
          '<span>МГУ имени М.В. Ломоносова · ИНТЦ МГУ «Воробьёвы&nbsp;горы»</span></div>'+
        '<div class="eyebrow">Платформа лабораторной инфраструктуры</div>'+
        '<h1>Найдите и забронируйте <em>научную инфраструктуру</em> МГУ</h1>'+
        '<p class="lead">Приборы, чистые комнаты, специалисты и аналитические услуги ИНТЦ МГУ «Воробьёвы горы» — в аренду по заявке.</p>'+
        '<div class="hs-cap">'+aiBadge()+
          '<span>Найдите прибор по названию — или просто опишите задачу</span></div>'+
        '<form class="searchbar ai-bar" id="hsearch" onsubmit="return false">'+
          '<input id="hq" aria-label="Поиск по каталогу или описание задачи" '+
            'placeholder="Напишите запрос или опишите задачу">'+
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
      // ответ — отдельная ячейка сетки во всю ширину: иначе диалог ютился бы
      // в левой колонке рядом с картинкой и выглядел приложением к форме
      '<div id="hres" class="hs-res"></div>'+
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
        '<p class="prose"><p>Инфраструктура ПУЛЬСАР расположена на территории ИНТЦ МГУ «Воробьёвы горы» в кластере «Ломоносов» — научно-технологической долине МГУ имени М.В. Ломоносова.</p><p>ПУЛЬСАР имеет доступ к лабораториям, чистым комнатам и опытным производствам ведущего университета страны.</p></p>'+
        '<a class="btn btn-primary" href="#/catalog" style="margin-top:6px">Открыть каталог</a>'+
      '</div>'+
      '<div class="figure">'+img({img:'hero',title:'Кластер «Ломоносов»'},'','Кластер «Ломоносов» · ИНТЦ МГУ «Воробьёвы горы»')+
        '<div class="figure-cap">Кластер «Ломоносов» · ИНТЦ МГУ «Воробьёвы горы»</div></div>'+
    '</div></div></section>'+

    /* ---- КАК РАБОТАЕМ (компактно) ---- */
    '<section class="section section-invert"><div class="wrap">'+
      '<div class="eyebrow">Как работаем</div><h2 class="h-lg" style="margin-bottom:34px">Четыре шага для доступа к инфраструктуре</h2>'+
      '<div class="steps">'+[
        ['Найдите ресурс','Поиск по каталогу приборов, помещений и услуг'],
        ['Соберите заявку','Выберите дату и слот — оператор добавится автоматически'],
        ['Подтверждение','Оператор согласует бронирование и договор'],
        ['Работа на объекте','Инструктаж, доступ и поддержка дежурного специалиста']
      ].map(function(s){ return '<div class="step"><h3>'+s[0]+'</h3><p>'+s[1]+'</p></div>'; }).join('')+'</div>'+
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
    var inp=el('hq'), out=el('hres'), btn=el('hgo');
    if(!inp||!out) return;
    var grid=qsAll('.hero2-grid')[0];
    // Раньше здесь был выбор раздела и переход в каталог. Теперь ответ даётся
    // сразу на главной: человек не обязан знать, прибор ему нужен или услуга.
    var go=function(){
      var q=inp.value.trim();
      if(!q){ out.innerHTML=''; return; }
      if(btn) btn.disabled=true;
      runAssist(q, {
        out:out, input:inp, catalogLink:true,
        // на время разговора картинка уходит: диалог занимает всю ширину,
        // иначе он зажат в колонке и читается как довесок к форме
        onOpen: function(){ if(grid) grid.classList.add('answering'); },
        onClose:function(){ if(grid) grid.classList.remove('answering'); },
        done:   function(){ if(btn) btn.disabled=false; }
      });
    };
    if(btn) btn.onclick=go;
    inp.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); go(); } });
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
      assistBoxHtml()+
      '<div class="tabs" id="tabs">'+tabs+'</div>'+
      '<div class="catalog-layout">'+
        '<aside class="filters">'+
          '<div class="fgroup"><h2><label for="fsearch">Поиск</label></h2><input class="search-box" id="fsearch" placeholder="Название, прибор…" value="'+esc(catState.q)+'"></div>'+
          '<div class="fgroup"><h2><label for="fcat">Направление</label></h2><select id="fcat">'+catOpts+'</select></div>'+
          '<div class="fgroup"><h2><label for="fsort">Сортировка</label></h2><select id="fsort">'+
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
    bindAssist();
    qsAll('#tabs .tab').forEach(function(b){ b.onclick=function(){ catState.type=b.getAttribute('data-tab'); catState.cat=''; catState.q=''; renderCatalog(); }; });
    el('fsearch').oninput=function(){ catState.q=this.value; drawList(); };
    el('fcat').onchange=function(){ catState.cat=this.value; drawList(); };
    el('fsort').onchange=function(){ catState.sort=this.value; drawList(); };
    el('fclear').onclick=function(){ catState.q='';catState.cat='';catState.onlyFree=false;catState.sort='default'; renderCatalog(); };
    drawList();
  }
  /* ---- ИИ-подбор в каталоге ----
     Тот же движок, что на главной (runAssist): и по названию прибора, и по
     описанию задачи. Фильтры слева остаются обычными — они про сужение
     списка, а не про поиск. */
  function assistBoxHtml(){
    return '<div class="assist" id="assistbox">'+
      '<div class="assist-in">'+
        '<label class="assist-cap" for="aq">'+aiBadge()+
          'Найдите прибор по названию — или опишите задачу своими словами</label>'+
        '<div class="assist-row">'+
          '<input id="aq" placeholder="Напишите запрос или опишите задачу">'+
          '<button class="btn btn-brass" id="aqgo">Подобрать</button>'+
        '</div>'+
        '<div id="aqres"></div>'+
      '</div>'+
    '</div>';
  }
  function bindAssist(){
    var inp=el('aq'), btn=el('aqgo'), out=el('aqres');
    if(!inp||!btn) return;
    function run(){
      btn.disabled=true; btn.textContent='Подбираем…';
      runAssist(inp.value, { out:out, input:inp, catalogLink:false,
        done:function(){ btn.disabled=false; btn.textContent='Подобрать'; } });
    }
    btn.onclick=run;
    inp.onkeydown=function(e){ if(e.key==='Enter'){ e.preventDefault(); run(); } };
  }

  /* ---- индивидуальная заявка на подбор ----
     Если в каталоге нужного нет, человек не должен упираться в тупик:
     предлагаем описать потребность словами. Для оператора это и заявка,
     и подсказка, каких позиций каталогу не хватает. */
  function noMatchHtml(lead){
    return '<div class="pick-none">'+
      // ассистент уже ответил своими словами — второй раз то же не повторяем
      (lead?'<div class="pick-none-t">'+esc(lead)+'</div>':'')+
      '<p class="pick-none-p">Оставьте индивидуальную заявку — оператор ПУЛЬСАР '+
        'подберёт оборудование под вашу задачу, в том числе у партнёров МГУ.</p>'+
      '<button class="btn btn-brass" id="pickopen">Оставить заявку на подбор</button>'+
      '<div id="pickbox"></div>'+
    '</div>';
  }
  // query — то, что человек уже написал: переносим в форму, чтобы не набирать заново
  function bindPick(query){
    var open=el('pickopen'); if(!open) return;
    open.onclick=function(){ drawPickForm(query); };
  }
  function drawPickForm(query){
    var box=el('pickbox'); if(!box) return;
    var c=P.company && P.company();
    var known=P.isLogged && P.isLogged() && c;
    box.innerHTML='<div class="pick-form">'+
      '<div class="form-grid">'+
        '<div class="field full"><label for="pk_need">Что требуется *</label>'+
          '<textarea id="pk_need" rows="3" placeholder="Опишите оборудование, метод или задачу — чем подробнее, тем точнее подберём">'+esc(query||'')+'</textarea></div>'+
        '<div class="field full"><label for="pk_period">Желаемые сроки</label>'+
          '<input id="pk_period" placeholder="Например: до конца сентября, или 2–3 недели в октябре"></div>'+
        (known ? '' :
        '<div class="field"><label for="pk_org">Организация</label><input id="pk_org" placeholder="ООО «Название»"></div>'+
        '<div class="field"><label for="pk_name">Контактное лицо *</label><input id="pk_name" placeholder="Иванов Иван"></div>'+
        '<div class="field"><label for="pk_email">Email *</label><input id="pk_email" type="email" placeholder="ivan@company.ru"></div>'+
        '<div class="field"><label for="pk_phone">Телефон</label><input id="pk_phone" placeholder="+7 (___) ___-__-__"></div>')+
      '</div>'+
      (known ? '<p class="sub">Заявка от <strong>'+esc(c.name)+'</strong> ('+esc(c.email)+') — '+
               'контакты возьмём из профиля.</p>' : '')+
      '<div id="pk_msg"></div>'+
      '<button class="btn btn-brass" id="pk_send">Отправить заявку</button>'+
    '</div>';
    el('pk_need').focus();
    el('pk_send').onclick=function(){ sendPick(query, known); };
  }
  function sendPick(query, known){
    var msg=el('pk_msg'), btn=el('pk_send');
    var need=el('pk_need').value.trim();
    if(need.length<10){ msg.innerHTML='<div class="form-msg err">Опишите подробнее, что требуется.</div>'; return; }
    var d={ need:need, period:el('pk_period').value.trim(), search_query:query||'' };
    if(!known){
      d.org=el('pk_org').value.trim();
      d.contact_name=el('pk_name').value.trim();
      d.email=el('pk_email').value.trim();
      d.phone=el('pk_phone').value.trim();
      if(!d.contact_name || !d.email){
        msg.innerHTML='<div class="form-msg err">Укажите контактное лицо и e-mail — иначе мы не сможем ответить.</div>'; return;
      }
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email)){
        msg.innerHTML='<div class="form-msg err">Проверьте e-mail.</div>'; return;
      }
    }
    btn.disabled=true; btn.textContent='Отправка…';
    P.customRequestApi.send(d).then(function(res){
      btn.disabled=false; btn.textContent='Отправить заявку';
      if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg||'Не удалось отправить. Попробуйте ещё раз.')+'</div>'; return; }
      el('pickbox').innerHTML='<div class="pick-done">'+icon('check',20)+
        '<div><strong>Заявка № '+esc(res.data.id)+' принята.</strong><br>'+
        'Оператор ПУЛЬСАР свяжется с вами и предложит варианты.</div></div>';
      toast('Заявка на подбор отправлена');
    });
  }

  /* ---- поиск по каталогу ----
     Раньше искали подстроку и только внутри выбранной вкладки: запрос «ЯМР»
     на вкладке «Лаборатории» не находил ЯМР-спектрометр, потому что тот лежит
     в «Оборудовании». Теперь при непустом запросе ищем по всему каталогу, а
     каждое слово расширяем словарём синонимов (data/synonyms.js), чтобы
     «NMR» и «ядерный магнитный резонанс» находили то же, что «ЯМР». */
  function searchText(r){
    return (r.title+' '+r.lab+' '+(r.specs||[]).join(' ')+' '+r.description+' '+(r.cleanClass||'')).toLowerCase();
  }
  // Русские окончания: без их отсечения «микроскопом» не найдёт «микроскоп».
  var ENDINGS=['иями','ами','ями','ого','ему','ому','ыми','ими','ей','ой','ый','ий',
               'ая','яя','ое','ее','ые','ие','ом','ем','ах','ях','ов','ев','ью',
               'и','ы','у','ю','а','я','е','о','ь'];
  function stem(w){
    for(var i=0;i<ENDINGS.length;i++){
      var e=ENDINGS[i];
      if(w.length-e.length>=4 && w.slice(-e.length)===e) return w.slice(0,-e.length);
    }
    return w;
  }
  // Все синонимы термина. Термин сверяем со всей записью словаря, а не только с
  // её началом: иначе «магнитный» не нашёл бы «ядерный магнитный резонанс».
  function expandTerm(term){
    var out=[term], st=stem(term), groups=P.synonyms||[];
    for(var i=0;i<groups.length;i++){
      var g=groups[i], hit=false;
      for(var j=0;j<g.length && !hit;j++){
        if(g[j].indexOf(term)>=0 || term.indexOf(g[j])>=0) hit=true;
        else if(st.length>3 && g[j].indexOf(st)>=0) hit=true;
      }
      if(hit) out=out.concat(g);
    }
    return out;
  }
  // Короткие аббревиатуры ищем по границам слова. Подстрокой «ms» совпадает с
  // «AMS» в описании 3D-принтера, а «исп» — с «испытательным», и в результаты
  // лезет постороннее. Для длинных основ подстрока остаётся: «сушк» → «сушка».
  var ALNUM='0-9a-zа-яё';
  function hasTerm(text, term){
    if(term.length<=4) return new RegExp('(?<!['+ALNUM+'])'+
      term.replace(/[.*+?^${}()|[\]\\-]/g,'\\$&')+'(?!['+ALNUM+'])').test(text);
    return text.indexOf(term)>=0;
  }
  // Оценка соответствия: 0 — не подходит. Совпадение в названии весомее, чем
  // в описании, поэтому нужное всплывает наверх списка.
  function scoreQuery(r, q){
    var text=searchText(r), title=(r.title||'').toLowerCase(), score=0;
    // фраза целиком — самый сильный сигнал
    if(title.indexOf(q)>=0) score+=100;
    else if(text.indexOf(q)>=0) score+=40;
    // фразу тоже прогоняем через словарь: «ядерный магнитный резонанс» → «ямр»
    expandTerm(q).forEach(function(v){
      if(v!==q && hasTerm(title,v)) score+=60;
      else if(v!==q && hasTerm(text,v)) score+=20;
    });
    var words=q.split(/[\s,;]+/).filter(function(w){ return w.length>1; });
    var matched=0;
    words.forEach(function(w){
      // основу слова — подстрокой, словарные аббревиатуры — по границам
      var vars=expandTerm(w).map(function(v){ return v===w?stem(v):v; });
      var inTitle=vars.some(function(v){ return v===stem(w)?title.indexOf(v)>=0:hasTerm(title,v); });
      var inText =vars.some(function(v){ return v===stem(w)?text.indexOf(v)>=0 :hasTerm(text,v); });
      if(inTitle){ score+=12; matched++; }
      else if(inText){ score+=4; matched++; }
    });
    // из нескольких слов должно совпасть хотя бы большинство, иначе это шум
    if(words.length>1 && matched<Math.ceil(words.length/2)) return score>=40?score:0;
    if(!matched && score===0) return 0;
    return score;
  }
  function drawList(){
    var q=(catState.q||'').toLowerCase().trim();
    var list;
    if(q){
      // при поиске игнорируем вкладку — иначе нужное в другом разделе не найти,
      // и сортируем по релевантности, а не по порядку в каталоге
      list=P.getResources().map(function(r){ return {r:r, s:scoreQuery(r,q)}; })
            .filter(function(x){ return x.s>0; })
            .sort(function(a,b){ return b.s-a.s; })
            .map(function(x){ return x.r; });
    } else {
      list=P.getByType(catState.type);
    }
    if(catState.cat) list=list.filter(function(r){ return r.category===catState.cat; });
    if(catState.sort==='price-asc') list.sort(function(a,b){ return a.priceValue-b.priceValue; });
    if(catState.sort==='price-desc') list.sort(function(a,b){ return b.priceValue-a.priceValue; });
    var grid=el('rgrid'), bar=el('rbar'); if(!grid) return;
    bar.innerHTML='Найдено: <strong style="color:var(--navy)">'+list.length+'</strong>'+
      (q ? ' <span class="cline-meta">· по всему каталогу</span>' : '');
    grid.innerHTML = list.length ? list.map(resCard).join('')
      : '<div class="empty" style="grid-column:1/-1"><h3>Ничего не найдено</h3>'+
        '<p>Попробуйте другой запрос или опишите задачу своими словами в поле выше.</p>'+
        noMatchHtml('Нужного нет в каталоге?')+'</div>';
    // кнопка заявки живёт и в пустом результате обычного поиска
    if(!list.length) bindPick(q);
  }

  /* ==========================================================
     КАРТОЧКА РЕСУРСА + панель бронирования
     ========================================================== */
  var book={};
  function viewResource(id){
    var r=P.getById(id);
    if(!r) return render('<section class="section"><div class="wrap empty"><h3>Ресурс не найден</h3><a class="btn btn-primary" href="#/catalog">В каталог</a></div></section>');
    // по умолчанию — один день / одна смена
    var d1=P.dates.plusISO(1);
    book={ res:r, date:d1, start:null, hours:r.minUnits||2, qty:1, shift:'day',
           startDate:d1, endDate:d1, rangePick:'start',
           shiftType:'day',
           cal:new Date(parseInt(d1.slice(0,4),10), parseInt(d1.slice(5,7),10)-1, 1), err:'' };
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
          '<h2 class="h-md" style="margin-bottom:14px">Характеристики</h2>'+
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

  /* ---- календарь дат для брони по сменам/суткам ---- */
  function pad2(n){ return (n<10?'0':'')+n; }
  // статус дня: past | busy (день занят, выбрать нельзя) | free
  function dayStatus(resId, iso){
    if(iso < P.dates.todayISO()) return 'past';
    var busy=P.getBusy(resId).filter(function(b){ return b.date===iso; });
    if(!busy.length) return 'free';
    // почасово день недоступен только если занят целиком; частичную занятость снимают слоты времени
    if(book.res.bookMode==='hour') return busy.some(function(b){ return b.slotStart==null; }) ? 'busy' : 'free';
    return 'busy'; // смены/сутки — любой занятый день недоступен
  }
  var CAL_WD=['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
  var CAL_MON=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  function rangeCalendarHtml(){
    var r=book.res, cal=book.cal, y=cal.getFullYear(), m=cal.getMonth();
    var startWd=(new Date(y,m,1).getDay()+6)%7, dim=new Date(y,m+1,0).getDate();
    var cells='';
    for(var i=0;i<startWd;i++) cells+='<span class="cal-cell empty"></span>';
    for(var d=1;d<=dim;d++){
      var iso=y+'-'+pad2(m+1)+'-'+pad2(d);
      var st=dayStatus(r.id,iso), cls='cal-cell '+st;
      if(book.startDate&&book.endDate&&iso>book.startDate&&iso<book.endDate) cls+=' inrange';
      if(iso===book.startDate) cls+=' start';
      if(iso===book.endDate) cls+=' end';
      var dis=(st==='past'||st==='busy');
      cells+='<button type="button" class="'+cls+'"'+(dis?' disabled':'')+' data-cal="'+iso+'">'+d+'</button>';
    }
    return '<div class="cal">'+
      '<div class="cal-head"><span class="cal-title">'+CAL_MON[m]+' '+y+'</span>'+
        '<span class="cal-nav"><button type="button" id="calPrev" aria-label="Предыдущий месяц">‹</button>'+
        '<button type="button" id="calNext" aria-label="Следующий месяц">›</button></span></div>'+
      '<div class="cal-wd">'+CAL_WD.map(function(w){return '<span>'+w+'</span>';}).join('')+'</div>'+
      '<div class="cal-grid" id="calGrid">'+cells+'</div>'+
    '</div>';
  }
  // выбор диапазона дат; занятые дни нельзя включить в интервал
  function pickCalDay(iso){
    if(book.rangePick==='start' || iso<book.startDate){
      book.startDate=iso; book.endDate=iso; book.rangePick='end';
    } else {
      var spanBusy=P.dates.range(book.startDate, iso).some(function(d){ return dayStatus(book.res.id,d)==='busy'; });
      if(spanBusy){ book.startDate=iso; book.endDate=iso; book.rangePick='end'; }
      else { book.endDate=iso; book.rangePick='start'; }
    }
    renderBooking();
  }
  // короткая подпись выбранного периода (сутки — для оборудования)
  function rangeSummaryHtml(){
    var s=book.startDate, e=book.endDate, days=P.dates.days(s,e), r=book.res;
    var span = s===e ? P.dates.human(s) : P.dates.human(s)+' – '+P.dates.human(e);
    return span+' · <strong>'+days+' '+unitWord(days, r.priceUnit==='сутки'?'сутки':'день')+'</strong>';
  }

  /* ---- смены (лаборатории): тип смены на весь период ---- */
  // day/eve = 1 смена в день, full (круглосуточно) = 2 смены в день
  var SHIFT_TYPES=[{k:'day',label:'Дневная',per:1},{k:'eve',label:'Ночная',per:1},{k:'full',label:'Круглосуточно',per:2}];
  var SHIFT_DESC={day:'дневная смена (09:00–17:00)', eve:'ночная смена (18:00–02:00)', full:'круглосуточно'};
  function shiftPerDay(){ var t=book.shiftType; return t==='full'?2:1; }
  function shiftCount(){ return P.dates.days(book.startDate,book.endDate)*shiftPerDay(); }
  function shiftTypeSelector(){
    return '<div class="seg" id="bshiftType">'+SHIFT_TYPES.map(function(t){
      return '<button type="button" class="seg-b'+(book.shiftType===t.k?' on':'')+'" data-s="'+t.k+'">'+t.label+'</button>';
    }).join('')+'</div>';
  }
  function shiftSummaryHtml(){
    var n=shiftCount(), s=book.startDate, e=book.endDate;
    var span = s===e ? P.dates.human(s) : P.dates.human(s)+' – '+P.dates.human(e);
    return span+' · '+SHIFT_DESC[book.shiftType]+' · <strong>'+n+' '+unitWord(n,'смена')+'</strong>';
  }

  function renderBooking(){
    var r=book.res, b=el('booking'); if(!b) return;
    var priceHead=fmt(r.priceValue)+' <small>'+unitLabel(r)+'</small>';
    var html='<div class="price-lead">'+priceHead+'</div><hr>';

    if(r.type==='service'){
      html+='<div class="field"><label for="bqty">Количество образцов</label>'+
        '<input type="number" id="bqty" min="'+(r.minUnits||1)+'" value="'+book.qty+'"></div>'+
        '<div class="op-note">'+icon('clock',16)+'<div>Услуга «под ключ»: время прибора и работа специалиста включены. Срок — по регламенту услуги.</div></div>';
    } else if(r.bookMode==='shift'){
      html+=rangeCalendarHtml()+
        '<div class="field" style="margin-top:12px"><span class="field-cap" id="capShift">Смена</span>'+
        '<div role="group" aria-labelledby="capShift">'+shiftTypeSelector()+'</div></div>'+
        '<div class="range-note" id="rnote">'+shiftSummaryHtml()+'</div>';
    } else if(r.bookMode==='range'){
      html+=rangeCalendarHtml()+
        '<div class="range-note" id="rnote">'+rangeSummaryHtml()+'</div>';
    } else { // hour — почасово, можно на несколько дат
      html+=rangeCalendarHtml()+
        '<div class="field" style="margin-top:12px"><span class="field-cap" id="capSlots">Время начала (в каждый выбранный день)</span><div class="slots" id="bslots" role="group" aria-labelledby="capSlots">'+
          timeStarts().map(function(t){
            var busy=isStartBusy(r.id,t,book.hours);
            return '<button class="slot'+(book.start===t?' sel':'')+'" data-t="'+t+'"'+(busy?' disabled':'')+'>'+t+'</button>';
          }).join('')+'</div></div>'+
        '<div class="field"><label for="bhours">Длительность</label><select id="bhours">'+
          [2,3,4,5,6].filter(function(h){return h>=(r.minUnits||1);}).map(function(h){
            return '<option value="'+h+'"'+(book.hours===h?' selected':'')+'>'+h+' ч</option>'; }).join('')+
        '</select></div>'+
        '<div class="range-note" id="rnote">'+hourSummaryHtml()+'</div>';
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

  // слот занят, если конфликтует по расписанию хотя бы в один день выбранного диапазона
  function isStartBusy(id,start,hours){
    var end=computeEnd(start,hours);
    return P.dates.range(book.startDate, book.endDate).some(function(d){ return !!P.cart.conflict(id,d,start,end); });
  }
  function hourSummaryHtml(){
    var s=book.startDate, e=book.endDate, days=P.dates.days(s,e);
    if(!book.start) return '<span class="rn-err">Выберите время начала.</span>';
    var span = s===e ? P.dates.human(s) : P.dates.human(s)+' – '+P.dates.human(e);
    var win = book.start+'–'+computeEnd(book.start,book.hours);
    var strong = days>1
      ? days+' '+unitWord(days,'день')+' × '+book.hours+' ч = '+(book.hours*days)+' ч'
      : book.hours+' '+unitWord(book.hours,'час');
    return span+', '+win+' · <strong>'+strong+'</strong>';
  }
  function bindBooking(){
    var r=book.res;
    if(el('bdate')) el('bdate').onchange=function(){ book.date=this.value; book.start=null; renderBooking(); };
    // календарь дат
    if(el('calPrev')) el('calPrev').onclick=function(){ book.cal=new Date(book.cal.getFullYear(),book.cal.getMonth()-1,1); renderBooking(); };
    if(el('calNext')) el('calNext').onclick=function(){ book.cal=new Date(book.cal.getFullYear(),book.cal.getMonth()+1,1); renderBooking(); };
    qsAll('#calGrid .cal-cell').forEach(function(c){
      if(c.disabled || !c.getAttribute('data-cal')) return;
      c.onclick=function(){ pickCalDay(c.getAttribute('data-cal')); };
    });
    // выбор типа смены (лаборатории)
    qsAll('#bshiftType .seg-b').forEach(function(bt){ bt.onclick=function(){ book.shiftType=bt.getAttribute('data-s'); renderBooking(); }; });
    if(el('bshift')) el('bshift').onchange=function(){ book.shift=this.value; };
    if(el('bqty')) el('bqty').oninput=function(){ book.qty=Math.max(parseInt(this.value||1,10),(r.minUnits||1)); updateEstimate(); };
    if(el('bhours')) el('bhours').onchange=function(){ book.hours=parseInt(this.value,10); renderBooking(); };
    qsAll('#bslots .slot').forEach(function(s){ if(s.disabled) return;
      s.onclick=function(){ book.start=s.getAttribute('data-t'); qsAll('#bslots .slot').forEach(function(x){x.classList.remove('sel');}); s.classList.add('sel');
        var n=el('rnote'); if(n) n.innerHTML=hourSummaryHtml(); updateEstimate(); };
    });
    el('badd').onclick=addToCart;
  }
  function currentOpts(){
    var r=book.res, o={};
    if(r.type==='service'){ o.qty=book.qty; return o; }
    if(r.bookMode==='shift'){
      o.startDate=book.startDate; o.endDate=book.endDate; o.date=book.startDate;
      o.shiftType=book.shiftType; o.days=P.dates.days(book.startDate,book.endDate); o.shifts=shiftCount();
      return o;
    }
    if(r.bookMode==='range'){
      o.startDate=book.startDate; o.endDate=book.endDate; o.date=book.startDate;
      o.days=P.dates.days(book.startDate,book.endDate);
      return o;
    }
    // hour — почасово, диапазон дат + окно времени в каждый день
    o.startDate=book.startDate; o.endDate=book.endDate; o.date=book.startDate;
    o.days=P.dates.days(book.startDate,book.endDate); o.hours=book.hours;
    if(book.start){ o.slotStart=book.start; o.slotEnd=computeEnd(book.start,book.hours); }
    return o;
  }
  function estimatePrice(){
    var r=book.res, o=currentOpts();
    if(r.bookMode==='shift') return r.priceValue*(o.shifts||1);
    if(r.bookMode==='range') return r.priceValue*P.cart.rangeUnits(r,o);
    if(r.bookMode==='hour') return r.priceValue*(o.hours||r.minUnits||1)*(o.days||1);
    if(r.bookMode==='sample'||r.bookMode==='day') return r.priceValue*(o.qty||1);
    return r.priceValue*(o.qty||1);
  }
  function updateEstimate(){
    var r=book.res, box=el('best'); if(!box) return;
    var base=estimatePrice(), opLine='';
    if(r.requiresOperator){
      var op=P.getById(r.requiresOperator);
      var days1=P.dates.days(book.startDate,book.endDate);
      var h = r.bookMode==='hour'?book.hours*days1 : r.bookMode==='day'?8*book.qty : r.bookMode==='range'?8*days1 : r.bookMode==='shift'?8*shiftCount() : 8;
      if(op){ opLine='<div class="est-line"><span>Оператор ('+h+' ч)</span><span>'+fmt(op.priceValue*h)+'</span></div>'; base+=op.priceValue*h; }
    }
    box.innerHTML='<div class="est-line"><span>'+esc(P.typeMeta[r.type].single)+'</span><span>'+fmt(estimatePrice())+'</span></div>'+
      opLine+'<div class="est-line" style="margin-top:6px"><span>Итого за позицию</span><strong>'+fmt(base)+'</strong></div>';
  }
  function addToCart(){
    var r=book.res, o=currentOpts(), msg=el('bmsg');
    if(r.bookMode==='hour' && !book.start){ msg.innerHTML='<div class="form-msg err">Выберите время начала.</div>'; return; }
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
    if(l.bookMode==='sample') return l.qty+' '+unitWord(l.qty,'образец');
    if(l.bookMode==='shift'){
      var ss=l.startDate||l.date, se=l.endDate||ss, n=l.shifts||1;
      var SD={day:'дневная',eve:'ночная',full:'круглосуточно'};
      var sp = ss===se ? P.dates.human(ss) : P.dates.human(ss)+' – '+P.dates.human(se);
      return sp+' · '+(SD[l.shiftType]||'')+' · '+n+' '+unitWord(n,'смена');
    }
    if(l.bookMode==='range'){
      var sd=l.startDate||l.date, ed=l.endDate||sd, days=l.days||P.dates.days(sd,ed);
      var span = sd===ed ? P.dates.human(sd) : P.dates.human(sd)+' – '+P.dates.human(ed);
      return span+' · '+days+' '+unitWord(days, l.unit==='сутки'?'сутки':'день');
    }
    var d=P.dates.human(l.date);
    if(l.bookMode==='day') return d+' · '+l.qty+' сут.';
    // час без конкретного времени (напр. оператор при суточной/сменной брони)
    if(!l.slotStart){
      var span=(l.startDate&&l.endDate&&l.startDate!==l.endDate)
        ? P.dates.human(l.startDate)+' — '+P.dates.human(l.endDate) : d;
      return span+' · '+(l.hours||'')+' ч';
    }
    // почасово (возможно на несколько дней)
    var hs=l.startDate||l.date, he=l.endDate||hs, hd=l.days||1;
    if(hs!==he) return P.dates.human(hs)+' – '+P.dates.human(he)+', '+l.slotStart+'–'+l.slotEnd+' · '+hd+' '+unitWord(hd,'день');
    return P.dates.human(hs)+' · '+l.slotStart+'–'+l.slotEnd+' ('+(l.hours||'')+' ч)';
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
    // Скидку 25% даёт только подтверждённый оператором резидент (считается в store).
    // Гость и непроверенная компания видят её как заявление, а не как готовый минус —
    // иначе итог в корзине расходился бы с суммой заявки в CRM.
    s.innerHTML='<h3>Смета</h3>'+
      '<div class="sum-line"><span>Позиций</span><span>'+t.count+'</span></div>'+
      '<div class="sum-line"><span>Стоимость</span><span>'+fmt(t.subtotal)+'</span></div>'+
      (t.confirmed
        ? '<div class="sum-line"><span>Скидка резидента ИНТЦ</span><span>−'+fmt(t.discount)+'</span></div>'
        : '<label class="resident-toggle"><input type="checkbox" id="resident" '+(t.claim?'checked':'')+'>'+
            '<span><strong>Мы резидент ИНТЦ МГУ</strong> — оператор проверит статус и применит скидку 25% к заявке</span></label>')+
      (!t.confirmed&&t.claim ? '<div class="sum-line muted"><span>Скидка резидента</span><span>после проверки</span></div>' : '')+
      '<div class="sum-total"><span>Итого</span><span class="val">'+fmt(t.total)+'</span></div>'+
      '<button class="btn btn-brass btn-block" id="tocheckout" style="margin-top:18px">Оформить заявку</button>'+
      '<button class="btn btn-ghost btn-block btn-sm" id="clearcart" style="margin-top:8px">Очистить</button>';
    if(el('resident')) el('resident').onchange=function(){ P.cart.setResident(this.checked); drawSummary(); };
    el('clearcart').onclick=function(){ P.cart.clear(); viewCart(); };
    el('tocheckout').onclick=function(){ drawCheckout(); el('checkoutbox').scrollIntoView({behavior:'smooth'}); };
  }
  function drawCheckout(){
    var box=el('checkoutbox'), c=P.company();
    if(P.isLogged() && c){
      // компания вошла в кабинет — контакты берём из профиля, повторно не спрашиваем
      box.innerHTML='<div class="checkout-form"><h3>Оформление заявки</h3>'+
        '<p class="sub">Заявка от <strong>'+esc(c.name)+'</strong> ('+esc(c.email)+'). '+
          'Данные берутся из профиля кабинета — изменить их можно в <a href="#/cabinet">профиле</a>.</p>'+
        '<div class="form-grid">'+
          '<div class="field full"><label for="c_note">Комментарий к заявке</label><input id="c_note" placeholder="Опишите задачу или пожелания"></div>'+
        '</div>'+
        '<div id="c_msg"></div>'+
        '<button class="btn btn-brass" id="submitorder" style="margin-top:8px">Отправить заявку</button>'+
      '</div>';
    } else {
      box.innerHTML='<div class="checkout-form"><h3>Контактные данные</h3>'+
        '<p class="sub">Гостевая заявка — регистрация не требуется. Мы свяжемся с вами для подтверждения. '+
          'С <a href="#/login">кабинетом компании</a> заявки хранятся в истории, а статус резидента подтверждается один раз.</p>'+
        '<div class="form-grid">'+
          '<div class="field"><label for="c_org">Организация *</label><input id="c_org" placeholder="ООО «Название»"></div>'+
          '<div class="field"><label for="c_name">Контактное лицо *</label><input id="c_name" placeholder="Иванов Иван Иванович"></div>'+
          '<div class="field"><label for="c_email">Email *</label><input id="c_email" type="email" placeholder="ivan@company.ru"></div>'+
          '<div class="field"><label for="c_phone">Телефон *</label><input id="c_phone" placeholder="+7 (___) ___-__-__"></div>'+
          '<div class="field full"><label for="c_note">Комментарий</label><input id="c_note" placeholder="Опишите задачу или пожелания"></div>'+
        '</div>'+
        '<div id="c_msg"></div>'+
        '<button class="btn btn-brass" id="submitorder" style="margin-top:8px">Отправить заявку</button>'+
      '</div>';
    }
    el('submitorder').onclick=submitOrder;
  }
  function submitOrder(){
    var msg=el('c_msg'), note=el('c_note').value.trim();
    var contact;
    if(P.isLogged()){
      // организация/контакты подставит бэкенд из профиля компании
      contact={note:note};
    } else {
      var org=el('c_org').value.trim(), name=el('c_name').value.trim(),
          email=el('c_email').value.trim(), phone=el('c_phone').value.trim();
      if(!org||!name||!email||!phone){ msg.innerHTML='<div class="form-msg err">Заполните обязательные поля (*).</div>'; return; }
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ msg.innerHTML='<div class="form-msg err">Проверьте email.</div>'; return; }
      contact={org:org,name:name,email:email,phone:phone,note:note};
    }
    var btn=el('submitorder'); if(btn){ btn.disabled=true; btn.textContent='Отправка…'; }
    P.cart.checkout(contact).then(function(res){
      if(btn){ btn.disabled=false; btn.textContent='Отправить заявку'; }
      if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
      location.hash='#/order/'+res.order.id;
    });
  }

  /* ==========================================================
     ПОДТВЕРЖДЕНИЕ ЗАЯВКИ
     ========================================================== */
  function viewOrder(id){
    var o=(P.lastOrder && P.lastOrder.id===id) ? P.lastOrder : null;
    var name=o && o.contact && o.contact.name ? (o.contact.name.split(' ')[0]||o.contact.name) : '';
    var linesHtml = o ? '<div class="confirm-card">'+
        o.lines.map(function(l){ return '<div class="cl"><span>'+esc(l.title)+(l.isOperator?' <em style="color:var(--brass)">(оператор)</em>':'')+'</span><span>'+fmt(l.linePrice)+'</span></div>'; }).join('')+
        (o.discount?'<div class="cl"><span>Скидка резидента ИНТЦ</span><span>−'+fmt(o.discount)+'</span></div>':'')+
        '<div class="cl" style="font-weight:700;color:var(--navy)"><span>Итого</span><span>'+fmt(o.total)+'</span></div>'+
        (o.residentClaimed?'<div class="cl"><span class="cline-meta">Заявлен статус резидента ИНТЦ — оператор проверит его и пересчитает скидку 25% в заявке.</span></div>':'')+
      '</div>' : '';
    render('<section class="confirm"><div class="wrap">'+
      '<div class="check-ic">'+icon('check',34)+'</div>'+
      '<h1>Заявка принята</h1>'+
      '<div class="onum">№ '+esc(id)+'</div>'+
      '<p class="muted">Спасибо'+(name?', '+esc(name):'')+'. Заявка отправлена оператору ПУЛЬСАР — он свяжется с вами для подтверждения бронирования и оформления договора.</p>'+
      linesHtml+
      '<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">'+
        '<a class="btn btn-primary" href="#/catalog">Продолжить в каталоге</a>'+
      '</div>'+
    '</div></section>');
  }

  /* ==========================================================
     КАБИНЕТ ОПЕРАТОРА — настоящая CRM на бэкенде (Django /admin).
     Прежний демо-кабинет на localStorage удалён: заявки теперь живут
     в базе, а не в браузере.
     ========================================================== */
  function viewAdmin(){
    location.replace(window.PULSAR_ADMIN_URL || '/admin/');
  }

  /* ==========================================================
     СТАТИЧЕСКИЕ СТРАНИЦЫ
     ========================================================== */
  function pageHead(eyebrow,title,sub){
    return '<section class="page-head"><div class="wrap"><div class="eyebrow">'+eyebrow+'</div><h1 class="h-lg">'+title+'</h1>'+(sub?'<p>'+sub+'</p>':'')+'</div></section>';
  }
  function viewAbout(){
    render(pageHead('О платформе','Точка сборки науки и бизнеса','Единый оператор доступа к научной инфраструктуре МГУ и ИНТЦ МГУ «Воробьёвы горы».')+
    '<section class="section"><div class="wrap"><div class="grid-2">'+
      '<div class="prose">'+
        '<p><strong>ПУЛЬСАР</strong> создан как механизм доступа технологических компаний к уникальной научно-технологической инфраструктуре ИНТЦ МГУ и ведущего научного университета страны. Мы даём бизнесу возможность использовать всю необходимую инфраструктуру, аттестованные лаборатории, оборудование, профильных специалистов и научные кадры МГУ для решения прикладных задач.</p>'+
        '<p>Наша задача — соединить фундаментальную науку МГУ с реальным сектором экономики. Не только помочь компаниям получить доступ к оборудованию и научному потенциалу университета, но и довести разработки МГУ до прототипов и вывести на рынок через коллаборацию с технологическим бизнесом.</p>'+
        '<div class="tags">'+['Биотехнологии','Фармацевтика','Микроэлектроника','Вакуумные технологии','Молекулярная генетика','Новые материалы','Функциональное питание'].map(function(t){return '<span class="tag">'+t+'</span>';}).join('')+'</div>'+
      '</div>'+
      '<div class="figure">'+img({img:'about',title:'ИНТЦ МГУ'},'','ИНТЦ МГУ')+'<div class="figure-cap">ИНТЦ МГУ «Воробьёвы горы» · кластер «Ломоносов»</div></div>'+
    '</div></div></section>'+
    '<section class="section" style="background:#fff;border-top:1px solid var(--line)"><div class="wrap">'+
      '<div class="eyebrow">Резидентам ИНТЦ</div><h2 class="h-lg" style="margin-bottom:32px">Что получают резиденты ИНТЦ МГУ «Воробьёвы горы»</h2>'+
      '<div class="cards-3">'+[
        ['Юридические и налоговые консультации','Налоговое и юридическое консультирование, регистрация ИС'],
        ['Доступ к науке МГУ','Совместные НИР, научный персонал, оборудование факультетов и ЦКП'],
        ['Скидка 25%','Резиденты получают скидку на бронирование оборудования и специалистов'],
        ['Грантовая поддержка','Сопровождение заявок в ФСИ, РНФ, Сколково — от стратегии до защиты'],
        ['Сеть партнёрств','Связи с промышленными предприятиями и государственными заказчиками'],
        ['Правовое сопровождение','Сопровождение договоров, согласование всех вопросов с МГУ и ИНТЦ, структурирование сделок, NDA, ТЗ на НИР']
      ].map(function(c,i){ return '<div class="card-flat"><div class="card-num">0'+(i+1)+'</div><h3>'+c[0]+'</h3><p>'+c[1]+'</p></div>'; }).join('')+'</div>'+
    '</div></section>');
  }
  function viewHow(){
    render(pageHead('Как работаем','Четыре шага для доступа к инфраструктуре','Прозрачный процесс единого оператора — от заявки до работы на объекте.')+
    '<section class="section"><div class="wrap">'+
      '<div class="steps">'+[
        ['Оставьте заявку','Соберите ресурсы в каталоге и отправьте бронирование — или опишите задачу, мы подберём ресурс'],
        ['Подпишем договор','Типовой договор аренды или технологического хостинга — подготовим и согласуем'],
        ['Пройдите инструктаж','Вводный инструктаж по объекту, безопасности и регламентам чистых зон'],
        ['Работайте','Полный доступ к инфраструктуре, поддержка дежурного специалиста, отчёты по использованию']
      ].map(function(s){ return '<div class="step"><h3>'+s[0]+'</h3><p>'+s[1]+'</p></div>'; }).join('')+'</div>'+
      '<div style="margin-top:44px;text-align:center"><a class="btn btn-brass" href="#/catalog">Перейти в каталог</a></div>'+
    '</div></section>'+
    '<section class="section" style="background:var(--navy-deep)"><div class="wrap text-center">'+
      '<h2 class="h-lg" style="color:#fff;margin-bottom:12px">Бронирование по модели «с оператором»</h2>'+
      '<p style="color:rgba(255,255,255,.72);max-width:640px;margin:0 auto">Сложные приборы бронируются вместе со специалистом автоматически — вам не нужно отдельно искать оператора. Услуги «под ключ» избавляют от работы с прибором совсем: вы передаёте образец и получаете протокол.</p>'+
    '</div></section>');
  }
  function viewContacts(){
    var items=[
      ['pin','Адрес','Москва, Раменский бульвар, дом 1',''],
      ['mail','Email','info@pulsar-mgu.ru','mailto:info@pulsar-mgu.ru'],
      ['phone','Телефон','+7 (495) 123-45-67','tel:+74951234567'],
      ['clock','Часы работы','Пн–Пт, 9:00–18:00','']
    ];
    var mapSrc='https://yandex.ru/map-widget/v1/?mode=search&text='+encodeURIComponent('Москва, Раменский бульвар, 1')+'&z=16';
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
     ЛИЧНЫЙ КАБИНЕТ КОМПАНИИ
     Вход/регистрация, профиль, свои заявки и показатели ИНТЦ.
     Данные — только с бэкенда, по токену компании.
     ========================================================== */
  var CATS = P.categories || {};

  function needAuth(){
    if(P.isLogged()) return false;
    location.hash='#/login';
    return true;
  }
  function cabTabs(active){
    var t=[['#/cabinet','Профиль'],['#/cabinet/orders','Мои заявки'],['#/cabinet/kpi','Показатели']];
    return '<div class="cab-tabs">'+t.map(function(x){
      return '<a href="'+x[0]+'" class="cab-tab'+(x[0]===active?' on':'')+'">'+x[1]+'</a>';
    }).join('')+'</div>';
  }
  // плашка статуса: пока оператор не подтвердил компанию, скидки нет
  function statusNote(c){
    if(!c) return '';
    if(c.resident && c.confirmed)
      return '<div class="cab-note ok">'+icon('check',18)+'<span>Компания подтверждена как <strong>резидент ИНТЦ МГУ</strong> — скидка 25% применяется к бронированию автоматически.</span></div>';
    if(c.confirmed)
      return '<div class="cab-note ok">'+icon('check',18)+'<span>Компания подтверждена оператором. Статус резидента ИНТЦ не присвоен — бронирование по базовым тарифам.</span></div>';
    return '<div class="cab-note wait">'+icon('clock',18)+'<span>Профиль на проверке у оператора. Бронировать можно сразу; статус резидента и скидку оператор подтвердит отдельно.</span></div>';
  }

  /* ---------- вход и регистрация ---------- */
  var loginTab='login';
  function viewLogin(){
    if(P.isLogged()){ location.hash='#/cabinet'; return; }
    render(pageHead('Личный кабинет','Вход для компаний','Кабинет резидента кластера «Ломоносов»: заявки, бронирования и отчётность по показателям ИНТЦ.')+
    '<section class="section"><div class="wrap"><div class="auth-box">'+
      '<div class="cab-tabs">'+
        '<a href="#/login" class="cab-tab'+(loginTab==='login'?' on':'')+'" data-ltab="login">Вход</a>'+
        '<a href="#/login" class="cab-tab'+(loginTab==='reg'?' on':'')+'" data-ltab="reg">Регистрация</a>'+
      '</div>'+
      '<div id="authbody"></div>'+
    '</div></div></section>', function(){
      qsAll('[data-ltab]').forEach(function(a){
        a.onclick=function(e){ e.preventDefault(); loginTab=a.getAttribute('data-ltab'); viewLogin(); };
      });
      drawAuth();
    });
  }
  function drawAuth(){
    var b=el('authbody'); if(!b) return;
    if(loginTab==='login'){
      b.innerHTML='<div class="form-grid">'+
        '<div class="field full"><label for="l_email">E-mail *</label><input id="l_email" type="email" placeholder="company@mail.ru"></div>'+
        '<div class="field full"><label for="l_pass">Пароль *</label><input id="l_pass" type="password" placeholder="••••••••"></div>'+
      '</div><div id="l_msg"></div>'+
      '<button class="btn btn-brass" id="dologin">Войти</button>'+
      '<p class="sub" style="margin-top:12px">Нет кабинета? Откройте вкладку «Регистрация».</p>';
      el('dologin').onclick=doLogin;
      el('l_pass').onkeydown=function(e){ if(e.key==='Enter') doLogin(); };
    } else {
      b.innerHTML='<div class="form-grid">'+
        '<div class="field"><label for="r_name">Организация *</label><input id="r_name" placeholder="ООО «Название»"></div>'+
        '<div class="field"><label for="r_phone">Телефон</label><input id="r_phone" placeholder="+7 (___) ___-__-__"></div>'+
        '<div class="field"><label for="r_email">E-mail *</label><input id="r_email" type="email" placeholder="company@mail.ru"></div>'+
        '<div class="field"><label for="r_pass">Пароль *</label><input id="r_pass" type="password" placeholder="не менее 8 символов"></div>'+
      '</div><div id="r_msg"></div>'+
      '<button class="btn btn-brass" id="doreg">Зарегистрировать компанию</button>'+
      '<p class="sub" style="margin-top:12px">Статус резидента ИНТЦ и скидку подтверждает оператор после проверки документов.</p>';
      el('doreg').onclick=doRegister;
    }
  }
  function doLogin(){
    var email=el('l_email').value.trim(), pass=el('l_pass').value, msg=el('l_msg');
    if(!email||!pass){ msg.innerHTML='<div class="form-msg err">Укажите e-mail и пароль.</div>'; return; }
    var b=el('dologin'); b.disabled=true; b.textContent='Вход…';
    P.authApi.login(email,pass).then(function(res){
      b.disabled=false; b.textContent='Войти';
      if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
      syncNav(); toast('Вы вошли в кабинет'); location.hash='#/cabinet';
    });
  }
  function doRegister(){
    var d={ name:el('r_name').value.trim(), phone:el('r_phone').value.trim(),
            email:el('r_email').value.trim(), password:el('r_pass').value };
    var msg=el('r_msg');
    if(!d.name||!d.email||!d.password){ msg.innerHTML='<div class="form-msg err">Заполните обязательные поля (*).</div>'; return; }
    var b=el('doreg'); b.disabled=true; b.textContent='Отправка…';
    P.authApi.register(d).then(function(res){
      b.disabled=false; b.textContent='Зарегистрировать компанию';
      if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
      syncNav(); toast('Кабинет создан'); location.hash='#/cabinet';
    });
  }

  /* ---------- профиль компании ---------- */
  function viewCabinet(){
    if(needAuth()) return;
    var c=P.company()||{};
    render(pageHead('Личный кабинет', esc(c.name||'Компания'), 'Профиль организации и статус в кластере «Ломоносов».')+
    '<section class="section"><div class="wrap">'+cabTabs('#/cabinet')+
      '<div id="cabbody"><div class="muted">Загрузка…</div></div>'+
    '</div></section>', function(){
      // перечитываем профиль: оператор мог подтвердить статус
      P.authApi.refresh().then(function(){ syncNav(); drawProfile(); });
    });
  }
  function drawProfile(){
    var box=el('cabbody'); if(!box) return;
    var c=P.company();
    if(!c){ location.hash='#/login'; return; }
    var opts=Object.keys(CATS).map(function(k){
      return '<option value="'+k+'"'+(c.category===k?' selected':'')+'>'+esc(CATS[k])+'</option>';
    }).join('');
    box.innerHTML=statusNote(c)+
      '<div class="checkout-form"><h3>Данные организации</h3>'+
      '<div class="form-grid">'+
        '<div class="field"><label for="p_name">Организация *</label><input id="p_name" value="'+esc(c.name)+'"></div>'+
        '<div class="field"><label for="p_inn">ИНН</label><input id="p_inn" value="'+esc(c.inn)+'" placeholder="10 или 12 цифр"></div>'+
        '<div class="field"><label for="p_contact">Контактное лицо</label><input id="p_contact" value="'+esc(c.contact_name)+'"></div>'+
        '<div class="field"><label for="p_phone">Телефон</label><input id="p_phone" value="'+esc(c.phone)+'"></div>'+
        '<div class="field"><label for="p_cat">Направление</label><select id="p_cat"><option value="">— не выбрано —</option>'+opts+'</select></div>'+
        '<div class="field"><label for="p_email">E-mail (логин)</label><input id="p_email" value="'+esc(c.email)+'" disabled></div>'+
      '</div>'+
      '<div id="p_msg"></div>'+
      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">'+
        '<button class="btn btn-brass" id="psave">Сохранить</button>'+
        '<button class="btn btn-ghost" id="plogout">Выйти из кабинета</button>'+
      '</div></div>';
    el('psave').onclick=function(){
      var msg=el('p_msg');
      var d={ name:el('p_name').value.trim(), inn:el('p_inn').value.trim(),
              contact_name:el('p_contact').value.trim(), phone:el('p_phone').value.trim(),
              category:el('p_cat').value };
      if(!d.name){ msg.innerHTML='<div class="form-msg err">Укажите название организации.</div>'; return; }
      var b=el('psave'); b.disabled=true; b.textContent='Сохранение…';
      P.authApi.save(d).then(function(res){
        b.disabled=false; b.textContent='Сохранить';
        if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
        msg.innerHTML='<div class="form-msg ok">Сохранено.</div>'; syncNav(); toast('Профиль обновлён');
      });
    };
    el('plogout').onclick=function(){ P.authApi.logout(); syncNav(); toast('Вы вышли из кабинета'); location.hash='#/'; };
  }

  /* ---------- мои заявки ---------- */
  function viewCabOrders(){
    if(needAuth()) return;
    render(pageHead('Личный кабинет','Мои заявки','История бронирований, статусы и запросы на перенос.')+
    '<section class="section"><div class="wrap">'+cabTabs('#/cabinet/orders')+
      '<div id="cabbody"><div class="muted">Загрузка…</div></div>'+
    '</div></section>', function(){ loadCabOrders(); });
  }
  function loadCabOrders(){
    var box=el('cabbody'); if(!box) return;
    P.ordersApi.list().then(function(res){
      if(!res.ok){
        if(res.status===401){ P.authApi.logout(); syncNav(); location.hash='#/login'; return; }
        box.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return;
      }
      var list=Array.isArray(res.data)?res.data:(res.data&&res.data.results)||[];
      if(!list.length){
        box.innerHTML='<div class="empty"><h3>Заявок пока нет</h3>'+
          '<p>Выберите оборудование, лабораторию или специалиста в каталоге и оформите бронирование.</p>'+
          '<a class="btn btn-primary" href="#/catalog">Открыть каталог</a></div>';
        return;
      }
      box.innerHTML=list.map(orderCard).join('');
      bindCabOrders();
    });
  }
  var ST={new:'new', confirmed:'ok', rejected:'rej'};
  function orderCard(o){
    var d=o.created_at?P.dates.human(String(o.created_at).slice(0,10)):'';
    return '<div class="ord-card">'+
      '<div class="ord-head">'+
        '<div><div class="ord-num">'+esc(o.number)+'</div><div class="cline-meta">'+esc(d)+'</div></div>'+
        '<div style="text-align:right">'+
          '<span class="badge '+(ST[o.status]||'new')+'">'+esc(o.statusLabel)+'</span>'+
          '<div class="ord-total">'+fmt(o.total)+'</div>'+
        '</div>'+
      '</div>'+
      '<div class="ord-lines">'+(o.lines||[]).map(function(l){
        var when=l.date?P.dates.human(l.date):'без даты';
        if(l.slotStart&&l.slotEnd) when+=', '+l.slotStart+'–'+l.slotEnd;
        return '<div class="cl"><span>'+esc(l.title)+(l.isOperator?' <em style="color:var(--brass)">(оператор)</em>':'')+
          '<br><span class="cline-meta">'+esc(when)+'</span></span><span>'+fmt(l.linePrice)+'</span></div>';
      }).join('')+
      (o.discount?'<div class="cl"><span>Скидка резидента ИНТЦ</span><span>−'+fmt(o.discount)+'</span></div>':'')+
      '</div>'+
      (o.note?'<div class="ord-note"><strong>Комментарий:</strong> '+esc(o.note)+'</div>':'')+
      (o.changeRequest?'<div class="ord-note"><strong>Запрос на изменение:</strong> '+esc(o.changeRequest)+'</div>':'')+
      '<div class="ord-actions">'+
        (o.status==='new'
          ? '<button class="btn btn-ghost btn-sm" data-chg="'+o.id+'">Попросить перенос</button>'+
            '<button class="btn btn-ghost btn-sm" data-cancel="'+o.id+'">Отменить заявку</button>'
          : '<span class="cline-meta">Заявку в этом статусе меняет оператор — напишите на info@pulsar-mgu.ru</span>')+
      '</div>'+
      '<div id="ordmsg-'+o.id+'"></div>'+
    '</div>';
  }
  function bindCabOrders(){
    qsAll('[data-cancel]').forEach(function(b){
      b.onclick=function(){
        var id=b.getAttribute('data-cancel');
        if(!confirm('Отменить заявку? Действие необратимо.')) return;
        b.disabled=true;
        P.ordersApi.cancel(id).then(function(res){
          if(!res.ok){ el('ordmsg-'+id).innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; b.disabled=false; return; }
          toast('Заявка отменена'); loadCabOrders();
        });
      };
    });
    qsAll('[data-chg]').forEach(function(b){
      b.onclick=function(){
        var id=b.getAttribute('data-chg');
        var msg=prompt('Что нужно изменить? Например: перенести на 5 августа, 14:00.');
        if(!msg||!msg.trim()) return;
        b.disabled=true;
        P.ordersApi.requestChange(id, msg.trim()).then(function(res){
          b.disabled=false;
          if(!res.ok){ el('ordmsg-'+id).innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
          toast('Запрос отправлен оператору'); loadCabOrders();
        });
      };
    });
  }

  /* ---------- показатели ИНТЦ ---------- */
  var kpiYear=null;
  function viewCabKpi(){
    if(needAuth()) return;
    render(pageHead('Личный кабинет','Показатели деятельности','Ключевые показатели по Методологии оценки участников ИНТЦ: план ставит оператор, факт складывается из ваших позиций.')+
    '<section class="section"><div class="wrap">'+cabTabs('#/cabinet/kpi')+
      '<div id="cabbody"><div class="muted">Загрузка…</div></div>'+
    '</div></section>', function(){ loadKpi(); });
  }
  function loadKpi(){
    var box=el('cabbody'); if(!box) return Promise.resolve();
    return P.kpiApi.get(kpiYear).then(function(res){
      if(!res.ok){
        if(res.status===401){ P.authApi.logout(); syncNav(); location.hash='#/login'; return; }
        box.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return;
      }
      kpiYear=res.data.year;
      var items=res.data.items||[];
      box.innerHTML='<div class="kpi-bar">'+
          '<button class="btn btn-ghost btn-sm" id="kyprev">‹ '+(kpiYear-1)+'</button>'+
          '<strong>'+kpiYear+' год</strong>'+
          '<button class="btn btn-ghost btn-sm" id="kynext">'+(kpiYear+1)+' ›</button>'+
        '</div>'+
        '<div class="kpi-grid">'+items.map(kpiCard).join('')+'</div>';
      el('kyprev').onclick=function(){ kpiYear--; loadKpi(); };
      el('kynext').onclick=function(){ kpiYear++; loadKpi(); };
      bindKpi();
    });
  }
  var KST={ok:'ok', warn:'new', bad:'rej', none:''};
  // Числа показателей могут быть дробными (12,5 %), поэтому запятую-разделитель
  // трогать нельзя: разделяем только разряды тысяч.
  function kpiNum(v,unit){
    if(v==null || v==='') return '—';
    var n=Number(v);
    if(isNaN(n)) return '—';
    var neg=n<0; n=Math.abs(n);
    var r=Math.round(n*100)/100;
    var ip=Math.floor(r), fp=Math.round((r-ip)*100);
    var s=String(ip).replace(/\B(?=(\d{3})+(?!\d))/g,' ');
    if(fp) s+=','+(fp<10?'0'+fp:String(fp)).replace(/0$/,'');
    return (neg?'−':'')+s+(unit?' '+unit:'');
  }
  function kpiCard(k){
    var val=k.value, plan=k.plan;
    var badge=k.status==='ok'?'достигнут':k.status==='warn'?'ниже плана':k.status==='bad'?'существенное отставание':'нет плана';
    return '<div class="kpi-card">'+
      '<div class="kpi-top">'+
        '<div><div class="kpi-label">'+esc(k.label)+'</div>'+
          (k.hint?'<div class="cline-meta">'+esc(k.hint)+'</div>':'')+'</div>'+
        '<span class="badge '+(KST[k.status]||'')+'">'+badge+'</span>'+
      '</div>'+
      '<div class="kpi-nums">'+
        '<div><span class="cline-meta">Факт</span><strong>'+kpiNum(val, k.percent?'%':k.unit)+'</strong></div>'+
        '<div><span class="cline-meta">План</span><strong>'+kpiNum(plan, k.percent?'%':k.unit)+'</strong></div>'+
      '</div>'+
      (k.percent?'<div class="cline-meta">Считается как доля от выручки — заполните выручку за тот же год.</div>':'')+
      '<div class="kpi-entries">'+((k.entries||[]).length
        ? k.entries.map(function(e){
            return '<div class="cl"><span>'+esc(e.title)+
              (e.date?' <span class="cline-meta">'+esc(P.dates.human(e.date))+'</span>':'')+
              (e.document?' <a href="'+esc(e.document)+'" target="_blank" class="kpi-doc">документ</a>':'')+
              (e.source==='auto'?' <em class="cline-meta">(из документа)</em>':'')+
              '</span><span>'+kpiNum(e.amount,'')+' <button class="cline-remove" data-kdel="'+k.key+':'+e.id+'">×</button></span></div>';
          }).join('')
        : '<div class="cline-meta">Позиций пока нет.</div>')+'</div>'+
      '<details class="kpi-add"><summary>Добавить позицию</summary>'+
        '<div class="form-grid">'+
          '<div class="field full"><label for="ke_t_'+k.key+'">Что сделано / на что потрачено</label><input id="ke_t_'+k.key+'" placeholder="Договор, патент, сотрудник…"></div>'+
          '<div class="field"><label for="ke_a_'+k.key+'">Сумма / количество ('+esc(k.unit)+')</label><input id="ke_a_'+k.key+'" type="number" step="0.01" placeholder="0"></div>'+
          '<div class="field"><label for="ke_d_'+k.key+'">Дата</label><input id="ke_d_'+k.key+'" type="date"></div>'+
        '</div>'+
        '<button class="btn btn-brass btn-sm" data-kadd="'+k.key+'">Добавить</button>'+
        '<div class="kpi-up">'+
          '<label class="cline-meta">…или прикрепите документ — система заведёт позицию сама'+
            (k.docs?'<br><span class="kpi-docs">Нужны: '+esc(k.docs)+'</span>':'')+'</label>'+
          '<input type="file" accept=".pdf" data-kfile="'+k.key+'">'+
        '</div>'+
        '<div id="kmsg-'+k.key+'"></div>'+
      '</details>'+
    '</div>';
  }
  function bindKpi(){
    qsAll('[data-kadd]').forEach(function(b){
      b.onclick=function(){
        var key=b.getAttribute('data-kadd'), msg=el('kmsg-'+key);
        var title=el('ke_t_'+key).value.trim(), amount=el('ke_a_'+key).value, date=el('ke_d_'+key).value;
        if(!title){ msg.innerHTML='<div class="form-msg err">Укажите наименование.</div>'; return; }
        b.disabled=true;
        var d={title:title}; if(amount!=='') d.amount=amount; if(date) d.date=date;
        P.kpiApi.addEntry(key, d, kpiYear).then(function(res){
          b.disabled=false;
          if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
          toast('Позиция добавлена'); loadKpi();
        });
      };
    });
    qsAll('[data-kdel]').forEach(function(b){
      b.onclick=function(){
        var p=b.getAttribute('data-kdel').split(':');
        P.kpiApi.deleteEntry(p[0], p[1]).then(function(res){
          if(!res.ok){ toast('Не удалось удалить'); return; }
          toast('Позиция удалена'); loadKpi();
        });
      };
    });
    qsAll('[data-kfile]').forEach(function(inp){
      inp.onchange=function(){
        var key=inp.getAttribute('data-kfile'), f=inp.files&&inp.files[0], msg=el('kmsg-'+key);
        if(!f) return;
        msg.innerHTML='<div class="cline-meta">Загрузка документа…</div>';
        P.kpiApi.upload(key, f, kpiYear).then(function(res){
          if(!res.ok){ msg.innerHTML='<div class="form-msg err">'+esc(res.msg)+'</div>'; return; }
          // Сумму из документа распознаёт эвристика — она срабатывает не всегда.
          // Если не вышло, честно просим указать вручную: иначе позиция висит
          // без суммы и в факт показателя не попадает.
          var noAmount = !res.data || res.data.amount==null || res.data.amount==='';
          toast(noAmount ? 'Документ загружен, сумму нужно указать' : 'Документ загружен');
          Promise.resolve(loadKpi()).then(function(){
            if(!noAmount) return;
            var d=document.querySelector('.kpi-card [data-kadd="'+key+'"]');
            var det=d && d.closest('details');
            if(det) det.open=true;                       // раскрываем блок добавления
            var m=el('kmsg-'+key);
            if(m) m.innerHTML='<div class="form-msg err">Документ прикреплён, но сумму распознать не удалось. '+
              'Укажите её вручную — иначе позиция не войдёт в факт показателя.</div>';
          });
        });
      };
    });
  }

  /* ---------- навигация: показываем состояние входа ---------- */
  function syncNav(){
    var a=el('cablink'); if(!a) return;
    var c=P.company();
    a.setAttribute('href', P.isLogged()?'#/cabinet':'#/login');
    a.textContent = P.isLogged() ? (c&&c.name ? shortName(c.name) : 'Кабинет') : 'Войти';
    a.classList.toggle('on', P.isLogged());
  }
  function shortName(n){ n=String(n); return n.length>22 ? n.slice(0,21)+'…' : n; }

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
      case 'login': return viewLogin();
      case 'cabinet':
        if(seg[1]==='orders') return viewCabOrders();
        if(seg[1]==='kpi') return viewCabKpi();
        return viewCabinet();
      case 'admin': return viewAdmin();
      case 'about': return viewAbout();
      case 'how': return viewHow();
      case 'contacts': return viewContacts();
      default: return viewHome();
    }
  }
  window.addEventListener('hashchange', route);

  // мобильное меню
  // мобильное меню: состояние дублируем в aria-expanded, иначе с экранного
  // диктора не понять, раскрыт список или нет
  function setNavOpen(open){
    el('navlinks').classList.toggle('open', open);
    el('navtoggle').setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  el('navtoggle').onclick=function(){ setNavOpen(!el('navlinks').classList.contains('open')); };
  qsAll('#navlinks a').forEach(function(a){ a.addEventListener('click',function(){ setNavOpen(false); }); });

  // ссылки «Кабинет оператора» ведут в Django-админку
  qsAll('a[data-admin]').forEach(function(a){ a.setAttribute('href', window.PULSAR_ADMIN_URL || '/admin/'); a.setAttribute('target','_blank'); });

  // Старт: подтягиваем из бэкенда каталог и занятость, затем рисуем страницу.
  // Оба запроса идут параллельно; если бэкенд недоступен, каталог берётся из
  // data/resources.js, а бронь работает без блокировок занятых слотов.
  syncCart();
  syncNav();
  var pending=2;
  function ready(){ if(--pending===0){ syncCart(); route(); } }
  P.loadCatalog(ready);
  P.loadBusy(ready);
  // если компания уже входила — обновляем профиль (статус мог измениться)
  if(P.isLogged()) P.authApi.refresh().then(syncNav);
})();
