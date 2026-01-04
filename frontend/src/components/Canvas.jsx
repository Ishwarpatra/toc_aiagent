import { useEffect, useRef, useCallback, useState } from "react";

// Color palette for nodes
const NODE_COLORS = {
  start: { fill: "#7ec8e3", stroke: "#4a90d9", text: "#1a365d" },
  accept: { fill: "#c4b5fd", stroke: "#8b5cf6", text: "#4c1d95" },
  regular: { fill: "#e2e8f0", stroke: "#94a3b8", text: "#334155" },
  dead: { fill: "#fecaca", stroke: "#ef4444", text: "#991b1b" },
};

export default function Canvas({ data, loading, error }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  // Zoom and Pan state
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 0.7 });
  const [isPanning, setIsPanning] = useState(false);
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });

  // Reset transform when new data arrives
  useEffect(() => {
    if (data?.dfa) {
      setTransform({ x: 0, y: 0, scale: 0.7 });
    }
  }, [data]);

  // Smart horizontal layout - states flow left to right
  const calculateLayout = useCallback((states, startState, acceptStates) => {
    const positions = {};
    const nodeCount = states.length;

    if (nodeCount === 0) return positions;

    // Calculate canvas dimensions - slightly tighter for "smaller" default feel
    const padding = 120;
    const nodeRadius = 40;
    const horizontalSpacing = 220;
    const verticalSpacing = 200;

    // Sort states: start first, then regular, accept states, dead last
    const sortedStates = [];

    // Start state first
    if (states.includes(startState)) {
      sortedStates.push(startState);
    }

    // Regular states (not start, not accept, not dead)
    states.forEach(s => {
      if (s !== startState && !acceptStates.includes(s) && !s.toLowerCase().includes('dead')) {
        sortedStates.push(s);
      }
    });

    // Accept states
    acceptStates.forEach(s => {
      if (s !== startState && !sortedStates.includes(s)) {
        sortedStates.push(s);
      }
    });

    // Dead states last
    states.forEach(s => {
      if (s.toLowerCase().includes('dead') && !sortedStates.includes(s)) {
        sortedStates.push(s);
      }
    });

    // Layout based on state count
    if (nodeCount <= 2) {
      // Simple horizontal layout
      sortedStates.forEach((state, i) => {
        positions[state] = {
          x: padding + nodeRadius + i * horizontalSpacing,
          y: 200,
        };
      });
    } else if (nodeCount <= 4) {
      // Two rows for 3-4 states
      const colCount = 2;
      sortedStates.forEach((state, i) => {
        const row = Math.floor(i / colCount);
        const col = i % colCount;
        positions[state] = {
          x: padding + nodeRadius + col * horizontalSpacing,
          y: padding + nodeRadius + row * verticalSpacing,
        };
      });
    } else {
      // Grid layout for more states
      const cols = 3;
      sortedStates.forEach((state, i) => {
        const row = Math.floor(i / cols);
        const col = i % cols;
        positions[state] = {
          x: padding + nodeRadius + col * horizontalSpacing,
          y: padding + nodeRadius + row * verticalSpacing,
        };
      });
    }

    return positions;
  }, []);

  // Generate clean curved path between two points
  const generatePath = useCallback((x1, y1, x2, y2, nodeRadius, isSelfLoop) => {
    if (isSelfLoop) {
      // Self-loop - draw a nice loop above the node
      const loopWidth = 35;
      const loopHeight = 60;
      return `M ${x1 - 12} ${y1 - nodeRadius + 4}
              C ${x1 - loopWidth} ${y1 - nodeRadius - loopHeight},
                ${x1 + loopWidth} ${y1 - nodeRadius - loopHeight},
                ${x1 + 12} ${y1 - nodeRadius + 4}`;
    }

    const dx = x2 - x1;
    const dy = y2 - y1;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance === 0) return "";

    // Normalize direction
    const nx = dx / distance;
    const ny = dy / distance;

    // Start and end points on node edges
    const startX = x1 + nx * nodeRadius;
    const startY = y1 + ny * nodeRadius;
    const endX = x2 - nx * (nodeRadius + 15);
    const endY = y2 - ny * (nodeRadius + 15);

    // Curve control point (perpendicular offset)
    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2;
    const curvature = Math.min(50, distance * 0.18);
    const ctrlX = midX - ny * curvature;
    const ctrlY = midY + nx * curvature;

    return `M ${startX} ${startY} Q ${ctrlX} ${ctrlY} ${endX} ${endY}`;
  }, []);

  // Handle Wheel Zoom
  const handleWheel = (e) => {
    if (!data?.dfa) return;
    e.preventDefault();
    const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.2, Math.min(3, transform.scale * scaleFactor));
    setTransform(prev => ({ ...prev, scale: newScale }));
  };

  // Handle Pan Start
  const handleMouseDown = (e) => {
    if (!data?.dfa) return;
    setIsPanning(true);
    setLastMousePos({ x: e.clientX, y: e.clientY });
  };

  // Handle Panning
  const handleMouseMove = (e) => {
    if (!isPanning) return;
    const dx = e.clientX - lastMousePos.x;
    const dy = e.clientY - lastMousePos.y;
    setTransform(prev => ({
      ...prev,
      x: prev.x + dx,
      y: prev.y + dy
    }));
    setLastMousePos({ x: e.clientX, y: e.clientY });
  };

  // Handle Pan End
  const handleMouseUp = () => {
    setIsPanning(false);
  };

  // Render the DFA
  const renderDFA = useCallback(() => {
    if (!data?.dfa || !svgRef.current) return;

    const { states, start_state, accept_states, transitions } = data.dfa;
    const nodeRadius = 40;
    const positions = calculateLayout(states, start_state, accept_states);

    // Calculate bounding box with extra padding for labels and arrows
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    // Account for nodes
    Object.values(positions).forEach(({ x, y }) => {
      minX = Math.min(minX, x - nodeRadius - 120);
      minY = Math.min(minY, y - nodeRadius - 120);
      maxX = Math.max(maxX, x + nodeRadius + 120);
      maxY = Math.max(maxY, y + nodeRadius + 120);
    });

    if (minX === Infinity) {
      minX = 0; minY = 0; maxX = 800; maxY = 600;
    }

    const width = maxX - minX;
    const height = maxY - minY;

    let svgContent = "";

    // SVG Definitions
    svgContent += `
      <defs>
        <marker id="arrow" markerWidth="14" markerHeight="10" refX="13" refY="5" orient="auto">
          <path d="M 0 0 L 14 5 L 0 10 L 3 5 Z" fill="#64748b"/>
        </marker>
        <marker id="arrow-self" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto">
          <path d="M 0 0 L 12 4.5 L 0 9 L 2.5 4.5 Z" fill="#64748b"/>
        </marker>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity="0.2"/>
        </filter>
      </defs>
    `;

    // Group edges by source-dest pair to handle multiple transitions
    const edgeGroups = {};
    Object.entries(transitions).forEach(([src, transMap]) => {
      Object.entries(transMap).forEach(([symbol, dest]) => {
        const key = `${src}->${dest}`;
        if (!edgeGroups[key]) {
          edgeGroups[key] = { src, dest, symbols: [] };
        }
        edgeGroups[key].symbols.push(symbol);
      });
    });

    // Start Content Group
    svgContent += `<g transform="translate(${transform.x}, ${transform.y}) scale(${transform.scale})">`;

    // Draw edges
    Object.values(edgeGroups).forEach(({ src, dest, symbols }) => {
      if (!positions[src] || !positions[dest]) return;

      const isSelfLoop = src === dest;
      const path = generatePath(
        positions[src].x,
        positions[src].y,
        positions[dest].x,
        positions[dest].y,
        nodeRadius,
        isSelfLoop
      );

      if (!path) return;

      // Edge line
      svgContent += `
        <path 
          d="${path}" 
          fill="none" 
          stroke="#94a3b8" 
          stroke-width="3"
          marker-end="url(#${isSelfLoop ? 'arrow-self' : 'arrow'})"
        />
      `;

      // Edge label
      const label = symbols.join(", ");
      let labelX, labelY;

      if (isSelfLoop) {
        labelX = positions[src].x;
        labelY = positions[src].y - nodeRadius - 75;
      } else {
        const dx = positions[dest].x - positions[src].x;
        const dy = positions[dest].y - positions[src].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const midX = (positions[src].x + positions[dest].x) / 2;
        const midY = (positions[src].y + positions[dest].y) / 2;
        const curvature = Math.min(50, dist * 0.18);
        const nx = dx / dist;
        const ny = dy / dist;
        labelX = midX - ny * (curvature + 20);
        labelY = midY + nx * (curvature + 20);
      }

      const labelWidth = label.length * 10 + 16;
      svgContent += `
        <rect 
          x="${labelX - labelWidth / 2}" y="${labelY - 12}" 
          width="${labelWidth}" height="24" 
          rx="5" fill="white" stroke="#e2e8f0" stroke-width="1.2"
          filter="url(#shadow)"
        />
        <text 
          x="${labelX}" y="${labelY + 5}" 
          text-anchor="middle" 
          font-size="14" 
          font-weight="700"
          font-family="Inter, system-ui, sans-serif"
          fill="#334155"
        >${label}</text>
      `;
    });

    // Draw start arrow
    if (positions[start_state]) {
      const startX = positions[start_state].x - nodeRadius - 70;
      const startY = positions[start_state].y;
      const endX = positions[start_state].x - nodeRadius - 5;

      svgContent += `
        <line 
          x1="${startX}" y1="${startY}" 
          x2="${endX}" y2="${startY}" 
          stroke="#1e293b" stroke-width="3" 
          marker-end="url(#arrow)"
        />
        <text 
          x="${startX - 12}" y="${startY + 5}" 
          text-anchor="end" 
          font-size="12" 
          font-weight="700"
          fill="#475569"
        >START</text>
      `;
    }

    // Draw nodes
    states.forEach((state) => {
      if (!positions[state]) return;
      const { x, y } = positions[state];
      const isStart = state === start_state;
      const isAccept = accept_states.includes(state);
      const isDead = state.toLowerCase().includes("dead");

      let colors;
      if (isDead) colors = NODE_COLORS.dead;
      else if (isAccept) colors = NODE_COLORS.accept;
      else if (isStart) colors = NODE_COLORS.start;
      else colors = NODE_COLORS.regular;

      svgContent += `
        <circle cx="${x}" cy="${y}" r="${nodeRadius}" 
                fill="${colors.fill}" stroke="${colors.stroke}" stroke-width="3"
                filter="url(#shadow)"/>
      `;

      if (isAccept) {
        svgContent += `
          <circle cx="${x}" cy="${y}" r="${nodeRadius - 7}" 
                  fill="none" stroke="${colors.stroke}" stroke-width="2"/>
        `;
      }

      svgContent += `
        <text x="${x}" y="${y + 6}" text-anchor="middle" 
              font-size="18" font-weight="800" 
              font-family="Inter, system-ui, sans-serif"
              fill="${colors.text}">${state}</text>
      `;
    });

    svgContent += `</g>`;

    // Update SVG
    svgRef.current.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);
    svgRef.current.innerHTML = svgContent;
  }, [data, calculateLayout, generatePath, transform]);

  useEffect(() => {
    if (data?.dfa) {
      renderDFA();
    }
  }, [data, renderDFA]);

  // Render empty state
  if (!data && !loading && !error) {
    return (
      <div className="canvas-container">
        <div className="canvas-frame">
          <div className="canvas-empty">
            <span className="canvas-empty-icon">◇</span>
            <span className="canvas-empty-text">No DFA Generated</span>
            <span className="canvas-empty-hint">Enter a description and click Generate</span>
          </div>
        </div>
      </div>
    );
  }

  // Render loading state
  if (loading) {
    return (
      <div className="canvas-container">
        <div className="canvas-frame">
          <div className="loading-overlay">
            <div className="loading-spinner"></div>
            <span className="loading-text">Architecting DFA...</span>
          </div>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="canvas-container">
        <div className="canvas-frame">
          <div className="error-message">
            <span className="error-icon">⚠</span>
            <span>{error}</span>
          </div>
        </div>
      </div>
    );
  }

  // Render DFA
  return (
    <div className="canvas-container" ref={containerRef}>
      <div
        className="canvas-frame"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isPanning ? 'grabbing' : 'grab' }}
      >
        <svg
          ref={svgRef}
          className="dfa-svg"
          preserveAspectRatio="xMidYMid meet"
        />

        {/* Zoom Controls Overlay */}
        <div className="zoom-controls">
          <button onClick={() => setTransform(prev => ({ ...prev, scale: Math.min(3, prev.scale + 0.1) }))}>+</button>
          <button onClick={() => setTransform(prev => ({ ...prev, scale: Math.max(0.2, prev.scale - 0.1) }))}>−</button>
          <button onClick={() => setTransform({ x: 0, y: 0, scale: 0.7 })}>⟲</button>
        </div>

        {/* DFA Info Panel */}
        {data?.dfa && (
          <div className="dfa-info">
            <div className="dfa-info-title">DFA Properties</div>
            <div className="dfa-info-item">
              <span className="dfa-info-label">States</span>
              <span className="dfa-info-value">{data.dfa.states.length}</span>
            </div>
            <div className="dfa-info-item">
              <span className="dfa-info-label">Alphabet</span>
              <span className="dfa-info-value">{data.dfa.alphabet.join(", ")}</span>
            </div>
            <div className="dfa-info-item">
              <span className="dfa-info-label">Valid</span>
              <span className={`dfa-info-value ${data.valid ? 'dfa-info-valid' : 'dfa-info-invalid'}`}>
                {data.valid ? "✓ Yes" : "✗ No"}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
