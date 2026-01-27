---
id: meeting_notetaker
name: Meeting Notetaker
category: productivity
status: available
ui_route: /agents/meeting-notetaker
agent_manager_id: <uuid-from-agent-manager>
---

# Meeting Notetaker Agent

## What It Does

Automatically joins your meetings, records conversations, and generates comprehensive notes with action items, decisions, and key discussion points. Never miss important details or spend time taking notes again.

The Meeting Notetaker acts as your personal assistant in every meeting, capturing everything discussed and organizing it into actionable insights.

## Best For

- **Team Meetings**: Standups, planning sessions, retrospectives
- **Client Calls**: Sales calls, discovery meetings, check-ins
- **Interviews**: Candidate interviews, user research
- **Brainstorming Sessions**: Capture all ideas and decisions
- **Training Sessions**: Document processes and learnings
- **Board Meetings**: Formal meeting minutes and records

## Requirements

### Required Inputs
1. **Meeting Information**:
   - Meeting link (Zoom, Google Meet, Teams, etc.)
   - Meeting time/schedule OR join immediately
   - Meeting title/purpose (optional but helpful)

### Optional Inputs
- Specific topics to focus on
- Custom note template
- Action item tracking preferences
- Participant names (for attribution)
- Language preference

## Output

### Meeting Notes Include

**1. Meeting Summary**
- Date, time, duration
- Participants
- Main topics discussed
- Overall outcome

**2. Key Discussion Points**
- Organized by topic
- Important quotes and statements
- Decisions made
- Questions raised

**3. Action Items**
- What needs to be done
- Who's responsible
- Due dates (if mentioned)
- Priority level

**4. Decisions Made**
- What was decided
- Rationale provided
- Who made the decision
- Any dissenting opinions

**5. Follow-up Items**
- Topics to revisit
- Questions to answer
- Information to gather
- Next meeting agenda items

### Delivery Formats
- Web dashboard (searchable, organized)
- Email summary
- Slack/Teams notification
- PDF export
- Integration with project management tools

## Use Cases

### Example Queries

**Schedule Regular Meeting:**
> "Join my daily standup every morning at 9 AM and take notes. Focus on blockers and progress updates."

**One-Time Meeting:**
> "Join my client call tomorrow at 2 PM. Here's the Zoom link. I need detailed notes on their requirements."

**Specific Focus:**
> "Take notes in my product planning meeting. Pay special attention to feature priorities and timeline decisions."

**Interview Recording:**
> "Join my candidate interview at 3 PM. Track their answers to technical questions and cultural fit."

**Brainstorming Session:**
> "Record our brainstorming session and organize all ideas by category. Capture who suggested what."

### Typical Workflow

1. **User schedules**: "Join my meeting at [time]" or "Join now"
2. **Agent joins**: Appears in meeting as "Meeting Notetaker"
3. **Agent records**: Captures audio and transcribes in real-time
4. **Agent processes**: Identifies key points, action items, decisions
5. **Agent delivers**: Notes available immediately after meeting ends

## When to Recommend

Recommend Meeting Notetaker when user mentions:
- "Need meeting notes"
- "Record this meeting"
- "Don't want to take notes"
- "Track action items"
- "Meeting minutes"
- "Capture decisions"
- "Interview recording"
- "Team standup"

## Features

### Real-Time Capabilities
- Live transcription during meeting
- Real-time action item detection
- Speaker identification
- Timestamp markers

### Post-Meeting
- Searchable transcript
- Topic segmentation
- Sentiment analysis
- Meeting insights and patterns

### Integrations
- Calendar sync (Google, Outlook)
- Slack/Teams notifications
- Project management (Asana, Jira, Trello)
- CRM systems (Salesforce, HubSpot)
- Note-taking apps (Notion, Evernote)

### Privacy & Security
- End-to-end encryption
- Automatic deletion options
- Access controls
- GDPR compliant
- Recording consent management

## Meeting Platforms Supported

- Zoom
- Google Meet
- Microsoft Teams
- Webex
- Slack Huddles
- Discord
- Custom video platforms (via browser)

## Pricing

- Per meeting OR monthly subscription
- Unlimited meetings (subscription)
- Unlimited storage
- Team plans available
- Enterprise features (custom integrations, SSO)

## Technical Details

- Processing time: Real-time + 1-2 minutes post-meeting
- Transcription accuracy: 95%+ (English)
- Languages supported: 50+ languages
- Max meeting length: Unlimited
- Storage: Unlimited (with subscription)
- Export formats: PDF, DOCX, TXT, JSON
