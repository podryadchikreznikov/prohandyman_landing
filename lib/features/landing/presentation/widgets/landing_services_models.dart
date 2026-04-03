class LandingServiceOffer {
  const LandingServiceOffer({
    required this.title,
    required this.imagePath,
    required this.summary,
    required this.priceFrom,
    required this.workDuration,
    required this.approvalTime,
  });

  final String title;
  final String imagePath;
  final String summary;
  final String priceFrom;
  final String workDuration;
  final String approvalTime;
}

const landingServiceOffers = <LandingServiceOffer>[
  LandingServiceOffer(
    title: 'Сборка и установка гостиничной, ресторанной мебели',
    imagePath: 'assets/handyman_images/photo_handyman_work_10.png',
    summary:
        'Профессионально, в срок и с соблюдением всех стандартов качества.',
    priceFrom: 'от 12 000 ₽',
    workDuration: '1-2 дня',
    approvalTime: 'до 4 часов',
  ),
  LandingServiceOffer(
    title: 'Сборка и установка мебели по дизайн-проектам',
    imagePath: 'assets/handyman_images/photo_handyman_work_11.png',
    summary:
        'Воплощаем любые идеи в реальность. Берёмся за самые сложные заказы.',
    priceFrom: 'от 15 000 ₽',
    workDuration: '2-4 дня',
    approvalTime: 'до 1 рабочего дня',
  ),
  LandingServiceOffer(
    title: 'Сборка и установка мебели для учреждений',
    imagePath: 'assets/handyman_images/photo_handyman_work_12.png',
    summary:
        'Школы, детские сады, больницы, библиотеки, конференц-залы и офисы.',
    priceFrom: 'от 9 500 ₽',
    workDuration: '1-3 дня',
    approvalTime: '2-6 часов',
  ),
  LandingServiceOffer(
    title: 'Сборка металлической мебели',
    imagePath: 'assets/handyman_images/photo_handyman_work_13.png',
    summary:
        'Шкафы, сейфы, перегородки, стеллажи, верстаки и лабораторное оборудование.',
    priceFrom: 'от 6 500 ₽',
    workDuration: '1-2 дня',
    approvalTime: '2-6 часов',
  ),
  LandingServiceOffer(
    title: 'Сборка мебели и оборудования для застройщиков ЖК',
    imagePath: 'assets/handyman_images/photo_handyman_work_14.png',
    summary:
        'Кухни, встроенная мебель, двери, санузлы, почтовые ящики и техлюки.',
    priceFrom: 'от 14 000 ₽',
    workDuration: '2-5 дней',
    approvalTime: 'до 2 рабочих дней',
  ),
  LandingServiceOffer(
    title: 'Сборка торговой мебели и складских систем',
    imagePath: 'assets/handyman_images/photo_handyman_work_15.png',
    summary:
        'Торговые стеллажи, витрины, острова, складская мебель и разгрузочные узлы.',
    priceFrom: 'от 11 000 ₽',
    workDuration: '1-4 дня',
    approvalTime: 'до 2 рабочих дней',
  ),
];

class LandingPricingRow {
  const LandingPricingRow({
    required this.index,
    required this.service,
    required this.unit,
    required this.basePrice,
    required this.minVisit,
    required this.estimateWindow,
    required this.approvalWindow,
    required this.prepWindow,
    required this.executionWindow,
    required this.handoverWindow,
    required this.guarantee,
    required this.documents,
    required this.vat,
    required this.nightFactor,
    required this.urgencyFactor,
    required this.volumeDiscount,
    required this.installationTeam,
    required this.comment,
  });

  final String index;
  final String service;
  final String unit;
  final String basePrice;
  final String minVisit;
  final String estimateWindow;
  final String approvalWindow;
  final String prepWindow;
  final String executionWindow;
  final String handoverWindow;
  final String guarantee;
  final String documents;
  final String vat;
  final String nightFactor;
  final String urgencyFactor;
  final String volumeDiscount;
  final String installationTeam;
  final String comment;
}

const landingPricingRows = <LandingPricingRow>[
  LandingPricingRow(
    index: '01',
    service: 'Гостиничная и ресторанная мебель',
    unit: 'объект',
    basePrice: '12 000 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '2-4 часа',
    approvalWindow: 'до 4 часов',
    prepWindow: '1 рабочий день',
    executionWindow: '1-2 дня',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт',
    vat: 'без НДС',
    nightFactor: '1.25x',
    urgencyFactor: '1.35x',
    volumeDiscount: 'до -12%',
    installationTeam: '2-4 мастера',
    comment: 'Подходит для сетевых объектов и точечных запусков.',
  ),
  LandingPricingRow(
    index: '02',
    service: 'Дизайн-проекты и bespoke',
    unit: 'объект',
    basePrice: '15 000 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '4-8 часов',
    approvalWindow: 'до 1 дня',
    prepWindow: '1-2 дня',
    executionWindow: '2-4 дня',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт, спецификация',
    vat: 'без НДС',
    nightFactor: '1.30x',
    urgencyFactor: '1.40x',
    volumeDiscount: 'до -10%',
    installationTeam: '3-5 мастеров',
    comment: 'Сложные решения с повышенным контролем по ТЗ.',
  ),
  LandingPricingRow(
    index: '03',
    service: 'Мебель для учреждений',
    unit: 'объект',
    basePrice: '9 500 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '2-6 часов',
    approvalWindow: '2-6 часов',
    prepWindow: '1 рабочий день',
    executionWindow: '1-3 дня',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт',
    vat: 'без НДС',
    nightFactor: '1.20x',
    urgencyFactor: '1.25x',
    volumeDiscount: 'до -15%',
    installationTeam: '2-4 мастера',
    comment: 'Школы, медцентры, офисы и культурные объекты.',
  ),
  LandingPricingRow(
    index: '04',
    service: 'Металлическая мебель',
    unit: 'объект',
    basePrice: '6 500 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '2-6 часов',
    approvalWindow: '2-6 часов',
    prepWindow: '1 рабочий день',
    executionWindow: '1-2 дня',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт',
    vat: 'без НДС',
    nightFactor: '1.18x',
    urgencyFactor: '1.22x',
    volumeDiscount: 'до -8%',
    installationTeam: '2-3 мастера',
    comment: 'Шкафы, сейфы, стеллажи, верстаки и спецоборудование.',
  ),
  LandingPricingRow(
    index: '05',
    service: 'ЖК и застройщики',
    unit: 'объект',
    basePrice: '14 000 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '4-12 часов',
    approvalWindow: 'до 2 дней',
    prepWindow: '1-2 дня',
    executionWindow: '2-5 дней',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт, спецификация',
    vat: 'без НДС',
    nightFactor: '1.28x',
    urgencyFactor: '1.33x',
    volumeDiscount: 'до -14%',
    installationTeam: '3-6 мастеров',
    comment: 'Подходит для поэтапной сдачи и серийных поставок.',
  ),
  LandingPricingRow(
    index: '06',
    service: 'Торговая мебель и складские системы',
    unit: 'объект',
    basePrice: '11 000 ₽',
    minVisit: 'бесплатно',
    estimateWindow: '4-12 часов',
    approvalWindow: 'до 2 дней',
    prepWindow: '1 рабочий день',
    executionWindow: '1-4 дня',
    handoverWindow: 'в день завершения',
    guarantee: '12 мес.',
    documents: 'договор, акт',
    vat: 'без НДС',
    nightFactor: '1.24x',
    urgencyFactor: '1.31x',
    volumeDiscount: 'до -11%',
    installationTeam: '2-5 мастеров',
    comment: 'Магазины, стеллажные зоны, складские и логистические узлы.',
  ),
];
