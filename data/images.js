/* ============================================================
   ПУЛЬСАР — манифест изображений (тематическое соответствие).
   Ключ = поле img у ресурса. Каждая карточка — своя картинка по теме.
   Только ЛОКАЛЬНЫЕ файлы (assets/img/*) — чтобы всё гарантированно
   грузилось и на GitHub Pages, и с мобильного интернета, без внешних
   CDN. Пусто ('') → аккуратный брендовый плейсхолдер по направлению
   (рисуется инлайн SVG, не требует сети).
   ============================================================ */
window.PULSAR = window.PULSAR || {};

(function(){
  window.PULSAR.images = {
    // крупные декоративные фото (реальные локальные снимки)
    'hero'       : 'assets/img/building.jpg',        // здание кластера «Ломоносов»
    'about'      : 'assets/img/building.jpg',         // ИНТЦ МГУ
    'hero-media' : 'assets/img/lab-generic.jpg',      // лаборатория (первый экран)

    // помещения — брендовый плейсхолдер по научному направлению
    'room-a'        : '',
    'room-b'        : '',
    'room-v'        : '',
    'room-vacuum'   : 'assets/img/eq-vk1000.png',     // реальная камера ВК-1000 (входит в комплекс)
    'room-genomics' : '',
    'room-nutrition': '',

    // оборудование — РЕАЛЬНЫЕ фото из «Приложение_1_Испытательный_комплекс.pdf»
    'eq-vk1000'  : 'assets/img/eq-vk1000.png',
    'eq-kthv1000': 'assets/img/eq-kthv1000.png',
    'eq-fcc1000' : 'assets/img/eq-fcc1000.png',
    'eq-bgd856'  : 'assets/img/eq-bgd856.png',
    'eq-mim'     : 'assets/img/eq-mim.png',
    'eq-formolder':'assets/img/eq-formolder.png',

    // оборудование — реальные фото приборов
    'eq-massspec': 'assets/img/eq-massspec.jpg',      // масс-спектрометр / анализатор
    'eq-sem'     : 'assets/img/eq-sem.jpg',           // электронный микроскоп
    'eq-tem'     : 'assets/img/eq-tem.jpg',           // микроскоп
    'eq-nmr'     : 'assets/img/eq-nmr.jpg',           // крупный прибор/магнит (ЯМР)
    'eq-raman'   : 'assets/img/eq-raman.jpg',         // спектрометр
    'eq-xrd'     : 'assets/img/eq-xrd.jpg',           // приборная панель
    'eq-hplc'    : 'assets/img/eq-hplc.jpg',          // лабораторный стол/прибор
    'eq-pcr'     : 'assets/img/eq-pcr.jpg',           // молекулярная лаборатория
    'eq-facs'    : 'assets/img/eq-facs.jpg',          // приборы на столе
    'eq-meter'   : 'assets/img/eq-meter.jpg',         // стекло/анализ (Zetasizer)
    'eq-its1'    : 'assets/img/eq-its1.jpg',          // реальное фото ИТС-1
    'eq-lyo'     : 'assets/img/eq-lyo.jpg',
    'eq-3d'      : 'assets/img/eq-3d.jpg',

    // специалисты — брендовый плейсхолдер (роль в лаборатории)
    'sp-em'     : '',
    'sp-ms'     : '',
    'sp-nmr'    : '',
    'sp-clean'  : '',
    'sp-bioinf' : '',
    'sp-test'   : '',

    // услуги под ключ — реальные фото / брендовый плейсхолдер по направлению
    'srv-analysis': '',
    'srv-icp'     : '',
    'srv-sem'     : 'assets/img/srv-sem.jpg',         // СЭМ+EDX — реальное фото
    'srv-xrd'     : '',
    'srv-lyo'     : 'assets/img/srv-lyo.jpg'          // лиофилизация — реальное фото
  };
})();
