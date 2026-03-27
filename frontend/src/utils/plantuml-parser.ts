import { Node, Edge, MarkerType } from 'reactflow';

interface ParseResult {
  nodes: Node[];
  edges: Edge[];
}

interface BranchContext {
    type: 'if';
    entryNodeId: string;
    activeBranchStartNodeId: string; 
    exitNodeIds: string[];
}

interface LoopContext {
    type: 'repeat' | 'while';
    entryNodeId: string;
}

interface ForkContext {
    type: 'fork';
    entryNodeId: string; 
    exitNodeIds: string[];
}

interface CompositeStateContext {
    type: 'composite';
    parentNodeId: string;
}

interface SequenceGroupContext {
    type: 'group';
    label: string;
}

type StackItem = BranchContext | LoopContext | ForkContext | CompositeStateContext | SequenceGroupContext;

export function parsePlantUML(code: string): ParseResult {
  const lines = code.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith("'") && !l.startsWith("@"));
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  
  let lastNodeId: string | null = null;
  let pendingEdgeLabel: string | null = null;
  const stack: StackItem[] = []; 
  const aliasMap = new Map<string, string>(); 

  const patterns = {
    // Activity
    start: /^start$/,
    stop: /^stop$/,
    activity: /^:(.*?);$/, 
    ifStart: /^if\s*\((.*?)\)\s*then(?:\s*\((.*?)\))?$/, 
    elseIf: /^elseif\s*\((.*?)\)\s*then(?:\s*\((.*?)\))?$/,
    else: /^else(?:\s*\((.*?)\))?$/, 
    endif: /^endif$/,
    detach: /^(detach|kill|end)$/,
    partitionStart: /^partition\s+"?(.*?)"?\s*\{?$/,
    partitionEnd: /^\}$/,
    
    // Fork/Split
    fork: /^(fork|split)$/,
    forkAgain: /^(fork\s+again|split\s+again)$/,
    endFork: /^(end\s+fork|end\s+split)$/,
    
    // Loops
    repeat: /^repeat$/,
    repeatWhile: /^repeat\s*while\s*\((.*?)\)(?:\s+is\s+\((.*?)\))?$/,
    while: /^while\s*\((.*?)\)(?:\s+is\s+\((.*?)\))?$/,
    endWhile: /^end\s*while(?:\s*\((.*?)\))?$/,

    // Sequence
    message: /^(\S+)\s*(<-+|-+>)\s*(\S+)\s*:\s*(.*)$/, 
    participant: /^(participant|actor|boundary|control|entity|database)\s+"?(.*?)"?(?:\s+as\s+(\S+))?$/,
    groupStart: /^(alt|opt|loop|par|critical|group)(?:\s+(.*))?$/,
    groupElse: /^else(?:\s*(.*))?$/,
    groupEnd: /^end(?:\s+\w+)?$/,
    
    // State
    stateAlias: /^state\s+"(.*?)"\s+as\s+(\S+)$/,
    stateSimple: /^state\s+(\S+)$/,
    stateCompositeStart: /^state\s+"?(.*?)"?\s*(?:as\s+(\S+))?\s*\{$/,
    stateCompositeEnd: /^\}$/,
    transition: /^(\S+)\s*-->\s*(\S+)(?:\s*:\s*(.*))?$/,
    startState: /^\[\*\]\s*-->\s*(\S+)$/
  };
  
  const resolveId = (name: string) => aliasMap.get(name) || name;

  const getParentNodeId = () => {
    for (let i = stack.length - 1; i >= 0; i--) {
        if (stack[i].type === 'composite') return (stack[i] as CompositeStateContext).parentNodeId;
    }
    return undefined;
  };

  const getGroupLabel = () => {
      const labels: string[] = [];
      for (const item of stack) {
          if (item.type === 'group') labels.push((item as SequenceGroupContext).label);
      }
      return labels.length > 0 ? `[${labels.join(' ')}] ` : '';
  };

  lines.forEach((line, index) => {
    let match;

    // --- Activity Diagram ---
    if (patterns.start.test(line)) {
        const id = 'start';
        if (!nodes.find(n => n.id === id))
            nodes.push({ id, type: 'start', data: { label: 'Start' }, position: { x: 0, y: 0 } });
        if (lastNodeId) edges.push(createEdge(lastNodeId, id));
        lastNodeId = id;
    } 
    else if (patterns.stop.test(line)) {
        const id = `stop_${index}`;
        nodes.push({ id, type: 'stop', data: { label: 'End' }, position: { x: 0, y: 0 } });
        if (lastNodeId) edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
        pendingEdgeLabel = null;
        lastNodeId = null;
    }
    else if (patterns.detach.test(line)) {
        lastNodeId = null;
    }
    else if ((match = patterns.partitionStart.exec(line))) {
        const name = match[1];
        const id = `partition_${index}`;
        nodes.push({ 
            id, 
            type: 'group', 
            data: { label: name }, 
            position: { x: 0, y: 0 },
            style: { width: 200, height: 200, backgroundColor: 'rgba(240, 240, 240, 0.5)' } 
        });
        stack.push({ type: 'composite', parentNodeId: id });
    }
    else if (patterns.partitionEnd.test(line)) {
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'composite') {
                stack.pop();
            }
        }
    }
    else if ((match = patterns.activity.exec(line))) {
        const label = match[1];
        const id = `act_${index}`;
        const parentId = getParentNodeId();
        const node: Node = { id, type: 'activity', data: { label }, position: { x: 0, y: 0 } };
        if (parentId) {
            node.parentNode = parentId;
            node.extent = 'parent';
        }
        nodes.push(node);
        if (lastNodeId) {
            edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
            pendingEdgeLabel = null;
        }
        lastNodeId = id;
    }
    else if ((match = patterns.ifStart.exec(line))) {
        const condition = match[1];
        const label = match[2] || 'yes';
        const id = `if_${index}`;
        
        const parentId = getParentNodeId();
        const node: Node = { id, type: 'condition', data: { label: condition }, position: { x: 0, y: 0 } };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);

        if (lastNodeId) {
            edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
            pendingEdgeLabel = null;
        }
        
        stack.push({ type: 'if', entryNodeId: id, activeBranchStartNodeId: id, exitNodeIds: [] });
        lastNodeId = id; 
        pendingEdgeLabel = label;
    }
    else if ((match = patterns.elseIf.exec(line))) {
        const condition = match[1];
        const label = match[2] || 'yes';
        
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'if') {
                if (lastNodeId) (ctx as BranchContext).exitNodeIds.push(lastNodeId);
                const elseIfId = `elseif_${index}`;
                
                const parentId = getParentNodeId();
                const node: Node = { id: elseIfId, type: 'condition', data: { label: condition }, position: { x: 0, y: 0 } };
                if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
                nodes.push(node);

                edges.push(createEdge((ctx as BranchContext).entryNodeId, elseIfId, 'no'));
                (ctx as BranchContext).entryNodeId = elseIfId;
                lastNodeId = elseIfId;
                pendingEdgeLabel = label;
            }
        }
    }
    else if ((match = patterns.else.exec(line))) {
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'if') {
                if (lastNodeId) (ctx as BranchContext).exitNodeIds.push(lastNodeId);
                lastNodeId = (ctx as BranchContext).entryNodeId; 
                pendingEdgeLabel = match[1] || null; 
            }
        }
    }
    else if (patterns.endif.test(line)) {
        if (stack.length > 0) {
            const ctx = stack.pop();
            if (ctx && ctx.type === 'if') {
                if (lastNodeId) (ctx as BranchContext).exitNodeIds.push(lastNodeId);
                const mergeId = `merge_${index}`;
                
                const parentId = getParentNodeId();
                const node: Node = { 
                    id: mergeId, type: 'merge', data: { label: '' }, position: { x: 0, y: 0 }
                };
                if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
                nodes.push(node);

                (ctx as BranchContext).exitNodeIds.forEach(exitId => {
                    if (!edges.find(e => e.source === exitId && e.target === mergeId))
                        edges.push(createEdge(exitId, mergeId));
                });
                lastNodeId = mergeId;
            }
        }
    }
    
    // --- Fork / Split ---
    else if (patterns.fork.test(line)) {
        const id = `fork_${index}`;
        
        const parentId = getParentNodeId();
        const node: Node = { 
            id, type: 'fork', data: { label: '' }, position: { x: 0, y: 0 }
        };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);

        if (lastNodeId) {
            edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
            pendingEdgeLabel = null;
        }
        stack.push({ type: 'fork', entryNodeId: id, exitNodeIds: [] });
        lastNodeId = id;
    }
    else if (patterns.forkAgain.test(line)) {
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'fork') {
                if (lastNodeId) (ctx as ForkContext).exitNodeIds.push(lastNodeId);
                lastNodeId = (ctx as ForkContext).entryNodeId;
            }
        }
    }
    else if (patterns.endFork.test(line)) {
        if (stack.length > 0) {
            const ctx = stack.pop();
            if (ctx && ctx.type === 'fork') {
                if (lastNodeId) (ctx as ForkContext).exitNodeIds.push(lastNodeId);
                
                const joinId = `join_${index}`;
                const parentId = getParentNodeId();
                const node: Node = { 
                    id: joinId, type: 'join', data: { label: '' }, position: { x: 0, y: 0 }
                };
                if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
                nodes.push(node);
                
                (ctx as ForkContext).exitNodeIds.forEach(exitId => {
                    edges.push(createEdge(exitId, joinId));
                });
                lastNodeId = joinId;
            }
        }
    }
    
    // --- Repeat Loop ---
    else if (patterns.repeat.test(line)) {
        const id = `repeat_${index}`;
        const parentId = getParentNodeId();
        const node: Node = { 
            id, type: 'merge', data: { label: '' }, position: { x: 0, y: 0 }
        };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);

        if (lastNodeId) {
            edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
            pendingEdgeLabel = null;
        }
        lastNodeId = id;
        stack.push({ type: 'repeat', entryNodeId: id });
    }
    else if ((match = patterns.repeatWhile.exec(line))) {
        const condition = match[1];
        const labelYes = match[2] || 'yes';
        
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'repeat') {
                stack.pop();
                const id = `repeat_while_${index}`;
                
                const parentId = getParentNodeId();
                const node: Node = { id, type: 'condition', data: { label: condition }, position: { x: 0, y: 0 } };
                if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
                nodes.push(node);

                if (lastNodeId) edges.push(createEdge(lastNodeId, id));
                edges.push(createEdge(id, (ctx as LoopContext).entryNodeId, labelYes));
                lastNodeId = id; 
            }
        }
    }

    // --- While Loop ---
    else if ((match = patterns.while.exec(line))) {
        const condition = match[1];
        const id = `while_${index}`;
        
        const parentId = getParentNodeId();
        const node: Node = { id, type: 'condition', data: { label: condition }, position: { x: 0, y: 0 } };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);

        if (lastNodeId) {
            edges.push(createEdge(lastNodeId, id, pendingEdgeLabel || undefined));
            pendingEdgeLabel = null;
        }
        
        stack.push({ type: 'while', entryNodeId: id });
        lastNodeId = id; 
    }
    else if (patterns.endWhile.test(line)) {
         if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'while') {
                stack.pop();
                if (lastNodeId) edges.push(createEdge(lastNodeId, (ctx as LoopContext).entryNodeId));
                lastNodeId = (ctx as LoopContext).entryNodeId;
            }
         }
    }

    // --- Sequence Diagram ---
    else if ((match = patterns.groupStart.exec(line))) {
        const type = match[1];
        const label = match[2];
        stack.push({ type: 'group', label: `${type} ${label}` });
    }
    else if ((match = patterns.groupElse.exec(line))) {
        const label = match[1];
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'group') {
                (ctx as SequenceGroupContext).label = `else ${label}`;
            }
        }
    }
    else if (patterns.groupEnd.test(line)) {
        if (stack.length > 0) {
            const ctx = stack[stack.length - 1];
            if (ctx.type === 'group') {
                stack.pop();
            }
        }
    }
    else if ((match = patterns.participant.exec(line))) {
        const label = match[2];
        const alias = match[3] || label.replace(/"/g, '').replace(/\s+/g, '_');
        aliasMap.set(alias, alias);
        if (!nodes.find(n => n.id === alias)) {
             nodes.push({ id: alias, type: 'activity', data: { label: label.replace(/"/g, '') }, position: { x: 0, y: 0 } });
        }
    }
    else if ((match = patterns.message.exec(line))) {
        let [_, source, arrow, target, label] = match;
        
        if (arrow.startsWith('<')) {
            [source, target] = [target, source];
        }
        
        source = resolveId(source);
        target = resolveId(target);

        [source, target].forEach(name => {
            if (!nodes.find(n => n.id === name)) {
                nodes.push({ id: name, type: 'activity', data: { label: name }, position: { x: 0, y: 0 } });
            }
        });
        
        const groupLabel = getGroupLabel();
        const finalLabel = groupLabel + label;
        
        const edge = createEdge(source, target, finalLabel);
        if (arrow.includes('--')) {
             edge.style = { ...edge.style, strokeDasharray: '5,5' };
        }
        edges.push(edge);
    }

    // --- State Diagram ---
    else if ((match = patterns.stateAlias.exec(line))) {
        const label = match[1];
        const alias = match[2];
        aliasMap.set(alias, alias); 
        
        const parentId = getParentNodeId();
        const node: Node = { id: alias, type: 'activity', data: { label }, position: { x: 0, y: 0 } };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);
    }
    else if ((match = patterns.stateSimple.exec(line))) {
        const name = match[1];
        if (!nodes.find(n => n.id === name)) {
            const parentId = getParentNodeId();
            const node: Node = { id: name, type: 'activity', data: { label: name }, position: { x: 0, y: 0 } };
            if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
            nodes.push(node);
        }
    }
    else if ((match = patterns.stateCompositeStart.exec(line))) {
        const name = match[1];
        const alias = match[2] || name;
        aliasMap.set(alias, alias);
        
        const parentId = getParentNodeId();
        const node: Node = { 
            id: alias, 
            type: 'group', 
            data: { label: name }, 
            position: { x: 0, y: 0 },
            style: { width: 200, height: 200, backgroundColor: 'rgba(240, 240, 240, 0.5)' }
        };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        nodes.push(node);
        
        stack.push({ type: 'composite', parentNodeId: alias });
    }
    else if (patterns.stateCompositeEnd.test(line)) {
        if (stack.length > 0) {
             const ctx = stack[stack.length - 1];
             if (ctx.type === 'composite') {
                 stack.pop();
             }
        }
    }
    else if ((match = patterns.startState.exec(line))) {
        const targetRaw = match[1];
        const target = resolveId(targetRaw);
        
        const id = `start_state_${index}`; // Use index to allow multiple start states (nested)
        const parentId = getParentNodeId();
        
        const node: Node = { id, type: 'start', data: { label: '[*]' }, position: { x: 0, y: 0 } };
        if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
        if (!nodes.find(n => n.id === id))
            nodes.push(node);
            
        if (!nodes.find(n => n.id === target)) {
             const targetNode: Node = { id: target, type: 'activity', data: { label: target }, position: { x: 0, y: 0 } };
             if (parentId) { targetNode.parentNode = parentId; targetNode.extent = 'parent'; }
             nodes.push(targetNode);
        }
        edges.push(createEdge(id, target));
    }
    else if ((match = patterns.transition.exec(line))) {
        const [_, sourceRaw, targetRaw, label] = match;
        const source = resolveId(sourceRaw);
        const parentId = getParentNodeId();
        
        if (targetRaw === '[*]') {
            const endId = `end_state_${index}`;
            const node: Node = { id: endId, type: 'stop', data: { label: 'End' }, position: { x: 0, y: 0 } };
            if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
            nodes.push(node);
            edges.push(createEdge(source, endId, label));
        } else {
            const target = resolveId(targetRaw);
            [source, target].forEach(name => {
                if (name !== '[*]' && !nodes.find(n => n.id === name)) {
                    const node: Node = { id: name, type: 'activity', data: { label: name }, position: { x: 0, y: 0 } };
                    if (parentId) { node.parentNode = parentId; node.extent = 'parent'; }
                    nodes.push(node);
                }
            });
            edges.push(createEdge(source, target, label));
        }
    }
  });

  return { nodes, edges };
}

function createEdge(source: string, target: string, label?: string): Edge {
    return {
        id: `e_${source}_${target}_${Math.random().toString(36).substr(2, 5)}`,
        source,
        target,
        label,
        markerEnd: { type: MarkerType.ArrowClosed },
        type: 'smoothstep',
        style: { stroke: '#333', strokeWidth: 2 }
    };
}
