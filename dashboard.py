#!/usr/bin/env python3
"""
Hermes Agent Dashboard
A web dashboard showing agent components and their relationships with an interactive mind map.
"""
import json
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Agent/Component definitions with descriptions
AGENTS = [
    {
        "id": "aiagent",
        "name": "AIAgent",
        "category": "Core",
        "description": "The main agent loop class that orchestrates conversations. Handles message passing, tool calling, and response generation.",
        "file": "run_agent.py",
        "color": "#FFD700"
    },
    {
        "id": "model_tools",
        "name": "Model Tools",
        "category": "Core",
        "description": "Tool orchestration system that discovers tools, handles function calls, and manages tool schemas.",
        "file": "model_tools.py",
        "color": "#FFA500"
    },
    {
        "id": "toolsets",
        "name": "Toolsets",
        "category": "Core",
        "description": "Tool grouping system that organizes tools into categories like 'web', 'terminal', 'browser', etc.",
        "file": "toolsets.py",
        "color": "#FF6347"
    },
    {
        "id": "cli",
        "name": "HermesCLI",
        "category": "Interface",
        "description": "Interactive command-line interface with Rich UI, autocomplete, and slash commands.",
        "file": "cli.py",
        "color": "#4169E1"
    },
    {
        "id": "gateway",
        "name": "Messaging Gateway",
        "category": "Interface",
        "description": "Cross-platform messaging system supporting Telegram, Discord, Slack, WhatsApp, Signal, and Home Assistant.",
        "file": "gateway/run.py",
        "color": "#9370DB"
    },
    {
        "id": "terminal_tool",
        "name": "Terminal Tool",
        "category": "Tool",
        "description": "Execute shell commands in various environments: local, Docker, SSH, Modal, Daytona, Singularity.",
        "file": "tools/terminal_tool.py",
        "color": "#32CD32"
    },
    {
        "id": "file_tools",
        "name": "File Tools",
        "category": "Tool",
        "description": "File manipulation tools: read_file, write_file, patch (with fuzzy matching), and search.",
        "file": "tools/file_tools.py",
        "color": "#20B2AA"
    },
    {
        "id": "web_tools",
        "name": "Web Tools",
        "category": "Tool",
        "description": "Web search and content extraction using Parallel, Firecrawl, and other providers.",
        "file": "tools/web_tools.py",
        "color": "#1E90FF"
    },
    {
        "id": "browser_tool",
        "name": "Browser Automation",
        "category": "Tool",
        "description": "Browser automation via Browserbase: navigate, click, type, scroll, snapshot, vision analysis.",
        "file": "tools/browser_tool.py",
        "color": "#FF1493"
    },
    {
        "id": "vision_tools",
        "name": "Vision Tools",
        "category": "Tool",
        "description": "Image analysis and understanding using vision-capable models.",
        "file": "tools/vision_tools.py",
        "color": "#8B008B"
    },
    {
        "id": "tts_tool",
        "name": "Text-to-Speech",
        "category": "Tool",
        "description": "Convert text to audio using Edge TTS (free), ElevenLabs, or OpenAI.",
        "file": "tools/tts_tool.py",
        "color": "#FF8C00"
    },
    {
        "id": "skills_tool",
        "name": "Skills System",
        "category": "Memory",
        "description": "System for creating, managing, and using specialized skills with instructions and knowledge.",
        "file": "tools/skills_tool.py",
        "color": "#DC143C"
    },
    {
        "id": "memory_tool",
        "name": "Memory Tool",
        "category": "Memory",
        "description": "Persistent memory across sessions for personal notes and user profiles.",
        "file": "tools/memory_tool.py",
        "color": "#228B22"
    },
    {
        "id": "session_search",
        "name": "Session Search",
        "category": "Memory",
        "description": "Full-text search (FTS5) across past conversations with LLM summarization.",
        "file": "tools/session_search_tool.py",
        "color": "#006400"
    },
    {
        "id": "honcho_tools",
        "name": "Honcho Integration",
        "category": "Memory",
        "description": "AI-native user modeling for persistent cross-session profile understanding.",
        "file": "tools/honcho_tools.py",
        "color": "#2F4F4F"
    },
    {
        "id": "delegate_tool",
        "name": "Delegation Tool",
        "category": "Tool",
        "description": "Spawn isolated subagents with isolated context for complex subtasks.",
        "file": "tools/delegate_tool.py",
        "color": "#708090"
    },
    {
        "id": "code_execution",
        "name": "Code Execution",
        "category": "Tool",
        "description": "Run Python scripts that programmatically call tools via RPC.",
        "file": "tools/code_execution_tool.py",
        "color": "#4682B4"
    },
    {
        "id": "mcp_tool",
        "name": "MCP Client",
        "category": "Tool",
        "description": "Model Context Protocol client for connecting external MCP servers.",
        "file": "tools/mcp_tool.py",
        "color": "#D2691E"
    },
    {
        "id": "cron",
        "name": "Cron Scheduler",
        "category": "Automation",
        "description": "Scheduled task system running自动化任务 with platform delivery.",
        "file": "cron/scheduler.py",
        "color": "#8B4513"
    },
    {
        "id": "rl_training",
        "name": "RL Training",
        "category": "Research",
        "description": "Reinforcement learning training integration with Tinker-Atropos.",
        "file": "tools/rl_training_tool.py",
        "color": "#4B0082"
    },
    {
        "id": "prompt_builder",
        "name": "Prompt Builder",
        "category": "Core",
        "description": "System prompt assembly with context files, skills, and memory integration.",
        "file": "agent/prompt_builder.py",
        "color": "#B8860B"
    },
    {
        "id": "context_compressor",
        "name": "Context Compressor",
        "category": "Core",
        "description": "Automatic context compression to fit more information in token limits.",
        "file": "agent/context_compressor.py",
        "color": "#CD853F"
    },
    {
        "id": "skill_manager",
        "name": "Skill Manager",
        "category": "Memory",
        "description": "Create, edit, and manage skill documents with specialized instructions.",
        "file": "tools/skill_manager_tool.py",
        "color": "#A0522D"
    },
    {
        "id": "skills_hub",
        "name": "Skills Hub",
        "category": "Memory",
        "description": "Marketplace for community skills following agentskills.io standard.",
        "file": "tools/skills_hub.py",
        "color": "#CD5C5C"
    }
]

# Relationships for mind map
RELATIONSHIPS = [
    {"source": "aiagent", "target": "model_tools", "type": "uses"},
    {"source": "aiagent", "target": "prompt_builder", "type": "uses"},
    {"source": "aiagent", "target": "context_compressor", "type": "uses"},
    {"source": "model_tools", "target": "toolsets", "type": "uses"},
    {"source": "model_tools", "target": "terminal_tool", "type": "uses"},
    {"source": "model_tools", "target": "file_tools", "type": "uses"},
    {"source": "model_tools", "target": "web_tools", "type": "uses"},
    {"source": "model_tools", "target": "browser_tool", "type": "uses"},
    {"source": "model_tools", "target": "vision_tools", "type": "uses"},
    {"source": "model_tools", "target": "skills_tool", "type": "uses"},
    {"source": "model_tools", "target": "memory_tool", "type": "uses"},
    {"source": "model_tools", "target": "session_search", "type": "uses"},
    {"source": "model_tools", "target": "delegate_tool", "type": "uses"},
    {"source": "model_tools", "target": "code_execution", "type": "uses"},
    {"source": "model_tools", "target": "mcp_tool", "type": "uses"},
    {"source": "cli", "target": "aiagent", "type": "uses"},
    {"source": "gateway", "target": "aiagent", "type": "uses"},
    {"source": "gateway", "target": "cli", "type": "shares-commands"},
    {"source": "skills_tool", "target": "skill_manager", "type": "uses"},
    {"source": "skills_tool", "target": "skills_hub", "type": "uses"},
    {"source": "memory_tool", "target": "honcho_tools", "type": "uses"},
    {"source": "prompt_builder", "target": "skills_tool", "type": "includes"},
    {"source": "prompt_builder", "target": "memory_tool", "type": "includes"},
    {"source": "cron", "target": "send_message_tool", "type": "uses"},
    {"source": "rl_training", "target": "aiagent", "type": "trains"},
    {"source": "delegate_tool", "target": "aiagent", "type": "spawns"},
    {"source": "tts_tool", "target": "voice_mode", "type": "uses"},
]

# HTML Template with D3.js Mind Map
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Agent Dashboard</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            padding: 2rem;
            text-align: center;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid rgba(255,215,0,0.3);
        }
        .header h1 {
            font-size: 2.5rem;
            color: #FFD700;
            margin-bottom: 0.5rem;
        }
        .header p { color: #aaa; font-size: 1.1rem; }
        .container {
            display: flex;
            height: calc(100vh - 120px);
        }
        .sidebar {
            width: 350px;
            background: rgba(0,0,0,0.4);
            overflow-y: auto;
            padding: 1rem;
            border-right: 1px solid rgba(255,215,0,0.2);
        }
        .sidebar h2 {
            color: #FFD700;
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid rgba(255,215,0,0.3);
        }
        .agent-card {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            cursor: pointer;
            transition: all 0.3s ease;
            border-left: 4px solid var(--agent-color, #FFD700);
        }
        .agent-card:hover {
            background: rgba(255,255,255,0.1);
            transform: translateX(5px);
        }
        .agent-card.selected {
            background: rgba(255,215,0,0.2);
            box-shadow: 0 0 15px rgba(255,215,0,0.3);
        }
        .agent-card h3 {
            font-size: 1rem;
            margin-bottom: 0.5rem;
            color: #fff;
        }
        .agent-card .category {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        .agent-card p {
            font-size: 0.85rem;
            color: #bbb;
            line-height: 1.4;
        }
        .agent-card .file {
            font-size: 0.7rem;
            color: #666;
            margin-top: 0.5rem;
            font-family: monospace;
        }
        .mindmap-container {
            flex: 1;
            position: relative;
            overflow: hidden;
        }
        svg {
            width: 100%;
            height: 100%;
        }
        .node circle {
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .node circle:hover {
            filter: brightness(1.3);
        }
        .node.selected circle {
            stroke: #FFD700;
            stroke-width: 3px;
            filter: drop-shadow(0 0 10px #FFD700);
        }
        .node text {
            font-size: 11px;
            fill: #fff;
            text-anchor: middle;
            pointer-events: none;
        }
        .link {
            stroke: rgba(255,255,255,0.3);
            stroke-width: 1.5px;
            fill: none;
        }
        .legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            padding: 1rem;
            border-radius: 8px;
            font-size: 0.8rem;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 0.3rem 0;
        }
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .controls {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }
        .btn {
            background: rgba(255,215,0,0.2);
            border: 1px solid #FFD700;
            color: #FFD700;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: rgba(255,215,0,0.4);
        }
        .tooltip {
            position: absolute;
            background: rgba(0,0,0,0.9);
            padding: 0.75rem;
            border-radius: 6px;
            font-size: 0.85rem;
            max-width: 250px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 100;
        }
        .category-filter {
            margin-bottom: 1rem;
        }
        .category-filter select {
            width: 100%;
            padding: 0.5rem;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,215,0,0.3);
            color: #fff;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>☤ Hermes Agent Dashboard</h1>
        <p>Interactive mind map of agent components and their relationships</p>
    </div>
    <div class="container">
        <div class="sidebar">
            <h2>Components</h2>
            <div class="category-filter">
                <select id="categoryFilter">
                    <option value="all">All Categories</option>
                    <option value="Core">Core</option>
                    <option value="Interface">Interface</option>
                    <option value="Tool">Tool</option>
                    <option value="Memory">Memory</option>
                    <option value="Automation">Automation</option>
                    <option value="Research">Research</option>
                </select>
            </div>
            <div id="agentList"></div>
        </div>
        <div class="mindmap-container">
            <div class="controls">
                <button class="btn" onclick="resetZoom()">Reset View</button>
                <button class="btn" onclick="toggleNames()">Toggle Names</button>
            </div>
            <svg id="mindmap"></svg>
            <div class="legend">
                <div class="legend-item"><span class="legend-color" style="background:#FFD700"></span>Core</div>
                <div class="legend-item"><span class="legend-color" style="background:#4169E1"></span>Interface</div>
                <div class="legend-item"><span class="legend-color" style="background:#32CD32"></span>Tool</div>
                <div class="legend-item"><span class="legend-color" style="background:#DC143C"></span>Memory</div>
                <div class="legend-item"><span class="legend-color" style="background:#8B4513"></span>Automation</div>
                <div class="legend-item"><span class="legend-color" style="background:#4B0082"></span>Research</div>
            </div>
            <div class="tooltip" id="tooltip"></div>
        </div>
    </div>

    <script>
        const agents = {{ agents | tojson }};
        const relationships = {{ relationships | tojson }};
        
        let selectedAgent = null;
        let showNames = true;
        let svg, g, zoom;
        
        const categoryColors = {
            'Core': '#FFD700',
            'Interface': '#4169E1',
            'Tool': '#32CD32',
            'Memory': '#DC143C',
            'Automation': '#8B4513',
            'Research': '#4B0082'
        };
        
        function init() {
            const container = document.querySelector('.mindmap-container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            svg = d3.select('#mindmap')
                .attr('width', width)
                .attr('height', height);
            
            g = svg.append('g');
            
            zoom = d3.zoom()
                .scaleExtent([0.3, 3])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });
            
            svg.call(zoom);
            
            renderMindmap();
            renderAgentList();
            setupEventListeners();
        }
        
        function renderMindmap() {
            g.selectAll('*').remove();
            
            // Create nodes map
            const nodesMap = {};
            agents.forEach(a => {
                nodesMap[a.id] = {...a};
            });
            
            // Create links
            const links = relationships.map(r => ({
                source: nodesMap[r.source],
                target: nodesMap[r.target],
                type: r.type
            })).filter(l => l.source && l.target);
            
            // Force simulation
            const simulation = d3.forceSimulation(Object.values(nodesMap))
                .force('link', d3.forceLink(links).id(d => d.id).distance(120))
                .force('charge', d3.forceManyBody().strength(-400))
                .force('center', d3.forceCenter(
                    svg.attr('width') / 2,
                    svg.attr('height') / 2
                ))
                .force('collision', d3.forceCollide().radius(50));
            
            // Draw links
            const link = g.selectAll('.link')
                .data(links)
                .join('line')
                .attr('class', 'link')
                .attr('stroke', d => {
                    const colors = {
                        'uses': 'rgba(255,255,255,0.3)',
                        'includes': 'rgba(255,215,0,0.4)',
                        'spawns': 'rgba(255,100,100,0.4)',
                        'trains': 'rgba(100,100,255,0.4)',
                        'shares-commands': 'rgba(100,255,100,0.3)'
                    };
                    return colors[d.type] || 'rgba(255,255,255,0.3)';
                });
            
            // Draw nodes
            const node = g.selectAll('.node')
                .data(Object.values(nodesMap))
                .join('g')
                .attr('class', 'node')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended))
                .on('click', (event, d) => selectAgent(d.id))
                .on('mouseover', showTooltip)
                .on('mouseout', hideTooltip);
            
            node.append('circle')
                .attr('r', 25)
                .attr('fill', d => d.color);
            
            node.append('text')
                .attr('dy', 40)
                .text(d => d.name)
                .style('display', showNames ? 'block' : 'none');
            
            simulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node.attr('transform', d => `translate(${d.x},${d.y})`);
            });
        }
        
        function renderAgentList(filter = 'all') {
            const list = document.getElementById('agentList');
            list.innerHTML = '';
            
            const filtered = filter === 'all' 
                ? agents 
                : agents.filter(a => a.category === filter);
            
            filtered.forEach(agent => {
                const card = document.createElement('div');
                card.className = 'agent-card';
                card.style.setProperty('--agent-color', agent.color);
                if (selectedAgent === agent.id) card.classList.add('selected');
                card.innerHTML = `
                    <div class="category">${agent.category}</div>
                    <h3>${agent.name}</h3>
                    <p>${agent.description}</p>
                    <div class="file">${agent.file}</div>
                `;
                card.onclick = () => selectAgent(agent.id);
                list.appendChild(card);
            });
        }
        
        function selectAgent(id) {
            selectedAgent = selectedAgent === id ? null : id;
            
            // Update mindmap
            g.selectAll('.node').classed('selected', d => d.id === selectedAgent);
            
            // Update sidebar cards
            document.querySelectorAll('.agent-card').forEach(card => {
                card.classList.remove('selected');
            });
            
            // Find and highlight card
            const cards = document.querySelectorAll('.agent-card');
            const agentIndex = agents.findIndex(a => a.id === id);
            if (selectedAgent && cards[agentIndex]) {
                cards[agentIndex].classList.add('selected');
            }
            
            // Zoom to selected node
            if (selectedAgent) {
                const node = agents.find(a => a.id === selectedAgent);
                if (node && node.x !== undefined) {
                    svg.transition()
                        .duration(500)
                        .call(zoom.transform, d3.zoomIdentity
                            .translate(-node.x + svg.attr('width')/2, -node.y + svg.attr('height')/2)
                            .scale(1.5));
                }
            }
        }
        
        function showTooltip(event, d) {
            const tooltip = document.getElementById('tooltip');
            tooltip.innerHTML = `<strong>${d.name}</strong><br>${d.description}`;
            tooltip.style.left = (event.pageX + 15) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
            tooltip.style.opacity = 1;
        }
        
        function hideTooltip() {
            document.getElementById('tooltip').style.opacity = 0;
        }
        
        function resetZoom() {
            svg.transition()
                .duration(500)
                .call(zoom.transform, d3.zoomIdentity);
        }
        
        function toggleNames() {
            showNames = !showNames;
            g.selectAll('.node text').style('display', showNames ? 'block' : 'none');
        }
        
        function setupEventListeners() {
            document.getElementById('categoryFilter').addEventListener('change', (e) => {
                renderAgentList(e.target.value);
            });
            
            window.addEventListener('resize', () => {
                const container = document.querySelector('.mindmap-container');
                svg.attr('width', container.clientWidth)
                   .attr('height', container.clientHeight);
            });
        }
        
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        let simulation;
        
        init();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                         agents=json.dumps(AGENTS), 
                         relationships=json.dumps(RELATIONSHIPS))

@app.route('/api/agents')
def api_agents():
    return jsonify(AGENTS)

@app.route('/api/relationships')
def api_relationships():
    return jsonify(RELATIONSHIPS)

if __name__ == '__main__':
    import os
    
    # Use port 12345 or find free port
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('0.0.0.0', 12345))
        port = 12345
        s.close()
    except:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
    
    print(f"\n{'='*60}")
    print(f"☤ Hermes Agent Dashboard")
    print(f"{'='*60}")
    print(f"Starting on http://0.0.0.0:{port}")
    print(f"Open in browser: http://localhost:{port}")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)