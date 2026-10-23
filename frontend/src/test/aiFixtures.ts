import type { ScanAIAnalysisResponse } from '@/api/scans'
import { criticalFinding } from '@/test/mswHandlers'

export const readyAnalysis = {
  scan_id: criticalFinding.scan_id,
  analysis_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  provider: 'openai',
  model: 'gpt-6-luna',
  language: 'en',
  context_version: '6',
  prompt_version: '11',
  created_at: '2026-10-23T12:00:00Z',
  updated_at: '2026-10-23T12:01:00Z',
  completed_at: '2026-10-23T12:01:00Z',
  status: 'completed',
  analysis: {
    summary: 'The camera needs a software update.',
    tasks: [
      {
        rank: 1,
        priority: 'immediate',
        title: 'Update the camera software',
        who: 'it_person',
        time: '30_minutes',
        steps: [
          'Get the update from the vendor.',
          'Install it from the settings page.',
        ],
        fallback: 'Unplug it until you can update.',
        fixes_fully: true,
        finding_ids: [criticalFinding.finding_id],
        highest_risk_score: 91,
        sources: [
          {
            name: 'Vendor advisory',
            url: 'https://vendor.example.com/advisory',
          },
        ],
      },
    ],
    findings: [
      {
        finding_id: criticalFinding.finding_id,
        plain_title: 'Someone could control this camera',
        cause: 'It runs old software.',
        what_could_happen: 'Someone could watch its video.',
        task_rank: 1,
      },
    ],
    not_checked: 'Passwords were not checked.',
  },
} satisfies ScanAIAnalysisResponse
