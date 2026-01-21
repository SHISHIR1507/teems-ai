# Agent Knowledge Base

## Overview

This directory contains specifications for all available agents in the Teems platform. Eve (Chief of Staff) uses these specs to understand agent capabilities and recommend the right agent for each task.

## Available Agents

### 1. UGC Creator
**Category**: Content Creation  
**Status**: Available  
**File**: `ugc_creator.md`

Creates authentic user-generated content (UGC) style videos for social media and marketing campaigns.

### 2. Fashion Photographer
**Category**: Content Creation  
**Status**: Available  
**File**: `fashion_photographer.md`

Generates professional studio-quality product photography with fashion and lifestyle aesthetics.

### 3. Meeting Notetaker
**Category**: Productivity  
**Status**: Available  
**File**: `meeting_notetaker.md`

Joins meetings automatically, records conversations, and generates comprehensive notes with action items.

### 4. Social Media Manager
**Category**: Marketing  
**Status**: Available  
**File**: `social_media_manager.md`

Manages social media posting across platforms with optimized captions, hashtags, and thumbnails.

## Agent Spec Format

Each agent specification includes:

### Metadata (Frontmatter)
```yaml
---
id: agent_id
name: Agent Name
category: content_creation | productivity | marketing
status: available | coming_soon | beta
ui_route: /agents/agent-id
---
```

### Content Sections
1. **What It Does** - Clear description of agent's purpose
2. **Best For** - Ideal use cases and scenarios
3. **Requirements** - What inputs/data the agent needs
4. **Output** - What the agent produces
5. **Use Cases** - Example queries and scenarios
6. **Pricing** (optional) - Cost structure if applicable

## How Eve Uses Agent Specs

### 1. Understanding Capabilities
Eve reads agent specs to understand what each agent can do and when to recommend them.

### 2. Matching User Needs
When users describe their needs, Eve matches requirements to agent capabilities:
- "I need product photos" → Fashion Photographer
- "Create social media content" → UGC Creator + Social Media Manager
- "Take notes in my meetings" → Meeting Notetaker

### 3. Providing Context
Eve explains what each agent does, what's required, and what output to expect.

### 4. Recommending Combinations
Eve can recommend multiple agents working together:
- UGC Creator + Social Media Manager (content creation + distribution)
- Fashion Photographer + Social Media Manager (product shots + posting)

## Future Integration

### Phase 1: Knowledge Base (Current)
- ✅ Agent specs in markdown
- ✅ Eve can read and recommend agents
- ✅ Clear descriptions and use cases

### Phase 2: MCP Tool (Future)
```python
# MCP tool: add_agent_to_team
def add_agent_to_team(agent_id: str, team_id: str):
    """Provision agent and return UI route"""
    return {
        "agent_id": agent_id,
        "ui_route": f"/agents/{agent_id}",
        "status": "provisioned"
    }
```

### Phase 3: Agent Management (Future)
- Agent configuration UI
- Usage tracking and analytics
- Team collaboration features
- Agent customization

## Adding New Agents

To add a new agent:

1. Create `resources/agents/new_agent.md`
2. Follow the spec format with frontmatter
3. Include all required sections
4. Update this README
5. Restart server for Eve to learn about it

## Agent Categories

### Content Creation
Agents that create visual or video content:
- UGC Creator
- Fashion Photographer

### Productivity
Agents that improve workflow efficiency:
- Meeting Notetaker

### Marketing
Agents that handle marketing and distribution:
- Social Media Manager

### Future Categories
- Analytics & Insights
- Customer Support
- Sales & Outreach
- Design & Branding
