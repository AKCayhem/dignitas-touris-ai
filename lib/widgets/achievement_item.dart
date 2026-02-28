import 'package:flutter/material.dart';

class AchievementItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  const AchievementItem({super.key, required this.icon, required this.title, required this.description});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: ListTile(
        leading: Icon(icon, color: Colors.blue, size: 32),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(description),
        trailing: const Icon(Icons.check_circle, color: Colors.green),
      ),
    );
  }
}