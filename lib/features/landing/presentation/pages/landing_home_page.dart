import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

/// Placeholder for the future landing home screen.
@RoutePage()
class LandingHomePage extends StatelessWidget {
  const LandingHomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final headerTheme = theme.extension<LandingHeaderTheme>();
    assert(
      headerTheme != null,
      'LandingHeaderTheme must be provided via AppTheme extensions.',
    );
    if (headerTheme == null) {
      return const SizedBox.shrink();
    }
    final appBarBackgroundColor = headerTheme.headerBackgroundColor;
    final appBarForegroundColor =
        headerTheme.headerInfoTextStyle.color ??
        theme.appBarTheme.foregroundColor ??
        theme.colorScheme.onSurface;

    return DecoratedBox(
      decoration: const BoxDecoration(
        image: DecorationImage(
          repeat: ImageRepeat.repeat,
          alignment: Alignment.topLeft,
          image: AssetImage('assets/pattern.png'),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: AppThemeTokens.pageTopPadding),
        child: Scaffold(
          backgroundColor: Colors.transparent,
          extendBodyBehindAppBar: true,
          appBar: AppBar(
            backgroundColor: appBarBackgroundColor,
            foregroundColor: appBarForegroundColor,
            toolbarHeight: AppThemeTokens.landingHeaderHeight,
            flexibleSpace: SafeArea(
              child: Stack(
                alignment: Alignment.center,
                children: [
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final availableHeight = constraints.maxHeight;
                      return ConstrainedBox(
                        constraints: const BoxConstraints(
                          maxWidth: AppThemeTokens.contentMaxWidth,
                        ),
                        child: Padding(
                          padding: EdgeInsets.only(
                            bottom:
                                Size.fromHeight(
                                  headerTheme.navBarHeight,
                                ).height +
                                16,
                            top: 16,
                            left: headerTheme.titleSpacing,
                            right: headerTheme.titleSpacing,
                          ),
                          child: SizedBox(
                            height: availableHeight,
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.center,
                              children: [
                                _CompanyHeader(theme: headerTheme),
                                const Spacer(),
                                _HeaderInfoWrap(theme: headerTheme),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
            bottom: PreferredSize(
              preferredSize: Size.fromHeight(headerTheme.navBarHeight),
              child: Material(
                color: headerTheme.navBackgroundColor,
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: AppThemeTokens.contentMaxWidth,
                    ),
                    child: _NavBar(theme: headerTheme),
                  ),
                ),
              ),
            ),
          ),
          body: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppThemeTokens.contentMaxWidth,
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'Landing content заглушка.\nЗдесь будет главная страница.',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CompanyHeader extends StatelessWidget {
  const _CompanyHeader({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        AspectRatio(
          aspectRatio: theme.logoAspectRatio,
          child: FittedBox(
            fit: BoxFit.contain,
            alignment: Alignment.centerLeft,
            child: Image.asset('assets/prohandyman-logo-png.png'),
          ),
        ),
        SizedBox(width: theme.logoGap),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('MTL СЕРВИСНЫЙ ЦЕНТР', style: theme.titleTextStyle),
            Text(
              'У ВАС ЕСТЬ ВОПРОСЫ. У НАС ЕСТЬ ОТВЕТЫ',
              style: theme.subtitleTextStyle,
            ),
          ],
        ),
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
          Icon(icon, color: theme.headerInfoIconColor),
          const SizedBox(width: 8),
          Text(title, style: theme.headerInfoTextStyle),
        ],
      ),
    );
  }
}

// (Header CTA moved to nav bar; widget removed.)

class _NavBar extends StatelessWidget {
  const _NavBar({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    final items = [
      'Главная',
      'Услуги',
      'Цены',
      'Отзывы',
      'О компании',
      'Контакты',
    ];

    return SizedBox(
      height: theme.navBarHeight,
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final label in items) ...[
                    Padding(
                      padding: theme.navItemPadding,
                      child: label == 'Услуги'
                          ? Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(label, style: theme.navItemTextStyle),
                                const SizedBox(width: 4),
                                Icon(
                                  Icons.arrow_drop_down,
                                  color: theme.navItemTextStyle.color,
                                ),
                              ],
                            )
                          : Text(label, style: theme.navItemTextStyle),
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

class _HeaderInfoWrap extends StatelessWidget {
  const _HeaderInfoWrap({required this.theme});

  final LandingHeaderTheme theme;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AppBarInfoBlock(
              icon: Icons.schedule_outlined,
              title: 'Пн-Вс: с 08:00 до 20:00',
              theme: theme,
            ),
            const SizedBox(height: 4),
            _AppBarInfoBlock(
              icon: Icons.mail_outline,
              title: 'info@MTL-servis.ru',
              theme: theme,
            ),
          ],
        ),
        const SizedBox(width: AppThemeTokens.headerColumnsGap),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AppBarInfoBlock(
              icon: Icons.phone_in_talk_outlined,
              title: '+7 (999) 497-85-32',
              theme: theme,
            ),
            const SizedBox(height: 4),
            _AppBarInfoBlock(
              icon: Icons.phone_in_talk_outlined,
              title: '+7 (343) 521-55-09',
              theme: theme,
            ),
          ],
        ),
      ],
    );
  }
}
