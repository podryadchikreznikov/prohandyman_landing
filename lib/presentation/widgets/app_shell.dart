import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/router.dart';

typedef AppShellActionHandler = void Function(BuildContext context);

/// Metadata describing a single action icon displayed in the shell app bar.
class AppShellAction {
  const AppShellAction({
    required this.icon,
    required this.tooltip,
    this.onPressed,
    this.widget,
  });

  final IconData icon;
  final String tooltip;
  final AppShellActionHandler? onPressed;
  final Widget? widget;

  Widget build(BuildContext context) {
    if (widget != null) {
      return widget!;
    }
    return IconButton(
      icon: Icon(icon),
      tooltip: tooltip,
      onPressed: onPressed != null ? () => onPressed!(context) : null,
    );
  }
}

/// Common scaffold wrapper for all application pages.
class AppShell extends StatelessWidget {
  const AppShell({
    super.key,
    required this.title,
    required this.body,
    this.nestingLevel = 0,
    this.showBackButton,
    this.showDefaultActions = true,
    this.defaultActionsVisibilityDepth = 1,
    this.defaultActionsOverride,
    this.actions = const [],
    this.backgroundColor,
    this.bodyPadding,
    this.floatingActionButton,
    this.bottomNavigationBar,
    this.bottomSheet,
  });

  final String title;
  final Widget body;
  final int nestingLevel;
  final bool? showBackButton;
  final bool showDefaultActions;
  final int defaultActionsVisibilityDepth;
  final List<AppShellAction>? defaultActionsOverride;
  final List<AppShellAction> actions;
  final Color? backgroundColor;
  final EdgeInsetsGeometry? bodyPadding;
  final Widget? floatingActionButton;
  final Widget? bottomNavigationBar;
  final Widget? bottomSheet;

  static final List<AppShellAction> _defaultActions = [
    AppShellAction(
      icon: Icons.settings_outlined,
      tooltip: 'Настройки',
      onPressed: (context) {
        context.router.push(const LandingHomeRoute());
      },
    ),
  ];

  bool _shouldShowDefaultActions() {
    if (!showDefaultActions) return false;
    return nestingLevel <= defaultActionsVisibilityDepth;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canNavigateBack = context.router.canPop();
    final bool wantsBackButton = showBackButton ?? nestingLevel > 0;

    Widget? leading;
    if (wantsBackButton) {
      leading = IconButton(
        icon: Icon(canNavigateBack ? Icons.arrow_back : Icons.home_outlined),
        tooltip: canNavigateBack ? 'Назад' : 'Домой',
        onPressed: () {
          if (canNavigateBack) {
            context.router.maybePop();
          } else {
            context.router.replaceAll([const LandingHomeRoute()]);
          }
        },
      );
    }

    final actionsToRender = <Widget>[
      if (_shouldShowDefaultActions())
        ...(defaultActionsOverride ?? _defaultActions).map(
          (action) => action.build(context),
        ),
      ...actions.map((action) => action.build(context)),
    ];

    Widget bodyContent = body;
    if (bodyPadding != null) {
      bodyContent = Padding(padding: bodyPadding!, child: bodyContent);
    }

    return Scaffold(
      backgroundColor: backgroundColor ?? theme.colorScheme.surface,
      appBar: AppBar(
        title: Text(title),
        leading: leading,
        actions: actionsToRender,
      ),
      body: bodyContent,
      floatingActionButton: floatingActionButton,
      bottomNavigationBar: bottomNavigationBar,
      bottomSheet: bottomSheet,
    );
  }
}
