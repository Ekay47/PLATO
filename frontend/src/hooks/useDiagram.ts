import { useState, useEffect, useCallback } from 'react';
import { useNodesState, useEdgesState, Node, Edge, Connection, addEdge } from 'reactflow';
import { parsePlantUML as parseEnhanced } from '../utils/plantuml-parser';
import { convertFlowToPlantUML } from '../utils/flow-to-plantuml';
import { getLayoutedElements } from '../utils/layout-elk';
import { useDebounce } from './useDebounce';

const initialCode = ``;

const cloneNodes = (ns: Node[]) =>
  ns.map((n) => ({
    ...n,
    position: { ...n.position },
    data: { ...(n as any).data },
  }));

const cloneEdges = (es: Edge[]) =>
  es.map((e) => ({
    ...e,
    data: { ...(e as any).data },
  }));

export const useDiagram = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [code, setCode] = useState(initialCode);
  const debouncedCode = useDebounce(code, 500); // 500ms debounce
  const [error, setError] = useState<string | null>(null);
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [defaultLayout, setDefaultLayout] = useState<{ nodes: Node[]; edges: Edge[] } | null>(null);

  // Sync Code -> Diagram
  useEffect(() => {
    let isMounted = true;
    const parse = async () => {
      try {
        setError(null);
        // Always use Enhanced Local Parser (Regex-based)
        const result = parseEnhanced(debouncedCode);
        
        if (!isMounted) return;

        const { nodes: newNodes, edges: newEdges } = result;
        // ELK is async, so we await it
        const { nodes: layoutedNodes, edges: layoutedEdges } = await getLayoutedElements(newNodes, newEdges);
        
        if (!isMounted) return;
        
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setLayoutVersion(v => v + 1);
        setDefaultLayout({ nodes: cloneNodes(layoutedNodes), edges: cloneEdges(layoutedEdges) });
      } catch (e: any) {
        console.error("Failed to parse PlantUML:", e);
        if (isMounted) setError(e.message || "Unknown parsing error");
      }
    };
    parse();
    return () => { isMounted = false; };
  }, [debouncedCode, setNodes, setEdges]); // Depend on debouncedCode

  // Sync Diagram -> Code
  const onConnect = useCallback((params: Connection) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const updateCodeFromDiagram = useCallback(() => {
      // TODO: Implement robust graph -> code
      const newCode = convertFlowToPlantUML(nodes, edges);
      // setCode(newCode); // Disabled for now to prevent overwrite with incomplete generator
      console.log("Generated Code:", newCode);
  }, [nodes, edges]);

  const onNodeDoubleClick = useCallback((_event: React.MouseEvent, node: Node) => {
    // Label editing disabled per user request
    console.log("Node double clicked:", node);
  }, []);

  const resetToDefaultLayout = useCallback(() => {
    if (!defaultLayout) return false;
    setNodes(cloneNodes(defaultLayout.nodes));
    setEdges(cloneEdges(defaultLayout.edges));
    return true;
  }, [defaultLayout, setEdges, setNodes]);

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    code,
    setCode,
    error,
    updateCodeFromDiagram,
    onNodeDoubleClick,
    layoutVersion,
    resetToDefaultLayout
  };
};
