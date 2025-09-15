#  AIStylist Multi-Agent Web Interface

A comprehensive web interface for interacting with the AIStylist AI fashion recommendation system, providing real-time visibility into all agent thinking processes.

##  Quick Start

```bash
# Launch the web interface
python run_streamlit.py
```

The interface will open at: http://localhost:8501

## ✨ Features

### 💬 Interactive Chat
- Natural language conversation with ARI
- Conversation history and memory
- Example queries for quick testing

###  Multi-Agent Visibility
- **CypherBot**: See graph database queries in real-time
- **VibeBot**: Monitor semantic search processes  
- **Intelligence Systems**: View ML analysis outputs
- **Judge ARI**: Watch decision-making logic

### 🛍️ Product Display
- Beautiful product cards with details
- Image placeholders and pricing
- Category and metadata information

### 📊 Technical Insights
- Processing times and performance metrics
- Agent output history and debugging
- System status monitoring

##  Use Cases

### Fashion Queries
```
"I need a dress for a wedding"
"What should I wear to a job interview?"
"Show me casual outfits under $100"
"I need formal shoes for men"
```

### System Monitoring
- Watch how different agents contribute to responses
- Debug query processing issues
- Understand ML intelligence outputs
- Monitor system performance

##  Technical Details

### Architecture
- **Frontend**: Streamlit with custom CSS styling
- **Backend**: Enhanced ApplicationService with agent monitoring
- **Real-time Updates**: Agent output capture and display
- **Memory**: Session-based conversation history

### Agent Monitoring
The interface captures detailed outputs from:
- Intent detection and parameter extraction
- Graph database query generation and execution  
- Semantic search and embedding processes
- ML intelligence analysis (behavioral, visual, clustering)
- Final product selection and ranking decisions

### Data Flow
1. User enters query
2. System processes through all agents
3. Each agent's thinking is captured and displayed
4. Final response and products are shown
5. Full conversation history is maintained

##  Interface Layout

```
┌─────────────────────┬─────────────────────┐
│                     │                     │
│   Chat Interface    │   Agent Insights    │
│                     │                     │
│ - Input field       │ - CypherBot tab     │
│ - Response area     │ - VibeBot tab       │
│ - Product display   │ - Intelligence tab  │
│ - Example queries   │ - Judge tab         │
│                     │                     │
└─────────────────────┴─────────────────────┘
│              Conversation History           │
└─────────────────────────────────────────────┘
```

## 🐛 Debugging

### Common Issues
- **System not initializing**: Check .env file exists
- **No agent outputs**: Verify enhanced service is loaded
- **Connection errors**: Check Neo4j and Qdrant connectivity

### Logs
All agent outputs are captured and displayed in real-time within the interface tabs.

## 📈 Performance

The interface provides metrics on:
- Query processing time
- Number of products found
- Agent response times
- System resource usage