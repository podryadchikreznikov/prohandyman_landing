part of 'landing_home_header.dart';

class _LandingHeaderShell extends StatelessWidget {
  const _LandingHeaderShell({
    required this.backgroundColor,
    required this.foregroundColor,
    required this.headerTheme,
    required this.headerBody,
    required this.navWidget,
  });

  final Color backgroundColor;
  final Color foregroundColor;
  final LandingHeaderTheme headerTheme;
  final Widget headerBody;
  final Widget navWidget;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: IconTheme(
        data: IconThemeData(color: foregroundColor),
        child: DefaultTextStyle.merge(
          style: TextStyle(color: foregroundColor),
          child: SafeArea(
            bottom: false,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(
                  maxWidth: AppThemeTokens.contentMaxWidth,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DecoratedBox(
                      decoration: BoxDecoration(
                        color: backgroundColor,
                        borderRadius: BorderRadius.circular(
                          AppThemeTokens.appBarRadius,
                        ),
                      ),
                      child: headerBody,
                    ),
                    Container(
                      width: double.infinity,
                      height: headerTheme.navBarHeight,
                      color: headerTheme.navBackgroundColor,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: navWidget,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _LandingHeaderBody extends StatelessWidget {
  const _LandingHeaderBody({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        width: double.infinity,
        constraints: BoxConstraints(maxWidth: AppThemeTokens.contentMaxWidth),
        color: theme.headerBackgroundColor,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final containerWidth = constraints.maxWidth;
            final horizontalPadding = theme.titleSpacing
                .clamp(0.0, containerWidth / 4)
                .toDouble();

            return Container(
              width: containerWidth,
              padding: EdgeInsets.symmetric(
                horizontal: horizontalPadding,
                vertical: 16,
              ),
              child: _HeaderContent(theme: theme),
            );
          },
        ),
      ),
    );
  }
}

class _HeaderContent extends StatelessWidget {
  const _HeaderContent({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final bool shouldWrap = constraints.maxWidth < 900;
        final company = _CompanyHeader(theme: theme, compact: shouldWrap);
        final contacts = shouldWrap
            ? _CompactContactWrap(theme: theme)
            : _HeaderInfoWrap(theme: theme);

        if (shouldWrap) {
          return Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Center(child: company),
              const SizedBox(height: 16),
              Center(child: contacts),
            ],
          );
        }

        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Flexible(child: company),
            Flexible(child: contacts),
          ],
        );
      },
    );
  }
}

class _CompanyHeader extends StatelessWidget {
  const _CompanyHeader({required this.theme, required this.compact});

  final LandingHeaderTheme theme;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final maxLogoHeight = compact
        ? 56.0
        : (AppThemeTokens.landingHeaderHeight - 32);

    final logoWidget = SizedBox(
      height: maxLogoHeight,
      child: AspectRatio(
        aspectRatio: theme.logoAspectRatio,
        child: Image.asset(
          'assets/prohandyman-logo-png.png',
          fit: BoxFit.contain,
        ),
      ),
    );

    final textWidget = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            'MTL сервис бытовой техники',
            style: compact
                ? theme.titleTextStyle.copyWith(
                    fontSize: (theme.titleTextStyle.fontSize ?? 20) * 0.9,
                  )
                : theme.titleTextStyle,
          ),
        ),
        const SizedBox(height: 4),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            'С 2008 года ремонтируем брендовые устройства',
            style: compact
                ? theme.subtitleTextStyle.copyWith(
                    fontSize: (theme.subtitleTextStyle.fontSize ?? 14) * 0.9,
                  )
                : theme.subtitleTextStyle,
          ),
        ),
      ],
    );

    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        logoWidget,
        SizedBox(width: compact ? theme.logoGap / 2 : theme.logoGap),
        Flexible(child: textWidget),
      ],
    );
  }
}

class _HeaderInfoWrap extends StatelessWidget {
  const _HeaderInfoWrap({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppThemeTokens.headerColumnsGap,
      runSpacing: 12,
      alignment: WrapAlignment.start,
      crossAxisAlignment: WrapCrossAlignment.start,
      children: [
        IntrinsicWidth(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _AppBarInfoBlock(
                icon: Icons.schedule_outlined,
                title: _headerInfoItems[0].$2,
                theme: theme,
              ),
              const SizedBox(height: 4),
              _AppBarInfoBlock(
                icon: Icons.mail_outline,
                title: _headerInfoItems[1].$2,
                theme: theme,
              ),
            ],
          ),
        ),
        IntrinsicWidth(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _AppBarInfoBlock(
                icon: Icons.phone_in_talk_outlined,
                title: _headerInfoItems[2].$2,
                theme: theme,
              ),
              const SizedBox(height: 4),
              _AppBarInfoBlock(
                icon: Icons.phone_in_talk_outlined,
                title: _headerInfoItems[3].$2,
                theme: theme,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CompactContactWrap extends StatelessWidget {
  const _CompactContactWrap({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 16,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final (icon, text) in _headerInfoItems)
          _AppBarInfoBlock(icon: icon, title: text, theme: theme),
      ],
    );
  }
}

class _AppBarInfoBlock extends StatelessWidget {
  const _AppBarInfoBlock({
    required this.icon,
    required this.title,
    required this.theme,
  });

  final IconData icon;
  final String title;
  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: theme.infoPadding,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(icon, color: theme.headerInfoIconColor, size: 20),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              title,
              style: theme.headerInfoTextStyle,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

class _NavBar extends StatelessWidget {
  const _NavBar({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: theme.navBarHeight,
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: EdgeInsets.symmetric(horizontal: theme.titleSpacing),
              child: Row(
                children: [
                  for (final label in _navItems) ...[
                    Padding(
                      padding: theme.navItemPadding,
                      child: InkWell(
                        onTap: () {},
                        borderRadius: BorderRadius.circular(4),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          child: label == 'Услуги'
                              ? Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(label, style: theme.navItemTextStyle),
                                    const SizedBox(width: 4),
                                    Icon(
                                      Icons.arrow_drop_down,
                                      color: theme.navItemTextStyle.color,
                                      size: 20,
                                    ),
                                  ],
                                )
                              : Text(label, style: theme.navItemTextStyle),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: OutlinedButton(
              onPressed: () {},
              style: theme.navCallToActionStyle,
              child: Text(
                'ЗАКАЗАТЬ ЗВОНОК',
                style: theme.navCallToActionTextStyle,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactNavigationMenu extends StatelessWidget {
  const _CompactNavigationMenu({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    final navBackground = theme.navBackgroundColor;
    final navBrightness = ThemeData.estimateBrightnessForColor(navBackground);
    final fallbackColor = navBrightness == Brightness.dark
        ? Colors.white
        : Theme.of(context).colorScheme.onSurface;
    final menuTextColor = navBrightness == Brightness.light
        ? fallbackColor
        : (theme.navItemTextStyle.color ?? fallbackColor);
    final baseTextStyle = theme.navItemTextStyle.copyWith(color: menuTextColor);
    final borderColor = menuTextColor.withOpacity(0.6);
    final popupBackgroundColor = Theme.of(context).colorScheme.primary;
    final popupTextStyle =
        theme.navItemTextStyle.copyWith(color: Colors.white);

    final popupButton = Theme(
      data: Theme.of(context).copyWith(
        popupMenuTheme: PopupMenuThemeData(
          color: popupBackgroundColor,
          textStyle: popupTextStyle,
        ),
      ),
      child: PopupMenuButton<String>(
        tooltip: '\u041c\u0435\u043d\u044e',
        onSelected: (_) {},
        position: PopupMenuPosition.under,
        itemBuilder: (context) => [
          for (final label in _navItems)
            PopupMenuItem<String>(
              value: label,
              child: Text(label, style: popupTextStyle),
            ),
        ],
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppThemeTokens.appBarRadius),
            border: Border.all(color: borderColor),
            color: Colors.transparent,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('\u041c\u0435\u043d\u044e', style: baseTextStyle),
              const SizedBox(width: 4),
              Icon(
                Icons.arrow_drop_down,
                color: baseTextStyle.color,
              ),
            ],
          ),
        ),
      ),
    );

    final callToAction = SizedBox(
      height: double.infinity,
      child: OutlinedButton(
        onPressed: () {},
        style: theme.navCallToActionStyle,
        child: Text(
          '\u0417\u0430\u043a\u0430\u0437\u0430\u0442\u044c \u0437\u0432\u043e\u043d\u043e\u043a',
          style: theme.navCallToActionTextStyle,
          textAlign: TextAlign.center,
        ),
      ),
    );

    return Padding(
      padding: EdgeInsets.symmetric(horizontal: theme.titleSpacing),
      child: Row(
        children: [
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: popupButton,
            ),
          ),
          const SizedBox(width: 12),
          Flexible(
            child: Align(
              alignment: Alignment.centerRight,
              child: callToAction,
            ),
          ),
        ],
      ),
    );
  }
}

const _navItems = <String>[
  '\u0413\u043b\u0430\u0432\u043d\u0430\u044f',
  '\u0423\u0441\u043b\u0443\u0433\u0438',
  '\u0426\u0435\u043d\u044b',
  '\u041d\u043e\u0432\u043e\u0441\u0442\u0438',
  '\u041e \u043a\u043e\u043c\u043f\u0430\u043d\u0438\u0438',
  '\u041a\u043e\u043d\u0442\u0430\u043a\u0442\u044b',
];

const _headerInfoItems = <(IconData, String)>[
  (Icons.schedule_outlined, 'Пн-Вс: с 08:00 до 20:00'),
  (Icons.mail_outline, 'info@MTL-servis.ru'),
  (Icons.phone_in_talk_outlined, '+7 (999) 497-85-32'),
  (Icons.phone_in_talk_outlined, '+7 (343) 521-55-09'),
];
