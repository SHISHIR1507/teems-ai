---
id: presentation_agent
name: Presentation Agent
category: productivity
status: available
ui_route: /agents/presentation-agent
agent_manager_id: <uuid-from-agent-manager>
---

# Presentation Agent

## What It Does

Creates, edits, and manages professional PowerPoint presentations using natural language. Transforms your ideas, documents, or requirements into polished, branded presentations ready for meetings, pitches, or sharing.

The Presentation Agent uses a multi-agent system with specialized agents for generation, editing, and brand management, ensuring high-quality output that matches your brand guidelines.

## Best For

- **Business Presentations**: Pitch decks, quarterly reviews, strategy presentations
- **Educational Content**: Course materials, training slides, workshops
- **Sales & Marketing**: Product launches, client proposals, campaign overviews
- **Internal Communications**: Team updates, project status, company all-hands
- **Document-to-Slide Conversion**: Transform PDFs, Word docs, or research into presentations
- **Branded Presentations**: Consistent visual identity across all slides
- **Quick Presentations**: Fast turnaround for urgent meeting needs

## Requirements

### Required Inputs
1. **Content Source** (choose one):
   - Text description of presentation topic
   - Uploaded document (PDF, Word, etc.)
   - Existing presentation to edit

2. **Basic Information**:
   - Topic or subject matter
   - Target audience (optional but recommended)
   - Presentation purpose (optional but recommended)

### Optional Inputs
- **Slide Count**: Number of slides desired
- **Tone**: Professional, casual, technical, creative
- **Template**: Choose from available templates
- **Brand Guidelines**:
  - Logo URL
  - Primary color
  - Secondary color
  - Font preferences
- **Specific Sections**: Outline or structure preferences
- **Visual Style**: Minimalist, modern, corporate, creative

## Output

### Presentation Deliverables
- **Format**: PowerPoint (.pptx)
- **Quality**: Professional, production-ready
- **Branding**: Customizable logos, colors, fonts
- **Structure**: Well-organized with clear sections
- **Download**: Direct download link or presigned S3 URL

### Includes
- **Content Generation**: AI-generated slide content based on your input
- **Visual Design**: Professional layouts and formatting
- **Brand Consistency**: Applies your brand guidelines automatically
- **Multiple Variations**: Can generate different versions
- **Edit Capability**: Modify existing presentations
- **Template Support**: Use pre-designed templates or create custom

## Use Cases

### Example Queries

**Basic Presentation:**
> "Create a 10-slide presentation about quantum computing with a professional tone"

**From Document:**
> "Convert this research paper into a 15-slide presentation for a conference"

**Branded Presentation:**
> "Generate a pitch deck for our new product launch. Use our brand colors and logo."

**Specific Structure:**
> "Create a quarterly business review presentation with sections for: overview, achievements, challenges, and next quarter goals"

**Edit Existing:**
> "Add 3 slides about our new product features to this presentation"

**Quick Meeting Prep:**
> "I need a 5-slide presentation about our Q4 results for tomorrow's meeting"

### Typical Workflow

1. **User provides**: Topic description OR uploads document
2. **Agent asks**: "How many slides? What's the audience? Any specific sections?"
3. **Agent generates**: Presentation using SlideSpeak API
4. **User reviews**: Can request edits or regenerate
5. **Agent delivers**: Final presentation ready for download

## When to Recommend

Recommend Presentation Agent when user mentions:
- "Create a presentation"
- "Make slides"
- "PowerPoint"
- "Pitch deck"
- "Convert document to slides"
- "Presentation for meeting"
- "Branded presentation"
- "Edit my presentation"
- "Need slides about [topic]"

## Works Well With

- **Social Media Manager**: Create presentation → Extract key slides for social posts
- **Meeting Notetaker**: Generate presentation → Use in meeting → Get notes
- **Fashion Photographer**: Product photos → Include in presentation slides

## Features

### Generation Capabilities
- **From Text**: Natural language descriptions → Full presentation
- **From Documents**: PDF, Word docs → Structured slides
- **Slide-by-Slide**: Generate one slide at a time with control
- **Template-Based**: Use professional templates
- **Custom Structure**: Define your own outline

### Editing Capabilities
- **Add Slides**: Insert new content
- **Edit Slides**: Modify existing slides
- **Reorder**: Rearrange slide order
- **Update Content**: Change text, sections, or structure
- **Brand Updates**: Apply new brand guidelines

### Brand Management
- **Logo Integration**: Add logos to slides
- **Color Schemes**: Apply brand colors consistently
- **Font Customization**: Match brand typography
- **Style Consistency**: Maintain visual identity

### Document Processing
- **PDF Upload**: Extract content from PDFs
- **Word Document**: Process .docx files
- **Text Extraction**: Intelligent content parsing
- **Structure Detection**: Identify headings, sections, key points

### Template System
- **Pre-built Templates**: Professional designs ready to use
- **Branded Templates**: Templates with your brand applied
- **Custom Templates**: Create and save your own
- **Template Preview**: See templates before using

## Platform Integration

### SlideSpeak API
- Full integration with SlideSpeak presentation generation
- Async task processing with webhook notifications
- Real-time status updates
- Credit management and tracking

### Storage
- **S3 Integration**: All presentations stored in S3
- **Download Links**: Presigned URLs for secure access
- **Version History**: Track presentation versions
- **Conversation Tracking**: Link presentations to conversations

## Technical Details

- **Processing Time**: 30 seconds - 2 minutes per presentation
- **Max Slides**: Up to 50 slides per presentation
- **Supported Formats**: .pptx (PowerPoint)
- **Document Formats**: PDF, .docx, .txt
- **API Integration**: SlideSpeak API
- **Async Processing**: Webhook-based task completion
- **Brand Assets**: Logo, colors, fonts stored per tenant
- **Template Library**: 20+ professional templates

## Pricing

- Per presentation generation
- Edit operations included
- Document processing included
- Template usage included
- Bulk generation packages available

## Limitations

- English language only (for now)
- Maximum 50 slides per presentation
- Requires SlideSpeak API credits
- Document processing may take longer for large files
