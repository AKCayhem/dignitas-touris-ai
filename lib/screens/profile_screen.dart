import 'package:flutter/material.dart';
import '../widgets/stat_card.dart';
import '../widgets/achievement_item.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CivicEye', style: TextStyle(fontWeight: FontWeight.bold)),
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(30),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: EdgeInsets.only(left: 16.0, bottom: 8.0),
              child: Text('Community Watch', style: TextStyle(fontSize: 16)),
            ),
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const CircleAvatar(
            radius: 40,
            backgroundColor: Colors.blue,
            child: Text('JD', style: TextStyle(fontSize: 30, color: Colors.white)),
          ),
          const SizedBox(height: 12),
          const Text('Jane Doe', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const Text('jane@example.com', style: TextStyle(color: Colors.grey)),
          Container(
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.blue[100],
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text('Admin', style: TextStyle(fontSize: 12)),
          ),
          const SizedBox(height: 24),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: const [
              StatCard(label: 'Reports', value: '0'),
              StatCard(label: 'Votes', value: '3'),
              StatCard(label: 'Resolved', value: '0'),
            ],
          ),
          const SizedBox(height: 32),

          const Text('Achievements', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          const AchievementItem(
            icon: Icons.assignment,
            title: 'First Reporter',
            description: 'Created your first report',
          ),
          const AchievementItem(
            icon: Icons.how_to_vote,
            title: 'Active Voter',
            description: 'Voted on 10 issues',
          ),
          const AchievementItem(
            icon: Icons.change_circle,
            title: 'Change Maker',
            description: 'Had 1 issue resolved',
          ),
        ],
      ),
    );
  }
}