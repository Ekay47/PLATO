import ELK from 'elkjs/lib/elk.bundled.js';
import { Node, Edge, Position } from 'reactflow';

const elk = new ELK();

// Estimate node size based on type and label
const getNodeSize = (node: Node) => {
    const label = node.data?.label || '';
    const length = label.length;

    switch (node.type) {
        case 'start':
        case 'stop':
            return { width: 40, height: 40 };
        case 'merge':
            return { width: 24, height: 24 };
        case 'condition':
            return { width: 120, height: 120 };
        case 'fork':
        case 'join':
            return { width: 140, height: 20 };
        case 'note':
            return { width: Math.max(140, length * 8), height: Math.max(60, Math.ceil(length / 20) * 20) };
        case 'activity':
        case 'group':
        default:
            return {
                width: Math.max(140, length * 9 + 40),
                height: 60
            };
    }
};

export const getLayoutedElements = async (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const isHorizontal = direction === 'LR';
  
  // 1. Prepare Graph for ELK
  // ELK expects a hierarchical JSON structure
  const graph: any = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': isHorizontal ? 'RIGHT' : 'DOWN',
      
      // Node placement strategy: NETWORK_SIMPLEX usually produces more compact results
      'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
      
      // Spacing configuration
      'elk.spacing.nodeNode': '60', // Horizontal separation in DOWN mode
      'elk.layered.spacing.nodeNodeBetweenLayers': '80', // Vertical separation
      'elk.spacing.edgeNode': '30',
      'elk.layered.spacing.edgeEdgeBetweenLayers': '25', // Spacing between parallel edges
      
      // Routing
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.layered.unnecessaryBendpoints': 'false', // Reduce zig-zags
      'elk.layered.mergeEdges': 'true', // Merge edges from same parent/to same child
      
      // Alignment
      'elk.alignment': 'CENTER',
      
      // Ports
      'elk.portAlignment.default': 'CENTER',
    },
    children: [],
    edges: []
  };

  // Map React Flow nodes to ELK nodes
  // We need to handle parent-child relationships for nested groups (partitions/composite states)
  const nodeMap = new Map();
  
  nodes.forEach(node => {
      const size = getNodeSize(node);
      const elkNode = {
          id: node.id,
          width: size.width,
          height: size.height,
          // If it's a group, we might need specific layout options
          layoutOptions: node.type === 'group' ? { 
              'elk.padding': '[top=40,left=20,bottom=20,right=20]',
              'elk.algorithm': 'layered',
              'elk.direction': 'DOWN'
          } : undefined,
          children: [],
          edges: []
      };
      nodeMap.set(node.id, elkNode);
  });

  // Build hierarchy
  nodes.forEach(node => {
      const elkNode = nodeMap.get(node.id);
      if (node.parentNode && nodeMap.has(node.parentNode)) {
          const parent = nodeMap.get(node.parentNode);
          parent.children.push(elkNode);
      } else {
          graph.children.push(elkNode);
      }
  });

  // Map edges
  // ELK edges need to be placed in the common ancestor of source/target
  // For simplicity in flat graphs, root is fine. For nested, we need logic.
  // Current parser logic assigns parentNode, but edges are usually global in React Flow unless contained.
  // Let's put all edges in root for now unless we implement deep nesting logic for edges.
  // Note: ELK requires edge IDs.
  edges.forEach(edge => {
      graph.edges.push({
          id: edge.id,
          sources: [edge.source],
          targets: [edge.target]
      });
  });

  // 2. Compute Layout
  try {
      const layoutedGraph = await elk.layout(graph);
      
      // 3. Map back to React Flow
      const layoutedNodes: Node[] = [];
      
      // Helper to flatten ELK hierarchy back to React Flow flat array
      const flatten = (elkNodes: any[], parentX = 0, parentY = 0) => {
          elkNodes.forEach(elkNode => {
              const originalNode = nodes.find(n => n.id === elkNode.id);
              if (originalNode) {
                  // ELK coordinates are relative to parent. 
                  // React Flow handles parent-child coords automatically if parentNode is set.
                  // So we just use elkNode.x/y directly.
                  
                  const position = {
                      x: elkNode.x,
                      y: elkNode.y
                  };

                  const newStyle = { 
                    ...originalNode.style, 
                    width: elkNode.width, 
                    height: elkNode.height,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center'
                  };

                  layoutedNodes.push({
                      ...originalNode,
                      targetPosition: isHorizontal ? Position.Left : Position.Top,
                      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
                      position,
                      style: newStyle
                  });
              }
              
              if (elkNode.children && elkNode.children.length > 0) {
                  flatten(elkNode.children, parentX + elkNode.x, parentY + elkNode.y);
              }
          });
      };

      if (layoutedGraph.children) {
        flatten(layoutedGraph.children);
      }
      
      return { nodes: layoutedNodes, edges };
      
  } catch (e) {
      console.error("ELK Layout failed:", e);
      return { nodes, edges }; // Fallback to raw nodes
  }
};
