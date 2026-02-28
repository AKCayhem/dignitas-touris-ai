import 'package:flutter/material.dart';

class AdminScreen extends StatelessWidget {
  AdminScreen({super.key});

  final List<Map<String, dynamic>> priorityIssues = const [
    {'rank': 1, 'title': 'Abandoned Building - Safety Hazard', 'votes': 203},
    {'rank': 2, 'title': 'Dangerous Pothole on Main Street', 'votes': 127},
    {'rank': 3, 'title': 'Overflowing Garbage Bins on Park Avenue', 'votes': 89},
    {'rank': 4, 'title': 'Broken Street Light - Dark Corner', 'votes': 45},
    {'rank': 5, 'title': 'Graffiti Vandalism on Public Wall', 'votes': 23},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Panel', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text(
              'Priority Issues',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
            ),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16.0),
            child: Text('Most urgent problems in our community'),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: ListView.separated(
              itemCount: priorityIssues.length,
              separatorBuilder: (context, index) => const Divider(),
              itemBuilder: (context, index) {
                final issue = priorityIssues[index];
                return ListTile(
                  leading: CircleAvatar(
                    child: Text('#${issue['rank']}'),
                  ),
                  title: Text(issue['title']),
                  trailing: Text('${issue['votes']} votes'),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: ElevatedButton(
              onPressed: () {},
              style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 45)),
              child: const Text('Admin Dashboard'),
            ),
          ),
        ],
      ),
    );
  }
}