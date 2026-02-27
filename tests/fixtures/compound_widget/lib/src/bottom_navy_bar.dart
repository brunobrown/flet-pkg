import 'package:flutter/widgets.dart';

/// A beautiful bottom navigation bar with smooth animations.
class BottomNavyBar extends StatefulWidget {
  /// The list of navigation items.
  final List<BottomNavyBarItem> items;

  /// The currently selected index.
  final int selectedIndex;

  /// Called when an item is selected.
  final void Function(int index)? onItemSelected;

  /// The background color.
  final Color? backgroundColor;

  const BottomNavyBar({
    super.key,
    required this.items,
    this.selectedIndex = 0,
    this.onItemSelected,
    this.backgroundColor,
  });

  @override
  State<BottomNavyBar> createState() => _BottomNavyBarState();
}

class _BottomNavyBarState extends State<BottomNavyBar> {
  @override
  Widget build(BuildContext context) => Container();
}

/// A single navigation item for BottomNavyBar.
class BottomNavyBarItem {
  /// The icon for the item.
  final Widget icon;

  /// The title for the item.
  final String title;

  /// The active color for the item.
  final Color? activeColor;

  const BottomNavyBarItem({
    required this.icon,
    required this.title,
    this.activeColor,
  });
}
