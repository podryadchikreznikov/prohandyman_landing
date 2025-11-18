import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_service_center_theme.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

/// Section describing the service center: text on the left, photo on the right.
class LandingServiceCenterSection extends StatefulWidget {
  const LandingServiceCenterSection({
    super.key,
    this.tiltPointerController,
  });

  final TiltGlobalPointerController? tiltPointerController;

  static const _bodyText = '''
Сервисный центр MTL предлагает полный комплекс услуг по диагностике и устранению неисправностей бытовой техники разного назначения — посудомоечные и стиральные машины, холодильники, водонагреватели, варочные панели и духовые шкафы. Опытные мастера быстро определяют причину поломки и оперативно проведут ремонт, заменив необходимые комплектующие. На работы предоставляется официальная гарантия до 12 месяцев.

Все сотрудники сервиса — профессионалы своего дела, имеющие опыт работы в сфере ремонта бытовой техники не менее 5 лет. Мы постоянно внедряем современные технологии и используем оригинальные запасные части от производителей или дилеров.

> Наша команда оказывает услуги с выездом на дом без транспортировки техники в сервис. Это удобно для клиентов. Ремонт проводится в день обращения, при наличии запчастей. Мы нацелены на высокие результаты, проявляя индивидуальный подход к каждому клиенту и устройству.
''';

  static const _quoteText =
      'Наша команда оказывает услуги с выездом на дом без '
      'транспортировки техники в сервис. Это удобно для клиентов. Ремонт '
      'проводится в день обращения, при наличии запчастей. Мы нацелены на '
      'высокие результаты, проявляя индивидуальный подход к каждому клиенту '
      'и устройству.';

  @override
  State<LandingServiceCenterSection> createState() =>
      _LandingServiceCenterSectionState();
}

class _LandingServiceCenterSectionState
    extends State<LandingServiceCenterSection> {
  bool? _useCompactLayout;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_useCompactLayout == null) {
      final serviceTheme =
          Theme.of(context).extension<LandingServiceCenterTheme>();
      assert(
        serviceTheme != null,
        'LandingServiceCenterTheme must be provided via AppTheme extensions.',
      );
      if (serviceTheme == null) {
        return;
      }
      final width = MediaQuery.of(context).size.width;
      _useCompactLayout = width < serviceTheme.compactBreakpoint;
    }
  }

  @override
  Widget build(BuildContext context) {
    final serviceTheme =
        Theme.of(context).extension<LandingServiceCenterTheme>();
    assert(
      serviceTheme != null,
      'LandingServiceCenterTheme must be provided via AppTheme extensions.',
    );
    if (serviceTheme == null) {
      return const SizedBox.shrink();
    }

    final useCompact = _useCompactLayout ?? false;

    if (useCompact) {
      return _ServiceCenterCompactLayout(
        quoteText: LandingServiceCenterSection._quoteText,
        serviceTheme: serviceTheme,
        tiltPointerController: widget.tiltPointerController,
      );
    }

    return _ServiceCenterWideLayout(
      bodyText: LandingServiceCenterSection._bodyText,
      serviceTheme: serviceTheme,
      tiltPointerController: widget.tiltPointerController,
    );
  }
}

class _ServiceCenterWideLayout extends StatelessWidget {
  const _ServiceCenterWideLayout({
    required this.bodyText,
    required this.serviceTheme,
    this.tiltPointerController,
  });

  final String bodyText;
  final LandingServiceCenterTheme serviceTheme;
  final TiltGlobalPointerController? tiltPointerController;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: serviceTheme.sectionPadding,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: serviceTheme.maxContentWidth),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final isHorizontal =
                  constraints.maxWidth >= serviceTheme.compactBreakpoint;

              final textColumn = Expanded(
                flex: 3,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'MTL СЕРВИСНЫЙ ЦЕНТР',
                      style: serviceTheme.headingTextStyle,
                      textAlign: isHorizontal
                          ? TextAlign.left
                          : TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    _MarkdownText(text: bodyText),
                  ],
                ),
              );

              final resolvedRadius = serviceTheme.wideImageBorderRadius
                  .resolve(Directionality.of(context));
              final imageContent = AspectRatio(
                aspectRatio: 4 / 3,
                child: const _ServiceCenterImage(),
              );

              final image = Expanded(
                flex: 3,
                child: Padding(
                  padding: EdgeInsets.only(top: isHorizontal ? 0 : 24),
                  child: TiltWrapper(
                    borderRadius: resolvedRadius,
                    enableLight: false,
                    globalPointerMode: tiltPointerController != null,
                    globalPointerController: tiltPointerController,
                    invertGlobalPointer: true,
                    child: imageContent,
                  ),
                ),
              );

              if (isHorizontal) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [textColumn, const SizedBox(width: 40), image],
                );
              }

              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [textColumn, image],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _ServiceCenterCompactLayout extends StatelessWidget {
  const _ServiceCenterCompactLayout({
    required this.quoteText,
    required this.serviceTheme,
    this.tiltPointerController,
  });

  final String quoteText;
  final LandingServiceCenterTheme serviceTheme;
  final TiltGlobalPointerController? tiltPointerController;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: serviceTheme.sectionPadding,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: serviceTheme.maxContentWidth),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'MTL СЕРВИСНЫЙ ЦЕНТР',
                style: serviceTheme.headingTextStyle,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TiltWrapper(
                borderRadius:
                    serviceTheme.compactImageBorderRadius.resolve(
                  Directionality.of(context),
                ),
                enableLight: false,
                globalPointerMode: tiltPointerController != null,
                globalPointerController: tiltPointerController,
                invertGlobalPointer: true,
                child: AspectRatio(
                  aspectRatio: 4 / 3,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      const _ServiceCenterImage(),
                      Container(
                        decoration: BoxDecoration(
                          gradient: serviceTheme.compactOverlayGradient,
                        ),
                      ),
                      Align(
                        alignment: Alignment.bottomLeft,
                        child: Padding(
                          padding: serviceTheme.compactQuotePadding,
                          child: Text(
                            quoteText,
                            style: serviceTheme.quoteTextStyle,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ServiceCenterImage extends StatelessWidget {
  const _ServiceCenterImage();

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/service_center_hero.jpg',
      fit: BoxFit.cover,
    );
  }
}

/// Minimal markdown renderer that understands paragraphs and `>` quote blocks.
class _MarkdownText extends StatelessWidget {
  const _MarkdownText({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final paragraphs = text
        .trim()
        .split(RegExp(r'\n\s*\n'))
        .map((p) => p.trim())
        .where((p) => p.isNotEmpty)
        .toList();

    final widgets = <Widget>[];
    for (final paragraph in paragraphs) {
      if (paragraph.startsWith('>')) {
        widgets.add(
          _QuoteBlock(text: paragraph.replaceFirst(RegExp(r'^>\s*'), '')),
        );
      } else {
        widgets.add(_BodyParagraph(text: paragraph));
      }
      widgets.add(const SizedBox(height: 8));
    }
    if (widgets.isNotEmpty) {
      widgets.removeLast();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }
}

class _BodyParagraph extends StatelessWidget {
  const _BodyParagraph({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      textAlign: TextAlign.left,
      style: Theme.of(context).textTheme.bodySmall,
    );
  }
}

class _QuoteBlock extends StatelessWidget {
  const _QuoteBlock({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final baseStyle = Theme.of(context).textTheme.bodyMedium;
    const backgroundColor = AppThemeTokens.serviceQuoteBackground;
    const highlightColor = AppThemeTokens.serviceQuoteBorder;

    return Container(
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 4,
            margin: const EdgeInsets.only(right: 12),
            decoration: BoxDecoration(
              color: highlightColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(text, style: baseStyle),
            ),
          ),
        ],
      ),
    );
  }
}
