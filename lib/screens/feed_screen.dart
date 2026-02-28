import 'package:flutter/material.dart';
import '../models/report.dart';

class FeedScreen extends StatelessWidget {
  FeedScreen({super.key});

  final List<Report> reports = [
    Report(
      status: 'Sent to Municipality',
      category: 'Dangerous Building',
      title: 'Abandoned Building - Safety Hazard',
      description: 'Old building with broken windows and structural damage. Kids have been seen playing inside',
      location: '145 West Street',
      time: '13 days ago',
      votes: 203,
    ),
    Report(
      status: 'Urgent',
      category: 'Road Hazard',
      title: 'Dangerous Pothole on Main Street',
      description: 'Large pothole causing damage to vehicles',
      location: 'Main Street & 5th Ave',
      time: '5 days ago',
      votes: 127,
    ),
    Report(
      status: 'Pending',
      category: 'Sanitation',
      title: 'Overflowing Garbage Bins',
      description: 'Bins are overflowing and attracting pests',
      location: 'Park Avenue',
      time: '2 days ago',
      votes: 89,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CivicEye', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          TextButton.icon(
            onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Filter pressed (demo)')),
            ),
            icon: const Icon(Icons.filter_list),
            label: const Text('Show Filters'),
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              'Community Reports (${reports.length})',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: reports.length,
              itemBuilder: (context, index) {
                final report = reports[index];
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Chip(
                          label: Text(report.status),
                          backgroundColor: Colors.blue[50],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          report.category,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                        Text(
                          report.title,
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 4),
                        Text(report.description),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.location_on, size: 16, color: Colors.grey[600]),
                            const SizedBox(width: 4),
                            Text(report.location),
                            const Spacer(),
                            Icon(Icons.access_time, size: 16, color: Colors.grey[600]),
                            const SizedBox(width: 4),
                            Text(report.time),
                          ],
                        ),
                        const Divider(height: 24),
                        Row(
                          children: [
                            Icon(Icons.thumb_up, size: 20, color: Colors.blue),
                            const SizedBox(width: 4),
                            Text('${report.votes} votes'),
                            const Spacer(),
                            TextButton(
                              onPressed: () {},
                              child: const Text('Vote'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

