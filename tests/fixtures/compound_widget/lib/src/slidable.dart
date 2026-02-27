import 'package:flutter/widgets.dart';

/// A widget that can be slid to reveal actions.
class Slidable extends StatefulWidget {
  /// The action pane displayed when sliding to the right.
  final ActionPane? startActionPane;

  /// The action pane displayed when sliding to the left.
  final ActionPane? endActionPane;

  /// The widget below this widget in the tree.
  final Widget child;

  /// Whether the slidable is enabled.
  final bool enabled;

  /// Whether to close when the nearest scrollable starts scrolling.
  final bool closeOnScroll;

  /// Called when an error occurs.
  final void Function(Object error)? onError;

  const Slidable({
    super.key,
    this.startActionPane,
    this.endActionPane,
    required this.child,
    this.enabled = true,
    this.closeOnScroll = true,
    this.onError,
  });

  @override
  State<Slidable> createState() => _SlidableState();
}

class _SlidableState extends State<Slidable> {
  @override
  Widget build(BuildContext context) => widget.child;
}

/// Represents a group of actions on one side of a Slidable.
class ActionPane {
  /// The extent ratio of the action pane.
  final double extentRatio;

  /// The motion widget for the action pane.
  final Widget? motion;

  /// The list of action widgets.
  final List<Widget> children;

  const ActionPane({
    this.extentRatio = 0.4,
    this.motion,
    this.children = const [],
  });
}
