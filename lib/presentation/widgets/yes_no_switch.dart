import 'package:flutter/material.dart';
import 'package:flutter_switch/flutter_switch.dart';

class YesNoSwitch extends StatefulWidget {
  final String label;
  final bool value;
  final bool isEditing;
  final ValueChanged<bool>? onChanged;
  final Function(String, String)? copyToClipboard;

  const YesNoSwitch({
    super.key,
    required this.label,
    required this.value,
    required this.isEditing,
    this.onChanged,
    this.copyToClipboard,
  });

  @override
  State<YesNoSwitch> createState() => _YesNoSwitchState();
}

class _YesNoSwitchState extends State<YesNoSwitch> {
  late bool _currentValue;

  @override
  void initState() {
    super.initState();
    _currentValue = widget.value;
  }

  @override
  void didUpdateWidget(YesNoSwitch oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.value != _currentValue) {
      setState(() {
        _currentValue = widget.value;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    const switchWidth = 86.0;

    final switchWidget = FlutterSwitch(
      value: _currentValue,
      onToggle: (val) {
        if (widget.isEditing && widget.onChanged != null) {
          setState(() {
            _currentValue = val;
          });
          widget.onChanged!(val);
        }
      },
      activeText: 'Да',
      inactiveText: 'Нет',
      activeTextColor: theme.colorScheme.onPrimary,
      inactiveTextColor: theme.colorScheme.onSecondaryContainer,
      activeColor: theme.colorScheme.primary,
      inactiveColor: theme.colorScheme.secondaryContainer,
      valueFontSize: 12.0,
      width: 65,
      height: 35,
      borderRadius: 30.0,
      showOnOff: true,
      disabled: !widget.isEditing,
    );

    Widget buildSwitch(bool editable) {
      final content = editable
          ? switchWidget
          : GestureDetector(
              onTap: () {
                if (widget.copyToClipboard != null) {
                  widget.copyToClipboard!(
                    _currentValue ? 'Да' : 'Нет',
                    widget.label,
                  );
                }
              },
              child: switchWidget,
            );

      return SizedBox(
        width: switchWidth,
        child: Align(alignment: Alignment.centerRight, child: content),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Text(
            widget.label,
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
        ),
        const SizedBox(width: 12),
        buildSwitch(widget.isEditing),
      ],
    );
  }
}
