import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

class LandingServicesPricingSection extends StatefulWidget {
  const LandingServicesPricingSection({super.key});

  @override
  State<LandingServicesPricingSection> createState() =>
      _LandingServicesPricingSectionState();
}

class _LandingServicesPricingSectionState
    extends State<LandingServicesPricingSection> {
  late final ScrollController _tableScrollController;

  @override
  void initState() {
    super.initState();
    _tableScrollController = ScrollController();
  }

  @override
  void dispose() {
    _tableScrollController.dispose();
    super.dispose();
  }

  static const _columns = <_PricingColumn>[
    _PricingColumn('№', 52),
    _PricingColumn('Услуга', 230),
    _PricingColumn('Ед.', 82),
    _PricingColumn('Старт', 118),
    _PricingColumn('Выезд', 104),
    _PricingColumn('Смета', 110),
    _PricingColumn('Согласование', 132),
    _PricingColumn('Подготовка', 118),
    _PricingColumn('Монтаж', 116),
    _PricingColumn('Сдача', 104),
    _PricingColumn('Гарантия', 96),
    _PricingColumn('Документы', 122),
    _PricingColumn('НДС', 74),
    _PricingColumn('Ночь', 80),
    _PricingColumn('Срочность', 96),
    _PricingColumn('Объём', 92),
    _PricingColumn('Бригада', 106),
    _PricingColumn('Регион', 118),
    _PricingColumn('Объект', 122),
    _PricingColumn('Формат', 104),
    _PricingColumn('Ответственный', 132),
    _PricingColumn('Контроль', 108),
    _PricingColumn('Логистика', 112),
    _PricingColumn('Фото', 98),
    _PricingColumn('Акт', 82),
    _PricingColumn('Оплата', 96),
    _PricingColumn('Пакет', 100),
    _PricingColumn('Верификация', 116),
    _PricingColumn('Резерв', 88),
    _PricingColumn('Комментарий', 260),
  ];

  static const _rows = <_PricingMatrixRow>[
    _PricingMatrixRow([
      '01',
      'Гостиничная и ресторанная мебель',
      'объект',
      'от 12 000 ₽',
      'бесплатно',
      '2-4 часа',
      'до 4 часов',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.25x',
      '1.35x',
      'до -12%',
      '2-4 мастера',
      'Екатеринбург / область',
      'отель, ресторан',
      'проектный',
      'ведущий бригадир',
      'трёхступенчатый',
      'авто-маршрут',
      'по каждой зоне',
      'в день сдачи',
      '30% / 70%',
      'базовый',
      'по чек-листу',
      '12 часов',
      'ночные и утренние окна',
    ]),
    _PricingMatrixRow([
      '02',
      'Мебель по дизайн-проектам',
      'объект',
      'от 15 000 ₽',
      'бесплатно',
      '4-8 часов',
      'до 1 дня',
      '1-2 дня',
      '2-4 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт, спецификация',
      'без НДС',
      '1.30x',
      '1.40x',
      'до -10%',
      '3-5 мастеров',
      'Москва / Екатеринбург',
      'офис, шоурум',
      'премиальный',
      'архитектор проекта',
      'два цикла',
      'плановый',
      'по фотофиксации',
      'в день сдачи',
      '40% / 60%',
      'индивидуальный',
      'по ТЗ и чертежам',
      '1 рабочий день',
      'без корректировок по факту',
    ]),
    _PricingMatrixRow([
      '03',
      'Мебель для учреждений',
      'объект',
      'от 9 500 ₽',
      'бесплатно',
      '2-6 часов',
      '2-6 часов',
      '1 рабочий день',
      '1-3 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.20x',
      '1.25x',
      'до -15%',
      '2-4 мастера',
      'Екатеринбург / регионы',
      'школа, медцентр, офис',
      'стандартизированный',
      'старший смены',
      'контроль перед сдачей',
      'авто или грузовой',
      'по блокам',
      'в день сдачи',
      '50% / 50%',
      'базовый',
      'по ведомости',
      '8 часов',
      'без остановки процесса',
    ]),
    _PricingMatrixRow([
      '04',
      'Металлическая мебель',
      'объект',
      'от 6 500 ₽',
      'бесплатно',
      '2-6 часов',
      '2-6 часов',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.18x',
      '1.22x',
      'до -8%',
      '2-3 мастера',
      'Екатеринбург / область',
      'склад, лаборатория',
      'технический',
      'прораб',
      'приёмка на объекте',
      'авто-маршрут',
      'по узлам',
      'в день сдачи',
      '30% / 70%',
      'базовый',
      'с приложением фото',
      '12 часов',
      'ночные окна по запросу',
    ]),
    _PricingMatrixRow([
      '05',
      'Мебель для ЖК и застройщиков',
      'объект',
      'от 14 000 ₽',
      'бесплатно',
      '4-12 часов',
      'до 2 дней',
      '1-2 дня',
      '2-5 дней',
      'в день завершения',
      '12 мес.',
      'договор, акт, спецификация',
      'без НДС',
      '1.28x',
      '1.33x',
      'до -14%',
      '3-6 мастеров',
      'Екатеринбург / область',
      'ЖК, апарт, подъезд',
      'серийный',
      'координатор объекта',
      'контроль по секциям',
      'авто / склад',
      'по секциям',
      'по этапам',
      '40% / 60%',
      'проектный',
      'по графику девелопера',
      '2 рабочих дня',
      'без срывов графика',
    ]),
    _PricingMatrixRow([
      '06',
      'Торговая мебель и складские системы',
      'объект',
      'от 11 000 ₽',
      'бесплатно',
      '4-12 часов',
      'до 2 дней',
      '1 рабочий день',
      '1-4 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.24x',
      '1.31x',
      'до -11%',
      '2-5 мастеров',
      'Екатеринбург / РФ',
      'магазин, склад',
      'ритейл',
      'старший монтажник',
      'приёмка по чек-листу',
      'ночной склад',
      'по зонам',
      'в день сдачи',
      '30% / 70%',
      'пакетный',
      'по ведомости',
      '16 часов',
      'под запуск точки',
    ]),
    _PricingMatrixRow([
      '07',
      'Офисные перегородки и зонирование',
      'объект',
      'от 8 500 ₽',
      'бесплатно',
      '2-4 часа',
      'до 1 дня',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.19x',
      '1.24x',
      'до -9%',
      '2-3 мастера',
      'Екатеринбург / область',
      'офис, коворкинг',
      'модульный',
      'координатор монтажа',
      'контроль геометрии',
      'авто-маршрут',
      'по секциям',
      'в день сдачи',
      '40% / 60%',
      'базовый',
      'по планировке',
      '10 часов',
      'без остановки офиса',
    ]),
    _PricingMatrixRow([
      '08',
      'Кухонные блоки и бытовые зоны',
      'объект',
      'от 7 900 ₽',
      'бесплатно',
      '2-6 часов',
      'до 1 дня',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.17x',
      '1.20x',
      'до -7%',
      '2-3 мастера',
      'Екатеринбург / РФ',
      'офис, склад, ЖК',
      'пакетный',
      'старший мастер',
      'по узлам',
      'авто / склад',
      'по узлам',
      'в день завершения',
      '30% / 70%',
      'базовый',
      'по фото',
      '8 часов',
      'под ключ',
    ]),
    _PricingMatrixRow([
      '09',
      'Стеллажи и архивные системы',
      'объект',
      'от 5 900 ₽',
      'бесплатно',
      '2-4 часа',
      'до 1 дня',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.16x',
      '1.18x',
      'до -6%',
      '2-4 мастера',
      'Екатеринбург / область',
      'архив, склад',
      'серийный',
      'старший смены',
      'контроль по рядам',
      'авто-маршрут',
      'по секциям',
      'в день сдачи',
      '50% / 50%',
      'базовый',
      'по схеме',
      '6 часов',
      'без простоя',
    ]),
    _PricingMatrixRow([
      '10',
      'Ресепшн и клиентские зоны',
      'объект',
      'от 10 500 ₽',
      'бесплатно',
      '4-8 часов',
      'до 1 дня',
      '1-2 дня',
      '2-3 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт, спецификация',
      'без НДС',
      '1.26x',
      '1.30x',
      'до -10%',
      '3-4 мастера',
      'Москва / Екатеринбург',
      'офис, отель',
      'премиальный',
      'ведущий бригадир',
      'фото-контроль',
      'авто / склад',
      'по зонам',
      'в день сдачи',
      '40% / 60%',
      'индивидуальный',
      'по визуалу',
      '12 часов',
      'сдача без замечаний',
    ]),
    _PricingMatrixRow([
      '11',
      'Сервисные стойки и шоурумы',
      'объект',
      'от 13 500 ₽',
      'бесплатно',
      '4-12 часов',
      'до 2 дней',
      '1-2 дня',
      '2-4 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт, спецификация',
      'без НДС',
      '1.29x',
      '1.34x',
      'до -11%',
      '3-5 мастеров',
      'Москва / РФ',
      'шоурум, салон',
      'проектный',
      'координатор объекта',
      'приёмка по фото',
      'ночной слот',
      'по узлам',
      'в день сдачи',
      '30% / 70%',
      'пакетный',
      'по макету',
      '16 часов',
      'под открытие',
    ]),
    _PricingMatrixRow([
      '12',
      'Складская навигация и маркировка',
      'объект',
      'от 4 800 ₽',
      'бесплатно',
      '2-4 часа',
      'до 1 дня',
      '1 рабочий день',
      '1-2 дня',
      'в день завершения',
      '12 мес.',
      'договор, акт',
      'без НДС',
      '1.14x',
      '1.17x',
      'до -5%',
      '2-3 мастера',
      'Екатеринбург / РФ',
      'склад, логцентр',
      'операционный',
      'старший смены',
      'контроль маршрута',
      'авто-маршрут',
      'по секциям',
      'в день сдачи',
      '50% / 50%',
      'базовый',
      'по плану склада',
      '4 часа',
      'без остановки процесса',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final headerStyle = theme.textTheme.labelSmall?.copyWith(
      color: AppThemeTokens.textLight,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.8,
    );
    final cellStyle = theme.textTheme.bodySmall?.copyWith(
      color: AppThemeTokens.textDark,
      height: 1.25,
    );
    final columnWidths = <int, TableColumnWidth>{
      for (var index = 0; index < _columns.length; index++)
        index: FixedColumnWidth(_columns[index].width),
    };

    assert(_rows.every((row) => row.cells.length == _columns.length));

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppThemeTokens.contentMaxWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'ЦЕНЫ',
                textAlign: TextAlign.center,
                style: theme.textTheme.displaySmall,
              ),
              const SizedBox(height: 12),
              Text(
                'Ниже показана строгая корпоративная матрица ориентиров. Финальная цена, срок и резерв времени фиксируются после выезда и согласования объёма.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(
                    color: AppThemeTokens.brandPrimaryDark,
                    width: 2,
                  ),
                ),
                child: ScrollbarTheme(
                  data: const ScrollbarThemeData(
                    thickness: WidgetStatePropertyAll(8),
                    trackVisibility: WidgetStatePropertyAll(true),
                    thumbVisibility: WidgetStatePropertyAll(true),
                    crossAxisMargin: 0,
                    mainAxisMargin: 0,
                  ),
                  child: Scrollbar(
                    controller: _tableScrollController,
                    thumbVisibility: true,
                    trackVisibility: true,
                    child: SingleChildScrollView(
                      controller: _tableScrollController,
                      scrollDirection: Axis.horizontal,
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(minWidth: 3400),
                        child: Table(
                          border: TableBorder.all(
                            color: AppThemeTokens.brandPrimaryDark,
                            width: 1,
                          ),
                          defaultVerticalAlignment:
                              TableCellVerticalAlignment.middle,
                          columnWidths: columnWidths,
                          children: [
                            TableRow(
                              decoration: const BoxDecoration(
                                color: AppThemeTokens.brandPrimaryDark,
                              ),
                              children: [
                                for (final column in _columns)
                                  _TableCell(
                                    column.title.toUpperCase(),
                                    style: headerStyle,
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 12,
                                    ),
                                  ),
                              ],
                            ),
                            for (var rowIndex = 0;
                                rowIndex < _rows.length;
                                rowIndex++)
                              TableRow(
                                decoration: BoxDecoration(
                                  color: rowIndex.isEven
                                      ? AppThemeTokens.backgroundLight
                                      : AppThemeTokens.backgroundSurface,
                                ),
                                children: [
                                  for (final cell in _rows[rowIndex].cells)
                                    _TableCell(
                                      cell,
                                      style: cellStyle,
                                    ),
                                ],
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                'Пакеты, графики и окно на согласование можно менять под объект. Для сетевых заказов допустимы отдельные регламенты и фиксация ответственного.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: AppThemeTokens.textDark,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PricingColumn {
  const _PricingColumn(this.title, this.width);

  final String title;
  final double width;
}

class _PricingMatrixRow {
  const _PricingMatrixRow(this.cells);

  final List<String> cells;
}

class _TableCell extends StatelessWidget {
  const _TableCell(
    this.text, {
    required this.style,
    this.padding = const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
  });

  final String text;
  final TextStyle? style;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Text(
        text,
        style: style,
        maxLines: 4,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
