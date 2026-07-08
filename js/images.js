/* ============================================================
   ПУЛЬСАР — изображения: реальное фото из манифеста ИЛИ
   аккуратный брендовый дуотон-плейсхолдер (SVG data-URI),
   который рисуется всегда — на GitHub Pages и с file://.
   ============================================================ */
(function(){
  var P = window.PULSAR = window.PULSAR || {};

  // тонкие линейные глифы по типу ресурса
  var GLYPHS = {
    room:'<rect x="10" y="26" width="60" height="40" rx="2"/><path d="M10 40h60M28 26v40M52 26v40"/>',
    equipment:'<rect x="22" y="14" width="36" height="52" rx="2"/><path d="M30 26h20M30 36h20M30 46h12"/><circle cx="46" cy="58" r="3"/>',
    specialist:'<circle cx="40" cy="30" r="11"/><path d="M20 66c0-12 9-20 20-20s20 8 20 20"/>',
    service:'<path d="M30 16h20l10 12v34a2 2 0 0 1-2 2H22a2 2 0 0 1-2-2V18a2 2 0 0 1 2-2h8z"/><path d="M50 16v12h10M28 40h24M28 50h24"/>'
  };
  // цвет карточки по научному направлению (как в исходном прототипе — цветные плашки)
  var CAT = {
    pharma:   {g:['#123A5A','#0A2036'], a:'#7FB0DA'},
    bio:      {g:['#124A38','#0A2A1F'], a:'#7FCBA6'},
    micro:    {g:['#2A1A52','#160B30'], a:'#B49BDA'},
    vacuum:   {g:['#33415A','#1A2430'], a:'#A6B6CC'},
    genetics: {g:['#0E4A52','#08292E'], a:'#7FCBD0'},
    materials:{g:['#4A3316','#241206'], a:'#D9B476'},
    food:     {g:['#3A4A16','#1F2A0A'], a:'#BAC77F'},
    analytics:{g:['#123A5A','#0A1E33'], a:'#8FB3D9'}
  };

  function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function placeholder(res){
    var type = res && res.type || 'equipment';
    var cat  = (res && res.category) || 'analytics';
    var c = CAT[cat] || CAT.analytics;
    var glyph = GLYPHS[type] || GLYPHS.equipment;
    var label = esc((res && res.lab) || 'ПУЛЬСАР');
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 250" preserveAspectRatio="xMidYMid slice">'+
        '<defs>'+
          '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'+
            '<stop offset="0" stop-color="'+c.g[0]+'"/><stop offset="1" stop-color="'+c.g[1]+'"/>'+
          '</linearGradient>'+
          '<pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">'+
            '<path d="M26 0H0V26" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="1"/>'+
          '</pattern>'+
        '</defs>'+
        '<rect width="400" height="250" fill="url(#g)"/>'+
        '<rect width="400" height="250" fill="url(#grid)"/>'+
        '<g transform="translate(160,58) scale(1.1)" fill="none" stroke="'+c.a+'" stroke-width="2.2" '+
           'stroke-linecap="round" stroke-linejoin="round" opacity="0.92">'+glyph+'</g>'+
        '<rect x="0" y="208" width="400" height="42" fill="#000000" fill-opacity="0.28"/>'+
        '<text x="24" y="234" fill="#ffffff" fill-opacity="0.85" '+
           'font-family="Manrope,Arial,sans-serif" font-size="13" letter-spacing="0.3">'+label+'</text>'+
        '<circle cx="372" cy="230" r="4" fill="'+c.a+'"/>'+
      '</svg>';
    return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
  }

  // основной путь к картинке ресурса
  P.getImage = function(res){
    var key = res && res.img;
    var real = key && P.images && P.images[key];
    return real ? real : placeholder(res);
  };

  // именованное изображение (hero/about) с фолбэком-плейсхолдером
  P.getNamed = function(name, fallbackType){
    var real = P.images && P.images[name];
    return real ? real : placeholder({type:fallbackType||'room', lab:'ПУЛЬСАР'});
  };

  P.placeholderFor = placeholder;

  // <img> с onerror-фолбэком: если реальный файл не найден — рисуем плейсхолдер
  P.imgTag = function(res, cls, alt){
    var src = P.getImage(res);
    var fb = placeholder(res).replace(/"/g,'&quot;');
    return '<img src="'+src+'" alt="'+esc(alt||res.title||'')+'"'+(cls?' class="'+cls+'"':'')+
           ' loading="lazy" onerror="this.onerror=null;this.src=\''+fb+'\'">';
  };
})();
