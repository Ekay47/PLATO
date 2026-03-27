export type NodeType = 
  | 'start' 
  | 'stop' 
  | 'activity' 
  | 'condition' 
  | 'fork' 
  | 'join' 
  | 'note' 
  | 'partition';

export interface BaseNode {
  id: string;
  type: NodeType;
  label?: string;
  color?: string;
  stereotype?: string;
}

export interface ActivityNode extends BaseNode {
  type: 'activity';
}

export interface StartNode extends BaseNode {
  type: 'start';
}

export interface StopNode extends BaseNode {
  type: 'stop';
}

export interface ConditionNode extends BaseNode {
  type: 'condition';
  yesOut?: string; // ID of the next node for 'yes'
  noOut?: string;  // ID of the next node for 'no'
}

export interface ForkNode extends BaseNode {
  type: 'fork';
}

export interface JoinNode extends BaseNode {
  type: 'join';
}

export interface NoteNode extends BaseNode {
  type: 'note';
  position?: 'left' | 'right' | 'top' | 'bottom';
  targetId?: string; // The node this note is attached to
}

export interface PartitionNode extends BaseNode {
  type: 'partition';
  children: PlantUMLNode[];
}

export type PlantUMLNode = 
  | ActivityNode 
  | StartNode 
  | StopNode 
  | ConditionNode 
  | ForkNode 
  | JoinNode 
  | NoteNode 
  | PartitionNode;

export interface Edge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string; // 'yes', 'no', or custom
}

export interface PlantUMLDiagram {
  nodes: PlantUMLNode[];
  edges: Edge[];
}
